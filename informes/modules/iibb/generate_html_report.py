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
  - detalle_impositivo_factura (mismo crawl de arriba, pestana "Importes"
    de cada factura -- de aca sale el Subtotal s/IVA REAL cuando la
    factura mezcla alicuotas de IVA, ver _subtotal_real_por_factura() y el
    docstring de crawl_oc_por_factura.py: caso real factura 000500000567,
    2026-09-28)
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
        # La llena el mismo crawl que items_factura_oc (pestana "Importes"
        # de cada factura) -- puede no existir todavia si nunca se corrio
        # crawl_oc_por_factura.py con esta columna (ver su docstring).
        try:
            detalle_impositivo = pd.read_sql_query("SELECT * FROM detalle_impositivo_factura", conn)
        except Exception:
            detalle_impositivo = pd.DataFrame(columns=["numero_referencia", "no_gravado", "gravado_1", "gravado_2", "gravado_3"])
    if not facturas.empty:
        facturas["fecha"] = pd.to_datetime(facturas["fecha"], errors="coerce")
    return facturas, imputaciones, items_oc, ordenes_compra, ordenes_publicidad, detalle_impositivo


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


def _subtotal_real_por_factura(detalle_impositivo: pd.DataFrame) -> pd.DataFrame:
    """Subtotal s/IVA REAL de cada factura crawleada: suma de TODOS los
    conceptos "Gravado" (cualquier alicuota) de la pestana Importes -- ver
    docstring de crawl_oc_por_factura.py. Solo pisa subtotal_ml cuando esta
    fila existe (facturas sin deducible no se crawlean y siguen usando el
    Subtotal ML del export bulk, que para ellas ya viene bien).

    OJO -- moneda extranjera (confirmado en vivo 2026-09-28, facturas
    000500000077/001446/001462/001459/001468/001377, todas "Dolar EEUU"):
    la pestana Importes muestra los Gravado en la MONEDA DE LA FACTURA, no
    en pesos -- Advertys tampoco convierte ahi. El export bulk de Facturas
    para estas mismas facturas trae "Subtotal ML"=0 (nunca completa la
    conversion) pero "Subtotal ME" + "Cotizacion" si son correctos. Por eso
    esta funcion NO convierte a pesos (no tiene la cotizacion de cada
    factura aca) -- la devuelve en la moneda cruda de la pestana Importes,
    y es armar_tabla() quien multiplica por tabla["cotizacion"] (columna
    que ya viene de facturas) antes de pisar subtotal_ml. Para las facturas
    en pesos cotizacion=1.0, no cambia nada."""
    if detalle_impositivo.empty:
        return pd.DataFrame(columns=["numero_referencia", "subtotal_real"])
    tabla = detalle_impositivo.copy()
    tabla["subtotal_real"] = tabla[["no_gravado", "gravado_1", "gravado_2", "gravado_3"]].sum(axis=1)
    return tabla[["numero_referencia", "subtotal_real"]]


_TIPOS_NC = ("NCP", "NCM", "NCR")
_TIPO_FACTURA_DE_NC = {"NCP": "FP", "NCM": "FM"}
ESTADO_ANULADA = "Anulada por NC"
ESTADO_PARCIAL = "NC parcial"


