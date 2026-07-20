"""
Genera el informe HTML autocontenido de Facturas a partir de lo que haya en
la base local en este momento (mismo espiritu que generate_report.py, pero
como pagina web: se abre con doble click y se imprime/guarda en PDF desde
el navegador). Sobreescribe siempre el mismo archivo, no acumula versiones.

El tablero es dinamico: se embebe el dataset crudo + un spec declarativo, y
un motor JS compartido (html_report.DASHBOARD_JS) recalcula stat tiles,
graficos y tablas segun el rango de periodo que elija el usuario.

Uso:
    python -m modules.facturas.generate_html_report
"""
import pandas as pd

import db
import html_report as hr
from . import config


def cargar_datos() -> pd.DataFrame:
    with db.get_connection() as conn:
        df = pd.read_sql_query(f"SELECT * FROM {config.DB_TABLE}", conn)
    if not df.empty:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        df["_periodo"] = df["fecha"].dt.strftime("%Y-%m")
    return df


def main():
    df = cargar_datos()
    if df.empty:
        print("No hay datos cargados todavia. Corre 'python -m modules.facturas.ingest' primero.")
        return

    records = hr.records_from_df(df, [
        "fecha", "numero_referencia", "anunciante", "cliente", "cuit", "producto", "moneda",
        "subtotal_ml", "impuestos_ml", "total_ml", "estado", "_periodo",
    ])

    spec = {
        "dateField": "_periodo",
        "statTiles": [
            {"label": "Facturas", "kind": "count", "fmt": "int"},
            {"label": "Total ML facturado", "kind": "sum", "field": "total_ml", "fmt": "money"},
            {"label": "Clientes distintos", "kind": "nunique", "field": "cliente", "fmt": "int"},
            {"label": "Anunciantes distintos", "kind": "nunique", "field": "anunciante", "fmt": "int"},
        ],
        "charts": [
            {"mount": "chart-mes", "type": "bar", "groupBy": "_periodo", "agg": "sum", "field": "total_ml", "fmt": "money"},
            {"mount": "chart-comparacion", "type": "period_compare", "field": "total_ml", "fmt": "money", "granularity": "month"},
            {"mount": "chart-clientes", "type": "hbar", "groupBy": "cliente", "agg": "sum", "field": "total_ml", "fmt": "money", "topN": 10},
            {"mount": "chart-anunciantes", "type": "hbar", "groupBy": "anunciante", "agg": "sum", "field": "total_ml", "fmt": "money", "topN": 10},
        ],
        "tables": [
            {
                "mount": "tabla-clientes", "groupBy": "cliente",
                "aggs": [
                    {"key": "facturas", "op": "count"},
                    {"key": "subtotal_ml", "op": "sum", "field": "subtotal_ml"},
                    {"key": "total_ml", "op": "sum", "field": "total_ml"},
                ],
                "columns": [["cliente", "Cliente"], ["facturas", "Facturas"], ["subtotal_ml", "Subtotal ML"], ["total_ml", "Total ML"]],
                "numericCols": ["subtotal_ml", "total_ml"],
                "sort": {"key": "total_ml", "dir": "desc"},
            },
        ],
    }

    secciones = "".join([
        hr.filter_bar_html(),
        hr.stat_tiles_mount(),
        hr.section("Total ML facturado por mes", hr.mount("chart-mes")),
        hr.section("Comparación mes a mes / trimestre a trimestre", hr.period_compare_mount("chart-comparacion")),
        hr.section("Top 10 clientes por total ML", hr.mount("chart-clientes")),
        hr.section("Top 10 anunciantes por total ML", hr.mount("chart-anunciantes")),
        hr.section("Facturacion por cliente (todos)", hr.mount("tabla-clientes")),
        hr.dashboard_bundle(records, spec),
    ])

    html = hr.page_shell("Informe de Facturas", "ALESTE ADS S.A. - Advertys", secciones)

    with open(config.REPORT_HTML_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK: informe generado en {config.REPORT_HTML_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
