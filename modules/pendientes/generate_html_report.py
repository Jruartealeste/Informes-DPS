"""
Genera el informe HTML de "Pendientes": ordenes de trabajo abiertas con el
detalle de sus Estimados de Costo y Ordenes de Compra (Produccion)
asociadas, para poder revisar de un vistazo que contiene cada OT abierta y
por que sigue abierta.

A diferencia de los demas informe_*.html, este no ingesta su propia tabla:
cruza seis tablas ya cargadas por otros modulos:
  - ordenes_trabajo   (modules/ordenes_trabajo, filtrado a estado='Abierta')
  - estimados_costos  (modules/estimados_costos, vinculado por numero_ot)
  - ordenes_compra_produccion (modules/ordenes_compra, vinculado por
    numero_estimado, que a su vez cuelga de estimados_costos)
  - oc_pendientes_generar (modules/oc_pendientes_generar, vista propia de
    Advertys con items que tienen Proveedor cargado pero sin OC emitida --
    OJO, ver items_pendientes_oc abajo: esta vista es mas angosta de lo
    que parece)
  - estimados_pendientes_facturar (modules/estimados_pendientes_facturar,
    vista propia de Advertys con estimados que todavia tienen saldo
    pendiente de facturar)
  - items_pendientes_oc (modules/ordenes_trabajo/crawl_items_pendientes.py,
    crawl item-por-item de la pestana "Items del Estimado" para los
    estimados NO terminales de OT abiertas -- confirmado con Javier
    2026-07-21 que oc_pendientes_generar solo cubre casos en un estado
    YA avanzado, y se pierde items recien asignados a un proveedor o
    incluso items tercerizados que todavia ni tienen proveedor. Esta
    tabla NO se llena con un ingest.py de Excel: se llena corriendo
    `python -m modules.ordenes_trabajo.crawl_items_pendientes` (tarda
    unos minutos, navega Advertys en vivo estimado por estimado).

Por eso antes de correr esto conviene tener actualizado:
    python -m modules.ordenes_trabajo.ingest <export ultimo>
    python -m modules.estimados_costos.ingest <export ultimo>
    python -m modules.ordenes_compra.ingest <export ultimo>
    python -m modules.oc_pendientes_generar.ingest <export ultimo>
    python -m modules.estimados_pendientes_facturar.ingest <export ultimo>
    python -m modules.ordenes_trabajo.crawl_items_pendientes

Es un informe estatico (sin el filtro de periodo dinamico de los otros
modulos): "pendientes" es una foto del estado actual, no algo que tenga
sentido recortar por rango de fechas.

Uso:
    python -m modules.pendientes.generate_html_report
"""
from html import escape

import pandas as pd

import db
import html_report as hr

REPORT_HTML_OUTPUT_PATH = "informes/informe_pendientes.html"


def _fmt_money(v: float) -> str:
    return f"$ {v:,.0f}".replace(",", ".")

ESTADO_ESTIMADO_COLOR = {
    "Provisorio": hr.STATUS["warning"],
    "Definitivo": hr.STATUS["good"],
    "Autorizado AFacturar": hr.STATUS["good"],
    "Facturado total": hr.STATUS["good"],
    "Facturado manual": hr.STATUS["good"],
    "Finalizado": hr.STATUS["good"],
    "Anulado": hr.STATUS["critical"],
    "Rechazado": hr.STATUS["critical"],
}

# Semaforo "lista para cerrar" (confirmado con Javier 2026-07-20):
#   - Estimado en uno de estos estados ya no requiere seguimiento (terminal).
#   - OC en uno de estos estados ya no representa un compromiso pendiente.
# Si la OT no tiene NINGUN estimado cargado, no se puede evaluar -> critico
# (mismo caso que el badge "Sin estimados" que ya existia en esta tabla).
ESTIMADO_ESTADOS_TERMINALES = {
    "Finalizado", "Anulado", "Facturado total", "Facturado manual", "Rechazado",
}
OC_ESTADOS_RESUELTOS = {"Utilizada", "Anulada"}

