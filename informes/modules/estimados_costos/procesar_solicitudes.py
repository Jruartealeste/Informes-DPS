"""
Procesa las solicitudes de alta de Estimado de Costo que el equipo arma en
la app `ot/` (boton "Generar Estimado en Advertys" -> SolicitudAltaEstimado
PENDIENTE): las lista, y para las que Javier confirma, corre
`crear_estimado.crear_estimado(...)` contra Advertys real y resuelve la
solicitud en `ot/` con el numero devuelto. Mismo patron que
`modules.ordenes_trabajo.procesar_solicitudes`.

Escribe en Advertys (via crear_estimado.py) -- mismas salvaguardas que
`crear_estimado.py`: solo se procesan los ids pasados explicitamente con --ids,
que tienen que ser los que Javier confirmo en esa misma conversacion.

Idempotencia: apenas Advertys devuelve el numero, se anota en un log local
(JSONL) ANTES de llamar a `ot/`. Si el resolver falla (red, Vercel, Neon
dormido), la proxima corrida ve en el log que el Estimado ya existe y solo
reintenta el resolver -- nunca crea un segundo Estimado para el mismo pedido.

Uso (parado en informes/):
    python -m modules.estimados_costos.procesar_solicitudes listar --prod
    python -m modules.estimados_costos.procesar_solicitudes procesar --prod --ids 12,13
    # Estimado creado cuyo pedido ya no existe en ot/, despues de que Javier decidio que hacer:
    python -m modules.estimados_costos.procesar_solicitudes descartar --prod --ids 12
    # QA local (no toca Advertys, numero ficticio SIM-<id>; solo localhost):
    python -m modules.estimados_costos.procesar_solicitudes procesar --url http://localhost:8123 --ids 1 --simular
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

load_dotenv()

PROD_URL = "https://ot-sand-iota.vercel.app"
RUTA_API = "/api/sync/solicitudes-alta-estimado"
# Neon Free se suspende a los 5 min y el primer query tarda varios segundos;
# 60 s cubre ese arranque en frio de Vercel + Neon con margen.
TIMEOUT_HTTP = 60

DIR_LOG = Path(__file__).resolve().parents[2] / "salida"
# Un solo log para todo: cada evento lleva la URL de ot/, asi prod y QA local
# (unico lugar donde se permite --simular) nunca se mezclan.
LOG_PATH = DIR_LOG / "solicitudes_alta_estimado.jsonl"


class ProcesarError(RuntimeError):
    pass


# --- API de ot/ ---------------------------------------------------------------

def _token() -> str:
    token = os.environ.get("OT_SYNC_TOKEN")
    if not token:
        raise ProcesarError("Falta OT_SYNC_TOKEN en el .env de la raiz del repo (es el SYNC_TOKEN de ot/.env).")
    return token


def _api(metodo: str, url_base: str, ruta: str, **kwargs) -> httpx.Response:
    url = f"{url_base.rstrip('/')}{RUTA_API}{ruta}"
    try:
        return httpx.request(
            metodo, url, headers={"Authorization": f"Bearer {_token()}"}, timeout=TIMEOUT_HTTP, **kwargs
        )
    except httpx.HTTPError as e:
        raise ProcesarError(f"No se pudo conectar a {url}: {e}") from e


def listar_api(url_base: str, estado: str = "PENDIENTE") -> list[dict]:
    r = _api("GET", url_base, "", params={"estado": estado})
    if r.status_code != 200:
        raise ProcesarError(f"ot/ respondio {r.status_code} al listar solicitudes: {r.text[:300]}")
    return r.json()


def resolver_api(url_base: str, solicitud_id: int, numero: str) -> dict:
    """Devuelve {"ok": True, ...} o levanta ProcesarError con el motivo.
    404 = el pedido ya no existe (lo cancelaron); 409 = ya estaba resuelto
    con OTRO numero. Ambos dejan un Estimado en Advertys sin vincular."""
    r = _api("POST", url_base, f"/{solicitud_id}/resolver", json={"numero_estimado": numero})
    if r.status_code == 200:
        return r.json()
    raise ProcesarError(f"ot/ respondio {r.status_code} al resolver la solicitud {solicitud_id}: {r.text[:300]}")


# --- Log local ----------------------------------------------------------------

def _clave(url_base: str, solicitud_id: int) -> str:
    return f"{url_base.rstrip('/')}#{solicitud_id}"


def leer_log(path: Path) -> dict[str, dict]:
    """Ultimo evento por (url, id). Cada linea es un evento: "creada" o "resuelta"."""
    estado: dict[str, dict] = {}
    if not path.exists():
        return estado
    for linea in path.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            ev = json.loads(linea)
            estado[_clave(ev["url"], ev["id"])] = ev
    return estado


def anotar(path: Path, evento: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    evento = {**evento, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(evento, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def colgadas(log: dict[str, dict], url_base: str) -> dict[int, dict]:
    """Creados en Advertys pero sin resolver en ot/ (para esta URL)."""
    pref = url_base.rstrip("/") + "#"
    return {ev["id"]: ev for k, ev in log.items() if k.startswith(pref) and ev["evento"] == "creada"}


# --- Comandos -----------------------------------------------------------------

def _fmt_solicitud(s: dict) -> str:
    tareas = "; ".join(s["tareas"]) or "(sin tareas)"
    return "\n".join([
        f"Solicitud #{s['id']}  -  pedida por {s['creado_por'] or '?'} el {(s['creado_en'] or '')[:10]}",
        f"  OT de sistema:    {s['numero_ot_advertys']}",
        f"  Titulo:           {s['titulo']}",
        f"  Fecha solicitada: {s['fecha_solicitada'] or '(hoy, default de Advertys)'}",
        f"  Fecha analisis:   {s['fecha_analisis'] or '(default de Advertys)'}",
        f"  Tareas:           {tareas}",
    ])


def cmd_listar(url_base: str, log_path: Path) -> int:
    pendientes = listar_api(url_base)
    pend_colgadas = colgadas(leer_log(log_path), url_base)
    print(f"ot/: {url_base}")
    if not pendientes and not pend_colgadas:
        print("No hay solicitudes de alta de Estimado pendientes.")
        return 0
    print(f"{len(pendientes)} solicitud(es) PENDIENTE(s):\n")
    for s in pendientes:
        print(_fmt_solicitud(s))
        if s["id"] in pend_colgadas:
            print(
                f"  ** YA CREADO en Advertys como Estimado {pend_colgadas[s['id']]['numero']} (corrida anterior): "
                "falta solo vincularla. Procesarla NO crea otro Estimado."
            )
        print()
    ids_pendientes = {s["id"] for s in pendientes}
    huerfanas = {i: ev for i, ev in pend_colgadas.items() if i not in ids_pendientes}
    for i, ev in huerfanas.items():
        print(
            f"ATENCION: el Estimado {ev['numero']} se creo en Advertys para la solicitud #{i}, pero esa solicitud "
            "ya no esta pendiente en ot/ (cancelada o resuelta a mano). Revisar con Javier; "
            "`procesar --ids` con ese id intenta vincularla igual."
        )
    return 0


def cmd_descartar(url_base: str, ids: list[int], log_path: Path) -> int:
    """Deja de reportar un Estimado creado-sin-vincular (ej. el pedido se cancelo
    y Javier ya decidio que hacer con ese Estimado en Advertys). No toca nada remoto."""
    pend_colgadas = colgadas(leer_log(log_path), url_base)
    for sid in ids:
        if sid not in pend_colgadas:
            print(f"#{sid}: no figura como creado-sin-vincular en el log; nada que descartar.")
            continue
        anotar(log_path, {"evento": "descartada", "url": url_base.rstrip("/"), "id": sid,
                          "numero": pend_colgadas[sid]["numero"]})
        print(f"#{sid}: descartada (Estimado {pend_colgadas[sid]['numero']} queda como estaba en Advertys).")
    return 0


def _crear(s: dict, simular: bool) -> str:
    if simular:
        return f"SIM-{s['id']}"
    from modules.estimados_costos.crear_estimado import CrearEstimadoError, crear_estimado

    try:
        return crear_estimado(s["numero_ot_advertys"], s["titulo"], s["fecha_solicitada"], s["fecha_analisis"])
    except CrearEstimadoError as e:
        # No reintentar a ciegas: el alta pudo salir bien (ver workflows/crear_estimado.md).
        raise ProcesarError(f"crear_estimado fallo para la solicitud #{s['id']}: {e}") from e


def cmd_procesar(url_base: str, ids: list[int], simular: bool, log_path: Path) -> int:
    pendientes = {s["id"]: s for s in listar_api(url_base)}
    pend_colgadas = colgadas(leer_log(log_path), url_base)
    resultados: list[str] = []
    fallo = False

    for i, sid in enumerate(ids):
        try:
            if sid in pend_colgadas:
                numero = pend_colgadas[sid]["numero"]
                print(f"#{sid}: ya creado antes como Estimado {numero}; solo se vincula en ot/.")
            elif sid in pendientes:
                s = pendientes[sid]
                print(f"#{sid}: creando Estimado en Advertys (OT {s['numero_ot_advertys']} / {s['titulo']!r})...")
                numero = _crear(s, simular)
                anotar(log_path, {"evento": "creada", "url": url_base.rstrip("/"), "id": sid, "numero": numero,
                                  "simulado": simular,
                                  "datos": {k: s[k] for k in ("numero_ot_advertys", "titulo", "fecha_solicitada", "fecha_analisis")}})
                print(f"#{sid}: Estimado {numero} creado en Advertys.")
            else:
                resultados.append(f"#{sid}: SALTEADA - no esta pendiente en ot/ (ya resuelta, cancelada o id incorrecto).")
                continue

            r = resolver_api(url_base, sid, numero)
            anotar(log_path, {"evento": "resuelta", "url": url_base.rstrip("/"), "id": sid, "numero": numero})
            extra = " (ya estaba vinculado)" if r.get("ya_estaba_resuelta") else ""
            resultados.append(f"#{sid}: OK - Estimado {numero} creado en la OT {pendientes.get(sid, {}).get('numero_ot_advertys', '?')} y vinculado{extra}.")
        except ProcesarError as e:
            fallo = True
            resultados.append(f"#{sid}: ERROR - {e}")
            restantes = ids[i + 1:]
            if restantes:
                resultados.append(
                    f"Se frena la tanda: no se procesaron {', '.join(f'#{r}' for r in restantes)}."
                )
            break

    print("\nResumen:")
    for linea in resultados:
        print(f"  {linea}")
    return 1 if fallo else 0


def _es_local(url_base: str) -> bool:
    return (urlparse(url_base).hostname or "") in ("localhost", "127.0.0.1", "::1")


def main():
    # Los datos (Titulo) se confirman con Javier
    # leyendo esta salida: en la consola de Windows (cp1252) la ñ salía rota.
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Procesa solicitudes de alta de Estimado de la app ot/")
    sub = parser.add_subparsers(dest="comando", required=True)
    for nombre in ("listar", "procesar", "descartar"):
        p = sub.add_parser(nombre)
        destino = p.add_mutually_exclusive_group()
        destino.add_argument("--prod", action="store_true", help=f"Apunta a produccion ({PROD_URL})")
        destino.add_argument("--url", help="URL base de ot/ (default: OT_SYNC_URL del .env)")
        if nombre == "procesar":
            p.add_argument("--simular", action="store_true",
                           help="No toca Advertys: numero ficticio SIM-<id>. Solo contra localhost.")
        if nombre in ("procesar", "descartar"):
            p.add_argument("--ids", required=True,
                           help="Ids de solicitud confirmados por Javier, separados por coma (ej. 12,13)")
    args = parser.parse_args()

    url_base = PROD_URL if args.prod else (args.url or os.environ.get("OT_SYNC_URL"))
    if not url_base:
        print("ERROR: indicar --prod o --url (o OT_SYNC_URL en el .env de la raiz).")
        sys.exit(2)
    if getattr(args, "simular", False) and not _es_local(url_base):
        print("ERROR: --simular solo se permite contra localhost (cargaria numeros ficticios en datos reales).")
        sys.exit(2)
    log_path = LOG_PATH

    try:
        if args.comando == "listar":
            codigo = cmd_listar(url_base, log_path)
        else:
            try:
                ids = [int(x) for x in args.ids.split(",") if x.strip()]
            except ValueError:
                print(f"ERROR: --ids tiene que ser una lista de numeros separados por coma, no {args.ids!r}.")
                sys.exit(2)
            if not ids:
                print("ERROR: --ids vacio.")
                sys.exit(2)
            if args.comando == "procesar":
                codigo = cmd_procesar(url_base, ids, args.simular, log_path)
            else:
                codigo = cmd_descartar(url_base, ids, log_path)
    except ProcesarError as e:
        print(f"ERROR: {e}")
        codigo = 1
    sys.exit(codigo)


if __name__ == "__main__":
    main()
