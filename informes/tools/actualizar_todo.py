"""
Refresh completo y automatico del dashboard: para cada modulo de esta
lista hace login a Advertys, exporta el ultimo listado, lo carga en
advertys.db, y al final regenera todos los informes y el dashboard.
Reemplaza el paso manual de "bajar el Excel a mano" del skill
refresh-dashboard.

Un fallo en un modulo puntual (ej. Advertys renombro una columna) no
aborta el resto: se loggea y se sigue con los demas. Los informes se
regeneran siempre al final, incluso si algun modulo fallo, porque leen
lo que ya este en advertys.db (dato no tan fresco para ese modulo, pero
valido).

IIBB (que tiene su propio refresh completo en tools/actualizar_iibb.py
desde 2026-08-18, pero se dispara aparte a demanda -- ver
workflows/actualizar_informe.md), y el crawl opcional de items_pendientes_oc
(modules/ordenes_trabajo/crawl_items_pendientes.py), quedan fuera de
este script a proposito -- su export es mucho mas pesado (~22.700 filas
vs. cientos en el resto) y no hace falta refrescarlo con la misma
frecuencia que el resto.

Cobranza x Proveedores (agregado 2026-09-30): "recibos" esta en MODULOS y
CRAWLS_COBRANZA corre los 3 crawls de la cadena (referencias canceladas ->
OC/OP por factura -> facturas de compra por OC/OP) antes de regenerar el
informe. Suma bastante al tiempo total (ver docstring de
modules/cobranza_proveedores/generate_html_report.py).

Notas de Credito de Ventas (Produccion/Medios/Representante, agregado
2026-09-21): NO son un modulo mas de la lista MODULOS -- son 3 vistas
aparte que se fusionan en la tabla "facturas" ya cargada por el modulo
"facturas" de arriba (ver modules/facturas/export_nc.py e ingest_nc.py, y
la nota "Notas de Credito de Ventas" en README.md). Compras no necesita
este paso: sus notas de credito ya vienen en el mismo export de Compras,
como filas con importe negativo.

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
    "recibos",
]

CRAWLS_COBRANZA = [
    ("modules.recibos.crawl_referencias_canceladas", "facturas que cancela cada recibo"),
    ("modules.cobranza_proveedores.crawl_oc_por_factura", "OC/OP de cada factura cobrada"),
    ("modules.cobranza_proveedores.crawl_facturas_compra_por_oc", "facturas de compra de cada OC/OP"),
]

NC_VENTAS_SEGMENTOS = ["produccion", "medios", "representante"]

REPORTES = ["ordenes_trabajo", "compras", "facturas", "pendientes", "cobranza_proveedores"]


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


def exportar_e_ingerir_nc_ventas(segmento: str) -> tuple[bool, str]:
    print(f"--- facturas (NC {segmento}): exportando desde Advertys...")
    try:
        export_mod = import_module("modules.facturas.export_nc")
        xlsx_path = export_mod.exportar(segmento)
    except Exception as e:
        return False, f"export fallido: {e}"

    print(f"--- facturas (NC {segmento}): cargando {xlsx_path} en advertys.db...")
    resultado = _correr(["modules.facturas.ingest_nc", str(xlsx_path), "--segmento", segmento])
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

    for segmento in NC_VENTAS_SEGMENTOS:
        clave = f"facturas (NC {segmento})"
        exito, detalle = exportar_e_ingerir_nc_ventas(segmento)
        if exito:
            ok[clave] = detalle
        else:
            errores[clave] = detalle

    # Cadena de Cobranza x Proveedores (crawls de solo lectura, en este
    # orden: cada uno lee lo que dejo el anterior). El crawl de referencias
    # canceladas es el mas pesado (un recibo a la vez). Si un paso falla se
    # saltean los siguientes -- dependen de su salida -- pero el resto del
    # refresh sigue.
    for modulo, descripcion in CRAWLS_COBRANZA:
        print(f"--- cobranza_proveedores: {descripcion} (Playwright, tarda varios minutos)...")
        resultado = _correr([modulo])
        clave = f"cobranza ({modulo.rsplit('.', 1)[-1]})"
        if resultado.returncode != 0:
            detalle = (resultado.stderr or resultado.stdout).strip().splitlines()
            errores[clave] = detalle[-1] if detalle else "sin detalle"
            break
        ok[clave] = resultado.stdout.strip().splitlines()[-1]

    regenerar_reportes()

    print("\n=== Resumen ===")
    for modulo, detalle in ok.items():
        print(f"OK  {modulo}: {detalle}")
    for modulo, detalle in errores.items():
        print(f"ERROR {modulo}: {detalle}")
    print("IIBB no fue tocado por este script -- correr 'python -m tools.actualizar_iibb' aparte.")

    sys.exit(1 if errores else 0)


if __name__ == "__main__":
    main()