# Regla de negocio confirmada por Javier (2026-07-21), mas precisa que el
# check generico de arriba: un Estimado de Costos NO se puede Finalizar (y
# por lo tanto la OT que cuelga de el queda "bloqueada" para cerrar) si:
#   a) tiene algun item con Proveedor cargado pero sin O.C. emitida
#      (modules/oc_pendientes_generar -- vista propia de Advertys), o
#   b) todavia tiene saldo pendiente de facturar
#      (modules/estimados_pendientes_facturar -- idem).
# A diferencia del check generico basado en ESTIMADO_ESTADOS_TERMINALES/
# OC_ESTADOS_RESUELTOS (una aproximacion nuestra), estas dos vistas son
# calculadas por el propio Advertys, asi que son la fuente mas confiable
# para decidir el amarillo especifico "bloqueada para cerrar".
SEMAFORO_COLOR = {
    "good": hr.STATUS["good"],
    "warning": hr.STATUS["warning"],
    "critical": hr.STATUS["critical"],
}
SEMAFORO_LABEL = {
    "good": "Lista para cerrar",
    "warning": "En curso",
    "critical": "Sin estimados cargados",
}

DETALLE_CSS = """
table.ot-table tbody tr.ot-row { cursor: pointer; }
table.ot-table tbody tr.ot-row:hover { background: var(--page-plane); }
table.ot-table tbody tr.ot-row td:first-child { width: 22px; text-align: center; }
table.ot-table tbody tr.ot-row td:nth-child(2) { position: relative; padding-left: 22px; }
table.ot-table tbody tr.ot-row td:nth-child(2)::before {
  content: "\\25B8";
  position: absolute;
  left: 6px;
  color: var(--text-muted);
  display: inline-block;
  transition: transform 0.1s ease;
}
table.ot-table tbody tr.ot-row.open td:nth-child(2)::before { transform: rotate(90deg); }
table.ot-table tbody tr.ot-row.row-alerta { background: rgba(208,59,59,0.06); }
.semaforo-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
table.ot-table tbody tr.ot-detail-row { display: none; }
table.ot-table tbody tr.ot-detail-row.open { display: table-row; }
table.ot-table tbody tr.ot-detail-row > td { padding: 0; background: var(--page-plane); }
table.ot-table tbody tr.ot-detail-row .ot-detail-body { padding: 16px 20px 20px 28px; }
table.ot-table tbody tr.ot-detail-row .ot-detail-body table.report-table { margin-bottom: 4px; }
table.ot-table tbody tr.ot-detail-row h3 {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin: 18px 0 8px;
}
table.ot-table tbody tr.ot-detail-row h3:first-child { margin-top: 0; }
table.ot-table tbody tr.ot-detail-row p.empty {
  color: var(--text-muted);
  font-size: 13px;
  margin: 0 0 4px;
}
.badge-alerta {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  background: rgba(208,59,59,0.12);
  color: #d03b3b;
  margin-left: 6px;
}
.badge-bloqueada {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  background: rgba(212,160,23,0.15);
  color: #9a7d1a;
  margin-left: 6px;
}
/* Caja "Bloquea el cierre": agrupa Items pendientes de O.C./Proveedor y
   Pendiente de facturar, separada visualmente de Estimados de costo /
   Ordenes de compra (que muestran el CONTENIDO de la OT, no una alerta). */
.bloqueo-box {
  margin: 18px 0 4px;
  padding: 4px 16px 16px;
  border: 1px solid rgba(212,160,23,0.35);
  border-left: 3px solid #d4a017;
  border-radius: 6px;
  background: rgba(212,160,23,0.07);
}
.bloqueo-box .bloqueo-title {
  margin: 14px 0 2px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #9a7d1a;
}
.bloqueo-box h3 {
  color: #9a7d1a !important;
  margin: 14px 0 8px !important;
}
.bloqueo-box table.report-table td, .bloqueo-box table.report-table th {
  background: transparent;
}
@media print {
  table.ot-table tbody tr.ot-detail-row { display: table-row !important; }
  table.ot-table tbody tr.ot-row td:first-child::before { display: none; }
}
.semaforo-filter-bar .semaforo-filter-label { color: var(--text-secondary); margin-right: 2px; }
.semaforo-chip { display: inline-flex; align-items: center; gap: 6px; }
.filter-bar button.semaforo-chip.active {
  background: var(--brand); border-color: var(--brand); color: #fff;
}
.semaforo-chip.active .semaforo-dot { box-shadow: 0 0 0 2px rgba(255,255,255,0.7); }
table.ot-table tbody tr.filtered-hidden { display: none !important; }
@media print {
  .semaforo-filter-bar { display: none !important; }
}
"""

