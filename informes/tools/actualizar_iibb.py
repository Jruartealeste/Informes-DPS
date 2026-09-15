"""
Refresh completo de IIBB: encadena TODO lo que necesita
modules/iibb/generate_html_report.py para no dejar nada pendiente -- ver
la lista de prerequisitos en el docstring de ese archivo.

`tools/actualizar_todo.py` deja a IIBB afuera a proposito (export mas
pesado, se actualiza con menos frecuencia -- ver su docstring), pero hasta
2026-08-18 el "Caso especial IIBB" de workflows/actualizar_informe.md solo
corria el export+ingest de Imputaciones (paso 4 de abajo): facturas,
ordenes_compra y ordenes_publicidad (pasos 1-3) y el crawl de
items_factura_oc (paso 5) quedaban tal como estuvieran en advertys.db, a
veces con semanas de atraso. Una factura podia tener el monto deducible al
dia (paso 4 solo) pero el informe la mostraba sin el detalle desplegable
de OC/OP porque el paso 5 no se habia vuelto a correr -- sin ningun aviso
(caso real detectado por Javier: factura 000500000556, 2026-08-18). Este
script corre los 5 pasos siempre, en el orden que importa (facturas e
imputaciones tienen que estar frescas ANTES de crawlear, porque
`facturas_a_revisar()` en crawl_oc_por_factura.py cruza ambas tablas), y
al final chequea que no haya quedado ninguna factura con deducible sin su
detalle de OC/OP.

Pasos:
    1. facturas            (modules/facturas)
    2. ordenes_compra      (modules/ordenes_compra)      -- resuelve Proveedor/Monto OC (Produccion)
    3. ordenes_publicidad  (modules/ordenes_publicidad)   -- resuelve Proveedor/Monto OP (Medios)
    4. iibb                (modules/iibb -- export propio + ingest)
    5. items_factura_oc    (modules/iibb/crawl_oc_por_factura.py -- con
       reintento automatico de facturas que fallen por error transitorio)

Uso (desde la raiz del proyecto, con -m para que 'modules'/'tools' sean
importables):
    python -m tools.actualizar_iibb
"""
import subprocess
import sys

import db
from tools.actualizar_todo import exportar_e_ingerir

MODULOS_PREVIOS = ["facturas", "ordenes_compra", "ordenes_publicidad"]


def _correr(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", *args], capture_output=True, text=True)


def _facturas_sin_detalle_oc() -> list[str]:
    """De las facturas que modules/iibb/crawl_oc_por_factura.facturas_a_revisar()
    considera en alcance (mismo filtro de cuenta que usa ese script -- ver
    su docstring), las que despues del crawl siguen sin ninguna fila en
    items_factura_oc. Si esto devuelve algo, el refresh no esta completo:
    o el crawl no pudo con esa factura (ver aviso de "siguen_fallando" en
    su output) o la factura referencia una OC/OP que no aparece en
    ordenes_compra/ordenes_publicidad."""
    from modules.iibb.crawl_oc_por_factura import facturas_a_revisar
    en_alcance = set(facturas_a_revisar())
    with db.get_connection() as conn:
        cubiertas = {r[0] for r in conn.execute("SELECT DISTINCT numero_referencia FROM items_factura_oc")}
    return sorted(en_alcance - cubiertas)


def main():
    ok = {}
    errores = {}

    for modulo in MODULOS_PREVIOS:
        exito, detalle = exportar_e_ingerir(modulo)
        (ok if exito else errores)[modulo] = detalle

    exito, detalle = exportar_e_ingerir("iibb")
    (ok if exito else errores)["iibb"] = detalle

    print("--- iibb: crawleando N° de OC/OP por factura (Playwright, tarda varios minutos)...")
    resultado = _correr(["modules.iibb.crawl_oc_por_factura"])
    print(resultado.stdout)
    if resultado.returncode != 0:
        detalle = (resultado.stderr or resultado.stdout).strip().splitlines()
        errores["crawl_oc_por_factura"] = detalle[-1] if detalle else "sin detalle"

    print("--- regenerando informe de iibb...")
    resultado = _correr(["modules.iibb.generate_html_report"])
    print(resultado.stdout)
    if resultado.returncode != 0:
        errores["generate_html_report"] = (resultado.stderr or resultado.stdout).strip()

    pendientes = _facturas_sin_detalle_oc()

    print("\n=== Resumen ===")
    for modulo, detalle in ok.items():
        print(f"OK  {modulo}: {detalle}")
    for modulo, detalle in errores.items():
        print(f"ERROR {modulo}: {detalle}")
    if pendientes:
        print(
            f"AVISO: {len(pendientes)} factura(s) con deducible siguen SIN detalle de OC/OP "
            f"tras el refresh completo (revisar a mano -- puede ser que esa OC/OP no exista "
            f"todavia en ordenes_compra/ordenes_publicidad): {', '.join(pendientes)}"
        )
    else:
        print("OK: ninguna factura con deducible quedo pendiente de detalle de OC/OP.")

    sys.exit(1 if (errores or pendientes) else 0)


if __name__ == "__main__":
    main()
