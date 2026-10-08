"""
Genera el informe HTML "Cobranza x Factura Venta x Factura Compra": a
partir de lo que se cobra a clientes (Recibo Cliente), que facturas de
venta cancela cada cobro, y que Orden de Compra/proveedor corresponde
pagar como contrapartida -- pedido de Javier (2026-08-04): "a partir de lo
que cobramos vemos que proveedores vamos a pagar".

Cadena Cobrado -> Facturado -> Detalle de lo Facturado:
    recibos.numero_recibo                         (modules/recibos/ingest.py)
        -> referencias_canceladas.numero_recibo    (modules/recibos/crawl_referencias_canceladas.py)
            -> facturas (por tipo_referencia + numero_referencia,          (modules/facturas)
               desambiguado por monto si hay mas de una factura candidata)
                -> items_factura_oc_cobranza.numero_oc                     (crawl_oc_por_factura.py de este modulo)
                    -> ordenes_compra_produccion (proveedor, saldo, estado) (modules/ordenes_compra)
                    -> ordenes_publicidad (proveedor, importe_sin_iva,      (modules/ordenes_publicidad)
                       estado), para facturas Medios (TA=FM)

No tiene ingest propio (igual que modules/pendientes): cruza 7 tablas ya
cargadas por otros scripts. Antes de correr esto conviene tener
actualizado, en este orden:
    python -m modules.recibos.ingest <export ultimo>
    python -m modules.recibos.crawl_referencias_canceladas
    python -m modules.facturas.ingest <export ultimo>
    python -m modules.cobranza_proveedores.crawl_oc_por_factura
    python -m modules.ordenes_compra.ingest <export ultimo>
    python -m modules.ordenes_publicidad.ingest <export ultimo>
    python -m modules.cobranza_proveedores.crawl_facturas_compra_por_oc

Ventana rodante de 2 meses (no un periodo elegible por el usuario -- ver
config.VENTANA_MESES; empezo en 6 meses como IIBB pero se acorto el mismo
dia por costo del crawl de Referencias Canceladas, ver docstring de
config.py), recortada por fecha del RECIBO (fecha de cobro), no de la
factura.

Desambiguacion cuando un mismo N Referencia aparece en mas de una factura
(caso raro FP/FM, ver crawl_oc_por_factura.py de este modulo): se elige la
factura cuyo total_ml este mas cerca del monto aplicado por el recibo
(columna "Aplicar" de Referencias Canceladas); si dos candidatas quedan
igual de cerca, se marca la fila como "ambigua" en vez de adivinar
(decision confirmada con Javier, 2026-08-04).

**Gap real detectado 2026-08-04 (Producción vs Publicidad), cerrado el
mismo dia:** la columna "Orden Compra" de una factura Medios (TA=FM) trae
numeros en un rango totalmente distinto (ej. 7023) al de "Orden Compra
Produccion" (rango 2-205, tabla `ordenes_compra_produccion`) -- son
"Ordenes de Publicidad" (OP), una entidad de Advertys separada. La
primera version de este modulo no tenia un modulo propio para eso y
parseaba el texto crudo que ya trae el crawl (`orden_compra_raw`, formato
"<numero> - <proveedor> -$<monto> - <estado>"), pero se confirmo que ese
texto trae el SALDO actual de la OP (siempre $0,00 en estado "Utilizada"),
no el importe original -- de ahi se armo `modules/ordenes_publicidad`, que
releva la vista real de Advertys (Medios > Ordenes Publicidad >
Navegacion) con el importe sin IVA real ("Total Orden"), independiente del
estado. `_oc_por_factura()` ahora cruza contra esa tabla via
`oc_resolver.resolver_proveedor_monto()` (compartido con modules/iibb, ver
oc_resolver.py); el parseo de texto crudo (`oc_resolver.parsear_oc_texto`)
sigue vivo solo como fallback de ultimo recurso si una OP referenciada no
aparece en `ordenes_publicidad` (no debería pasar salvo datos
desactualizados) y como fuente del nombre de proveedor para desambiguar
(ver mas abajo). La columna "Origen OC" del informe marca `Producción` /
`Publicidad` / `Publicidad (año ambiguo)` / `Publicidad (estimado)` segun
que fuente/certeza tuvo cada fila.

**Gotcha real de `ordenes_publicidad`:** el numero de Orden que aparece en
`orden_compra_raw` (y por lo tanto en `items_oc.numero_oc`) NO trae el año
-- y ese numero se reinicia cada año (ver docstring de
`modules/ordenes_publicidad/config.py`), asi que puede matchear mas de una
fila real. `oc_resolver._resolver_op()` desambigua cruzando tambien por
Proveedor (texto ya parseado de `orden_compra_raw`): en una muestra real, de 164
numero_oc referenciados desde facturas, 116 (71%) colisionaban por año sin
este cruce, y bajan a ~12 (7%) cruzando por proveedor tambien. Los que
siguen ambiguos tras el cruce por proveedor se resuelven con la fila de
año mas reciente (mejor esfuerzo) y quedan marcados "Publicidad (año
ambiguo)" en vez de mostrarse como si fueran un dato cierto.

"Saldo a Pagar" = importe sin IVA de la OC/OP, siempre, sin importar el
estado (pedido explicito de Javier, 2026-08-04: "sin importar si esta
utilizada o autorizada [...] siempre el valor de las ordenes de
compra, es decir el monto sin IVA"). No se neteaba contra el "saldo"
que ya calcula Advertys ni se pisaba a 0 en estados terminales -- ver
`_oc_por_factura()`.

Uso:
    python -m modules.cobranza_proveedores.generate_html_report
"""
import pandas as pd

