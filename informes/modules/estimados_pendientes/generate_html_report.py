"""
Genera el informe HTML de "Estimados Pendientes": todos los Estimados de
Costo que todavia NO llegaron a un estado final (Finalizado/Anulado/
Rechazado), con independencia de si su Orden de Trabajo esta abierta o
cerrada -- a diferencia de Pendientes (que es por OT abierta y agrupa el
detalle de sus estimados adentro), esta pestana es ESTIMADO-centrica: una
fila por estimado, pensada para ver de un vistazo cuales ya estan en
condiciones de pasar a `Finalizado` en Advertys.

Regla de "Listo para Finalizado" (confirmada con Javier 2026-09-09), la
misma que ya calcula _resumen_por_estimado() en
modules/pendientes/generate_html_report.py (reusada de aca, no reimplementada)
pero aplicada a UN estimado puntual, sin exigir que el resto de la OT tambien
este resuelto:
  - el estimado ya esta facturado -- no aparece en la vista de Advertys
    "Estim.Pendientes Facturar" (sin saldo pendiente de facturar), Y
  - ningun item con Proveedor cargado le falta O.C. emitida, Y
  - sus O.C. estan todas resueltas -- Utilizada o Anulada (confirmado con
    Javier 2026-09-09 que a los fines practicos de este semaforo son
    equivalentes: "cambia el estado del estimado" en ambos casos), sin
    saldo pendiente con el proveedor.

OJO: "Facturado total"/"Facturado manual" NO se tratan como estado final
aca -- a diferencia de ESTIMADO_ESTADOS_TERMINALES en Pendientes (que los
trata como terminales a los fines de si la OT puede cerrarse), en este
informe son justamente los estados que interesa detectar: ya facturados,
todavia sin el click explicito a Finalizado en Advertys. Ver
modules/ordenes_trabajo/cerrar_ot.finalizar_estimado(), que solo saltea el
estimado si el estado actual contiene "Finalizado" o "Anulado" -- confirma
que "Facturado ..." sigue requiriendo la transicion.

No ingesta tabla propia: cruza estimados_costos + ordenes_compra_produccion
+ oc_pendientes_generar + estimados_pendientes_facturar + items_pendientes_oc
(mismas 5 tablas que consume Pendientes) + ordenes_trabajo (solo para dar
contexto de si la OT esta abierta/cerrada, y detectar el caso confirmado por
Javier de un estimado no-terminal colgando de una OT ya cerrada).

Es un informe estatico (sin filtro de periodo dinamico), igual que
Pendientes: es una foto del estado actual, no algo que tenga sentido
recortar por rango de fechas.

Uso:
    python -m modules.estimados_pendientes.generate_html_report
"""
from html import escape

import pandas as pd

import db
import html_report as hr
from modules.pendientes.generate_html_report import (
    MOTIVO_LABEL,
    _combinar_items_pendientes,
    _leer_tabla_opcional,
    _resumen_por_estimado,
)

REPORT_HTML_OUTPUT_PATH = "salida/informe_estimados_pendientes.html"


def _fmt_money(v: float) -> str:
    return f"$ {v:,.0f}".replace(",", ".")


# Estados en los que un estimado ya no requiere ninguna accion. Distinto de
# ESTIMADO_ESTADOS_TERMINALES en Pendientes (ver docstring del modulo).
ESTADOS_SIN_ACCION = {"Finalizado", "Anulado", "Rechazado"}

SEMAFORO_COLOR = {
    "listo": hr.STATUS["good"],
    "bloqueado": hr.STATUS["warning"],
}
SEMAFORO_LABEL = {
    "listo": "Listo para Finalizado",
    "bloqueado": "Bloqueado",
}

# Antiguedad (dias desde fecha_solicita) a partir de la cual un estimado no
# terminal se marca como senal de seguimiento -- mismo espiritu que
# UMBRAL_MUCHOS_ESTIMADOS de Pendientes, pero por tiempo en vez de cantidad.
UMBRAL_DIAS_ANTIGUO = 90

