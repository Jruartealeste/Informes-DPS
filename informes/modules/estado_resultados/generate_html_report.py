"""
Genera salida/informe_estado_resultados.html: Estado de Resultados mensual
(ingresos, costos directos, margen bruto, RRHH, costos fijos, resultado) y
la vista de Medios bruto vs neto. Ver config.py por el origen de los datos
y los criterios contables (staff devengado, retiro estimado, Medios en dos
vistas).

Uso (parado en informes/):
    python -m modules.balance_mensual.export          # baja el balance fresco de Advertys
    python -m modules.estado_resultados.generate_html_report [anio]
    python generate_dashboard.py
"""
import json
import sys
from datetime import date
from html import escape

import html_report as hr
from modules.estado_resultados import ajuste_usd, compute, config

CSS = """
<style>
.eerr-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
table.eerr { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 12px; font-variant-numeric: tabular-nums; }
table.eerr th, table.eerr td { padding: 6px 6px; border-bottom: 1px solid var(--gridline); white-space: nowrap; text-align: right; }
table.eerr th { color: var(--text-secondary); font-size: 11px; letter-spacing: .04em; text-transform: uppercase; position: sticky; top: 0; background: var(--surface-1); border-bottom: 1px solid var(--baseline); }
table.eerr th:first-child, table.eerr td:first-child { text-align: left; position: sticky; left: 0; background: var(--surface-1); z-index: 1; min-width: 200px; max-width: 260px; white-space: normal; }
table.eerr th:first-child { z-index: 2; }
table.eerr td.total, table.eerr th.total { border-left: 1px solid var(--baseline); font-weight: 600; }
table.eerr td.sin-dato { color: var(--text-muted); }
table.eerr td.neg { color: #d03b3b; }
table.eerr td.parcial { font-style: italic; }
table.eerr td.manual { background: rgba(240, 190, 30, 0.22); }
table.eerr tr.sec td { background: var(--page-plane); color: var(--text-secondary); font-weight: 700; font-size: 11px; letter-spacing: .05em; padding-top: 12px; }
table.eerr tr.sec td:first-child { background: var(--page-plane); }
table.eerr tr.det td { color: var(--text-secondary); font-size: 11.5px; }
table.eerr tr.det td:first-child { padding-left: 28px; }
table.eerr tr.grp td:first-child { padding-left: 16px; }
table.eerr tr.sub td { font-weight: 600; }
table.eerr tr.tot td { font-weight: 700; border-top: 1px solid var(--baseline); background: var(--brand-tint); }
/* La primera columna es sticky: su fondo tiene que ser opaco en todas las filas,
   si no los numeros que pasan por debajo al desplazar se ven a traves. */
table.eerr tr.tot td:first-child { background: linear-gradient(var(--brand-tint), var(--brand-tint)), var(--surface-1); }
table.eerr th:first-child, table.eerr td:first-child { box-shadow: inset -1px 0 0 var(--baseline); }
table.eerr tr.sec td + td { position: static; }
/* Resumen: cifras + grafico en una sola franja */
.eerr-resumen { display: grid; grid-template-columns: minmax(300px, 5fr) 7fr; gap: 28px; align-items: center; }
.eerr-kpis { display: grid; grid-template-columns: 1fr 1fr; gap: 16px 24px; }
.eerr-kpi { border-left: 2px solid var(--gridline); padding-left: 12px; min-width: 0; }
.eerr-kpi--clave { border-left-color: var(--brand); }
.eerr-kpi .k-label { font-size: 12px; color: var(--text-secondary); }
.eerr-kpi .k-valor { font-size: 21px; font-weight: 650; font-variant-numeric: tabular-nums; color: var(--text-primary); line-height: 1.25; white-space: nowrap; }
.eerr-kpi .k-pct { font-size: 13px; font-weight: 500; color: var(--text-secondary); margin-left: 6px; }
.eerr-kpi .k-sub { font-size: 11px; color: var(--text-muted); line-height: 1.35; }
.eerr-grafico .g-label { font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
@media (max-width: 760px) { .eerr-resumen { grid-template-columns: 1fr; gap: 18px; } }
@media (max-width: 600px) {
  table.eerr th:first-child, table.eerr td:first-child { min-width: 132px; max-width: 150px; font-size: 11.5px; }
  table.eerr tr.det td:first-child { padding-left: 14px; }
  table.eerr tr.grp td:first-child { padding-left: 8px; }
  table.eerr .nota { display: none; }
}
table.eerr tr.pct td { color: var(--text-secondary); font-style: italic; }
table.eerr tr.ctl td { color: var(--text-muted); font-size: 11.5px; }
table.eerr:not(.show-det) tr.det { display: none; }
table.eerr .nota { display: block; font-size: 10.5px; font-weight: 400; color: var(--text-muted); }
.eerr-toolbar { display: flex; gap: 10px; align-items: center; margin-bottom: 10px; flex-wrap: wrap; }
.eerr-aviso { border-left: 3px solid #d03b3b; background: rgba(208,59,59,0.08); padding: 8px 12px; border-radius: 6px; margin-bottom: 10px; font-size: 12.5px; }
.eerr-nota { color: var(--text-secondary); font-size: 12px; margin-top: 8px; }
.eerr-usd { margin-top: 22px; }
.eerr-usd h3 { font-size: 13px; font-weight: 600; margin: 0 0 2px; }
.eerr-usd p { color: var(--text-secondary); font-size: 12px; margin: 0 0 8px; }
.eerr-usd table { border-collapse: collapse; font-size: 12px; width: 100%; max-width: 980px; }
.eerr-usd th, .eerr-usd td { padding: 6px 10px; border-bottom: 1px solid var(--border); text-align: right; white-space: nowrap; }
.eerr-usd th { font-weight: 600; color: var(--text-secondary); font-size: 11.5px; }
.eerr-usd th:nth-child(-n+3), .eerr-usd td:nth-child(-n+3) { text-align: left; }
.eerr-usd tr.tot td { font-weight: 600; border-bottom: none; }
.eerr-usd .neg { color: #d03b3b; }
.eerr-alerta-staff {border-left: 3px solid #d98a00; background: rgba(217,138,0,0.10); padding: 9px 12px; border-radius: 6px; margin-bottom: 10px; font-size: 12.5px; }
.eerr-alerta-staff ul { margin: 4px 0 2px; padding-left: 18px; }
.eerr-alerta-staff .sub { color: var(--text-secondary); font-size: 11.5px; }
@media print { table.eerr th, table.eerr td:first-child { position: static; } .eerr-toolbar { display: none; } }
</style>
"""