def _marcar_estado_nc(facturas: pd.DataFrame) -> pd.DataFrame:
    """Agrega grupo_factura, estado_nc ("" / "Anulada por NC" / "NC parcial")
    y es_reversa, sobre TODAS las facturas cargadas (antes de recortar a la
    ventana de 6 meses).

    Como llegan las NC (confirmado con datos reales, 2026-09-29): cada NC
    automatica genera un asiento de reversa que el export de Facturas trae
    como una fila "espejo" (tipo FP/FM, tipo_referencia CA, mismo
    numero_referencia + numero_asiento que la NC, subtotal POSITIVO, y sus
    imputaciones con el signo invertido). La factura que realmente se
    anula es OTRA fila: la que indica nc_anula_referencia ("Anular N°
    Referencia" del export de NC). Espejo y NC son la reversa; la factura
    anulada es la original.

    - es_reversa=1: el espejo, y la NC si su factura anulada quedo
      "Anulada" o no se encontro. Se sacan del informe (netean entre si).
    - estado_nc en la factura original: "Anulada por NC" cuando el monto de
      la NC iguala al de la factura (o la factura esta en moneda
      extranjera y su Subtotal ML viene en 0, no comparable: las NC
      automaticas anulan la factura entera); "NC parcial" si difieren.
      En NC parcial la fila de la NC se conserva (agrupada bajo la
      factura) para que netee.
    """
    f = facturas.copy()
    es_nc = f["tipo_asiento"].isin(_TIPOS_NC)
    f["grupo_factura"] = f["numero_referencia"].astype(str) + "|" + f["numero_asiento"].astype(str)
    f["estado_nc"] = ""
    f["nc_numero"] = ""
    f["es_reversa"] = 0

    clave = list(zip(f["numero_referencia"], f["numero_asiento"]))
    claves_nc = set(k for k, n in zip(clave, es_nc) if n)
    es_espejo = pd.Series([(k in claves_nc) and not n for k, n in zip(clave, es_nc)], index=f.index)
    f.loc[es_espejo, "es_reversa"] = 1

    reales = f[~es_nc & ~es_espejo]
    if "nc_anula_referencia" not in f.columns:
        f.loc[es_nc, "es_reversa"] = 1
        return f

    nc_por_factura = {}  # idx factura -> [idx NC]
    for idx in f.index[es_nc]:
        anula = f.at[idx, "nc_anula_referencia"]
        cand = reales[reales["numero_referencia"] == anula] if pd.notna(anula) else reales.iloc[0:0]
        tipo_ok = _TIPO_FACTURA_DE_NC.get(f.at[idx, "tipo_asiento"])
        if tipo_ok is not None:
            cand = cand[cand["tipo_asiento"] == tipo_ok]
        if cand.empty:
            f.at[idx, "es_reversa"] = 1
            continue
        objetivo = (cand["subtotal_ml"] - abs(f.at[idx, "subtotal_ml"] or 0)).abs().idxmin()
        nc_por_factura.setdefault(objetivo, []).append(idx)

    for idx_fact, idx_ncs in nc_por_factura.items():
        fact = float(f.at[idx_fact, "subtotal_ml"] or 0.0)
        nc = sum(abs(float(f.at[i, "subtotal_ml"] or 0.0)) for i in idx_ncs)
        anulada = fact == 0 or abs(fact - nc) < 1.0
        f.at[idx_fact, "estado_nc"] = ESTADO_ANULADA if anulada else ESTADO_PARCIAL
        f.at[idx_fact, "nc_numero"] = ", ".join(str(f.at[i, "numero_referencia"]) for i in idx_ncs)
        for i in idx_ncs:
            if anulada:
                f.at[i, "es_reversa"] = 1
            else:
                f.at[i, "grupo_factura"] = f.at[idx_fact, "grupo_factura"]
                f.at[i, "estado_nc"] = ESTADO_PARCIAL
    return f