DETALLE_JS = """
function otFilterToggle(btn) {
  btn.classList.toggle('active');
  otFilterApply();
}
function otFilterClear() {
  Array.prototype.forEach.call(document.querySelectorAll('.semaforo-chip.active'), function (b) {
    b.classList.remove('active');
  });
  otFilterApply();
}
function otFilterApply() {
  var active = Array.prototype.map.call(document.querySelectorAll('.semaforo-chip.active'), function (b) {
    return b.dataset.value;
  });
  var rows = document.querySelectorAll('table.ot-table tbody tr.ot-row');
  var visible = 0;
  Array.prototype.forEach.call(rows, function (row) {
    var show = active.length === 0 || active.indexOf(row.dataset.semaforo) !== -1;
    row.classList.toggle('filtered-hidden', !show);
    var detail = row.nextElementSibling;
    if (detail && detail.classList.contains('ot-detail-row')) {
      detail.classList.toggle('filtered-hidden', !show);
      if (!show) {
        row.classList.remove('open');
        detail.classList.remove('open');
      }
    }
    if (show) { visible++; }
  });
  var counter = document.getElementById('semaforo-filter-count');
  if (counter) { counter.textContent = visible + ' de ' + rows.length + ' OT'; }
}
"""


def _leer_tabla_opcional(conn, tabla, columnas):
    """Lee una tabla si existe; si todavia no se corrio su ingest, devuelve
    un DataFrame vacio con las columnas esperadas en vez de romper (permite
    seguir usando este informe con las 3 tablas viejas mientras se suman
    oc_pendientes_generar/estimados_pendientes_facturar por primera vez)."""
    try:
        return pd.read_sql_query(f"SELECT * FROM {tabla}", conn)
    except Exception:
        return pd.DataFrame(columns=columnas)


def cargar_datos():
    with db.get_connection() as conn:
        ot = pd.read_sql_query(
            "SELECT * FROM ordenes_trabajo WHERE estado = 'Abierta'", conn
        )
        estimados = pd.read_sql_query("SELECT * FROM estimados_costos", conn)
        oc = pd.read_sql_query("SELECT * FROM ordenes_compra_produccion", conn)
        oc_pendientes = _leer_tabla_opcional(
            conn, "oc_pendientes_generar",
            ["numero_estimado", "detalle", "rubro_produccion", "proveedor", "costo", "estado"],
        )
        estimados_pend_facturar = _leer_tabla_opcional(
            conn, "estimados_pendientes_facturar",
            ["numero_estimado", "numero_ot", "pendiente_facturar", "estado"],
        )
        items_crawl = _leer_tabla_opcional(
            conn, "items_pendientes_oc",
            ["numero_ot", "numero_estimado", "detalle", "proveedor", "costo", "numero_oc", "motivo"],
        )
    if not ot.empty:
        ot["fecha_abierta"] = pd.to_datetime(ot["fecha_abierta"], errors="coerce")
    return ot, estimados, oc, oc_pendientes, estimados_pend_facturar, items_crawl


def _combinar_items_pendientes(oc_pendientes: pd.DataFrame, items_crawl: pd.DataFrame) -> pd.DataFrame:
    """Unifica las dos fuentes de 'item que todavia bloquea Finalizar el
    estimado por el lado de Proveedor/O.C.':
      - items_crawl: modules/ordenes_trabajo/crawl_items_pendientes.py,
        recorrido item-por-item de "Items del Estimado" para estimados NO
        terminales de OT abiertas -- mas temprano (agarra "sin_oc" y
        "sin_proveedor"), pero solo cubre esas OT/estimados.
      - oc_pendientes: vista propia de Advertys "OCs Pendientes de
        Generar" -- mas angosta (confirmado con Javier 2026-07-21: solo
        expone casos en un estado ya avanzado) pero cubre TODO el sistema,
        no solo lo que se llego a crawlear.
    Dedup por (numero_estimado, detalle) para no contar dos veces el mismo
    item si aparece en ambas fuentes.
    """
    filas = []
    if not items_crawl.empty:
        for r in items_crawl.to_dict(orient="records"):
            filas.append({
                "numero_estimado": r.get("numero_estimado"),
                "detalle": r.get("detalle") or "",
                "proveedor": r.get("proveedor") or "",
                "costo": r.get("costo") or 0.0,
                "motivo": r.get("motivo") or "sin_oc",
                "fuente": "crawl",
            })
    if not oc_pendientes.empty:
        vistos = {(f["numero_estimado"], f["detalle"]) for f in filas}
        for r in oc_pendientes.to_dict(orient="records"):
            clave = (r.get("numero_estimado"), r.get("detalle") or "")
            if clave in vistos:
                continue
            filas.append({
                "numero_estimado": r.get("numero_estimado"),
                "detalle": r.get("detalle") or "",
                "proveedor": r.get("proveedor") or "",
                "costo": r.get("costo") or 0.0,
                "motivo": "sin_oc",
                "fuente": "sistema",
            })
    return pd.DataFrame(filas, columns=["numero_estimado", "detalle", "proveedor", "costo", "motivo", "fuente"])