import db
import html_report as hr
import oc_resolver
from modules.facturas import config as facturas_config
from modules.ordenes_compra import config as oc_config
from modules.ordenes_publicidad import config as op_config
from modules.recibos import config as recibos_config
from . import config


def _fmt_money(v: float) -> str:
    return f"$ {v:,.0f}".replace(",", ".")


def cargar_datos():
    with db.get_connection() as conn:
        recibos = pd.read_sql_query(f"SELECT * FROM {recibos_config.DB_TABLE}", conn)
        try:
            referencias = pd.read_sql_query("SELECT * FROM referencias_canceladas", conn)
        except Exception:
            referencias = pd.DataFrame(columns=[
                "numero_recibo", "cuenta", "tipo_referencia", "numero_referencia",
                "fecha", "saldo", "aplicar", "dif_cambio", "saldo_me", "cotizacion", "aplicado_me",
            ])
        facturas = pd.read_sql_query(f"SELECT * FROM {facturas_config.DB_TABLE}", conn)
        try:
            items_oc = pd.read_sql_query("SELECT * FROM items_factura_oc_cobranza", conn)
        except Exception:
            items_oc = pd.DataFrame(columns=["numero_referencia", "tipo_asiento_inferido", "numero_oc"])
        try:
            ordenes_compra = pd.read_sql_query(f"SELECT * FROM {oc_config.DB_TABLE}", conn)
        except Exception:
            ordenes_compra = pd.DataFrame(columns=["numero_oc", "proveedor", "saldo", "estado", "importe_sin_iva"])
        try:
            ordenes_publicidad = pd.read_sql_query(f"SELECT * FROM {op_config.DB_TABLE}", conn)
        except Exception:
            ordenes_publicidad = pd.DataFrame(columns=["ano_op", "numero_oc", "proveedor", "importe_sin_iva", "estado"])

        try:
            facturas_compra = pd.read_sql_query("SELECT * FROM facturas_compra_oc_cobranza", conn)
        except Exception:
            facturas_compra = pd.DataFrame(columns=[
                "numero_oc", "proveedor_oc", "tr", "numero_referencia_compra", "leyenda",
            ])

    if not recibos.empty:
        recibos["fecha"] = pd.to_datetime(recibos["fecha"], errors="coerce")
    if not facturas.empty:
        facturas["fecha"] = pd.to_datetime(facturas["fecha"], errors="coerce")
    return recibos, referencias, facturas, items_oc, ordenes_compra, ordenes_publicidad, facturas_compra


def _recortar_ultimos_n_meses(recibos: pd.DataFrame, n_meses: int) -> tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    hasta = pd.Timestamp.now().normalize()
    desde = hasta - pd.DateOffset(months=n_meses)
    recorte = recibos[(recibos["fecha"] >= desde) & (recibos["fecha"] <= hasta)].copy()
    return recorte, desde, hasta


