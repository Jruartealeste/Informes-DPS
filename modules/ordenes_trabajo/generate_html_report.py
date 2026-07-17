"""
Genera el informe HTML autocontenido de Ordenes de Trabajo a partir de lo
que haya en la base local en este momento (mismo espiritu que
generate_report.py, pero como pagina web: se abre con doble click y se
imprime/guarda en PDF desde el navegador). Sobreescribe siempre el mismo
archivo, no acumula versiones.

El tablero es dinamico: se embebe el dataset crudo + un spec declarativo, y
un motor JS compartido (html_report.DASHBOARD_JS) recalcula stat tiles,
graficos y tablas segun el rango de periodo que elija el usuario.

Uso:
    python -m modules.ordenes_trabajo.generate_html_report
"""
import pandas as pd

import db
import html_report as hr
from . import config

ESTADO_COLOR = {
    "Abierta": hr.STATUS["warning"],
    "Cerrada": hr.STATUS["good"],
    "Anulada": hr.STATUS["critical"],
}
ESTADO_ORDEN = ["Abierta", "Cerrada", "Anulada"]


def cargar_datos() -> pd.DataFrame:
    with db.get_connection() as conn:
        df = pd.read_sql_query(f"SELECT * FROM {config.DB_TABLE}", conn)
    if not df.empty:
        df["fecha_abierta"] = pd.to_datetime(df["fecha_abierta"], errors="coerce")
        df["fecha_cerrada"] = pd.to_datetime(df["fecha_cerrada"], errors="coerce")
        df["_periodo"] = df["fecha_abierta"].dt.strftime("%Y-%m")
    return df


def main():
    df = cargar_datos()
    if df.empty:
        print("No hay datos cargados todavia. Corre 'python -m modules.ordenes_trabajo.ingest' primero.")
        return

    records = hr.records_from_df(df, [
        "numero_ot", "anunciante", "marca", "negocio", "fecha_abierta", "fecha_cerrada",
        "responsable", "equipo", "estado", "renta_teorica", "renta_real", "_periodo",
    ])

    spec = {
        "dateField": "_periodo",
        "statTiles": [
            {"label": "Ordenes de trabajo", "kind": "count", "fmt": "int"},
            {"label": "Renta real total", "kind": "sum", "field": "renta_real", "fmt": "money"},
            {"label": "Renta teorica total", "kind": "sum", "field": "renta_teorica", "fmt": "money"},
            {"label": "Cumplimiento vs. teorica", "kind": "ratio", "num": "renta_real", "den": "renta_teorica", "fmt": "pct"},
        ],
        "charts": [
            {"mount": "chart-mes", "type": "bar", "groupBy": "_periodo", "agg": "sum", "field": "renta_real", "fmt": "money"},
            {"mount": "chart-estado", "type": "bar", "groupBy": "estado", "agg": "count", "fmt": "int", "colors": ESTADO_COLOR, "order": ESTADO_ORDEN},
            {"mount": "chart-anunciante", "type": "hbar", "groupBy": "anunciante", "agg": "sum", "field": "renta_real", "fmt": "money", "topN": 10},
        ],
        "tables": [
            {
                "mount": "tabla-anunciante", "groupBy": "anunciante",
                "aggs": [
                    {"key": "ordenes", "op": "count"},
                    {"key": "renta_teorica", "op": "sum", "field": "renta_teorica"},
                    {"key": "renta_real", "op": "sum", "field": "renta_real"},
                ],
                "columns": [["anunciante", "Anunciante"], ["ordenes", "Ordenes"], ["renta_teorica", "Renta teorica"], ["renta_real", "Renta real"]],
                "numericCols": ["renta_teorica", "renta_real"],
                "sort": {"key": "renta_real", "dir": "desc"},
            },
            {
                "mount": "tabla-detalle",
                "columns": [
                    ["numero_ot", "Nro OT"], ["anunciante", "Anunciante"], ["marca", "Marca"], ["negocio", "Negocio"],
                    ["fecha_abierta", "F.Abierta"], ["fecha_cerrada", "F.Cerrada"], ["responsable", "Responsable"],
                    ["equipo", "Equipo"], ["estado", "Estado"], ["renta_teorica", "Renta teorica"], ["renta_real", "Renta real"],
                ],
                "numericCols": ["renta_teorica", "renta_real"],
                "sort": {"key": "fecha_abierta", "dir": "desc"},
            },
        ],
    }

    secciones = "".join([
        hr.filter_bar_html(),
        hr.stat_tiles_mount(),
        hr.section("Renta real por mes", hr.mount("chart-mes")),
        hr.section("Ordenes por estado", hr.mount("chart-estado")),
        hr.section("Top 10 anunciantes por renta real", hr.mount("chart-anunciante")),
        hr.section("Rentabilidad por anunciante (todos)", hr.mount("tabla-anunciante")),
        hr.section("Detalle completo de ordenes de trabajo", hr.mount("tabla-detalle")),
        hr.dashboard_bundle(records, spec),
    ])

    html = hr.page_shell("Informe de Ordenes de Trabajo", "ALESTE ADS S.A. - Advertys", secciones)

    with open(config.REPORT_HTML_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK: informe generado en {config.REPORT_HTML_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