MOTIVO_LABEL = {
    "sin_oc": "sin O.C. emitida",
    "sin_proveedor": "tercerizado sin proveedor asignado",
}


def _resumen_por_ot(
    ot: pd.DataFrame,
    estimados: pd.DataFrame,
    oc: pd.DataFrame,
    items_pendientes: pd.DataFrame,
    estimados_pend_facturar: pd.DataFrame,
) -> pd.DataFrame:
    est_por_ot = estimados.groupby("numero_ot").agg(
        cant_estimados=("numero_estimado", "count"),
        sub_total_estimado=("sub_total", "sum"),
        total_comprado_estimado=("total_comprado", "sum"),
        estados_estimados=("estado", lambda s: ", ".join(sorted(set(s)))),
        estimados_ok=("estado", lambda s: set(s) <= ESTIMADO_ESTADOS_TERMINALES),
    )

    # Ordenes de compra de una OT = las de todos los estimados que cuelgan de esa OT.
    oc_con_ot = oc.merge(
        estimados[["numero_estimado", "numero_ot"]], on="numero_estimado", how="inner"
    )
    oc_por_ot = oc_con_ot.groupby("numero_ot").agg(
        cant_oc=("numero_oc", "count"),
        total_oc=("importe_sin_iva", "sum"),
        oc_ok=("estado", lambda s: set(s) <= OC_ESTADOS_RESUELTOS),
    )
    # OC que NO estan en un estado resuelto (Utilizada/Anulada) y todavia
    # tienen saldo > 0: compromiso con el proveedor sin cerrar, aunque el
    # Estimado ya este en estado terminal (ej. OT 278: estimado "Facturado
    # manual" pero OC #198 a SADAIC en "Autorizada" con $677.000 de saldo --
    # confirmado con Javier 2026-07-21 que esto tambien debe bloquear el
    # cierre, no solo quedar en amarillo "En curso" sin explicacion).
    oc_pend_mask = ~oc_con_ot["estado"].isin(OC_ESTADOS_RESUELTOS) & (oc_con_ot["saldo"] > 0)
    oc_saldo_pend_por_ot = (
        oc_con_ot[oc_pend_mask]
        .groupby("numero_ot")
        .agg(
            saldo_oc_pendiente=("saldo", "sum"),
            cant_oc_pendiente=("numero_oc", "count"),
        )
    )

    # Items pendientes de O.C./Proveedor (crawl item-level + vista propia
    # de Advertys, unificados en items_pendientes -- ver _combinar_items_pendientes), por OT.
    if not items_pendientes.empty:
        items_pend_con_ot = items_pendientes.merge(
            estimados[["numero_estimado", "numero_ot"]], on="numero_estimado", how="inner"
        )
        items_sin_oc_por_ot = items_pend_con_ot.groupby("numero_ot").agg(
            cant_items_sin_oc=("numero_estimado", "count"),
        )
    else:
        items_sin_oc_por_ot = pd.DataFrame(columns=["cant_items_sin_oc"])

    # Estimados con saldo pendiente de facturar (vista propia de Advertys), por OT.
    if not estimados_pend_facturar.empty:
        pend_facturar_por_ot = estimados_pend_facturar.groupby("numero_ot").agg(
            monto_pendiente_facturar=("pendiente_facturar", "sum"),
            cant_estimados_pend_facturar=("numero_estimado", "count"),
        )
    else:
        pend_facturar_por_ot = pd.DataFrame(columns=["monto_pendiente_facturar", "cant_estimados_pend_facturar"])

    resumen = (
        ot.set_index("numero_ot")
        .join(est_por_ot, how="left")
        .join(oc_por_ot, how="left")
        .join(items_sin_oc_por_ot, how="left")
        .join(pend_facturar_por_ot, how="left")
        .join(oc_saldo_pend_por_ot, how="left")
    )
    resumen["cant_estimados"] = resumen["cant_estimados"].fillna(0).astype(int)
    resumen["cant_items_sin_oc"] = resumen["cant_items_sin_oc"].fillna(0).astype(int)
    resumen["cant_estimados_pend_facturar"] = resumen["cant_estimados_pend_facturar"].fillna(0).astype(int)
    resumen["monto_pendiente_facturar"] = resumen["monto_pendiente_facturar"].fillna(0.0)
    resumen["cant_oc"] = resumen["cant_oc"].fillna(0).astype(int)
    resumen["cant_oc_pendiente"] = resumen["cant_oc_pendiente"].fillna(0).astype(int)
    resumen["saldo_oc_pendiente"] = resumen["saldo_oc_pendiente"].fillna(0.0)
    for col in ("sub_total_estimado", "total_comprado_estimado", "total_oc"):
        resumen[col] = resumen[col].fillna(0.0)
    resumen["estados_estimados"] = resumen["estados_estimados"].fillna("")
    # Sin estimados -> no evaluable (critico). Sin OC -> no hay compromiso
    # pendiente, no bloquea el verde (vacuamente resuelto).
    resumen["estimados_ok"] = resumen["estimados_ok"].fillna(False)
    resumen["oc_ok"] = resumen["oc_ok"].fillna(True)

    def _bloqueada(fila):
        return (
            fila["cant_items_sin_oc"] > 0
            or fila["monto_pendiente_facturar"] > 0
            or fila["saldo_oc_pendiente"] > 0
        )

    def _semaforo(fila):
        if fila["cant_estimados"] == 0:
            return "critical"
        if _bloqueada(fila):
            return "warning"
        if fila["estimados_ok"] and fila["oc_ok"]:
            return "good"
        return "warning"

    def _motivo_bloqueo(fila):
        if not _bloqueada(fila):
            return ""
        motivos = []
        if fila["cant_items_sin_oc"] > 0:
            motivos.append(f"{fila['cant_items_sin_oc']} item(s) con proveedor sin O.C. emitida")
        if fila["monto_pendiente_facturar"] > 0:
            motivos.append(f"pendiente de facturar {_fmt_money(fila['monto_pendiente_facturar'])}")
        if fila["saldo_oc_pendiente"] > 0:
            motivos.append(
                f"{fila['cant_oc_pendiente']} O.C. sin resolver con saldo "
                f"{_fmt_money(fila['saldo_oc_pendiente'])}"
            )
        return "; ".join(motivos)

    resumen["semaforo"] = resumen.apply(_semaforo, axis=1)
    resumen["motivo_bloqueo"] = resumen.apply(_motivo_bloqueo, axis=1)
    return resumen.reset_index()