DETALLE_CSS = """
table.est-table tbody tr.est-row { cursor: pointer; }
table.est-table tbody tr.est-row:hover { background: var(--page-plane); }
table.est-table tbody tr.est-row td:first-child { width: 22px; text-align: center; }
table.est-table tbody tr.est-row td:nth-child(2) { position: relative; padding-left: 22px; }
table.est-table tbody tr.est-row td:nth-child(2)::before {
  content: "\\25B8";
  position: absolute;
  left: 6px;
  color: var(--text-muted);
  display: inline-block;
  transition: transform 0.1s ease;
}
table.est-table tbody tr.est-row.open td:nth-child(2)::before { transform: rotate(90deg); }
.semaforo-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
table.est-table tbody tr.est-detail-row { display: none; }
table.est-table tbody tr.est-detail-row.open { display: table-row; }
table.est-table tbody tr.est-detail-row > td { padding: 0; background: var(--page-plane); }
table.est-table tbody tr.est-detail-row .est-detail-body { padding: 16px 20px 20px 28px; }
table.est-table tbody tr.est-detail-row .est-detail-body table.report-table { margin-bottom: 4px; }
table.est-table tbody tr.est-detail-row h3 {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin: 18px 0 8px;
}
table.est-table tbody tr.est-detail-row h3:first-child { margin-top: 0; }
table.est-table tbody tr.est-detail-row p.empty {
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
.badge-info {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  background: rgba(42,120,214,0.12);
  color: #2a78d6;
  margin-left: 6px;
}
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
  table.est-table tbody tr.est-detail-row { display: table-row !important; }
  table.est-table tbody tr.est-row td:first-child::before { display: none; }
}
.semaforo-filter-bar .semaforo-filter-label { color: var(--text-secondary); margin-right: 2px; }
.semaforo-chip { display: inline-flex; align-items: center; gap: 6px; }
.filter-bar button.semaforo-chip.active {
  background: var(--brand); border-color: var(--brand); color: #fff;
}
.semaforo-chip.active .semaforo-dot { box-shadow: 0 0 0 2px rgba(255,255,255,0.7); }
table.est-table tbody tr.filtered-hidden { display: none !important; }
@media print {
  .semaforo-filter-bar { display: none !important; }
}
"""

DETALLE_JS = """
function estFilterToggle(btn) {
  btn.classList.toggle('active');
  estFilterApply();
}
function estFilterClear() {
  Array.prototype.forEach.call(document.querySelectorAll('.semaforo-chip.active'), function (b) {
    b.classList.remove('active');
  });
  estFilterApply();
}
function estFilterApply() {
  var active = Array.prototype.map.call(document.querySelectorAll('.semaforo-chip.active'), function (b) {
    return b.dataset.value;
  });
  var rows = document.querySelectorAll('table.est-table tbody tr.est-row');
  var visible = 0;
  Array.prototype.forEach.call(rows, function (row) {
    var show = active.length === 0 || active.indexOf(row.dataset.semaforo) !== -1;
    row.classList.toggle('filtered-hidden', !show);
    var detail = row.nextElementSibling;
    if (detail && detail.classList.contains('est-detail-row')) {
      detail.classList.toggle('filtered-hidden', !show);
      if (!show) {
        row.classList.remove('open');
        detail.classList.remove('open');
      }
    }
    if (show) { visible++; }
  });
  var counter = document.getElementById('semaforo-filter-count');
  if (counter) { counter.textContent = visible + ' de ' + rows.length + ' estimados'; }
}
"""


def cargar_datos():
    with db.get_connection() as conn:
        estimados = pd.read_sql_query("SELECT * FROM estimados_costos", conn)
        oc = pd.read_sql_query("SELECT * FROM ordenes_compra_produccion", conn)
        ot = pd.read_sql_query("SELECT numero_ot, estado AS ot_estado FROM ordenes_trabajo", conn)
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
    if not estimados.empty:
        estimados["fecha_solicita"] = pd.to_datetime(estimados["fecha_solicita"], errors="coerce")
    return estimados, oc, ot, oc_pendientes, estimados_pend_facturar, items_crawl


