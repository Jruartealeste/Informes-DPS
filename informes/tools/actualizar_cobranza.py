"""
Refresh de la cadena de Cobranza x Proveedores, aparte de
tools/actualizar_todo.py porque tarda ~70 min (verificado 2026-09-30, 23
recibos / 59 facturas / 118 ordenes): el crawl de referencias canceladas
visita un recibo a la vez y el de facturas de compra una orden a la vez.

Pasos, en orden (cada uno lee lo que dejo el anterior):
    1. recibos             (export + ingest)
    2. referencias canceladas de cada recibo de la ventana
    3. OC/OP de cada factura cobrada
    4. facturas de compra de cada OC/OP
    5. regenera el informe de Cobranza x Proveedores y el dashboard

Requiere facturas, ordenes_compra y ordenes_publicidad al dia: correr
antes `python -m tools.actualizar_todo` si hace falta.

Si un paso falla se saltean los siguientes (dependen de su salida) pero el
informe se regenera igual con lo que haya en advertys.db.

Uso (desde informes/):
    python -m tools.actualizar_cobranza
"""
import subprocess
import sys

from tools.actualizar_todo import _correr, exportar_e_ingerir

CRAWLS = [
    ("modules.recibos.crawl_referencias_canceladas", "facturas que cancela cada recibo"),
    ("modules.cobranza_proveedores.crawl_oc_por_factura", "OC/OP de cada factura cobrada"),
    ("modules.cobranza_proveedores.crawl_facturas_compra_por_oc", "facturas de compra de cada OC/OP"),
]


def main():
    ok, errores = {}, {}

    exito, detalle = exportar_e_ingerir("recibos")
    (ok if exito else errores)["recibos"] = detalle

    if exito:
        for modulo, descripcion in CRAWLS:
            print(f"--- {descripcion} (Playwright, tarda varios minutos)...", flush=True)
            resultado = _correr([modulo])
            clave = modulo.rsplit(".", 1)[-1]
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
    sys.exit(1 if errores else 0)


if __name__ == "__main__":
    main()