JS = """
<script>
(function () {
  var btn = document.getElementById('eerr-toggle-det');
  var tbl = document.getElementById('eerr-tabla');
  if (!btn || !tbl) return;
  btn.addEventListener('click', function () {
    var on = tbl.classList.toggle('show-det');
    btn.textContent = on ? 'Ocultar detalle por cuenta' : 'Mostrar detalle por cuenta';
  });
})();
</script>
"""


def _fmt(v, pct=False) -> str:
    if v is None:
        return "—"
    if pct:
        return f"{v * 100:.1f}%".replace(".", ",")
    if abs(v) < 0.5:  # evita "-0"
        return "0"
    return f"{v:,.0f}".replace(",", ".")


def _tabla_usd(items: list) -> str:
    """Detalle de la fila 'Diferencia de cotizacion compras USD': una fila por compra."""
    if not items:
        return ""
    def ars(v):
        return ("-" if v < -0.5 else "") + "$ " + f"{abs(v):,.0f}".replace(",", ".")
    def usd(v):
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    filas = []
    for it in items:
        libro, bna = it["usd"] * it["tc_cargado"], it["usd"] * it["tc_bna"]
        f = it["fecha"]
        filas.append(
            f'<tr><td>{f[8:10]}/{f[5:7]}/{f[:4]}</td><td>{escape(it["proveedor"])}</td><td>{escape(it["referencia"])}</td>'
            f'<td>{usd(it["usd"])}</td><td>{ars(it["tc_cargado"])}</td><td>{ars(it["tc_bna"])}</td>'
            f'<td>{ars(libro)}</td><td>{ars(bna)}</td>'
            f'<td class="{"neg" if it["ajuste"] < -0.5 else ""}">{ars(it["ajuste"])}</td></tr>'
        )
    total = sum(it["ajuste"] for it in items)
    filas.append(f'<tr class="tot"><td colspan="8">Total diferencia</td>'
                 f'<td class="{"neg" if total < -0.5 else ""}">{ars(total)}</td></tr>')
    return (
        '<div class="eerr-usd"><h3>Diferencia de cotización compras USD: detalle</h3>'
        '<p>Cada compra en dólares ya está en el libro con el dólar cargado en Advertys. '
        'Esta fila la recalcula con el dólar oficial BNA comprador del día de la factura y suma solo la diferencia.</p>'
        '<table><thead><tr><th>Fecha</th><th>Proveedor</th><th>Factura</th><th>USD</th>'
        '<th>Dólar cargado</th><th>Dólar BNA</th><th>Costo en libro</th><th>Costo a BNA</th><th>Diferencia</th>'
        '</tr></thead><tbody>' + "".join(filas) + '</tbody></table></div>'
    )


