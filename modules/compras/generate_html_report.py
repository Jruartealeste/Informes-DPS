"""
Genera el informe HTML autocontenido de Compras a partir de lo que haya en
la base local en este momento (mismo espiritu que generate_report.py, pero
como pagina web: se abre con doble click y se imprime/guarda en PDF desde
el navegador). Sobreescribe siempre el mismo archivo, no acumula versiones.

El tablero es dinamico: se embebe el dataset crudo + un spec declarativo, y
un motor JS compartido (html_report.DASHBOARD_JS) recalcula stat tiles,
graficos y tablas segun el rango de periodo que elija el usuario.

Uso:
    python -m modules.compras.generate_html_report
"""
import pandas as pd

import db
import html_report as hr
from . import config

ESTADO_COLOR = {
    "Contabilizado": hr.STATUS["good"],
    "Borrador": hr.STATUS["warning"],
    "Rechazado": hr.STATUS["serious"],
    "Anulado": hr.STATUS["critical"],
}
ESTADO_ORDEN = ["Contabilizado", "Borrador", "Rechazado", "Anulado"]


def cargar_datos() -> pd.DataFrame:
    with db.get_connection() as conn:
        df = pd.read_sql_query(f"SELECT * FROM {config.DB_TABLE}", conn)
    if not df.empty:
        df["fecha_factura"] = pd.to_datetime(df["fecha_factura"], errors="coerce")
        df["_periodo"] = df["fecha_factura"].dt.strftime("%Y-%m")
    return df


def main():
    df = cargar_datos()
    if df.empty:
        print("No hay datos cargados todavia. Corre 'python -m modules.compras.ingest' primero.")
        return

    records = hr.records_from_df(df, [
        "proveedor", "tipo_compra", "tipo_proveedor", "numero_referencia", "fecha_factura",
        "moneda", "importe_sin_iva_signado", "total_impositivo", "estado", "_periodo",
    ])

    spec = {
        "dateField": "_periodo",
        "statTiles": [
            {"label": "Compras (todos los estados)", "kind": "count", "fmt": "int"},
            {"label": "Compras contabilizadas", "kind": "count", "fmt": "int", "filter": {"field": "estado", "equals": "Contabilizado"}},
            {"label": "Total impositivo (contabilizadas)", "kind": "sum", "field": "total_impositivo", "fmt": "money", "filter": {"field": "estado", "equals": "Contabilizado"}},
            {"label": "Proveedores distintos", "kind": "nunique", "field": "proveedor", "fmt": "int"},
        ],
        "charts": [
            {"mount": "chart-mes", "type": "bar", "groupBy": "_periodo", "agg": "sum", "field": "total_impositivo", "fmt": "money"},
            {"mount": "chart-comparacion", "type": "period_compare", "field": "total_impositivo", "fmt": "money", "granularity": "month"},
            {"mount": "chart-estado", "type": "bar", "groupBy": "estado", "agg": "count", "fmt": "int", "colors": ESTADO_COLOR, "order": ESTADO_ORDEN},
            {"mount": "chart-tipo", "type": "bar", "groupBy": "tipo_compra", "agg": "sum", "field": "total_impositivo", "fmt": "money"},
            {"mount": "chart-proveedores", "type": "hbar", "groupBy": "proveedor", "agg": "sum", "field": "total_impositivo", "fmt": "money", "topN": 10},
        ],
        "tables": [
            {
                "mount": "tabla-proveedores", "groupBy": "proveedor",
                "aggs": [
                    {"key": "compras", "op": "count"},
                    {"key": "importe_sin_iva", "op": "sum", "field": "importe_sin_iva_signado"},
                    {"key": "total_impositivo", "op": "sum", "field": "total_impositivo"},
                ],
                "columns": [["proveedor", "Proveedor"], ["compras", "Compras"], ["importe_sin_iva", "Importe s/IVA"], ["total_impositivo", "Total impositivo"]],
                "numericCols": ["importe_sin_iva", "total_impositivo"],
                "sort": {"key": "total_impositivo", "dir": "desc"},
            },
        ],
    }

    secciones = "".join([
        hr.filter_bar_html(),
        hr.stat_tiles_mount(),
        hr.section("Total impositivo por mes", hr.mount("chart-mes")),
        hr.section("Comparación mes a mes / trimestre a trimestre", hr.period_compare_mount("chart-comparacion")),
        hr.section("Compras por estado", hr.mount("chart-estado")),
        hr.section("Compras por tipo (Gastos / Medios / Produccion)", hr.mount("chart-tipo")),
        hr.section("Top 10 proveedores por total impositivo", hr.mount("chart-proveedores")),
        hr.section("Compras por proveedor (todos)", hr.mount("tabla-proveedores")),
        hr.dashboard_bundle(records, spec),
    ])

    html = hr.page_shell("Informe de Compras", "ALESTE ADS S.A. - Advertys", secciones)

    with open(config.REPORT_HTML_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK: informe generado en {config.REPORT_HTML_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
