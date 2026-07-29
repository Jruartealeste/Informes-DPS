"""
Genera el informe HTML de IIBB: por cada factura de venta de los ultimos 6
meses, el monto de recupero de costo de terceros (OC produccion + OP
medios) que ALESTE ADS S.A. puede deducir de la base imponible por ser
agencia/comisionista, y la base imponible neta resultante. Pensado para
informar a ARBA -- ver modules/iibb/config.py para el detalle de que
cuentas contables se consideran deducibles y por que.

A diferencia de los demas informe_*.html, este no ingesta su propia fuente
de facturas: cruza tres tablas ya cargadas por otros scripts:
  - facturas          (modules/facturas, todas las facturas del periodo)
  - imputaciones_iibb (modules/iibb/ingest.py, ya filtrado a cuentas
    411040/411075 -- de aca sale el monto_deducible, la cifra autoritativa)
  - items_factura_oc  (modules/iibb/crawl_oc_por_factura.py, un crawl con
    Playwright factura por factura -- de aca sale SOLO el N° de OC/OP de
    referencia por factura, no un monto: el "Neto Sin Iva" de cada item
    incluye el margen/fee de la agencia sobre ese item, asi que NO es
    comparable 1 a 1 contra monto_deducible -- confirmado 2026-07-23
    comparando ambas fuentes, ver hallazgos en el commit/README)

Por eso antes de correr esto conviene tener actualizado:
    python -m modules.facturas.ingest <export ultimo>
    python -m modules.iibb.ingest <export ultimo>
    python -m modules.iibb.crawl_oc_por_factura

Es un informe de ventana rodante, no de periodo elegible por el usuario
(pedido explicito de Javier, 2026-07-23): siempre muestra los ultimos 6
meses completos a partir de la fecha en que se genera, recalculado cada
vez que se corre -- no el filtro de periodo dinamico de los demas modulos.

Uso:
    python -m modules.iibb.generate_html_report
"""
from datetime import datetime

import pandas as pd

import db
import html_report as hr
from modules.facturas import config as facturas_config
from . import config

MESES_VENTANA = 6

# barChartSvg escala su viewBox a ancho variable (max(560, n*70)); hbarChartSvg
# usa ancho fijo (760). A igual alto de viewBox, esa diferencia de ancho hace
# que -una vez escalados al mismo ancho de card- el bar chart salga mas alto
# que el hbar. Con la ventana fija de 6-7 meses de este informe el bar chart
# siempre cae en el piso de ancho (560), asi que escalar el alto del hbar por
# 760/560 iguala la altura renderizada de los dos charts que van lado a lado.
HBAR_HEIGHT_MATCH_BAR = round(260 * 760 / 560)


def _fmt_money(v: float) -> str:
    return f"$ {v:,.0f}".replace(",", ".")


def cargar_datos():
    with db.get_connection() as conn:
        facturas = pd.read_sql_query(f"SELECT * FROM {facturas_config.DB_TABLE}", conn)
        imputaciones = pd.read_sql_query(f"SELECT * FROM {config.DB_TABLE}", conn)
        # items_factura_oc la llena modules/iibb/crawl_oc_por_factura.py (un
        # crawl aparte, no un ingest de Excel -- ver docstring de ese script).
        # Puede no existir todavia si nunca se corrio ese crawl; en ese caso
        # el informe sigue andando, solo sin la columna de N° OC/OP.
        try:
            items_oc = pd.read_sql_query("SELECT * FROM items_factura_oc", conn)
        except Exception:
            items_oc = pd.DataFrame(columns=["numero_referencia", "numero_oc"])
    if not facturas.empty:
        facturas["fecha"] = pd.to_datetime(facturas["fecha"], errors="coerce")
    return facturas, imputaciones, items_oc


def _oc_relacionadas_por_factura(items_oc: pd.DataFrame) -> pd.DataFrame:
    """N° de OC/OP distintos por factura, releva dos por Playwright (no hay
    export bulk -- ver crawl_oc_por_factura.py), como texto separado por
    coma para mostrar en el detalle. Solo cubre las facturas sobre las que
    se corrio ese crawl (con deducible en la ventana de 6 meses al momento
    de crawlear), no el historico completo."""
    if items_oc.empty:
        return pd.DataFrame(columns=["numero_referencia", "oc_relacionadas"])
    con_oc = items_oc[items_oc["numero_oc"].notna()].copy()
    if con_oc.empty:
        return pd.DataFrame(columns=["numero_referencia", "oc_relacionadas"])
    con_oc["numero_oc_int"] = con_oc["numero_oc"].astype(int)
    agrupado = (
        con_oc.sort_values("numero_oc_int")
        .groupby("numero_referencia")["numero_oc"]
        .apply(lambda s: ", ".join(dict.fromkeys(s)))
        .reset_index()
        .rename(columns={"numero_oc": "oc_relacionadas"})
    )
    return agrupado


def _recortar_ultimos_n_meses(facturas: pd.DataFrame, n_meses: int) -> tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    hasta = pd.Timestamp.now().normalize()
    desde = hasta - pd.DateOffset(months=n_meses)
    recorte = facturas[(facturas["fecha"] >= desde) & (facturas["fecha"] <= hasta)].copy()
    return recorte, desde, hasta