def _matchear_facturas(referencias: pd.DataFrame, facturas: pd.DataFrame) -> pd.DataFrame:
    """Cruza cada fila de Referencias Canceladas con SU factura, desambiguando
    por monto cuando el N Referencia le pega a mas de una factura (falta el
    TA en la sub-grilla del recibo, ver docstring del modulo)."""
    if referencias.empty or facturas.empty:
        cols = list(referencias.columns) + ["clave_factura", "tipo_asiento", "cliente", "total_ml", "ambiguo"]
        return pd.DataFrame(columns=cols)

    candidatas = referencias.merge(
        facturas[["clave_factura", "tipo_asiento", "tipo_referencia", "numero_referencia", "cliente", "total_ml"]],
        on=["tipo_referencia", "numero_referencia"],
        how="left",
        suffixes=("", "_factura"),
    )
    candidatas["_dist"] = (candidatas["total_ml"].fillna(0) - candidatas["aplicar"].abs()).abs()

    # Para cada fila original de referencias_canceladas (identificada por su
    # posicion), quedarse con la candidata de menor distancia. Si hay empate
    # entre las 2 mejores, marcar "ambiguo" en vez de adivinar.
    referencias = referencias.reset_index().rename(columns={"index": "_ref_idx"})
    candidatas = candidatas.reset_index().rename(columns={"index": "_ref_idx"})

    resultado = []
    for ref_idx, grupo in candidatas.groupby("_ref_idx"):
        grupo = grupo.sort_values("_dist", na_position="last")
        mejor = grupo.iloc[0]
        ambiguo = False
        if len(grupo) > 1 and pd.notna(grupo.iloc[1]["_dist"]):
            if abs(grupo.iloc[0]["_dist"] - grupo.iloc[1]["_dist"]) < 1.0:
                ambiguo = True
        fila = mejor.to_dict()
        fila["ambiguo"] = ambiguo or pd.isna(mejor.get("clave_factura"))
        resultado.append(fila)

    return pd.DataFrame(resultado).drop(columns=["_dist"], errors="ignore")


_COLUMNAS_OC = [
    "numero_referencia", "tipo_asiento_inferido", "numero_oc",
    "proveedor", "oc_importe_sin_iva", "oc_saldo", "oc_estado", "oc_origen",
]


def _oc_por_factura(items_oc: pd.DataFrame, ordenes_compra: pd.DataFrame,
                     ordenes_publicidad: pd.DataFrame) -> pd.DataFrame:
    """Cruza cada item con OC/OP referenciada contra ordenes_compra/
    ordenes_publicidad -- ver oc_resolver.resolver_proveedor_monto para el
    detalle de la desambiguacion Produccion/Publicidad (compartida con
    modules/iibb)."""
    if items_oc.empty:
        return pd.DataFrame(columns=_COLUMNAS_OC)
    con_oc = items_oc[items_oc["numero_oc"].notna()].drop_duplicates(
        subset=["numero_referencia", "tipo_asiento_inferido", "numero_oc"]
    ).copy()
    if con_oc.empty:
        return pd.DataFrame(columns=_COLUMNAS_OC)

    resuelto = oc_resolver.resolver_proveedor_monto(con_oc, ordenes_compra, ordenes_publicidad)
    return resuelto[_COLUMNAS_OC]


def _facturas_compra_por_oc(facturas_compra: pd.DataFrame) -> pd.DataFrame:
    """Una fila por (numero_oc, proveedor) con las facturas de compra
    imputadas a esa orden y sus leyendas, unidas en un solo texto -- una fila
    por factura multiplicaria las filas de detalle de la OC y distorsionaria
    los totales del informe. Ver crawl_facturas_compra_por_oc.py."""
    cols = ["numero_oc", "proveedor", "factura_compra", "leyenda_compra"]
    if facturas_compra.empty:
        return pd.DataFrame(columns=cols)
    fc = facturas_compra.drop_duplicates(subset=["numero_oc", "proveedor_oc", "tr", "numero_referencia_compra"]).copy()
    fc["_txt_factura"] = fc["numero_referencia_compra"].astype(str) + fc["tr"].apply(
        lambda t: " (NC)" if t == "CA" else ""
    )
    fc["_txt_leyenda"] = fc["leyenda"].fillna("").str.strip()
    agrupado = fc.groupby(["numero_oc", "proveedor_oc"], as_index=False).agg(
        factura_compra=("_txt_factura", " / ".join),
        leyenda_compra=("_txt_leyenda", lambda v: " / ".join(dict.fromkeys(x for x in v if x))),
    )
    return agrupado.rename(columns={"proveedor_oc": "proveedor"})[cols]


