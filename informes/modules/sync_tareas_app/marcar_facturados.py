"""
Pasa a FACTURADO, en la app `ot/`, las tareas cuyo Estimado ya se facturo de
verdad en Advertys.

No escribe en Advertys (solo lee `estimados_costos` de advertys.db, ya
ingestada) y habla con `ot/` igual que push.py (OT_SYNC_URL / OT_SYNC_TOKEN).

Criterio de "facturado de verdad" (por Estimado, columna `estado` del export
+ `total_facturado`):
  - estado "Facturado total" o "Facturado manual"      -> FACTURADO
  - estado "Finalizado" con total_facturado > 0         -> FACTURADO
    (en Advertys un Estimado solo se finaliza facturado y con O.C. cruzadas)
  - cualquier otro (Provisorio, Autorizado AFacturar, Ok cliente, Anulado...)
    -> NO se toca.
Se muestra la relacion total_facturado/neto solo como dato; no decide porque
el neto incluye conceptos que no se facturan (ratio tipico ~0.9).

Antes correr el ingest de estimados_costos (refresh) para que advertys.db
este al dia; el script imprime la fecha de la ultima ingesta.

Uso (parado en informes/):
    python -m modules.sync_tareas_app.marcar_facturados            # solo muestra
    python -m modules.sync_tareas_app.marcar_facturados --aplicar  # marca en ot/
"""
import argparse
import os
import sys

import httpx
from dotenv import load_dotenv

import db

load_dotenv()

OT_SYNC_URL = os.environ.get("OT_SYNC_URL")
OT_SYNC_TOKEN = os.environ.get("OT_SYNC_TOKEN")

ESTADOS_FACTURADO = {"Facturado total", "Facturado manual"}


def _headers() -> dict:
    return {"Authorization": f"Bearer {OT_SYNC_TOKEN}"}


def _es_facturado(estado: str | None, total_facturado: float | None) -> bool:
    if estado in ESTADOS_FACTURADO:
        return True
    return estado == "Finalizado" and (total_facturado or 0) > 0


def _linea(c: dict, a) -> str:
    ratio = f"{a['total_facturado'] / a['neto']:.0%}" if a["neto"] else "-"
    return (
        f"  Est {c['numero_estimado']:>5} (OT {c['numero_ot_advertys']}) [{a['estado']}] "
        f"facturado/neto={ratio} - {len(c['tareas_pendientes'])} tarea(s) - {c['titulo'][:50]}"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true", help="marcar de verdad en ot/ (default: solo mostrar)")
    args = ap.parse_args()

    if not OT_SYNC_URL or not OT_SYNC_TOKEN:
        sys.exit("ERROR: completa OT_SYNC_URL y OT_SYNC_TOKEN en el .env de la raiz del repo.")
    base = OT_SYNC_URL.rstrip("/")

    resp = httpx.get(f"{base}/api/sync/estimados-a-facturar", headers=_headers(), timeout=30)
    resp.raise_for_status()
    candidatos = resp.json()

    with db.get_connection() as conn:
        ultima = conn.execute("SELECT MAX(fecha_ingesta) FROM estimados_costos").fetchone()[0]
        adv = {
            str(r["numero_estimado"]): r
            for r in conn.execute("SELECT numero_estimado, estado, neto, total_facturado FROM estimados_costos")
        }
    print(f"estimados_costos de advertys.db ingestado el: {ultima}")
    print(f"Estimados de la app con tareas sin facturar: {len(candidatos)}\n")

    a_marcar, sin_cambio, no_en_adv = [], [], []
    for c in candidatos:
        a = adv.get(str(c["numero_estimado"]))
        if a is None:
            no_en_adv.append(c)
        elif _es_facturado(a["estado"], a["total_facturado"]):
            a_marcar.append((c, a))
        else:
            sin_cambio.append((c, a))

    n_tareas = sum(len(c["tareas_pendientes"]) for c, _ in a_marcar)
    print(f"== A MARCAR FACTURADO ({len(a_marcar)} estimados, {n_tareas} tareas) ==")
    for c, a in a_marcar:
        print(_linea(c, a))
    print(f"\n== TODAVIA NO FACTURADOS en Advertys ({len(sin_cambio)}) ==")
    for c, a in sin_cambio:
        print(_linea(c, a))
    if no_en_adv:
        print(f"\n== NO ESTAN en advertys.db ({len(no_en_adv)}) - ingesta desactualizada? ==")
        for c in no_en_adv:
            print(f"  Est {c['numero_estimado']} - {c['titulo'][:60]}")

    if not args.aplicar:
        print("\nDry-run: no se cambio nada. Correr con --aplicar para marcar.")
        return
    if not a_marcar:
        print("\nNada para marcar.")
        return
    r = httpx.post(
        f"{base}/api/sync/estimados-facturados",
        json={"numeros_estimado": [str(c["numero_estimado"]) for c, _ in a_marcar]},
        headers=_headers(),
        timeout=60,
    )
    r.raise_for_status()
    print(f"\nOK: {r.json()}")


if __name__ == "__main__":
    main()