def _tabla_estimados(numero_ot: str, estimados: pd.DataFrame) -> str:
    filas = estimados[estimados["numero_ot"] == numero_ot].sort_values(
        "numero_estimado", ascending=False
    )
    if filas.empty:
        return '<p class="empty">Sin estimados de costo cargados en Advertys para esta OT.</p>'
    return hr.data_table(
        [
            ("numero_estimado", "N° Est."),
            ("titulo", "Título"),
            ("estado", "Estado"),
            ("sub_total", "Sub Total"),
            ("total_comprado", "Comprado"),
            ("total_facturado", "Facturado"),
            ("total_ordenado", "Ordenado"),
        ],
        filas.to_dict(orient="records"),
        numeric_cols=("sub_total", "total_comprado", "total_facturado", "total_ordenado"),
    )


def _tabla_oc(numero_ot: str, estimados: pd.DataFrame, oc: pd.DataFrame) -> str:
    nums_estimado = set(estimados.loc[estimados["numero_ot"] == numero_ot, "numero_estimado"])
    filas = oc[oc["numero_estimado"].isin(nums_estimado)].sort_values("numero_oc", ascending=False)
    if filas.empty:
        return '<p class="empty">Sin ordenes de compra generadas para los estimados de esta OT.</p>'
    return hr.data_table(
        [
            ("numero_oc", "N° O.C."),
            ("proveedor", "Proveedor"),
            ("detalle", "Detalle"),
            ("estado", "Estado"),
            ("importe_sin_iva", "Importe"),
            ("saldo", "Saldo"),
        ],
        filas.to_dict(orient="records"),
        numeric_cols=("importe_sin_iva", "saldo"),
    )