def _armar_resumen(
    estimados: pd.DataFrame,
    oc: pd.DataFrame,
    ot: pd.DataFrame,
    items_pendientes: pd.DataFrame,
    estimados_pend_facturar: pd.DataFrame,
) -> pd.DataFrame:
    bloqueo = _resumen_por_estimado(estimados, oc, items_pendientes, estimados_pend_facturar)
    bloqueo = bloqueo.drop(columns=["numero_ot"])

    resumen = estimados.merge(bloqueo, on="numero_estimado", how="left")
    resumen = resumen.merge(ot, on="numero_ot", how="left")
    resumen["ot_estado"] = resumen["ot_estado"].fillna("(sin OT)")

    hoy = pd.Timestamp.now().normalize()
    resumen["antiguedad_dias"] = (hoy - resumen["fecha_solicita"]).dt.days

    def _semaforo(fila):
        if fila["estado"] in ESTADOS_SIN_ACCION:
            return ""
        return "bloqueado" if fila["bloqueado"] else "listo"

    resumen["semaforo"] = resumen.apply(_semaforo, axis=1)
    # Desvio de costo: lo que realmente se compro supero el presupuesto del
    # estimado -- dato que ya trae el export pero que ningun informe resalta
    # hoy (revision profunda pedida por Javier 2026-09-09).
    resumen["desvio_costo"] = resumen["total_comprado"] > resumen["sub_total"]
    resumen["ot_cerrada_anomalia"] = resumen["ot_estado"] == "Cerrada"
    return resumen


def _tabla_oc_estimado(numero_estimado, oc: pd.DataFrame) -> str:
    filas = oc[oc["numero_estimado"] == numero_estimado].sort_values("numero_oc", ascending=False)
    if filas.empty:
        return '<p class="empty">Sin ordenes de compra generadas para este estimado.</p>'
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