def _detalle_por_factura(items_oc: pd.DataFrame) -> pd.DataFrame:
    """Texto "Detalle" de los items de cada factura de venta (ej. "Sponsor
    Congreso del Mercado de Gas"), agrupado por (factura, OC) para que cada
    fila de detalle del informe -- una por factura x OC -- muestre el detalle
    de SUS items; si hay varios, van unidos con " / ". Los items sin OC
    quedan bajo OC vacia (filas "sin OC vinculada")."""
    cols = ["numero_referencia", "_ta_det", "_oc", "detalle_factura", "texto_cabecera"]
    if items_oc.empty or "detalle" not in items_oc.columns:
        return pd.DataFrame(columns=cols)
    it = items_oc.copy()
    if "texto_cabecera" not in it.columns:  # base crawleada antes de esta columna
        it["texto_cabecera"] = ""
    it["texto_cabecera"] = it["texto_cabecera"].fillna("").str.strip()
    it["_oc"] = it["numero_oc"].fillna("")
    it["detalle"] = it["detalle"].fillna("").str.strip()
    agrupado = it.groupby(["numero_referencia", "tipo_asiento_inferido", "_oc"], as_index=False).agg(
        detalle_factura=("detalle", lambda v: " / ".join(dict.fromkeys(x for x in v if x))),
        texto_cabecera=("texto_cabecera", lambda v: next((x for x in v if x), "")),
    )
    return agrupado.rename(columns={"tipo_asiento_inferido": "_ta_det"})[cols]


def armar_tabla(recibos_6m: pd.DataFrame, referencias: pd.DataFrame, facturas: pd.DataFrame,
                 items_oc: pd.DataFrame, ordenes_compra: pd.DataFrame,
                 ordenes_publicidad: pd.DataFrame, facturas_compra: pd.DataFrame | None = None) -> pd.DataFrame:
    referencias_ventana = referencias[referencias["numero_recibo"].isin(recibos_6m["numero_recibo"])]
    matcheadas = _matchear_facturas(referencias_ventana, facturas)
    oc_detalle = _oc_por_factura(items_oc, ordenes_compra, ordenes_publicidad)

    tabla = matcheadas.merge(
        recibos_6m[["numero_recibo", "fecha", "cliente", "efvo_otros"]].rename(
            columns={"fecha": "fecha_recibo", "cliente": "cliente_recibo", "efvo_otros": "cobrado_transf"}
        ),
        on="numero_recibo", how="left",
    )
    tabla = tabla.merge(
        oc_detalle, left_on=["numero_referencia", "tipo_asiento"],
        right_on=["numero_referencia", "tipo_asiento_inferido"], how="left",
        suffixes=("", "_oc"),
    )
    tabla["_oc"] = tabla["numero_oc"].fillna("")
    tabla = tabla.merge(
        _detalle_por_factura(items_oc),
        left_on=["numero_referencia", "tipo_asiento", "_oc"],
        right_on=["numero_referencia", "_ta_det", "_oc"], how="left",
    ).drop(columns=["_ta_det", "_oc"])
    tabla["detalle_factura"] = tabla["detalle_factura"].fillna("")
    tabla["texto_cabecera"] = tabla["texto_cabecera"].fillna("")
    tabla = tabla.merge(
        _facturas_compra_por_oc(facturas_compra if facturas_compra is not None else pd.DataFrame()),
        on=["numero_oc", "proveedor"], how="left",
    )
    tabla["factura_compra"] = tabla["factura_compra"].fillna("")
    tabla["leyenda_compra"] = tabla["leyenda_compra"].fillna("")
    # Con signo (pedido de Javier, 2026-10-08): "Aplicar" viene negativo en las
    # facturas (FA) y positivo en las notas de credito (CA) que el recibo
    # cancela -- cobrado = facturas - CA, no la suma de los valores absolutos.
    tabla["monto_aplicado"] = -tabla["aplicar"]
    tabla["proveedor"] = tabla["proveedor"].fillna("(sin OC vinculada)")
    tabla["oc_origen"] = tabla["oc_origen"].fillna("")
    return tabla