def _tabla(res: dict, hoy: date) -> str:
    datos = set(res["meses_datos"])
    incompletos = set(res["meses_incompletos"])
    ult = max(datos) if datos else 0
    en_curso = res["anio"] == hoy.year and ult == hoy.month

    # Solo se muestran los meses con datos (diciembre vacio solo ensancha la tabla).
    visibles = sorted(datos) or list(range(1, 13))
    head = ['<th>Concepto</th>']
    for i in visibles:
        marca = "*" if (en_curso and i == ult) else ""
        head.append(f"<th>{compute.MESES[i - 1]}{marca}</th>")
    head.append(f'<th class="total">Total {res["anio"]}</th>')

    body = []
    for f in res["filas"]:
        tipo = f["tipo"]
        if tipo == "sec":
            body.append(f'<tr class="sec"><td>{escape(f["label"])}</td><td colspan="{len(visibles) + 1}"></td></tr>')
            continue
        nota = f'<span class="nota">{escape(f["nota"])}</span>' if f.get("nota") else ""
        celdas = [f'<td>{escape(f["label"])}{nota}</td>']
        for i in visibles:
            v = f["valores"][i - 1]
            clases = []
            if i not in datos:
                celdas.append('<td class="sin-dato">—</td>')
                continue
            if v is not None and not f["pct"] and v < -0.5:
                clases.append("neg")
            if f["pct"] and v is not None and v < 0:
                clases.append("neg")
            if f["id"] in ("rrhh-free", "rrhh") and i in incompletos:
                clases.append("parcial")
            titulo = ' title="Mes incompleto: faltan facturas de staff por llegar"' if (f["id"] in ("rrhh-free", "rrhh") and i in incompletos) else ""
            if i in f.get("marcas", []):
                clases.append("manual")
                titulo = ' title="Corregido a mano en la planilla (factura mal emitida o de varios meses)"'
            celdas.append(f'<td class="{" ".join(clases)}"{titulo}>{_fmt(v, f["pct"])}</td>')
        t = f["total"]
        neg = " neg" if (t is not None and t < -0.5 and not f["pct"]) or (f["pct"] and t is not None and t < 0) else ""
        celdas.append(f'<td class="total{neg}">{_fmt(t, f["pct"])}</td>')
        body.append(f'<tr class="{tipo}">{"".join(celdas)}</tr>')

    return f"""<div class="eerr-wrap"><table class="eerr" id="eerr-tabla">
    <thead><tr>{''.join(head)}</tr></thead>
    <tbody>{''.join(body)}</tbody>
  </table></div>"""