def _tabla_items_pendientes_estimado(numero_estimado, items_pendientes: pd.DataFrame) -> str:
    if items_pendientes.empty:
        return ""
    filas = items_pendientes[items_pendientes["numero_estimado"] == numero_estimado].copy()
    if filas.empty:
        return ""
    filas["motivo_label"] = filas["motivo"].map(MOTIVO_LABEL).fillna(filas["motivo"])
    tabla = hr.data_table(
        [
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


def _nota_pendiente_facturar_estimado(numero_estimado, estimados_pend_facturar: pd.DataFrame) -> str:
    if estimados_pend_facturar.empty:
        return ""
    filas = estimados_pend_facturar[estimados_pend_facturar["numero_estimado"] == numero_estimado]
    if filas.empty:
        return ""
    monto = filas["pendiente_facturar"].sum()
    return (
        '<h3>Pendiente de facturar</h3>'
        f'<p class="empty">{escape(_fmt_money(monto))}</p>'
    )


def _nota_oc_pendiente_estimado(numero_estimado, oc: pd.DataFrame) -> str:
    from modules.pendientes.generate_html_report import OC_ESTADOS_RESUELTOS

    if oc.empty:
        return ""
    filas = oc[
        (oc["numero_estimado"] == numero_estimado)
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


def _bloqueo_html(numero_estimado, oc, items_pendientes, estimados_pend_facturar) -> str:
    items_html = _tabla_items_pendientes_estimado(numero_estimado, items_pendientes)
    facturar_html = _nota_pendiente_facturar_estimado(numero_estimado, estimados_pend_facturar)
    oc_html = _nota_oc_pendiente_estimado(numero_estimado, oc)
    if not items_html and not facturar_html and not oc_html:
        return ""
    return (
        '<div class="bloqueo-box"><p class="bloqueo-title">Bloquea el pase a Finalizado</p>'
        f'{items_html}{facturar_html}{oc_html}</div>'
    )


ESTIMADOS_TABLE_COLUMNAS = [
    ("semaforo", ""),
    ("numero_estimado", "N° Est."),
    ("numero_ot", "N° OT"),
    ("titulo", "Título"),
    ("anunciante", "Anunciante"),
    ("estado", "Estado"),
    ("sub_total", "Sub Total"),
    ("total_comprado", "Comprado"),
    ("total_facturado", "Facturado"),
    ("antiguedad_dias", "Antigüedad (días)"),
]
ESTIMADOS_TABLE_NUM_COLS = ("sub_total", "total_comprado", "total_facturado")

_ROW_TOGGLE_JS = "this.classList.toggle('open'); this.nextElementSibling.classList.toggle('open')"


def _fila_tabla_estimado(fila: dict, oc, items_pendientes, estimados_pend_facturar) -> str:
    numero_estimado = fila["numero_estimado"]
    semaforo = fila.get("semaforo") or "bloqueado"
    motivo_bloqueo = fila.get("motivo_bloqueo") or ""

    badges = []
    if fila.get("ot_cerrada_anomalia"):
        badges.append(
            '<span class="badge-alerta" title="La OT de este estimado ya esta Cerrada en Advertys, '
            'pero el estimado sigue sin pasar a Finalizado.">OT ya cerrada</span>'
        )
    if fila.get("desvio_costo"):
        badges.append(
            '<span class="badge-info" title="El total comprado supera el Sub Total presupuestado '
            'de este estimado.">Desvío de costo</span>'
        )
    antiguedad = fila.get("antiguedad_dias")
    if pd.notna(antiguedad) and antiguedad > UMBRAL_DIAS_ANTIGUO:
        badges.append(f'<span class="badge-alerta">Antiguo ({int(antiguedad)} días)</span>')
    if semaforo == "bloqueado":
        badges.append(f'<span class="badge-bloqueada" title="{escape(motivo_bloqueo)}">Bloqueado</span>')

    titulo_semaforo = motivo_bloqueo if semaforo == "bloqueado" else SEMAFORO_LABEL.get(semaforo, "")
    semaforo_dot = (
        f'<span class="semaforo-dot" style="background:{SEMAFORO_COLOR.get(semaforo, hr.STATUS["warning"])}" '
        f'title="{escape(titulo_semaforo)}"></span>'
    )

    antiguedad_str = str(int(antiguedad)) if pd.notna(antiguedad) else "-"
    titulo_txt = fila.get("titulo") or "(sin título)"

    fila_resumen = f"""<tr class="est-row" data-semaforo="{semaforo}" onclick="{_ROW_TOGGLE_JS}">
      <td>{semaforo_dot}</td>
      <td>{escape(str(numero_estimado))}</td>
      <td>{escape(str(fila.get("numero_ot") or ""))} <span class="badge-info" style="margin-left:4px">{escape(str(fila.get("ot_estado") or ""))}</span></td>
      <td>{escape(str(titulo_txt))}{''.join(badges)}</td>
      <td>{escape(str(fila.get("anunciante") or ""))}</td>
      <td>{escape(str(fila.get("estado") or ""))}</td>
      <td class="num">{escape(_fmt_money(fila.get("sub_total") or 0))}</td>
      <td class="num">{escape(_fmt_money(fila.get("total_comprado") or 0))}</td>
      <td class="num">{escape(_fmt_money(fila.get("total_facturado") or 0))}</td>
      <td class="num">{antiguedad_str}</td>
    </tr>"""
    fila_detalle = f"""<tr class="est-detail-row">
      <td colspan="{len(ESTIMADOS_TABLE_COLUMNAS)}">
        <div class="est-detail-body">
          <h3>Ordenes de compra</h3>
          {_tabla_oc_estimado(numero_estimado, oc)}
          {_bloqueo_html(numero_estimado, oc, items_pendientes, estimados_pend_facturar)}
        </div>
      </td>
    </tr>"""
    return fila_resumen + fila_detalle


def _semaforo_filter_bar_html(counts: dict, total: int) -> str:
    chips = "".join(
        f'<button type="button" class="semaforo-chip" data-value="{clave}" onclick="estFilterToggle(this)">'
        f'<span class="semaforo-dot" style="background:{SEMAFORO_COLOR[clave]}"></span>'
        f'{escape(SEMAFORO_LABEL[clave])} ({counts.get(clave, 0)})</button>'
        for clave in ("listo", "bloqueado")
    )
    return f"""<div class="filter-bar semaforo-filter-bar">
    <div class="filter-controls no-print">
      <span class="semaforo-filter-label">Filtrar por semáforo:</span>
      {chips}
      <button type="button" onclick="estFilterClear()">Ver todos</button>
    </div>
    <div class="filter-coverage" id="semaforo-filter-count">{total} de {total} estimados</div>
  </div>"""


def _tabla_estimados_html(activos_ordenados: pd.DataFrame, oc, items_pendientes, estimados_pend_facturar) -> str:
    thead = "".join(
        f'<th class="{"num" if clave in ESTIMADOS_TABLE_NUM_COLS else ""}">{escape(titulo)}</th>'
        for clave, titulo in ESTIMADOS_TABLE_COLUMNAS
    )
    filas_html = "".join(
        _fila_tabla_estimado(fila, oc, items_pendientes, estimados_pend_facturar)
        for fila in activos_ordenados.to_dict(orient="records")
    )
    return f"""<table class="report-table est-table">
    <thead><tr>{thead}</tr></thead>
    <tbody>{filas_html}</tbody>
  </table>"""


def main():
    estimados, oc, ot, oc_pendientes, estimados_pend_facturar, items_crawl = cargar_datos()
    if estimados.empty:
        print("No hay estimados de costo en la base (correr el ingest de estimados_costos primero).")
        return

    items_pendientes = _combinar_items_pendientes(oc_pendientes, items_crawl)
    resumen = _armar_resumen(estimados, oc, ot, items_pendientes, estimados_pend_facturar)

    activos = resumen[resumen["semaforo"] != ""].copy()
    activos_ordenados = activos.sort_values("antiguedad_dias", ascending=False, na_position="last")

    cant_total = len(resumen)
    cant_activos = len(activos)
    cant_resueltos = cant_total - cant_activos
    cant_listos = int((activos["semaforo"] == "listo").sum())
    cant_bloqueados = int((activos["semaforo"] == "bloqueado").sum())
    cant_ot_cerrada = int(activos["ot_cerrada_anomalia"].sum())
    cant_desvio = int(activos["desvio_costo"].sum())
    cant_antiguos = int((activos["antiguedad_dias"] > UMBRAL_DIAS_ANTIGUO).sum())
    total_comprometido_oc = float(activos["total_oc"].fillna(0).sum())

    tiles = hr.stat_tiles([
        ("Estimados activos", str(cant_activos), "no terminales, de cualquier OT"),
        ("Listos para Finalizado", str(cant_listos), "facturados y con O.C. cruzadas"),
        ("Bloqueados", str(cant_bloqueados), "item sin O.C. y/o saldo pendiente"),
        ("OT ya cerrada", str(cant_ot_cerrada), "estimado sin finalizar en una OT Cerrada"),
        ("Desvío de costo", str(cant_desvio), "comprado > presupuestado"),
        (f"Antiguos (> {UMBRAL_DIAS_ANTIGUO} días)", str(cant_antiguos)),
        ("Comprometido en órdenes de compra", _fmt_money(total_comprometido_oc)),
        ("Ya resueltos (histórico)", str(cant_resueltos), "Finalizado / Anulado / Rechazado"),
    ])

    semaforo_counts = activos["semaforo"].value_counts().to_dict()
    filtro_html = _semaforo_filter_bar_html(semaforo_counts, cant_activos)
    tabla_html = _tabla_estimados_html(activos_ordenados, oc, items_pendientes, estimados_pend_facturar)

    secciones = "".join([
        tiles,
        hr.section(
            "Estimados de costo no terminales (todas las OT, abiertas o cerradas)",
            filtro_html + tabla_html,
            wide=True,
        ),
    ])

    html = hr.page_shell("Estimados Pendientes", "ALESTE ADS S.A. - Advertys", secciones)
    html = html.replace("</style>", DETALLE_CSS + "</style>")
    html = html.replace("</body>", f"<script>{DETALLE_JS}</script></body>")

    with open(REPORT_HTML_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK: informe generado en {REPORT_HTML_OUTPUT_PATH}")
    print(f"  {cant_activos} estimados activos, {cant_listos} listos para Finalizado, {cant_bloqueados} bloqueados, {cant_resueltos} ya resueltos.")


if __name__ == "__main__":
    main()