def _deducible_por_factura(imputaciones: pd.DataFrame) -> pd.DataFrame:
    if imputaciones.empty:
        return pd.DataFrame(columns=config.CLAVE_COMPUESTA + ["monto_deducible"])
    agrupado = (
        imputaciones.groupby(config.CLAVE_COMPUESTA)["importe"]
        .sum()
        .reset_index()
        .rename(columns={"importe": "monto_deducible"})
    )
    # El libro de Imputaciones registra los ingresos en negativo (contrapartida
    # de credito); se toma el valor absoluto para mostrar un monto deducible
    # positivo en el informe.
    agrupado["monto_deducible"] = agrupado["monto_deducible"].abs()
    return agrupado


def armar_tabla(facturas_6m: pd.DataFrame, deducible: pd.DataFrame, oc_relacionadas: pd.DataFrame) -> pd.DataFrame:
    tabla = facturas_6m.merge(deducible, on=config.CLAVE_COMPUESTA, how="left")
    tabla["monto_deducible"] = tabla["monto_deducible"].fillna(0.0)
    tabla["base_imponible"] = tabla["subtotal_ml"] - tabla["monto_deducible"]
    tabla = tabla.merge(oc_relacionadas, on="numero_referencia", how="left")
    tabla["oc_relacionadas"] = tabla["oc_relacionadas"].fillna("")
    return tabla


def main():
    facturas, imputaciones, items_oc = cargar_datos()
    if facturas.empty:
        print("No hay facturas cargadas todavia. Corre 'python -m modules.facturas.ingest' primero.")
        return

    facturas_6m, desde, hasta = _recortar_ultimos_n_meses(facturas, MESES_VENTANA)
    if facturas_6m.empty:
        print(f"No hay facturas entre {desde.date()} y {hasta.date()}. Nada para informar.")
        return

    deducible = _deducible_por_factura(imputaciones)
    oc_relacionadas = _oc_relacionadas_por_factura(items_oc)
    tabla = armar_tabla(facturas_6m, deducible, oc_relacionadas).sort_values("fecha", ascending=False)
    tabla["_periodo"] = tabla["fecha"].dt.strftime("%Y-%m")
    tabla["con_deducible"] = (tabla["monto_deducible"] > 0).astype(int)

    cant_facturas = len(tabla)
    cant_con_deducible = int(tabla["con_deducible"].sum())
    total_base_imponible = float(tabla["base_imponible"].sum())

    # Nota: statTiles/charts/tabla se recalculan en el navegador (DASHBOARD_JS)
    # segun el rango Desde/Hasta que elija el usuario -- igual que
    # Facturas/Compras. La base de datos que se embebe (records) YA viene
    # recortada a los ultimos 6 meses (ver _recortar_ultimos_n_meses): el
    # filtro de periodo solo permite acotar DENTRO de esa ventana, no verla
    # completa desde siempre (pedido explicito de Javier, 2026-07-23).
    records = hr.records_from_df(tabla, [
        "fecha", "numero_referencia", "cliente", "subtotal_ml",
        "monto_deducible", "base_imponible", "oc_relacionadas", "con_deducible", "_periodo",
    ])

    spec = {
        "dateField": "_periodo",
        "statTiles": [
            {"label": "Facturas", "kind": "count", "fmt": "int"},
            {"label": "Con OC/OP deducible", "kind": "count", "fmt": "int", "filter": {"field": "con_deducible", "equals": 1}},
            {"label": "Subtotal s/IVA facturado", "kind": "sum", "field": "subtotal_ml", "fmt": "money"},
            {"label": "Monto OC/OP deducible", "kind": "sum", "field": "monto_deducible", "fmt": "money"},
            {"label": "Base imponible IIBB neta", "kind": "sum", "field": "base_imponible", "fmt": "money"},
        ],
        "charts": [
            {"mount": "chart-mes", "type": "bar", "groupBy": "_periodo", "agg": "sum", "field": "monto_deducible", "fmt": "money"},
            {"mount": "chart-clientes", "type": "hbar", "groupBy": "cliente", "agg": "sum", "field": "monto_deducible", "fmt": "money", "topN": 10, "height": HBAR_HEIGHT_MATCH_BAR},
        ],
        "tables": [
            {
                "mount": "tabla-facturas",
                "columns": [
                    ["fecha", "Fecha"], ["numero_referencia", "N° Factura"], ["cliente", "Cliente"],
                    ["subtotal_ml", "Subtotal s/IVA"], ["monto_deducible", "Monto OC/OP deducible"],
                    ["base_imponible", "Base imponible IIBB"], ["oc_relacionadas", "N° OC/OP"],
                ],
                "numericCols": ["subtotal_ml", "monto_deducible", "base_imponible"],
                "sort": {"key": "fecha", "dir": "desc"},
            },
        ],
    }

    secciones = "".join([
        hr.filter_bar_html(),
        hr.stat_tiles_mount(),
        hr.section("Monto OC/OP deducible por mes", hr.mount("chart-mes")),
        hr.section("Top 10 clientes por monto OC/OP deducible", hr.mount("chart-clientes")),
        hr.section("Detalle por factura", hr.mount("tabla-facturas"), wide=True),
        hr.dashboard_bundle(records, spec),
    ])

    html = hr.page_shell("Informe IIBB (recupero OC/OP)", "ALESTE ADS S.A. - Advertys", secciones)

    with open(config.REPORT_HTML_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK: informe generado en {config.REPORT_HTML_OUTPUT_PATH}")
    print(f"  {cant_facturas} facturas en ventana ({desde.date()} a {hasta.date()}), {cant_con_deducible} con OC/OP deducible, base imponible neta {_fmt_money(total_base_imponible)}.")


if __name__ == "__main__":
    main()
