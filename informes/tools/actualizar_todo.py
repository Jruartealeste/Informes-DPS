"""
Refresh completo y automatico del dashboard: para cada modulo con
export.py (todos salvo IIBB, que queda deliberadamente afuera por ser
mucho mas pesado -- ver README) hace login a Advertys, exporta el ultimo
listado, lo carga en advertys.db, y al final regenera todos los informes
y el dashboard. Reemplaza el paso manual de "bajar el Excel a mano" del
skill refresh-dashboard.

Un fallo en un modulo puntual (ej. Advertys renombro una columna) no
aborta el resto: se loggea y se sigue con los demas. Los informes se
regeneran siempre al final, incluso si algun modulo fallo, porque leen
lo que ya este en advertys.db (dato no tan fresco para ese modulo, pero
valido).

IIBB, y el crawl opcional de items_pendientes_oc
(modules/ordenes_trabajo/crawl_items_pendientes.py), quedan fuera de
este script a proposito -- se siguen actualizando aparte.

Uso (desde la raiz del proyecto, con -m para que 'modules' sea importable):
    python -m tools.actualizar_todo
"""
import subprocess
import sys
from importlib import import_module

MODULOS = [
    "compras",
    "facturas",
    "estimados_costos",
    "ordenes_compra",
    "ordenes_publicidad",
    "oc_pendientes_generar",
    "estimados_pendientes_facturar",
    "ordenes_trabajo",
]

REPORTES = ["ordenes_trabajo", "compras", "facturas", "pendientes"]


def _correr(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", *args],
        capture_output=True,
        text=True,
    )


def exportar_e_ingerir(modulo: str) -> tuple[bool, str]:
    print(f"--- {modulo}: exportando desde Advertys...")
    try:
        export_mod = import_module(f"modules.{modulo}.export")
        xlsx_path = export_mod.exportar()
    except Exception as e:
        return False, f"export fallido: {e}"

    print(f"--- {modulo}: cargando {xlsx_path} en advertys.db...")
    resultado = _correr(["modules." + modulo + ".ingest", str(xlsx_path)])
    if resultado.returncode != 0:
        detalle = (resultado.stderr or resultado.stdout).strip().splitlines()
        return False, f"ingest fallido: {detalle[-1] if detalle else 'sin detalle'}"

    ultima_linea = resultado.stdout.strip().splitlines()
    return True, ultima_linea[-1] if ultima_linea else "OK"


def regenerar_reportes() -> None:
    for modulo in REPORTES:
        print(f"--- regenerando informe de {modulo}...")
        resultado = _correr([f"modules.{modulo}.generate_html_report"])
        if resultado.returncode != 0:
            print(f"AVISO: fallo la regeneracion de {modulo}: {(resultado.stderr or resultado.stdout).strip()}")

    print("--- regenerando dashboard...")
    resultado = subprocess.run([sys.executable, "generate_dashboard.py"], capture_output=True, text=True)
    if resultado.returncode != 0:
        print(f"AVISO: fallo la regeneracion del dashboard: {(resultado.stderr or resultado.stdout).strip()}")


def main():
    ok = {}
    errores = {}

    for modulo in MODULOS:
        exito, detalle = exportar_e_ingerir(modulo)
        if exito:
            ok[modulo] = detalle
        else:
            errores[modulo] = detalle

    regenerar_reportes()

    print("\n=== Resumen ===")
    for modulo, detalle in ok.items():
        print(f"OK  {modulo}: {detalle}")
    for modulo, detalle in errores.items():
        print(f"ERROR {modulo}: {detalle}")
    print("IIBB no fue tocado por este script (queda manual).")

    sys.exit(1 if errores else 0)


if __name__ == "__main__":
    main()
