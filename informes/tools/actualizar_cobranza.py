"""
Refresh de la cadena de Cobranza x Proveedores, aparte de
tools/actualizar_todo.py porque la corrida vieja tardaba ~70 min (verificado
2026-09-30, 23 recibos / 59 facturas / 118 ordenes): cada crawl borraba su
tabla y visitaba todo de a uno.

Desde 2026-10-13 los 3 crawls son INCREMENTALES por default (tools/
crawl_comun.py: cache + regla de cierre de mes, solo visitan lo nuevo o
cambiado). Modos, que se propagan a los 3 crawls:
    (sin flags)    incremental
    --completo     ignora la cache y revisita todo (con upsert)
    --legacy       la corrida vieja tal cual (borra y recrawlea todo, de a uno)
    --workers N    N navegadores en paralelo (default 1)

Pasos, en orden (cada uno lee lo que dejo el anterior):
    0. facturas, ordenes_compra, ordenes_publicidad (export + ingest) --
       desde 2026-10-27 siempre (pedido de Javier: todo refresh baja los
       exports frescos que necesita). `--sin-previos` lo saltea, solo si
       se acaban de bajar en la misma sesion (ej. recien corrio
       tools/actualizar_iibb o tools/actualizar_todo).
    1. recibos             (export + ingest)
    2. referencias canceladas de cada recibo de la ventana
    3. OC/OP de cada factura cobrada
    4. facturas de compra de cada OC/OP
    5. regenera el informe de Cobranza x Proveedores y el dashboard

Si un paso falla se saltean los siguientes (dependen de su salida) pero el
informe se regenera igual con lo que haya en advertys.db.

Uso (desde informes/):
    python -m tools.actualizar_cobranza [--sin-previos] [--completo|--legacy] [--workers N]
"""
import subprocess
import sys
import time

from tools import crawl_comun as cc
from tools.actualizar_todo import _correr, exportar_e_ingerir

MODULOS_PREVIOS = ["facturas", "ordenes_compra", "ordenes_publicidad"]

CRAWLS = [
    ("modules.recibos.crawl_referencias_canceladas", "facturas que cancela cada recibo"),
    ("modules.cobranza_proveedores.crawl_oc_por_factura", "OC/OP de cada factura cobrada"),
    ("modules.cobranza_proveedores.crawl_facturas_compra_por_oc", "facturas de compra de cada OC/OP"),
]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sin_previos = "--sin-previos" in argv
    if sin_previos:
        argv.remove("--sin-previos")
    args = cc.parsear_args("Refresh de Cobranza x Proveedores.", argv)
    flags = (["--completo"] if args.completo else []) + (["--legacy"] if args.legacy else []) + ["--workers", str(args.workers)]
    modo = "legacy" if args.legacy else ("completo" if args.completo else "incremental")
    print(f"Modo: {modo}, workers: {args.workers}", flush=True)
    t_inicio = time.time()
    tiempos = {}
    ok, errores = {}, {}

    if not sin_previos:
        for modulo in MODULOS_PREVIOS:
            t = time.time()
            exito, detalle = exportar_e_ingerir(modulo)
            tiempos[modulo] = time.time() - t
            (ok if exito else errores)[modulo] = detalle

    t = time.time()
    exito, detalle = exportar_e_ingerir("recibos")
    tiempos["recibos"] = time.time() - t
    (ok if exito else errores)["recibos"] = detalle

    if exito:
        for modulo, descripcion in CRAWLS:
            print(f"--- {descripcion} (Playwright, tarda varios minutos)...", flush=True)
            t = time.time()
            resultado = _correr([modulo, *flags])
            clave = modulo.rsplit(".", 1)[-1]
            tiempos[clave] = time.time() - t
            if resultado.returncode != 0:
                detalle = (resultado.stderr or resultado.stdout).strip().splitlines()
                errores[clave] = detalle[-1] if detalle else "sin detalle"
                break
            ok[clave] = resultado.stdout.strip().splitlines()[-1]

    print("--- regenerando informe de cobranza_proveedores...", flush=True)
    resultado = _correr(["modules.cobranza_proveedores.generate_html_report"])
    if resultado.returncode != 0:
        print(f"AVISO: fallo la regeneracion: {(resultado.stderr or resultado.stdout).strip()}")
    resultado = subprocess.run([sys.executable, "generate_dashboard.py"], capture_output=True, text=True)
    if resultado.returncode != 0:
        print(f"AVISO: fallo la regeneracion del dashboard: {(resultado.stderr or resultado.stdout).strip()}")

    print("\n=== Resumen ===")
    for k, v in ok.items():
        print(f"OK  {k}: {v}")
    for k, v in errores.items():
        print(f"ERROR {k}: {v}")
    print("Tiempos: " + ", ".join(f"{k} {v:.0f}s" for k, v in tiempos.items()) + f" | total {time.time() - t_inicio:.0f}s ({modo})")
    sys.exit(1 if errores else 0)


if __name__ == "__main__":
    main()