def _tabla_items_sin_oc(numero_ot: str, estimados: pd.DataFrame, items_pendientes: pd.DataFrame) -> str:
    if items_pendientes.empty:
        return ""
    nums_estimado = set(estimados.loc[estimados["numero_ot"] == numero_ot, "numero_estimado"])
    filas = items_pendientes[items_pendientes["numero_estimado"].isin(nums_estimado)].sort_values("numero_estimado").copy()
    if filas.empty:
        return ""
    filas["motivo_label"] = filas["motivo"].map(MOTIVO_LABEL).fillna(filas["motivo"])
    tabla = hr.data_table(
        [
            ("numero_estimado", "N° Est."),
            ("detalle", "Detalle"),
            ("proveedor", "Proveedor"),
            ("costo", "Costo"),
            ("motivo_label", "Motivo"),
            ("fuente", "Fuente"),
        ],
        filas.to_dict(orient="records"),
        numeric_cols=("costo",),
    )
    return f'<h3>Items pendientes de O.C./Proveedor</h3>{tabla}'


def _nota_pendiente_facturar(numero_ot: str, estimados_pend_facturar: pd.DataFrame) -> str:
    if estimados_pend_facturar.empty:
        return ""
    filas = estimados_pend_facturar[estimados_pend_facturar["numero_ot"] == numero_ot]
    if filas.empty:
        return ""
    detalle = ", ".join(
        f"Est. {r['numero_estimado']} ({_fmt_money(r['pendiente_facturar'])})"
        for r in filas.sort_values("numero_estimado").to_dict(orient="records")
    )
    return (
        '<h3>Pendiente de facturar</h3>'
        f'<p class="empty">{escape(detalle)}</p>'
    )


def _nota_oc_pendiente(numero_ot: str, estimados: pd.DataFrame, oc: pd.DataFrame) -> str:
    """OC que cuelgan de esta OT y no estan en un estado resuelto
    (Utilizada/Anulada) con saldo > 0 -- compromiso con el proveedor sin
    cerrar aunque el Estimado ya este terminal (ver OT 278: estimado
    "Facturado manual" pero OC #198 en "Autorizada" con saldo pendiente)."""
    if oc.empty:
        return ""
    nums_estimado = set(estimados.loc[estimados["numero_ot"] == numero_ot, "numero_estimado"])
    filas = oc[
        oc["numero_estimado"].isin(nums_estimado)
        & ~oc["estado"].isin(OC_ESTADOS_RESUELTOS)
        & (oc["saldo"] > 0)
    ]
    if filas.empty:
        return ""
    detalle = ", ".join(
        f"O.C. {r['numero_oc']} - {r['proveedor']} ({r['estado']}, saldo {_fmt_money(r['saldo'])})"
        for r in filas.sort_values("numero_oc").to_dict(orient="records")
    )
    return (
        '<h3>O.C. sin resolver con saldo pendiente</h3>'
        f'<p class="empty">{escape(detalle)}</p>'
    )


def _bloqueo_cierre_html(
    numero_ot: str,
    estimados: pd.DataFrame,
    oc: pd.DataFrame,
    items_pendientes: pd.DataFrame,
    estimados_pend_facturar: pd.DataFrame,
) -> str:
    """Agrupa las causas que bloquean el cierre de la OT (items sin O.C.,
    saldo pendiente de facturar, O.C. sin resolver con saldo) en una unica
    caja resaltada, separada de Estimados de costo / Ordenes de compra: esas
    dos muestran el CONTENIDO de la OT, esta caja muestra ALERTAS que
    bloquean el cierre."""
    items_html = _tabla_items_sin_oc(numero_ot, estimados, items_pendientes)
    facturar_html = _nota_pendiente_facturar(numero_ot, estimados_pend_facturar)
    oc_html = _nota_oc_pendiente(numero_ot, estimados, oc)
    if not items_html and not facturar_html and not oc_html:
        return ""
    return (
        '<div class="bloqueo-box"><p class="bloqueo-title">Bloquea el cierre</p>'
        f'{items_html}{facturar_html}{oc_html}</div>'
    )