def _grafico_resultado(res: dict) -> str:
    """Barras mensuales de resultado, con negativos (bar_chart_svg del
    html_report solo soporta valores >= 0)."""
    datos = res["meses_datos"]
    if not datos:
        return "<p>Sin datos.</p>"
    cats = [compute.MESES[m - 1] for m in datos]
    vals = [res["series"]["resultado"][m - 1] for m in datos]
    fmt = lambda v: f"{v / 1e6:,.1f} M".replace(",", "X").replace(".", ",").replace("X", ".")  # noqa: E731
    n = len(cats)
    width = max(380, n * 40)
    pad_l, pad_r, pad_t, label_h, plot_h = 58, 8, 8, 22, 112
    plot_w = width - pad_l - pad_r
    vmax = max(max(vals), 0)
    vmin = min(min(vals), 0)
    rango = (vmax - vmin) or 1
    y_cero = pad_t + plot_h * (vmax / rango)
    slot = plot_w / n
    bar_w = max(12, slot - 10)
    partes = []
    for i, (c, v) in enumerate(zip(cats, vals)):
        x = pad_l + i * slot + (slot - bar_w) / 2
        h = abs(v) / rango * plot_h
        y = y_cero - h if v >= 0 else y_cero
        color = "var(--series-1)" if v >= 0 else "#d03b3b"
        partes.append(
            f'<g><rect class="hit" x="{x - 4:.1f}" y="{pad_t}" width="{bar_w + 8:.1f}" height="{plot_h}" '
            f'data-label="{escape(c)}" data-value="{escape(fmt(v))}" />'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{max(h, 1):.1f}" rx="3" fill="{color}" opacity="0.9" pointer-events="none" />'
            f'<text x="{x + bar_w / 2:.1f}" y="{pad_t + plot_h + 16}" text-anchor="middle" font-size="10">{escape(c)}</text></g>'
        )
    grid = []
    # Tres referencias: maximo, cero y minimo (el cero ya es la baseline).
    for val in sorted({vmax, vmin}):
        y = y_cero - (val / rango) * plot_h
        grid.append(f'<line class="gridline" x1="{pad_l}" x2="{width - pad_r}" y1="{y:.1f}" y2="{y:.1f}" />'
                    f'<text x="{pad_l - 8}" y="{y + 4:.1f}" text-anchor="end">{escape(fmt(val))}</text>')
    return (f'<svg class="chart" style="--w:{width}" viewBox="0 0 {width} {pad_t + plot_h + label_h}" preserveAspectRatio="xMinYMin meet">'
            f'{"".join(grid)}<line class="baseline" x1="{pad_l}" x2="{width - pad_r}" y1="{y_cero:.1f}" y2="{y_cero:.1f}" />'
            f'{"".join(partes)}</svg>')


