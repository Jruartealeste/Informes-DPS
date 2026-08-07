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

No tiene ingest propio (igual que modules/pendientes): cruza 6 tablas ya
cargadas por otros scripts. Antes de correr esto conviene tener
actualizado, en este orden:
    python -m modules.recibos.ingest <export ultimo>
    python -m modules.recibos.crawl_referencias_canceladas
    python -m modules.facturas.ingest <export ultimo>
    python -m modules.cobranza_proveedores.crawl_oc_por_factura
    python -m modules.ordenes_compra.ingest <export ultimo>
    python -m modules.ordenes_publicidad.ingest <export ultimo>

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
estado. `_oc_por_factura()` ahora cruza contra esa tabla; el parseo de
texto crudo (`_parsear_oc_texto`) sigue vivo solo como fallback de ultimo
recurso si una OP referenciada no aparece en `ordenes_publicidad` (no
debería pasar salvo datos desactualizados) y como fuente del nombre de
proveedor para desambiguar (ver mas abajo). La columna "Origen OC" del
informe marca `Producción` / `Publicidad` / `Publicidad (año ambiguo)` /
`Publicidad (estimado)` segun que fuente/certeza tuvo cada fila.

**Gotcha real de `ordenes_publicidad`:** el numero de Orden que aparece en
`orden_compra_raw` (y por lo tanto en `items_oc.numero_oc`) NO trae el año
-- y ese numero se reinicia cada año (ver docstring de
`modules/ordenes_publicidad/config.py`), asi que puede matchear mas de una
fila real. `_resolver_op()` desambigua cruzando tambien por Proveedor
(texto ya parseado de `orden_compra_raw`): en una muestra real, de 164
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
import re

import pandas as pd

import db
import html_report as hr
from common import normalizar_numero
from modules.facturas import config as facturas_config
from modules.ordenes_compra import config as oc_config
from modules.ordenes_publicidad import config as op_config
from modules.recibos import config as recibos_config
from . import config

# "7023 - El Bajo Producciones SRL -$ 57463770,15 - Autorizada" ->
# ("El Bajo Producciones SRL", "57463770,15", "Autorizada"). Mismo formato
# de texto que ya parsea crawl_oc_por_factura.parsear_numero_oc (solo el
# numero). El proveedor/estado se usan para desambiguar contra
# `ordenes_publicidad` (ver _resolver_op); el monto parseado de aca solo se
# usa como ultimo recurso si la OP no aparece en esa tabla.
_RE_OC_TEXTO = re.compile(r"^\s*\d+\s*-\s*(.+?)\s*-\$\s*([\d.,]+)\s*-\s*(.+?)\s*$")


def _parsear_oc_texto(texto: str) -> dict | None:
    m = _RE_OC_TEXTO.match(texto or "")
    if not m:
        return None
    proveedor, monto_txt, estado = m.groups()
    return {"proveedor": proveedor.strip(), "monto": normalizar_numero(monto_txt), "estado": estado.strip()}


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

    if not recibos.empty:
        recibos["fecha"] = pd.to_datetime(recibos["fecha"], errors="coerce")
    if not facturas.empty:
        facturas["fecha"] = pd.to_datetime(facturas["fecha"], errors="coerce")
    return recibos, referencias, facturas, items_oc, ordenes_compra, ordenes_publicidad


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


def _normalizar_proveedor(nombre) -> str | None:
    return nombre.strip().upper() if isinstance(nombre, str) and nombre.strip() else None