OT_TABLE_COLUMNAS = [
    ("semaforo", ""),
    ("numero_ot", "N° OT"),
    ("resumen", "Resumen"),
    ("anunciante", "Anunciante"),
    ("responsable", "Responsable"),
    ("fecha_abierta", "Fecha apertura"),
    ("cant_estimados", "Estimados"),
    ("estados_estimados", "Estado(s) estimado"),
    ("cant_oc", "OC"),
    ("total_oc", "Total OC"),
    ("renta_teorica", "Renta teórica"),
]
OT_TABLE_NUM_COLS = ("total_oc", "renta_teorica")

# Toggle sin JS externo: la fila resumen y su fila de detalle son hermanas
# directas en el tbody, asi que alcanza con alternar 'open' en ambas.
_ROW_TOGGLE_JS = "this.classList.toggle('open'); this.nextElementSibling.classList.toggle('open')"


def _fila_tabla_ot(
    fila: dict,
    estimados: pd.DataFrame,
    oc: pd.DataFrame,
    items_pendientes: pd.DataFrame,
    estimados_pend_facturar: pd.DataFrame,
) -> str:
    numero_ot = fila["numero_ot"]
    sin_estimados = fila["cant_estimados"] == 0
    bloqueada = bool(fila.get("motivo_bloqueo"))
    row_class = "ot-row row-alerta" if sin_estimados else "ot-row"
    alerta = '<span class="badge-alerta">Sin estimados</span>' if sin_estimados else ""
    badge_bloqueo = (
        f'<span class="badge-bloqueada" title="{escape(fila["motivo_bloqueo"])}">Bloqueada</span>'
        if bloqueada else ""
    )
    fecha_abierta = fila.get("fecha_abierta")
    fecha_str = fecha_abierta.strftime("%Y-%m-%d") if pd.notna(fecha_abierta) else "-"
    renta_teorica = fila.get("renta_teorica")
    renta_str = f"{renta_teorica:.1f}%" if pd.notna(renta_teorica) else "-"
    resumen_txt = fila.get("resumen") or "(sin resumen)"
    semaforo = fila.get("semaforo", "warning")
    titulo_semaforo = fila["motivo_bloqueo"] if bloqueada else SEMAFORO_LABEL[semaforo]
    semaforo_dot = (
        f'<span class="semaforo-dot" style="background:{SEMAFORO_COLOR[semaforo]}" '
        f'title="{escape(titulo_semaforo)}"></span>'
    )

    fila_resumen = f"""<tr class="{row_class}" data-semaforo="{semaforo}" onclick="{_ROW_TOGGLE_JS}">
      <td>{semaforo_dot}</td>
      <td>{escape(str(numero_ot))}</td>
      <td>{escape(str(resumen_txt))}{alerta}{badge_bloqueo}</td>
      <td>{escape(str(fila.get("anunciante") or ""))}</td>
      <td>{escape(str(fila.get("responsable") or ""))}</td>
      <td>{fecha_str}</td>
      <td>{fila["cant_estimados"]}</td>
      <td>{escape(str(fila.get("estados_estimados") or ""))}</td>
      <td>{fila["cant_oc"]}</td>
      <td class="num">{escape(_fmt_money(fila["total_oc"]))}</td>
      <td class="num">{escape(renta_str)}</td>
    </tr>"""
    fila_detalle = f"""<tr class="ot-detail-row">
      <td colspan="{len(OT_TABLE_COLUMNAS)}">
        <div class="ot-detail-body">
          <h3>Estimados de costo</h3>
          {_tabla_estimados(numero_ot, estimados)}
          <h3>Ordenes de compra</h3>
          {_tabla_oc(numero_ot, estimados, oc)}
          {_bloqueo_cierre_html(numero_ot, estimados, oc, items_pendientes, estimados_pend_facturar)}
        </div>
      </td>
    </tr>"""
    return fila_resumen + fila_detalle