def armar_tabla(facturas_6m: pd.DataFrame, deducible: pd.DataFrame, servicio_agencia: pd.DataFrame,
                 oc_detalle: pd.DataFrame, subtotal_real: pd.DataFrame) -> pd.DataFrame:
    tabla = facturas_6m.merge(deducible, on=config.CLAVE_COMPUESTA, how="left")
    tabla["monto_deducible"] = tabla["monto_deducible"].fillna(0.0)
    tabla = tabla.merge(servicio_agencia, on=config.CLAVE_COMPUESTA, how="left")
    tabla["servicio_agencia"] = tabla["servicio_agencia"].fillna(0.0)
    # Pisar subtotal_ml con el Subtotal real (suma de Gravados) cuando el
    # crawl trajo el detalle impositivo de esta factura -- ver
    # _subtotal_real_por_factura(). El Subtotal ML del export bulk alcanza
    # para el resto (facturas sin deducible, no crawleadas).
    #
    # Ojo con las Notas de Credito automaticas (ver modules/facturas/config.py):
    # comparten el mismo numero_referencia que la factura que anulan (mismo
    # numero_asiento, tipo_asiento NCP/NCM/NCR), y el crawl -- que solo
    # navega DPS_Factura_ListView, donde las NC NO aparecen (viven en una
    # vista aparte) -- unicamente pudo haber abierto la factura real (FP/FM).
    # Sin este filtro, el merge por numero_referencia le pisaria tambien el
    # subtotal (positivo) a la fila de la NC, que tiene que quedar en
    # negativo para seguir neteando el total (confirmado en vivo 2026-09-28:
    # facturas 000500000077/000500000079/000500000015/000500000016).
    tabla = tabla.merge(subtotal_real, on="numero_referencia", how="left")
    es_nc = tabla["tipo_asiento"].isin(("NCP", "NCM", "NCR"))
    # subtotal_real viene en la moneda de la factura (ver docstring de
    # _subtotal_real_por_factura) -- convertir a pesos con la cotizacion de
    # CADA fila antes de pisar subtotal_ml (=1.0 para facturas en Pesos).
    subtotal_real_ml = tabla["subtotal_real"] * tabla["cotizacion"].fillna(1.0)
    tabla["subtotal_ml"] = tabla["subtotal_ml"].where(es_nc, subtotal_real_ml.fillna(tabla["subtotal_ml"]))
    tabla = tabla.drop(columns=["subtotal_real"])
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
    facturas, imputaciones, items_oc, ordenes_compra, ordenes_publicidad, detalle_impositivo = cargar_datos()
    if facturas.empty:
        print("No hay facturas cargadas todavia. Corre 'python -m modules.facturas.ingest' primero.")
        return

    facturas = _marcar_estado_nc(facturas)
    facturas = facturas[facturas["es_reversa"] == 0].copy()
    facturas_6m, desde, hasta = _recortar_ultimos_n_meses(facturas, MESES_VENTANA)
    if facturas_6m.empty:
        print(f"No hay facturas entre {desde.date()} y {hasta.date()}. Nada para informar.")
        return

    deducible = _deducible_por_factura(imputaciones)
    servicio_agencia = _servicio_agencia_por_factura(imputaciones)
    oc_detalle = _oc_por_factura(items_oc, ordenes_compra, ordenes_publicidad)
    subtotal_real = _subtotal_real_por_factura(detalle_impositivo)
    tabla = armar_tabla(facturas_6m, deducible, servicio_agencia, oc_detalle, subtotal_real)
    # La fila de la factura real va antes que la de su NC dentro del grupo
    # (la tabla agrupada toma "first" para fecha/cliente/montos).
    tabla["_es_nc"] = tabla["tipo_asiento"].isin(_TIPOS_NC).astype(int)
    tabla = tabla.sort_values(["fecha", "numero_referencia", "_es_nc"], ascending=[False, True, True])
    tabla["_periodo"] = tabla["fecha"].dt.strftime("%Y-%m")
    tabla["anulada"] = (tabla["estado_nc"] == ESTADO_ANULADA).astype(int)
    tabla["con_deducible"] = ((tabla["monto_deducible"] > 0) & (tabla["anulada"] == 0)).astype(int)
    tabla["cuenta_factura"] = ((tabla["_es_nc"] == 0) & (tabla["anulada"] == 0)).astype(int)
    # Una factura con varias OC/OP genera varias filas (ver armar_tabla) --
    # sumar subtotal_ml/monto_deducible/servicio_agencia/base_imponible tal
    # cual en un stat tile las multiplicaria por esa cantidad de OC. Mismo
    # patron que "monto_cobrado_unico" en modules/cobranza_proveedores: estos
    # campos solo llevan el valor en la PRIMERA fila de cada factura y 0 en
    # las repetidas, para que sumarlos de un tirón de el total real.
    #
    # La clave es (grupo_factura, tipo_asiento) y no numero_referencia solo:
    # asi la fila de la NC (mismo numero_referencia que su factura) cuenta
    # aparte y netea el total, en vez de anularse como "repetida".
    # Las facturas ANULADAS por NC (factura + NC netean a 0) se sacan
    # completas de los totales: ni la factura ni su NC suman.
    tabla["_dup_factura"] = tabla.duplicated(subset=["grupo_factura", "tipo_asiento"], keep="first") | (tabla["anulada"] == 1)
    tabla["subtotal_unico"] = tabla["subtotal_ml"].where(~tabla["_dup_factura"], 0.0)
    tabla["monto_deducible_unico"] = tabla["monto_deducible"].where(~tabla["_dup_factura"], 0.0)
    tabla["servicio_agencia_unico"] = tabla["servicio_agencia"].where(~tabla["_dup_factura"], 0.0)
    tabla["base_imponible_unico"] = tabla["base_imponible"].where(~tabla["_dup_factura"], 0.0)

    facturas_unicas = tabla[(tabla["anulada"] == 0)].drop_duplicates(subset=["grupo_factura", "tipo_asiento"])
    cant_facturas = len(facturas_unicas[facturas_unicas["_es_nc"] == 0])
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
        "grupo_factura", "estado_nc", "nc_numero", "anulada", "cuenta_factura",
    ])

    spec = {
        "dateField": "_periodo",
        "statTiles": [
            {"label": "Facturas vigentes", "kind": "nunique", "field": "grupo_factura", "fmt": "int", "filter": {"field": "cuenta_factura", "equals": 1}},
            {"label": "Con OC/OP deducible", "kind": "nunique", "field": "grupo_factura", "fmt": "int", "filter": {"field": "con_deducible", "equals": 1}},
            {"label": "Subtotal s/IVA facturado", "kind": "sum", "field": "subtotal_unico", "fmt": "money"},
            {"label": "Monto OC/OP deducible", "kind": "sum", "field": "monto_deducible_unico", "fmt": "money"},
            {"label": "Servicio de Agencia deducido", "kind": "sum", "field": "servicio_agencia_unico", "fmt": "money"},
            {"label": "Base imponible IIBB neta", "kind": "sum", "field": "base_imponible_unico", "fmt": "money"},
        ],
        "tables": [
            {
                "mount": "tabla-facturas",
                "mode": "grouped",
                "groupField": "grupo_factura",
                "groupNoun": {"one": "factura", "many": "facturas"},
                "groupAggs": [
                    {"key": "numero_referencia", "field": "numero_referencia", "op": "first"},
                    {"key": "estado_nc", "field": "estado_nc", "op": "first"},
                    {"key": "nc_numero", "field": "nc_numero", "op": "first"},
                    {"key": "anulada", "field": "anulada", "op": "first"},
                    {"key": "fecha", "field": "fecha", "op": "first"},
                    {"key": "cliente", "field": "cliente", "op": "first"},
                    {"key": "tipo_venta", "field": "tipo_venta", "op": "first"},
                    {"key": "subtotal_ml", "field": "subtotal_ml", "op": "first"},
                    {"key": "monto_deducible", "field": "monto_deducible", "op": "first"},
                    {"key": "servicio_agencia", "field": "servicio_agencia", "op": "first"},
                    {"key": "base_imponible", "field": "base_imponible", "op": "first"},
                ],
                "groupColumns": [
                    ["fecha", "Fecha"], ["numero_referencia", "N° Factura"], ["estado_nc", "Estado"],
                    ["cliente", "Cliente"], ["tipo_venta", "Tipo"],
                    ["subtotal_ml", "Subtotal s/IVA"], ["monto_deducible", "Monto OC/OP deducible"],
                    ["servicio_agencia", "Servicio de Agencia"],
                    ["base_imponible", "Base imponible IIBB"],
                ],
                "groupNumericCols": ["subtotal_ml", "monto_deducible", "servicio_agencia", "base_imponible"],
                # Mobile: solo Fecha, N° Factura y Base imponible en la fila; el resto
                # va en una ficha dentro del detalle desplegable.
                "groupMobileHide": ["estado_nc", "cliente", "tipo_venta", "subtotal_ml", "monto_deducible", "servicio_agencia"],
                # Escritorio: que Cliente no se parta en 5 líneas.
                "groupMinWidths": {"cliente": 160},
                "groupMobileWidths": {"fecha": 84, "numero_referencia": 112},
                "groupBadges": {"estado_nc": {ESTADO_ANULADA: "critical", ESTADO_PARCIAL: "serious"}},
                "groupBadgeNotes": {"estado_nc": {"field": "nc_numero", "prefix": "NC "}},
                "groupStrikeField": "anulada",
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