def _resolver_op(numero_oc: str, proveedor_txt: str | None, ordenes_publicidad: pd.DataFrame) -> tuple[pd.Series | None, str]:
    """Busca la OP real por numero_oc, desambiguando por proveedor cuando el
    numero solo (sin año) matchea mas de una fila -- ver "Gotcha real de
    ordenes_publicidad" en el docstring del modulo. Devuelve (fila o None,
    origen: 'Publicidad' | 'Publicidad (año ambiguo)' | None)."""
    candidatos = ordenes_publicidad[ordenes_publicidad["numero_oc"] == numero_oc]
    if candidatos.empty:
        return None, None
    if len(candidatos) == 1:
        return candidatos.iloc[0], "Publicidad"

    prov_norm = _normalizar_proveedor(proveedor_txt)
    por_proveedor = candidatos[candidatos["proveedor"].apply(_normalizar_proveedor) == prov_norm]
    if len(por_proveedor) == 1:
        return por_proveedor.iloc[0], "Publicidad"

    restantes = por_proveedor if not por_proveedor.empty else candidatos
    return restantes.sort_values("ano_op", ascending=False).iloc[0], "Publicidad (año ambiguo)"


def _oc_por_factura(items_oc: pd.DataFrame, ordenes_compra: pd.DataFrame,
                     ordenes_publicidad: pd.DataFrame) -> pd.DataFrame:
    if items_oc.empty:
        return pd.DataFrame(columns=_COLUMNAS_OC)
    con_oc = items_oc[items_oc["numero_oc"].notna()].drop_duplicates(
        subset=["numero_referencia", "tipo_asiento_inferido", "numero_oc"]
    ).copy()
    if con_oc.empty:
        return pd.DataFrame(columns=_COLUMNAS_OC)

    if not ordenes_compra.empty:
        detalle_oc = ordenes_compra[["numero_oc", "proveedor", "importe_sin_iva", "estado"]].rename(
            columns={"importe_sin_iva": "oc_importe_sin_iva", "estado": "oc_estado"}
        )
        con_oc = con_oc.merge(detalle_oc, on="numero_oc", how="left")
    else:
        con_oc["proveedor"] = None
        con_oc["oc_importe_sin_iva"] = None
        con_oc["oc_estado"] = None
    con_oc["oc_origen"] = con_oc["proveedor"].notna().map({True: "Producción", False: None})

    # Para lo que no matcheo en ordenes_compra_produccion (Ordenes de
    # Publicidad, TA=FM -- ver "Gap real detectado 2026-08-04" en el
    # docstring del modulo): cruzar contra modules/ordenes_publicidad,
    # desambiguando por proveedor cuando el numero de Orden solo no alcanza.
    sin_match = con_oc["proveedor"].isna()
    if sin_match.any():
        parseado = con_oc.loc[sin_match, "orden_compra_raw"].apply(_parsear_oc_texto)
        proveedor_txt = parseado.apply(lambda d: d["proveedor"] if d else None)
        estado_txt = parseado.apply(lambda d: d["estado"] if d else None)
        monto_txt = parseado.apply(lambda d: d["monto"] if d else None)

        for idx in con_oc.loc[sin_match].index:
            fila_op, origen = _resolver_op(
                con_oc.at[idx, "numero_oc"], proveedor_txt.loc[idx], ordenes_publicidad
            )
            if fila_op is not None:
                con_oc.at[idx, "proveedor"] = fila_op["proveedor"]
                con_oc.at[idx, "oc_importe_sin_iva"] = fila_op["importe_sin_iva"]
                con_oc.at[idx, "oc_estado"] = fila_op["estado"]
                con_oc.at[idx, "oc_origen"] = origen
            else:
                # Ultimo recurso: la OP referenciada no esta en
                # ordenes_publicidad (dato desactualizado) -- usar el texto
                # crudo tal cual se hacia antes de tener el modulo propio.
                con_oc.at[idx, "proveedor"] = proveedor_txt.loc[idx]
                con_oc.at[idx, "oc_importe_sin_iva"] = monto_txt.loc[idx]
                con_oc.at[idx, "oc_estado"] = estado_txt.loc[idx]
                con_oc.at[idx, "oc_origen"] = "Publicidad (estimado)" if proveedor_txt.loc[idx] else None

    # "Saldo a Pagar" es siempre el importe sin IVA de la OC/OP, sin importar
    # su estado (Utilizada/Autorizada/etc) -- pedido explicito de Javier
    # (2026-08-04). Antes esta columna se pisaba a 0 para OC/OP en estado
    # terminal, o tomaba el "saldo" que ya trae Advertys para OC de
    # Produccion, y en ambos casos el numero mostrado no coincidia con el
    # monto sin IVA real.
    con_oc["oc_saldo"] = con_oc["oc_importe_sin_iva"]

    return con_oc[_COLUMNAS_OC]


