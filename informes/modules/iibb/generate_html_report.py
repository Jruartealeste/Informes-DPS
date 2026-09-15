"""
Genera el informe HTML de IIBB: por cada factura de venta de los ultimos 6
meses, el monto de recupero de costo de terceros (OC produccion + OP
medios) mas el Servicio de Agencia que ALESTE ADS S.A. puede deducir de la
base imponible por ser agencia/comisionista, la base imponible neta
resultante, y si la venta corresponde a Produccion (OC) o Medios (OP).
Pensado para informar a ARBA -- ver modules/iibb/config.py para el detalle
de que cuentas contables se consideran deducibles y por que.

A diferencia de los demas informe_*.html, este no ingesta su propia fuente
de facturas: cruza estas tablas ya cargadas por otros scripts:
  - facturas          (modules/facturas, todas las facturas del periodo --
    tambien de aca sale tipo_asiento/TA, que da el tipo_venta Produccion/
    Medios por factura sin necesidad de otro cruce)
  - imputaciones_iibb (modules/iibb/ingest.py, ya filtrado a
    config.CUENTAS_A_CARGAR -- de aca salen monto_deducible y
    servicio_agencia, las cifras autoritativas, ver
    _deducible_por_factura/_servicio_agencia_por_factura)
  - items_factura_oc  (modules/iibb/crawl_oc_por_factura.py, un crawl con
    Playwright factura por factura -- de aca sale SOLO el N° de OC/OP de
    referencia por factura, no un monto: el "Neto Sin Iva" de cada item
    incluye el margen/fee de la agencia sobre ese item, asi que NO es
    comparable 1 a 1 contra monto_deducible -- confirmado 2026-07-23
    comparando ambas fuentes, ver hallazgos en el commit/README)
  - ordenes_compra_produccion / ordenes_publicidad (modules/ordenes_compra,
    modules/ordenes_publicidad) -- de aca sale el Proveedor y el Monto sin
    IVA real de cada OC/OP referenciada, via oc_resolver.py (mismo cruce
    que ya usa modules/cobranza_proveedores, compartido para no duplicar
    la desambiguacion Produccion/Publicidad -- ver oc_resolver.py)

Por eso antes de correr esto conviene tener actualizado (los 5 pasos, en
este orden -- ver tools/actualizar_iibb.py para correrlos todos de una
sola vez, es el camino recomendado):
    python -m modules.facturas.ingest <export ultimo>
    python -m modules.ordenes_compra.ingest <export ultimo>
    python -m modules.ordenes_publicidad.ingest <export ultimo>
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
import oc_resolver
from modules.facturas import config as facturas_config
from modules.ordenes_compra import config as oc_config
from modules.ordenes_publicidad import config as op_config
from . import config

MESES_VENTANA = 6


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
            items_oc = pd.DataFrame(columns=["numero_referencia", "orden_compra_raw", "numero_oc"])
        # ordenes_compra/ordenes_publicidad son las mismas tablas que usa
        # modules/cobranza_proveedores para resolver Proveedor/Monto sin IVA
        # (ver oc_resolver.py) -- pueden no estar cargadas todavia; en ese
        # caso el detalle de OC/OP queda solo con el N° (sin Proveedor/Monto).
        try:
            ordenes_compra = pd.read_sql_query(f"SELECT * FROM {oc_config.DB_TABLE}", conn)
        except Exception:
            ordenes_compra = pd.DataFrame(columns=["numero_oc", "proveedor", "importe_sin_iva", "estado"])
        try:
            ordenes_publicidad = pd.read_sql_query(f"SELECT * FROM {op_config.DB_TABLE}", conn)
        except Exception:
            ordenes_publicidad = pd.DataFrame(columns=["ano_op", "numero_oc", "proveedor", "importe_sin_iva", "estado"])
    if not facturas.empty:
        facturas["fecha"] = pd.to_datetime(facturas["fecha"], errors="coerce")
    return facturas, imputaciones, items_oc, ordenes_compra, ordenes_publicidad


_COLUMNAS_OC = ["numero_referencia", "numero_oc", "proveedor", "oc_saldo"]


def _oc_por_factura(items_oc: pd.DataFrame, ordenes_compra: pd.DataFrame,
                     ordenes_publicidad: pd.DataFrame) -> pd.DataFrame:
    """Una fila por (factura, OC/OP referenciada), con Proveedor y Monto sin
    IVA real -- mismo cruce que modules/cobranza_proveedores, ver
    oc_resolver.py. Solo cubre las facturas sobre las que se corrio el
    crawl (con deducible en la ventana de 6 meses al momento de crawlear),
    no el historico completo."""
    if items_oc.empty:
        return pd.DataFrame(columns=_COLUMNAS_OC)
    con_oc = items_oc[items_oc["numero_oc"].notna()].drop_duplicates(
        subset=["numero_referencia", "numero_oc"]
    ).copy()
    if con_oc.empty:
        return pd.DataFrame(columns=_COLUMNAS_OC)
    resuelto = oc_resolver.resolver_proveedor_monto(con_oc, ordenes_compra, ordenes_publicidad)
    return resuelto[_COLUMNAS_OC]


def _recortar_ultimos_n_meses(facturas: pd.DataFrame, n_meses: int) -> tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    hasta = pd.Timestamp.now().normalize()
    desde = hasta - pd.DateOffset(months=n_meses)
    recorte = facturas[(facturas["fecha"] >= desde) & (facturas["fecha"] <= hasta)].copy()
    return recorte, desde, hasta


def _deducible_por_factura(imputaciones: pd.DataFrame) -> pd.DataFrame:
    if imputaciones.empty:
        return pd.DataFrame(columns=config.CLAVE_COMPUESTA + ["monto_deducible"])
    solo_oc_op = imputaciones[imputaciones["cuenta"].isin(config.CUENTAS_DEDUCIBLES)]
    agrupado = (
        solo_oc_op.groupby(config.CLAVE_COMPUESTA)["importe"]
        .sum()
        .reset_index()
        .rename(columns={"importe": "monto_deducible"})
    )
    # El libro de Imputaciones registra los ingresos en negativo (contrapartida
    # de credito); se toma el valor absoluto para mostrar un monto deducible
    # positivo en el informe.
    agrupado["monto_deducible"] = agrupado["monto_deducible"].abs()
    return agrupado


def _servicio_agencia_por_factura(imputaciones: pd.DataFrame) -> pd.DataFrame:
    """Importe de Servicio de Agencia por factura: cuentas
    config.CUENTAS_SERVICIO_AGENCIA (411020 Produccion / 411070 Medios)
    cuando existen; si una factura no tiene ninguna de esas dos, cae a su
    linea de FEE (config.CUENTA_FEE_FALLBACK) -- confirmado con Javier
    2026-08-18, ver docstring de config.py (la factura 000500001455 es el
    caso real que no tiene 411020: el cargo de agencia esta en el item de
    FEE)."""
    if imputaciones.empty:
        return pd.DataFrame(columns=config.CLAVE_COMPUESTA + ["servicio_agencia"])

    directo = imputaciones[imputaciones["cuenta"].isin(config.CUENTAS_SERVICIO_AGENCIA)]
    agrupado_directo = (
        directo.groupby(config.CLAVE_COMPUESTA)["importe"].sum().reset_index()
        .rename(columns={"importe": "servicio_agencia"})
    )
    fee = imputaciones[imputaciones["cuenta"] == config.CUENTA_FEE_FALLBACK]
    agrupado_fee = (
        fee.groupby(config.CLAVE_COMPUESTA)["importe"].sum().reset_index()
        .rename(columns={"importe": "servicio_agencia_fee"})
    )
    combinado = agrupado_directo.merge(agrupado_fee, on=config.CLAVE_COMPUESTA, how="outer")
    combinado["servicio_agencia"] = combinado["servicio_agencia"].fillna(combinado["servicio_agencia_fee"])
    combinado["servicio_agencia"] = combinado["servicio_agencia"].abs()
    return combinado[config.CLAVE_COMPUESTA + ["servicio_agencia"]]


_TIPO_VENTA_POR_TA = {"FP": "Producción (OC)", "FM": "Medios (OP)"}


def armar_tabla(facturas_6m: pd.DataFrame, deducible: pd.DataFrame, servicio_agencia: pd.DataFrame,
                 oc_detalle: pd.DataFrame) -> pd.DataFrame:
    tabla = facturas_6m.merge(deducible, on=config.CLAVE_COMPUESTA, how="left")
    tabla["monto_deducible"] = tabla["monto_deducible"].fillna(0.0)
    tabla = tabla.merge(servicio_agencia, on=config.CLAVE_COMPUESTA, how="left")
    tabla["servicio_agencia"] = tabla["servicio_agencia"].fillna(0.0)
    tabla["base_imponible"] = tabla["subtotal_ml"] - tabla["monto_deducible"] - tabla["servicio_agencia"]
    tabla["tipo_venta"] = tabla["tipo_asiento"].map(_TIPO_VENTA_POR_TA).fillna(tabla["tipo_asiento"])
    # Una fila por (factura, OC/OP) para el detalle desplegable -- una
    # factura con varias OC/OP genera varias filas, los campos propios de la
    # factura (fecha/cliente/montos) se repiten en cada una (se agregan con
    # op "first" al armar la tabla agrupada, ver spec en main()).
    tabla = tabla.merge(oc_detalle, on="numero_referencia", how="left")
    # Mismo texto que modules/cobranza_proveedores para una factura sin
    # ninguna OC/OP vinculada, en vez de dejar la celda en blanco.
    tabla["proveedor"] = tabla["proveedor"].fillna("(sin OC vinculada)")
    tabla["oc_saldo"] = tabla["oc_saldo"].fillna(0.0)
    return tabla


def main():
    facturas, imputaciones, items_oc, ordenes_compra, ordenes_publicidad = cargar_datos()
    if facturas.empty:
        print("No hay facturas cargadas todavia. Corre 'python -m modules.facturas.ingest' primero.")
        return

    facturas_6m, desde, hasta = _recortar_ultimos_n_meses(facturas, MESES_VENTANA)
    if facturas_6m.empty:
        print(f"No hay facturas entre {desde.date()} y {hasta.date()}. Nada para informar.")
        return

    deducible = _deducible_por_factura(imputaciones)
    servicio_agencia = _servicio_agencia_por_factura(imputaciones)
    oc_detalle = _oc_por_factura(items_oc, ordenes_compra, ordenes_publicidad)
    tabla = armar_tabla(facturas_6m, deducible, servicio_agencia, oc_detalle).sort_values(["fecha", "numero_referencia"], ascending=[False, True])
    tabla["_periodo"] = tabla["fecha"].dt.strftime("%Y-%m")
    tabla["con_deducible"] = (tabla["monto_deducible"] > 0).astype(int)
    # Una factura con varias OC/OP genera varias filas (ver armar_tabla) --
    # sumar subtotal_ml/monto_deducible/servicio_agencia/base_imponible tal
    # cual en un stat tile las multiplicaria por esa cantidad de OC. Mismo
    # patron que "monto_cobrado_unico" en modules/cobranza_proveedores: estos
    # campos solo llevan el valor en la PRIMERA fila de cada factura y 0 en
    # las repetidas, para que sumarlos de un tirón de el total real.
    tabla["_dup_factura"] = tabla.duplicated(subset=["numero_referencia"], keep="first")
    tabla["subtotal_unico"] = tabla["subtotal_ml"].where(~tabla["_dup_factura"], 0.0)
    tabla["monto_deducible_unico"] = tabla["monto_deducible"].where(~tabla["_dup_factura"], 0.0)
    tabla["servicio_agencia_unico"] = tabla["servicio_agencia"].where(~tabla["_dup_factura"], 0.0)
    tabla["base_imponible_unico"] = tabla["base_imponible"].where(~tabla["_dup_factura"], 0.0)

    facturas_unicas = tabla.drop_duplicates(subset=["numero_referencia"])
    cant_facturas = len(facturas_unicas)
    cant_con_deducible = int(facturas_unicas["con_deducible"].sum())
    total_base_imponible = float(facturas_unicas["base_imponible"].sum())

    # Nota: statTiles/charts/tabla se recalculan en el navegador (DASHBOARD_JS)
    # segun el rango Desde/Hasta que elija el usuario -- igual que
    # Facturas/Compras. La base de datos que se embebe (records) YA viene
    # recortada a los ultimos 6 meses (ver _recortar_ultimos_n_meses): el
    # filtro de periodo solo permite acotar DENTRO de esa ventana, no verla
    # completa desde siempre (pedido explicito de Javier, 2026-07-23).
    records = hr.records_from_df(tabla, [
        "fecha", "numero_referencia", "cliente", "tipo_venta", "subtotal_ml", "subtotal_unico",
        "monto_deducible", "monto_deducible_unico", "servicio_agencia", "servicio_agencia_unico",
        "base_imponible", "base_imponible_unico",
        "numero_oc", "proveedor", "oc_saldo", "con_deducible", "_periodo",
    ])

    spec = {
        "dateField": "_periodo",
        "statTiles": [
            {"label": "Facturas", "kind": "nunique", "field": "numero_referencia", "fmt": "int"},
            {"label": "Con OC/OP deducible", "kind": "nunique", "field": "numero_referencia", "fmt": "int", "filter": {"field": "con_deducible", "equals": 1}},
            {"label": "Subtotal s/IVA facturado", "kind": "sum", "field": "subtotal_unico", "fmt": "money"},
            {"label": "Monto OC/OP deducible", "kind": "sum", "field": "monto_deducible_unico", "fmt": "money"},
            {"label": "Servicio de Agencia deducido", "kind": "sum", "field": "servicio_agencia_unico", "fmt": "money"},
            {"label": "Base imponible IIBB neta", "kind": "sum", "field": "base_imponible_unico", "fmt": "money"},
        ],
        "tables": [
            {
                "mount": "tabla-facturas",
                "mode": "grouped",
                "groupField": "numero_referencia",
                "groupNoun": {"one": "factura", "many": "facturas"},
                "groupAggs": [
                    {"key": "fecha", "field": "fecha", "op": "first"},
                    {"key": "cliente", "field": "cliente", "op": "first"},
                    {"key": "tipo_venta", "field": "tipo_venta", "op": "first"},
                    {"key": "subtotal_ml", "field": "subtotal_ml", "op": "first"},
                    {"key": "monto_deducible", "field": "monto_deducible", "op": "first"},
                    {"key": "servicio_agencia", "field": "servicio_agencia", "op": "first"},
                    {"key": "base_imponible", "field": "base_imponible", "op": "first"},
                ],
                "groupColumns": [
                    ["fecha", "Fecha"], ["numero_referencia", "N° Factura"], ["cliente", "Cliente"],
                    ["tipo_venta", "Tipo"],
                    ["subtotal_ml", "Subtotal s/IVA"], ["monto_deducible", "Monto OC/OP deducible"],
                    ["servicio_agencia", "Servicio de Agencia"],
                    ["base_imponible", "Base imponible IIBB"],
                ],
                "groupNumericCols": ["subtotal_ml", "monto_deducible", "servicio_agencia", "base_imponible"],
                "detailColumns": [
                    ["numero_oc", "N° OC/OP"], ["proveedor", "Proveedor"], ["oc_saldo", "Monto sin IVA"],
                ],
                "detailNumericCols": ["oc_saldo"],
                "sort": {"key": "fecha", "dir": "desc"},
            },
        ],
    }

    secciones = "".join([
        hr.filter_bar_html(),
        hr.stat_tiles_mount(),
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