def _semaforo_filter_bar_html(counts: dict, total: int) -> str:
    chips = "".join(
        f'<button type="button" class="semaforo-chip" data-value="{clave}" onclick="otFilterToggle(this)">'
        f'<span class="semaforo-dot" style="background:{SEMAFORO_COLOR[clave]}"></span>'
        f'{escape(SEMAFORO_LABEL[clave])} ({counts.get(clave, 0)})</button>'
        for clave in ("good", "warning", "critical")
    )
    return f"""<div class="filter-bar semaforo-filter-bar">
    <div class="filter-controls no-print">
      <span class="semaforo-filter-label">Filtrar por semáforo:</span>
      {chips}
      <button type="button" onclick="otFilterClear()">Ver todas</button>
    </div>
    <div class="filter-coverage" id="semaforo-filter-count">{total} de {total} OT</div>
  </div>"""


def _tabla_ot_html(
    resumen_ordenado: pd.DataFrame,
    estimados: pd.DataFrame,
    oc: pd.DataFrame,
    items_pendientes: pd.DataFrame,
    estimados_pend_facturar: pd.DataFrame,
) -> str:
    thead = "".join(
        f'<th class="{"num" if clave in OT_TABLE_NUM_COLS else ""}">{escape(titulo)}</th>'
        for clave, titulo in OT_TABLE_COLUMNAS
    )
    filas_html = "".join(
        _fila_tabla_ot(fila, estimados, oc, items_pendientes, estimados_pend_facturar)
        for fila in resumen_ordenado.to_dict(orient="records")
    )
    return f"""<table class="report-table ot-table">
    <thead><tr>{thead}</tr></thead>
    <tbody>{filas_html}</tbody>
  </table>"""


def main():
    ot, estimados, oc, oc_pendientes, estimados_pend_facturar, items_crawl = cargar_datos()
    if ot.empty:
        print("No hay ordenes de trabajo abiertas en la base (o no corriste el ingest de ordenes_trabajo todavia).")
        return

    items_pendientes = _combinar_items_pendientes(oc_pendientes, items_crawl)
    resumen = _resumen_por_ot(ot, estimados, oc, items_pendientes, estimados_pend_facturar)
    resumen_ordenado = resumen.sort_values("fecha_abierta", ascending=False)

    cant_ot = len(resumen)
    cant_sin_estimados = int((resumen["cant_estimados"] == 0).sum())
    cant_listas = int((resumen["semaforo"] == "good").sum())
    cant_bloqueadas = int((resumen["motivo_bloqueo"] != "").sum())
    # renta_teorica/renta_real son porcentajes de rentabilidad (ej. 49.51),
    # no montos -- confirmado contra Advertys real (rango 0-158, ver
    # modules/ordenes_trabajo/config.py). Formatear con "%", nunca con
    # _fmt_money como se hizo por error en una version anterior de este
    # informe.
    renta_teorica_promedio = float(resumen["renta_teorica"].fillna(0).mean()) if cant_ot else 0.0
    total_comprometido_oc = float(resumen["total_oc"].sum())

    tiles = hr.stat_tiles([
        ("OT abiertas", str(cant_ot)),
        ("Listas para cerrar", str(cant_listas), "estimados y OC ya resueltos"),
        ("Bloqueadas para cierre", str(cant_bloqueadas), "item sin O.C. y/o saldo pendiente de facturar"),
        ("Sin estimados cargados", str(cant_sin_estimados), "revisar por que siguen abiertas"),
        ("Renta teórica promedio", f"{renta_teorica_promedio:.1f}%"),
        ("Comprometido en órdenes de compra", _fmt_money(total_comprometido_oc)),
    ])

    semaforo_counts = resumen["semaforo"].value_counts().to_dict()
    filtro_html = _semaforo_filter_bar_html(semaforo_counts, cant_ot)
    tabla_ot_html = _tabla_ot_html(resumen_ordenado, estimados, oc, items_pendientes, estimados_pend_facturar)

    secciones = "".join([
        tiles,
        hr.section(
            "Detalle por OT abiertas (estimados de costo + órdenes de compra)",
            filtro_html + tabla_ot_html,
            wide=True,
        ),
    ])

    html = hr.page_shell("Pendientes", "ALESTE ADS S.A. - Advertys", secciones)
    html = html.replace("</style>", DETALLE_CSS + "</style>")
    html = html.replace("</body>", f"<script>{DETALLE_JS}</script></body>")

    with open(REPORT_HTML_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK: informe generado en {REPORT_HTML_OUTPUT_PATH}")
    print(f"  {cant_ot} OT abiertas, {cant_sin_estimados} sin estimados cargados, {cant_bloqueadas} bloqueadas para cierre.")


if __name__ == "__main__":
    main()