def main():
    recibos, referencias, facturas, items_oc, ordenes_compra, ordenes_publicidad, facturas_compra = cargar_datos()
    if recibos.empty:
        print("No hay recibos cargados todavia. Corre 'python -m modules.recibos.ingest' primero.")
        return
    if referencias.empty:
        print("No hay Referencias Canceladas cargadas todavia. Corre")
        print("'python -m modules.recibos.crawl_referencias_canceladas' primero.")
        return

    recibos_6m, desde, hasta = _recortar_ultimos_n_meses(recibos, config.VENTANA_MESES)
    if recibos_6m.empty:
        print(f"No hay recibos entre {desde.date()} y {hasta.date()}. Nada para informar.")
        return

    tabla = armar_tabla(recibos_6m, referencias, facturas, items_oc, ordenes_compra, ordenes_publicidad, facturas_compra)
    if tabla.empty:
        print("No se pudo armar el cruce (revisar que los crawls de referencias/OC se hayan corrido).")
        return

    tabla = tabla.sort_values("fecha_recibo", ascending=False)
    tabla["_periodo"] = tabla["fecha_recibo"].dt.strftime("%Y-%m")
    tabla["tiene_oc"] = tabla["numero_oc"].notna().astype(int)
    tabla["oc_saldo"] = tabla["oc_saldo"].fillna(0.0)
    tabla["ambiguo_txt"] = tabla["ambiguo"].map({True: "Revisar (cruce ambiguo)", False: ""})
    # Una factura puede tener varias OC vinculadas (una fila por OC, para
    # poder listar cada proveedor/saldo por separado) -- sumar
    # "monto_aplicado" tal cual en un stat tile/chart lo multiplicaria por
    # esa cantidad de OC. Este campo solo lleva el monto en la PRIMERA fila
    # de cada (recibo, factura) y 0 en las repetidas, para que sumarlo de
    # un tirón (statTiles/charts) de el total real cobrado.
    tabla["_dup_referencia"] = tabla.duplicated(subset=["numero_recibo", "tipo_referencia", "numero_referencia"], keep="first")
    tabla["monto_cobrado_unico"] = tabla["monto_aplicado"].where(~tabla["_dup_referencia"], 0.0)

    # Idem para el cobrado en transferencia (dato de cabecera del recibo, se
    # repite en cada linea de detalle): solo cuenta en la primera fila de cada recibo.
    tabla["transf_unico"] = tabla["cobrado_transf"].where(~tabla.duplicated(subset=["numero_recibo"], keep="first"), 0.0)

    cant_recibos = recibos_6m["numero_recibo"].nunique()
    cant_facturas = tabla["numero_referencia"].nunique()
    cant_ambiguas = int(tabla["ambiguo"].sum())
    total_cobrado = float(recibos_6m["cancelaciones"].abs().sum())
    proveedores_distintos = tabla.loc[tabla["tiene_oc"] == 1, "proveedor"].nunique()
    # Sumar oc_saldo de la propia tabla (no re-consultar ordenes_compra_produccion):
    # esa tabla solo cubre el lado Produccion, y dejaria afuera el saldo estimado
    # de las Ordenes de Publicidad que resuelve el fallback de _oc_por_factura.
    oc_unicas = tabla.loc[tabla["tiene_oc"] == 1].drop_duplicates(subset=["numero_oc"])
    total_saldo_oc = float(oc_unicas["oc_saldo"].sum())

    records = hr.records_from_df(tabla, [
        "fecha_recibo", "numero_recibo", "cliente_recibo", "cobrado_transf", "numero_referencia",
        "detalle_factura", "texto_cabecera", "monto_aplicado", "monto_cobrado_unico", "transf_unico", "numero_oc", "proveedor",
        "oc_saldo", "oc_estado", "factura_compra", "leyenda_compra",
        "oc_origen", "tiene_oc", "ambiguo_txt", "_periodo",
    ])

    # Filtros categoricos (dropdown "Todos" + valores unicos, ver
    # hr.category_filters_html): pedido de Javier (2026-08-04), "poner
    # filtros por cliente, numero de recibo de cobro y mas". Actuan sobre
    # statTiles/charts/tabla por igual (a diferencia del buscador en vivo de
    # la tabla, que solo filtra esa tabla).
    CATEGORY_FILTERS = [
        {"field": "cliente_recibo", "label": "Cliente"},
        {"field": "numero_recibo", "label": "N° Recibo"},
        {"field": "numero_referencia", "label": "N° Factura"},
        {"field": "proveedor", "label": "Proveedor"},
        {"field": "oc_estado", "label": "Estado OC"},
        {"field": "oc_origen", "label": "Origen OC"},
    ]

    spec = {
        "dateField": "_periodo",
        "categoryFilters": CATEGORY_FILTERS,
        # Filtros detras de un boton "Filtros" junto al buscador de la tabla
        # (pedido de Javier, 2026-10-01: sacar tanta info de la pagina
        # principal) + orden por titulo de columna.
        "filtersInToolbar": True,
        "statTiles": [
            {"label": "Total cobrado (facturas - NC)", "kind": "sum", "field": "monto_cobrado_unico", "fmt": "money"},
            {"label": "Cobrado en transferencia", "kind": "sum", "field": "transf_unico", "fmt": "money"},
        ],
        "tables": [
            {
                "mount": "tabla-detalle",
                "mode": "grouped",
                "sortableHeaders": True,
                # Exportar CSV (pedido de Javier, 2026-10-01): una fila por
                # linea de detalle, con el recibo repetido. "Monto Cobrado
                # (sin repetir)" lleva el monto solo en la primera fila de
                # cada (recibo, factura) para que sumar la columna en Excel
                # de el total real (ver monto_cobrado_unico en main()).
                "csvExport": {
                    "filename": "cobranza_proveedores",
                    # Titulos del CSV: el recibo se repite en cada linea, asi
                    # que se aclara que columnas son del recibo, de la factura
                    # o de la OC/OP, y cual se puede sumar sin duplicar.
                    "labels": {
                        "fecha_recibo": "Fecha Recibo",
                        "numero_recibo": "N° Recibo",
                        "cliente_recibo": "Cliente",
                        "_cant_facturas": "Facturas del recibo (cant.)",
                        "_total_cobrado": "Total Cobrado del recibo",
                        "cobrado_transf": "Cobrado en Transferencia del recibo",
                        "_cant_proveedores": "Proveedores del recibo (cant.)",
                        "_saldo_oc": "Saldo a Pagar del recibo",
                        "numero_referencia": "N° Factura de Venta",
                        "detalle_factura": "Detalle Factura de Venta",
                        "texto_cabecera": "Texto Cabecera de la Factura",
                        "monto_aplicado": "Monto Cobrado de la factura",
                        "numero_oc": "N° OC/OP",
                        "proveedor": "Proveedor",
                        "oc_saldo": "Saldo a Pagar de la OC/OP",
                        "factura_compra": "N° Factura de Compra",
                        "leyenda_compra": "Leyenda Factura de Compra",
                        "oc_estado": "Estado OC/OP",
                        "oc_origen": "Origen OC/OP",
                        "ambiguo_txt": "Aviso",
                        "monto_cobrado_unico": "Monto Cobrado SUMABLE (sin repetir)",
                    },
                    "extraDetail": [["monto_cobrado_unico", "Monto Cobrado SUMABLE (sin repetir)"]],
                    "extraNumeric": ["monto_cobrado_unico"],
                },
                "groupField": "numero_recibo",
                "groupNoun": {"one": "recibo", "many": "recibos"},
                # Fila resumen: una por recibo. "sum_unique" en Saldo a Pagar
                # evita contar dos veces una misma OC si aparece en mas de una
                # linea de detalle del mismo recibo (ver groupRows en
                # html_report.py). "monto_cobrado_unico" (no monto_aplicado)
                # porque una factura con varias OC ya genera varias filas de
                # detalle -- sumar monto_aplicado tal cual multiplicaria el
                # cobrado real por esa cantidad de OC.
                "groupAggs": [
                    {"key": "fecha_recibo", "field": "fecha_recibo", "op": "first"},
                    {"key": "cliente_recibo", "field": "cliente_recibo", "op": "first"},
                    {"key": "_cant_facturas", "field": "numero_referencia", "op": "nunique"},
                    {"key": "_total_cobrado", "field": "monto_cobrado_unico", "op": "sum"},
                    # Cobrado en transferencia (columna "Efvo.Otros" del recibo, pedido
                    # de Javier 2026-10-08): dato de cabecera del recibo, no de sus
                    # facturas/OC -- "first" (se repite igual en cada linea de detalle).
                    {"key": "_cobrado_transf", "field": "cobrado_transf", "op": "first"},
                    {"key": "_cant_proveedores", "field": "proveedor", "op": "nunique", "filter": {"field": "tiene_oc", "equals": 1}},
                    {"key": "_saldo_oc", "field": "oc_saldo", "op": "sum_unique", "dedupeField": "numero_oc", "filter": {"field": "tiene_oc", "equals": 1}},
                ],
                "groupColumns": [
                    ["fecha_recibo", "Fecha Recibo"], ["numero_recibo", "N° Recibo"],
                    ["cliente_recibo", "Cliente"], ["_cant_facturas", "Facturas"],
                    ["_total_cobrado", "Total Cobrado"], ["_cobrado_transf", "Cobrado Transf."],
                    ["_cant_proveedores", "Proveedores"],
                    ["_saldo_oc", "Saldo a Pagar"],
                ],
                "groupNumericCols": ["_total_cobrado", "_cobrado_transf", "_saldo_oc"],
                # Mobile: la fila muestra N° Recibo, Total Cobrado y Saldo a Pagar; el
                # resto (fecha, cliente, cantidades) va en una ficha dentro del detalle.
                "groupMobileHide": ["fecha_recibo", "cliente_recibo", "_cant_facturas", "_cobrado_transf", "_cant_proveedores"],
                "groupMobileWidths": {"_total_cobrado": 108, "_saldo_oc": 108},
                "detailColumns": [
                    ["numero_referencia", "N° Factura"], ["detalle_factura", "Detalle Factura"],
                    ["texto_cabecera", "Texto Cabecera"],
                    ["monto_aplicado", "Monto Cobrado"],
                    ["numero_oc", "N° OC/OP"], ["proveedor", "Proveedor"],
                    ["oc_saldo", "Saldo a Pagar"],
                    ["factura_compra", "Factura de Compra"], ["leyenda_compra", "Leyenda Factura Compra"],
                    ["oc_estado", "Estado OC"], ["oc_origen", "Origen OC"], ["ambiguo_txt", "Aviso"],
                ],
                "detailNumericCols": ["monto_aplicado", "oc_saldo"],
                "sort": {"key": "fecha_recibo", "dir": "desc"},
            },
        ],
    }

    secciones = "".join([
        hr.stat_tiles_mount(),
        hr.filters_panel_html(CATEGORY_FILTERS),
        hr.section("Detalle: Recibo → Factura → OC/Proveedor", hr.mount("tabla-detalle"), wide=True),
        hr.dashboard_bundle(records, spec),
    ])

    html = hr.page_shell("Cobranza x Proveedores", "ALESTE ADS S.A. - Advertys", secciones)

    with open(config.REPORT_HTML_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK: informe generado en {config.REPORT_HTML_OUTPUT_PATH}")
    print(f"  {cant_recibos} recibos en ventana ({desde.date()} a {hasta.date()}), {cant_facturas} facturas canceladas,")
    print(f"  total cobrado {_fmt_money(total_cobrado)}, {proveedores_distintos} proveedores a pagar, saldo OC pendiente {_fmt_money(total_saldo_oc)}.")
    if cant_ambiguas:
        print(f"  AVISO: {cant_ambiguas} fila(s) con cruce Recibo->Factura ambiguo (revisar a mano, ver docstring).")


if __name__ == "__main__":
    main()