def main(anio: int = config.ANIO_DEFAULT):
    if not config.BALANCE_CSV.exists():
        print(f"Falta {config.BALANCE_CSV}. Corre 'python -m modules.balance_mensual.export' primero.")
        sys.exit(1)
    df = compute.cargar_balance()
    if config.INPUTS_JSON.exists():
        inputs = json.loads(config.INPUTS_JSON.read_text(encoding="utf-8"))
    else:  # inputs.json esta gitignored (montos de sueldos): en un clon nuevo no existe
        print(f"AVISO: falta {config.INPUTS_JSON} (copiar inputs.example.json y completar): RRHH y retiro quedan en 0.")
        inputs = json.loads(config.INPUTS_JSON.with_name("inputs.example.json").read_text(encoding="utf-8"))
    if int(inputs.get("anio", anio)) != anio:
        print(f"AVISO: inputs.json es de {inputs.get('anio')} y se pidio {anio}: RRHH/retiro quedan en 0.")
        inputs = {"meses_incompletos": []}
    try:
        ajustes = ajuste_usd.calcular_ajustes(anio)
    except Exception as e:  # sin API/cache/export: el informe sale igual, sin ajuste
        print(f"AVISO: sin ajuste USD ({e})")
        ajustes = {"items": [], "sin_cotizacion": [f"No se pudo calcular el ajuste de compras en USD: {e}"]}
    res = compute.calcular(df, inputs, anio, ajustes)
    hoy = date.today()
    t = res["tot"]
    pct = lambda a, b: f"{(a / b * 100):.1f}%".replace(".", ",") if b else "—"  # noqa: E731
    m = lambda v: f"$ {v / 1e6:,.1f} M".replace(",", "X").replace(".", ",").replace("X", ".")  # noqa: E731

    def kpi(label, valor, pct_txt="", sub="", clave=False):
        pct_html = f'<span class="k-pct">{escape(pct_txt)}</span>' if pct_txt else ""
        return (f'<div class="eerr-kpi{" eerr-kpi--clave" if clave else ""}">'
                f'<div class="k-label">{escape(label)}</div>'
                f'<div class="k-valor">{escape(valor)}{pct_html}</div>'
                f'<div class="k-sub">{escape(sub)}</div></div>')

    n_meses = len(res["meses_datos"])
    resumen = (
        '<div class="eerr-resumen"><div class="eerr-kpis">'
        + kpi("Ingresos", m(t["ingresos"]), sub=f"{n_meses} meses con datos")
        + kpi("Margen bruto", m(t["mg_bruto"]), pct(t["mg_bruto"], t["ingresos"]), "sobre ingresos")
        + kpi("Resultado", m(t["resultado"]), pct(t["resultado"], t["ingresos"]), "incluye retiro estimado", clave=True)
        + kpi("Sin diferencia pass-through", m(t["resultado_sin_dif"]),
              sub=f"saca {m(t['dif_pass'])} de Medios sin costo cargado")
        + '</div><div class="eerr-grafico"><div class="g-label">Resultado por mes</div>'
        + _grafico_resultado(res) + '</div></div>'
    )

    avisos = "".join(f'<div class="eerr-aviso">{escape(a)}</div>' for a in res["avisos"])
    sin_fact = compute.staff_sin_facturar(inputs, anio, hoy.month) if anio == hoy.year else []
    if sin_fact:
        mes_falta = compute.MESES_NOMBRE[sin_fact[0]["mes_falta"] - 1]
        mes_ult = compute.MESES_NOMBRE[sin_fact[0]["mes_ultima"] - 1]
        items = "".join(f'<li><b>{escape(a["nombre"])}</b>: última factura en {mes_ult} por {m(a["importe_ultima"])}</li>'
                        for a in sin_fact)
        avisos = (
            f'<div class="eerr-alerta-staff">Staff sin factura de {mes_falta}: '
            f'{len(sin_fact)} {"persona facturó" if len(sin_fact) == 1 else "personas facturaron"} en {mes_ult} y todavía no en {mes_falta}.'
            f'<ul>{items}</ul>'
            '<div class="sub">Pedí la factura o, si ya llegó, re-sincronizá la planilla. '
            'Quien lleva dos meses o más sin facturar no aparece acá: se asume que dejó de trabajar con la agencia.</div></div>'
        ) + avisos
    notas = (
        '<p class="eerr-nota">Fuente: Balance Mensual de Advertys (Consultas &gt; Contabilidad), ingresos y costos por cuenta. '
        'RRHH y Retiro socio salen de <code>modules/estado_resultados/inputs.json</code> (no están en Advertys). '
        '<b>Staff Freelance</b> está imputado al mes devengado (la factura llega el mes siguiente); '
        'los meses en cursiva tienen facturas pendientes de llegar. '
        'En el detalle por cuenta, las celdas en amarillo del staff son facturas corregidas a mano en la planilla. '
        '<b>Retiro socio</b> es un número estimado. '
        '<b>Medios</b> se muestra bruto (con pass-through de OP) y neto en la última sección. '
        + ('El mes con * está en curso. ' if res["anio"] == hoy.year and res["meses_datos"] and max(res["meses_datos"]) == hoy.month else '')
        + '</p>'
    )
    toolbar = ('<div class="eerr-toolbar"><button class="print-btn" id="eerr-toggle-det" type="button">'
               'Mostrar detalle por cuenta</button></div>')

    secciones = "".join([
        CSS,
        hr.section(f"Resumen {anio}", resumen, wide=True),
        hr.section(f"Estado de Resultados {anio}", avisos + toolbar + _tabla(res, hoy) + notas + _tabla_usd(res.get("compras_usd", [])) + JS, wide=True),
    ])
    html = hr.page_shell(f"Estado de Resultados {anio}", "ALESTE ADS S.A. - Advertys", secciones)
    with open(config.REPORT_HTML_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK: informe generado en {config.REPORT_HTML_OUTPUT_PATH}")
    print(f"  Ingresos {m(t['ingresos'])} | MG bruto {m(t['mg_bruto'])} | Resultado {m(t['resultado'])} | sin dif. pass-through {m(t['resultado_sin_dif'])}")
    for a in res["avisos"]:
        print(f"  AVISO: {a}")
    for a in sin_fact:
        print(f"  ALERTA STAFF: {a['nombre']} facturó en {compute.MESES_NOMBRE[a['mes_ultima'] - 1]} "
              f"y no en {compute.MESES_NOMBRE[a['mes_falta'] - 1]}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else config.ANIO_DEFAULT)
