"""
Genera el informe HTML de "Pendientes": ordenes de trabajo abiertas con el
detalle de sus Estimados de Costo y Ordenes de Compra (Produccion)
asociadas, para poder revisar de un vistazo que contiene cada OT abierta y
por que sigue abierta.

A diferencia de los demas informe_*.html, este no ingesta su propia tabla:
cruza tres tablas ya cargadas por otros modulos:
  - ordenes_trabajo   (modules/ordenes_trabajo, filtrado a estado='Abierta')
  - estimados_costos  (modules/estimados_costos, vinculado por numero_ot)
  - ordenes_compra_produccion (modules/ordenes_compra, vinculado por
    numero_estimado, que a su vez cuelga de estimados_costos)

Por eso antes de correr esto hace falta tener las 3 tablas actualizadas:
    python -m modules.ordenes_trabajo.ingest <export ultimo>
    python -m modules.estimados_costos.ingest <export ultimo>
    python -m modules.ordenes_compra.ingest <export ultimo>

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

REPORT_HTML_OUTPUT_PATH = "informe_pendientes.html"


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
table.ot-table tbody tr.ot-detail-row td { padding: 0; background: var(--page-plane); }
table.ot-table tbody tr.ot-detail-row .ot-detail-body { padding: 14px 20px 18px 28px; }
table.ot-table tbody tr.ot-detail-row h3 {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin: 14px 0 8px;
}
table.ot-table tbody tr.ot-detail-row h3:first-child { margin-top: 0; }
table.ot-table tbody tr.ot-detail-row p.empty {
  color: var(--text-muted);
  font-size: 13px;
  margin: 0 0 4px;
}
.badge-alerta {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  background: rgba(208,59,59,0.12);
  color: #d03b3b;
  margin-left: 6px;
}
@media print {
  table.ot-table tbody tr.ot-detail-row { display: table-row !important; }
  table.ot-table tbody tr.ot-row td:first-child::before { display: none; }
}
"""


def cargar_datos():
    with db.get_connection() as conn:
        ot = pd.read_sql_query(
            "SELECT * FROM ordenes_trabajo WHERE estado = 'Abierta'", conn
        )
        estimados = pd.read_sql_query("SELECT * FROM estimados_costos", conn)
        oc = pd.read_sql_query("SELECT * FROM ordenes_compra_produccion", conn)
    if not ot.empty:
        ot["fecha_abierta"] = pd.to_datetime(ot["fecha_abierta"], errors="coerce")
    return ot, estimados, oc


def _resumen_por_ot(ot: pd.DataFrame, estimados: pd.DataFrame, oc: pd.DataFrame) -> pd.DataFrame:
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

    resumen = ot.set_index("numero_ot").join(est_por_ot, how="left").join(oc_por_ot, how="left")
    resumen["cant_estimados"] = resumen["cant_estimados"].fillna(0).astype(int)
    resumen["cant_oc"] = resumen["cant_oc"].fillna(0).astype(int)
    for col in ("sub_total_estimado", "total_comprado_estimado", "total_oc"):
        resumen[col] = resumen[col].fillna(0.0)
    resumen["estados_estimados"] = resumen["estados_estimados"].fillna("")
    # Sin estimados -> no evaluable (critico). Sin OC -> no hay compromiso
    # pendiente, no bloquea el verde (vacuamente resuelto).
    resumen["estimados_ok"] = resumen["estimados_ok"].fillna(False)
    resumen["oc_ok"] = resumen["oc_ok"].fillna(True)

    def _semaforo(fila):
        if fila["cant_estimados"] == 0:
            return "critical"
        if fila["estimados_ok"] and fila["oc_ok"]:
            return "good"
        return "warning"

    resumen["semaforo"] = resumen.apply(_semaforo, axis=1)
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


def _fila_tabla_ot(fila: dict, estimados: pd.DataFrame, oc: pd.DataFrame) -> str:
    numero_ot = fila["numero_ot"]
    sin_estimados = fila["cant_estimados"] == 0
    row_class = "ot-row row-alerta" if sin_estimados else "ot-row"
    alerta = '<span class="badge-alerta">Sin estimados</span>' if sin_estimados else ""
    fecha_abierta = fila.get("fecha_abierta")
    fecha_str = fecha_abierta.strftime("%Y-%m-%d") if pd.notna(fecha_abierta) else "-"
    renta_teorica = fila.get("renta_teorica")
    renta_str = f"{renta_teorica:.1f}%" if pd.notna(renta_teorica) else "-"
    resumen_txt = fila.get("resumen") or "(sin resumen)"
    semaforo = fila.get("semaforo", "warning")
    semaforo_dot = (
        f'<span class="semaforo-dot" style="background:{SEMAFORO_COLOR[semaforo]}" '
        f'title="{escape(SEMAFORO_LABEL[semaforo])}"></span>'
    )

    fila_resumen = f"""<tr class="{row_class}" onclick="{_ROW_TOGGLE_JS}">
      <td>{semaforo_dot}</td>
      <td>{escape(str(numero_ot))}</td>
      <td>{escape(str(resumen_txt))}{alerta}</td>
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
        </div>
      </td>
    </tr>"""
    return fila_resumen + fila_detalle


def _tabla_ot_html(resumen_ordenado: pd.DataFrame, estimados: pd.DataFrame, oc: pd.DataFrame) -> str:
    thead = "".join(
        f'<th class="{"num" if clave in OT_TABLE_NUM_COLS else ""}">{escape(titulo)}</th>'
        for clave, titulo in OT_TABLE_COLUMNAS
    )
    filas_html = "".join(
        _fila_tabla_ot(fila, estimados, oc)
        for fila in resumen_ordenado.to_dict(orient="records")
    )
    return f"""<table class="report-table ot-table">
    <thead><tr>{thead}</tr></thead>
    <tbody>{filas_html}</tbody>
  </table>"""


def main():
    ot, estimados, oc = cargar_datos()
    if ot.empty:
        print("No hay ordenes de trabajo abiertas en la base (o no corriste el ingest de ordenes_trabajo todavia).")
        return

    resumen = _resumen_por_ot(ot, estimados, oc)
    resumen_ordenado = resumen.sort_values("fecha_abierta", ascending=False)

    cant_ot = len(resumen)
    cant_sin_estimados = int((resumen["cant_estimados"] == 0).sum())
    cant_listas = int((resumen["semaforo"] == "good").sum())
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
        ("Sin estimados cargados", str(cant_sin_estimados), "revisar por que siguen abiertas"),
        ("Renta teórica promedio", f"{renta_teorica_promedio:.1f}%"),
        ("Comprometido en órdenes de compra", _fmt_money(total_comprometido_oc)),
    ])

    tabla_ot_html = _tabla_ot_html(resumen_ordenado, estimados, oc)

    secciones = "".join([
        tiles,
        hr.section("Detalle por OT (estimados de costo + órdenes de compra)", tabla_ot_html),
    ])

    html = hr.page_shell("Pendientes", "ALESTE ADS S.A. - Advertys", secciones)
    html = html.replace("</style>", DETALLE_CSS + "</style>")

    with open(REPORT_HTML_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK: informe generado en {REPORT_HTML_OUTPUT_PATH}")
    print(f"  {cant_ot} OT abiertas, {cant_sin_estimados} sin estimados cargados.")


if __name__ == "__main__":
    main()