def armar_tabla(recibos_6m: pd.DataFrame, referencias: pd.DataFrame, facturas: pd.DataFrame,
                 items_oc: pd.DataFrame, ordenes_compra: pd.DataFrame,
                 ordenes_publicidad: pd.DataFrame) -> pd.DataFrame:
    referencias_ventana = referencias[referencias["numero_recibo"].isin(recibos_6m["numero_recibo"])]
    matcheadas = _matchear_facturas(referencias_ventana, facturas)
    oc_detalle = _oc_por_factura(items_oc, ordenes_compra, ordenes_publicidad)

    tabla = matcheadas.merge(
        recibos_6m[["numero_recibo", "fecha", "cliente"]].rename(
            columns={"fecha": "fecha_recibo", "cliente": "cliente_recibo"}
        ),
        on="numero_recibo", how="left",
    )
    tabla = tabla.merge(
        oc_detalle, left_on=["numero_referencia", "tipo_asiento"],
        right_on=["numero_referencia", "tipo_asiento_inferido"], how="left",
        suffixes=("", "_oc"),
    )
    tabla["monto_aplicado"] = tabla["aplicar"].abs()
    tabla["proveedor"] = tabla["proveedor"].fillna("(sin OC vinculada)")
    tabla["oc_origen"] = tabla["oc_origen"].fillna("")
    return tabla


def main():
    recibos, referencias, facturas, items_oc, ordenes_compra, ordenes_publicidad = cargar_datos()
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

    tabla = armar_tabla(recibos_6m, referencias, facturas, items_oc, ordenes_compra, ordenes_publicidad)
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
    tabla["_dup_referencia"] = tabla.duplicated(subset=["numero_recibo", "numero_referencia"], keep="first")
    tabla["monto_cobrado_unico"] = tabla["monto_aplicado"].where(~tabla["_dup_referencia"], 0.0)

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
        "fecha_recibo", "numero_recibo", "cliente_recibo", "numero_referencia",
        "monto_aplicado", "monto_cobrado_unico", "numero_oc", "proveedor",
        "oc_saldo", "oc_estado",
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
        "tables": [
            {
                "mount": "tabla-detalle",
                "mode": "grouped",
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
                    {"key": "_cant_proveedores", "field": "proveedor", "op": "nunique", "filter": {"field": "tiene_oc", "equals": 1}},
                    {"key": "_saldo_oc", "field": "oc_saldo", "op": "sum_unique", "dedupeField": "numero_oc", "filter": {"field": "tiene_oc", "equals": 1}},
                ],
                "groupColumns": [
                    ["fecha_recibo", "Fecha Recibo"], ["numero_recibo", "N° Recibo"],
                    ["cliente_recibo", "Cliente"], ["_cant_facturas", "Facturas"],
                    ["_total_cobrado", "Total Cobrado"], ["_cant_proveedores", "Proveedores"],
                    ["_saldo_oc", "Saldo a Pagar"],
                ],
                "groupNumericCols": ["_total_cobrado", "_saldo_oc"],
                "detailColumns": [
                    ["numero_referencia", "N° Factura"], ["monto_aplicado", "Monto Cobrado"],
                    ["numero_oc", "N° OC/OP"], ["proveedor", "Proveedor"],
                    ["oc_saldo", "Saldo a Pagar"],
                    ["oc_estado", "Estado OC"], ["oc_origen", "Origen OC"], ["ambiguo_txt", "Aviso"],
                ],
                "detailNumericCols": ["monto_aplicado", "oc_saldo"],
                "sort": {"key": "fecha_recibo", "dir": "desc"},
            },
        ],
    }

    secciones = "".join([
        hr.filter_bar_html(),
        hr.category_filters_html(CATEGORY_FILTERS),
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
