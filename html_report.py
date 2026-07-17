"""
Utilidades compartidas para generar informes HTML autocontenidos: un solo
archivo, sin CDN ni dependencias externas, pensado para abrir con doble
click y usar "Imprimir > Guardar como PDF" del navegador. Cada modulo arma
su propio generate_html_report.py llamando a estas funciones y sobreescribe
siempre la misma ruta de salida (no acumula archivos).
"""
import json
from datetime import datetime
from html import escape

import pandas as pd

# --- Paleta (dataviz skill / references/palette.md) ---
SERIES_1 = ("#2a78d6", "#3987e5")  # azul: magnitud de una sola serie
STATUS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
}

# Isotipo ALESTE (assets/aleste-logo.svg), viewBox recortado al bbox real de
# los paths y fill -> currentColor para que siga --text-primary en
# claro/oscuro/print sin tener que mantener una copia por tema.
LOGO_SVG = """<svg viewBox="66 48 176 131" width="176" height="131" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="ALESTE">
  <path d="M120.184,87.073l-3.576-6.358h-30.943l-3.377,6.358h-12.119l19.172-34.817h23.344l20.314,34.817h-12.814ZM105.135,60.302h-8.444l-6.755,12.566h22.301l-7.103-12.566Z" fill="currentColor"/>
  <path d="M135.829,52.405h11.871v26.075h26.324v8.642h-38.195v-34.718Z" fill="currentColor"/>
  <path d="M73.198,96.203h112.448v7.897h-100.727v5.165h100.081v7.947h-100.081v5.712h101.223v8.096h-112.944v-34.817Z" fill="currentColor"/>
  <path d="M212.268,131.666c-3.775-.034-7.07-.331-9.884-.894-2.815-.596-4.984-1.316-6.507-2.16-1.523-.845-2.74-1.863-3.651-3.055s-1.482-2.285-1.713-3.278c-.265-.96-.398-1.987-.398-3.08v-.496h12.367c.199,2.55,1.705,4.205,4.52,4.967,1.49.365,3.378.546,5.662.546h2.732c1.788,0,3.443-.099,4.967-.298,1.556-.199,2.698-.48,3.427-.844.696-.397,1.158-.795,1.391-1.192.231-.397.364-.845.398-1.341,0-.761-.216-1.358-.646-1.788-.43-.43-1.374-.811-2.831-1.142-1.523-.331-3.675-.529-6.457-.596l-3.725-.05-2.831-.099c-12.317-.298-18.476-3.692-18.476-10.182v-.397c.033-1.125.182-2.168.447-3.129.331-.927.951-1.87,1.863-2.831.91-.96,2.111-1.755,3.601-2.384,1.49-.662,3.477-1.208,5.96-1.639,2.516-.43,5.447-.646,8.792-.646h3.477c3.477,0,6.539.224,9.189.67,2.649.447,4.76,1.01,6.333,1.689,1.572.679,2.855,1.515,3.849,2.508,1.026,1.027,1.722,2.02,2.086,2.98.364.993.546,2.037.546,3.129v.497h-12.318c-.066-.397-.166-.712-.298-.944-.099-.265-.372-.621-.819-1.068-.447-.447-1.018-.803-1.713-1.068-.762-.298-1.821-.547-3.179-.745-1.458-.231-2.914-.348-4.371-.348h-1.788c-2.582,0-4.636.166-6.159.497-1.523.331-2.451.679-2.782,1.043-.331.331-.496.812-.496,1.44.033.596.215,1.076.546,1.44.364.397,1.216.754,2.557,1.068,1.341.315,3.236.472,5.687.472l2.781.05,3.576.05c7.053.133,12.152,1.018,15.298,2.657,3.145,1.639,4.719,4.197,4.719,7.674v.645c0,1.291-.149,2.451-.447,3.477-.331.993-.968,2.02-1.912,3.079-.944,1.06-2.203,1.946-3.775,2.657-1.573.712-3.734,1.3-6.482,1.763-2.749.463-5.944.695-9.586.695h-3.527Z" fill="currentColor"/>
  <path d="M87.006,174.918v-26.523h-16.291v-8.195h44.602v8.195h-16.341v26.523h-11.97Z" fill="currentColor"/>
  <path d="M118.843,140.051h40.032v7.897h-28.311v5.165h27.616v7.947h-27.616v5.712h28.807v8.096h-40.529v-34.817Z" fill="currentColor"/>
</svg>"""

PAGE_CSS = """
:root {
  color-scheme: light;
  --surface-1:      #fcfcfb;
  --page-plane:     #f9f9f7;
  --text-primary:   #0b0b0b;
  --text-secondary: #52514e;
  --text-muted:     #898781;
  --gridline:       #e1e0d9;
  --baseline:       #c3c2b7;
  --border:         rgba(11,11,11,0.10);
  --series-1:       #2a78d6;
}
@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --surface-1:      #1a1a19;
    --page-plane:     #0d0d0d;
    --text-primary:   #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted:     #898781;
    --gridline:       #2c2c2a;
    --baseline:       #383835;
    --border:         rgba(255,255,255,0.10);
    --series-1:       #3987e5;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  background: var(--page-plane);
  color: var(--text-primary);
}
.page {
  max-width: 980px;
  margin: 0 auto;
  padding: 32px 24px 64px;
}
header.report-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border);
}
header.report-header .brand {
  display: flex;
  align-items: center;
  gap: 16px;
}
header.report-header .brand-logo {
  width: 46px;
  height: auto;
  flex-shrink: 0;
  color: var(--text-primary);
}
header.report-header .brand-logo svg {
  display: block;
  width: 100%;
  height: auto;
}
header.report-header h1 {
  font-size: 22px;
  letter-spacing: -0.01em;
  margin: 0 0 4px;
}
header.report-header .meta {
  color: var(--text-secondary);
  font-size: 13px;
}
button.print-btn {
  border: 1px solid var(--border);
  background: var(--surface-1);
  color: var(--text-primary);
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
}
button.print-btn:hover { background: var(--page-plane); }

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 28px;
}
.stat-tile {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 16px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.stat-tile .label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}
.stat-tile .value {
  font-size: 24px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.stat-tile .sublabel {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

section.report-section {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
section.report-section h2 {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.01em;
  margin: 0 0 14px;
}

svg.chart { width: 100%; height: auto; display: block; overflow: visible; }
svg.chart text { fill: var(--text-muted); font-size: 11px; }
svg.chart .gridline { stroke: var(--gridline); stroke-width: 1; }
svg.chart .baseline { stroke: var(--baseline); stroke-width: 1; }
svg.chart .hit { fill: transparent; cursor: pointer; }

table.report-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
table.report-table th, table.report-table td {
  text-align: left;
  padding: 7px 10px;
  border-bottom: 1px solid var(--gridline);
}
table.report-table th {
  color: var(--text-secondary);
  font-weight: 600;
  border-bottom: 1px solid var(--baseline);
}
table.report-table td.num, table.report-table th.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
table.report-table tr { break-inside: avoid; }

#viz-tooltip {
  position: fixed;
  pointer-events: none;
  background: var(--text-primary);
  color: var(--surface-1);
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 6px;
  transform: translate(-50%, calc(-100% - 10px));
  white-space: nowrap;
  opacity: 0;
  transition: opacity 0.08s ease;
  z-index: 10;
}
#viz-tooltip.visible { opacity: 1; }

.legend { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 10px; font-size: 12px; color: var(--text-secondary); }
.legend .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; vertical-align: middle; }

footer.report-footer {
  color: var(--text-muted);
  font-size: 12px;
  margin-top: 24px;
}

@media print {
  :root {
    color-scheme: light;
    --surface-1: #ffffff;
    --page-plane: #ffffff;
    --text-primary: #0b0b0b;
    --text-secondary: #3a3936;
    --text-muted: #6a6963;
    --gridline: #d8d7d0;
    --baseline: #9a988f;
    --border: rgba(11,11,11,0.15);
    --series-1: #2a78d6;
  }
  .no-print { display: none !important; }
  .page { max-width: none; padding: 0; }
  section.report-section { break-inside: avoid; border: 1px solid #ddd; box-shadow: none; }
  .stat-tile { box-shadow: none; }
  table.report-table tr { break-inside: avoid; }
  thead { display: table-header-group; }
}
"""

DASHBOARD_CSS = """
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 16px;
  margin-bottom: 20px;
  font-size: 13px;
}
.filter-bar .filter-controls { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.filter-bar label { display: flex; align-items: center; gap: 6px; color: var(--text-secondary); }
.filter-bar input[type=month] {
  border: 1px solid var(--border);
  background: var(--page-plane);
  color: var(--text-primary);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 13px;
  font-family: inherit;
}
.filter-bar button {
  border: 1px solid var(--border);
  background: var(--page-plane);
  color: var(--text-primary);
  border-radius: 6px;
  padding: 5px 12px;
  font-size: 13px;
  cursor: pointer;
}
.filter-bar button:hover { background: var(--surface-1); }
.filter-coverage { color: var(--text-muted); }
.filter-coverage strong { color: var(--text-primary); font-weight: 600; }
"""

TOOLTIP_JS = """
(function () {
  var tip = document.getElementById('viz-tooltip');
  if (!tip) return;
  document.addEventListener('mousemove', function (e) {
    var hit = e.target.closest('.hit');
    if (!hit) { tip.classList.remove('visible'); return; }
    tip.textContent = hit.dataset.label + ': ' + hit.dataset.value;
    tip.style.left = e.clientX + 'px';
    tip.style.top = e.clientY + 'px';
    tip.classList.add('visible');
  });
  document.addEventListener('mouseleave', function () { tip.classList.remove('visible'); });
})();
"""


def _fmt_money(v: float) -> str:
    return f"$ {v:,.0f}".replace(",", ".")


def page_shell(titulo: str, subtitulo: str, secciones_html: str) -> str:
    generado = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{escape(titulo)}</title>
<style>{PAGE_CSS}{DASHBOARD_CSS}</style>
</head>
<body>
<div class="page">
  <header class="report-header">
    <div class="brand">
      <div class="brand-logo">{LOGO_SVG}</div>
      <div>
        <h1>{escape(titulo)}</h1>
        <div class="meta">{escape(subtitulo)} &middot; Generado: {generado}</div>
      </div>
    </div>
    <button class="print-btn no-print" onclick="window.print()">Imprimir / Guardar PDF</button>
  </header>
  {secciones_html}
  <footer class="report-footer">Informe generado automaticamente desde advertys.db. Volve a correr el script para reflejar el ultimo export.</footer>
</div>
<div id="viz-tooltip"></div>
<script>{TOOLTIP_JS}</script>
</body>
</html>"""


def stat_tiles(items) -> str:
    """items: lista de (label, value_str, sublabel_opcional)"""
    tiles = []
    for item in items:
        label, value = item[0], item[1]
        sublabel = item[2] if len(item) > 2 else None
        sub_html = f'<div class="sublabel">{escape(sublabel)}</div>' if sublabel else ""
        tiles.append(f"""<div class="stat-tile">
      <div class="label">{escape(label)}</div>
      <div class="value">{escape(value)}</div>
      {sub_html}
    </div>""")
    return f'<div class="stat-grid">{"".join(tiles)}</div>'


def section(titulo: str, contenido_html: str) -> str:
    return f"""<section class="report-section">
    <h2>{escape(titulo)}</h2>
    {contenido_html}
  </section>"""


def bar_chart_svg(categorias, valores, *, colors=None, value_fmt=None, height=260):
    """
    Grafico de barras verticales de una sola magnitud. `colors` (opcional)
    es una lista paralela a `categorias` para pintar cada barra distinto
    (usado para Estado con la paleta de status); si no se pasa, todas las
    barras usan --series-1.
    """
    value_fmt = value_fmt or (lambda v: f"{v:,.0f}")
    n = len(categorias)
    if n == 0:
        return "<p>Sin datos.</p>"

    width = max(560, n * 70)
    pad_left, pad_right, pad_top = 50, 20, 20
    label_h = 46
    chart_h = height
    plot_h = chart_h - pad_top - label_h
    plot_w = width - pad_left - pad_right

    max_val = max(valores) or 1
    bar_gap = 10
    bar_w = max(18, (plot_w / n) - bar_gap)

    gridlines = []
    grid_labels = []
    steps = 4
    for i in range(steps + 1):
        frac = i / steps
        y = pad_top + plot_h - frac * plot_h
        gridlines.append(f'<line class="gridline" x1="{pad_left}" x2="{width - pad_right}" y1="{y:.1f}" y2="{y:.1f}" />')
        grid_labels.append(f'<text x="{pad_left - 8}" y="{y + 4:.1f}" text-anchor="end">{value_fmt(max_val * frac)}</text>')

    bars = []
    for i, (cat, val) in enumerate(zip(categorias, valores)):
        x = pad_left + i * (plot_w / n) + ((plot_w / n) - bar_w) / 2
        bar_h = (val / max_val) * plot_h if max_val else 0
        y = pad_top + plot_h - bar_h
        baseline_y = pad_top + plot_h
        color = colors[i] if colors else "var(--series-1)"
        squared_h = min(4, bar_h)
        bars.append(f"""<g>
      <rect class="hit" x="{x - 4:.1f}" y="{pad_top:.1f}" width="{bar_w + 8:.1f}" height="{plot_h:.1f}" data-label="{escape(str(cat))}" data-value="{escape(value_fmt(val))}" />
      <rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="4" ry="4" fill="{color}" pointer-events="none" />
      <rect x="{x:.1f}" y="{baseline_y - squared_h:.1f}" width="{bar_w:.1f}" height="{squared_h:.1f}" fill="{color}" pointer-events="none" />
      <text x="{x + bar_w / 2:.1f}" y="{baseline_y + 18:.1f}" text-anchor="middle" transform="rotate(-40 {x + bar_w / 2:.1f} {baseline_y + 18:.1f})">{escape(str(cat))}</text>
    </g>""")

    baseline_y = pad_top + plot_h
    return f"""<svg class="chart" viewBox="0 0 {width} {chart_h}" preserveAspectRatio="xMinYMin meet">
    {''.join(gridlines)}
    {''.join(grid_labels)}
    <line class="baseline" x1="{pad_left}" x2="{width - pad_right}" y1="{baseline_y:.1f}" y2="{baseline_y:.1f}" />
    {''.join(bars)}
  </svg>"""


def _truncar(texto: str, max_chars: int) -> str:
    return texto if len(texto) <= max_chars else texto[: max_chars - 1].rstrip() + "…"


def hbar_chart_svg(categorias, valores, *, value_fmt=None, row_h=28):
    """Grafico de barras horizontales, para rankings (top N por categoria)."""
    value_fmt = value_fmt or (lambda v: f"{v:,.0f}")
    n = len(categorias)
    if n == 0:
        return "<p>Sin datos.</p>"

    max_len = max((len(str(c)) for c in categorias), default=0)
    label_w = min(260, max(120, max_len * 6.4 + 10))
    max_chars = int((label_w - 10) / 6.4)
    pad_right = 90
    width = 760
    plot_w = width - label_w - pad_right
    height = n * row_h + 20
    max_val = max(valores) or 1

    rows = []
    for i, (cat, val) in enumerate(zip(categorias, valores)):
        y = 10 + i * row_h
        bar_w = (val / max_val) * plot_w if max_val else 0
        etiqueta = _truncar(str(cat), max_chars)
        rows.append(f"""<g>
      <text x="{label_w - 10}" y="{y + row_h / 2 + 4:.1f}" text-anchor="end">{escape(etiqueta)}</text>
      <rect class="hit" x="0" y="{y:.1f}" width="{width:.1f}" height="{row_h - 6:.1f}" data-label="{escape(str(cat))}" data-value="{escape(value_fmt(val))}" />
      <rect x="{label_w}" y="{y:.1f}" width="{max(bar_w, 2):.1f}" height="{row_h - 6:.1f}" rx="4" ry="4" fill="var(--series-1)" pointer-events="none" />
      <text x="{label_w + bar_w + 8:.1f}" y="{y + row_h / 2 + 4:.1f}" text-anchor="start">{value_fmt(val)}</text>
    </g>""")

    return f"""<svg class="chart" viewBox="0 0 {width} {height}" preserveAspectRatio="xMinYMin meet">
    {''.join(rows)}
  </svg>"""


def data_table(columnas, filas, *, numeric_cols=()) -> str:
    """columnas: lista de (clave, titulo). filas: lista de dicts."""
    head = "".join(
        f'<th class="{"num" if clave in numeric_cols else ""}">{escape(titulo)}</th>'
        for clave, titulo in columnas
    )
    body_rows = []
    for fila in filas:
        cells = []
        for clave, _ in columnas:
            valor = fila.get(clave, "")
            if clave in numeric_cols:
                valor_str = _fmt_money(valor) if valor is not None else ""
                cells.append(f'<td class="num">{escape(valor_str)}</td>')
            else:
                cells.append(f"<td>{escape('' if valor is None else str(valor))}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    return f"""<table class="report-table">
    <thead><tr>{head}</tr></thead>
    <tbody>{''.join(body_rows)}</tbody>
  </table>"""


# --- Tablero dinamico: filtro de periodo editable por el usuario ---
#
# Los stat tiles / graficos / tablas de mas arriba son estaticos (calculados
# una vez en Python al generar el archivo). Para que el usuario pueda elegir
# un rango de periodo y ver todo recalculado en el momento, en vez de eso se
# embebe el dataset crudo como JSON y un motor generico en JS (DASHBOARD_JS)
# que agrega/dibuja segun un "spec" declarativo (ver cada
# modules/<modulo>/generate_html_report.py para el spec real de cada informe).
# Los graficos de barra en JS son un puerto 1:1 de bar_chart_svg/hbar_chart_svg
# de aca arriba, para que se vean identicos.


def records_from_df(df, columns) -> list:
    """Convierte un DataFrame a una lista de dicts serializable a JSON (para
    embeber en el HTML): NaN/NaT -> None, Timestamps -> 'YYYY-MM-DD'."""
    records = []
    for row in df[list(columns)].to_dict(orient="records"):
        clean = {}
        for k, v in row.items():
            if pd.isna(v):
                clean[k] = None
            elif isinstance(v, (pd.Timestamp, datetime)):
                clean[k] = v.strftime("%Y-%m-%d")
            elif isinstance(v, (int, float)):
                clean[k] = float(v)
            else:
                clean[k] = v
        records.append(clean)
    return records


def mount(id_: str) -> str:
    """Placeholder vacio que el motor JS va a llenar (grafico o tabla)."""
    return f'<div id="{id_}"></div>'


def stat_tiles_mount(mount_id: str = "stat-tiles") -> str:
    return f'<div class="stat-grid" id="{mount_id}"></div>'


def filter_bar_html() -> str:
    """Barra de filtro de periodo (Desde/Hasta editable + texto de cobertura).
    Los inputs van en no-print asi no aparecen al imprimir/PDF, pero el texto
    de cobertura ("Datos disponibles" / "Mostrando") queda visible en el
    impreso para que quede claro que periodo contempla el informe."""
    return """<div class="filter-bar">
    <div class="filter-controls no-print">
      <label>Desde <input type="month" id="f-desde"></label>
      <label>Hasta <input type="month" id="f-hasta"></label>
      <button type="button" id="f-reset">Ver todo el periodo</button>
    </div>
    <div class="filter-coverage" id="f-coverage">Calculando periodos disponibles...</div>
  </div>"""


DASHBOARD_JS = """
(function () {
  var recordsEl = document.getElementById('report-records');
  var specEl = document.getElementById('report-spec');
  if (!recordsEl || !specEl) return;
  var records = JSON.parse(recordsEl.textContent);
  var spec = JSON.parse(specEl.textContent);
  var dateField = spec.dateField;

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function fmtInt(v) {
    v = Math.round(v || 0);
    var neg = v < 0; v = Math.abs(v);
    var s = String(v), out = '';
    while (s.length > 3) { out = '.' + s.slice(-3) + out; s = s.slice(0, -3); }
    out = s + out;
    return (neg ? '-' : '') + out;
  }
  function fmtMoney(v) { return '$ ' + fmtInt(v); }
  function fmtPct(v) { return Math.round(v || 0) + '%'; }
  function fmt(kind, v) {
    if (kind === 'money') return fmtMoney(v);
    if (kind === 'pct') return fmtPct(v);
    return fmtInt(v);
  }
  function truncar(s, maxChars) {
    s = String(s);
    return s.length <= maxChars ? s : s.slice(0, maxChars - 1).replace(/\\s+$/, '') + '\\u2026';
  }

  var periods = records.map(function (r) { return r[dateField]; }).filter(Boolean).sort();
  var minPeriod = periods.length ? periods[0] : null;
  var maxPeriod = periods.length ? periods[periods.length - 1] : null;

  var elDesde = document.getElementById('f-desde');
  var elHasta = document.getElementById('f-hasta');
  var elReset = document.getElementById('f-reset');
  var elCoverage = document.getElementById('f-coverage');

  if (minPeriod && elDesde && elHasta) {
    elDesde.min = minPeriod; elDesde.max = maxPeriod; elDesde.value = minPeriod;
    elHasta.min = minPeriod; elHasta.max = maxPeriod; elHasta.value = maxPeriod;
  }

  // Filas sin fecha (dato faltante en el origen) solo se muestran cuando el
  // filtro esta en su rango completo (sin recortar) -- no hay forma de saber
  // si "pertenecen" a un recorte de periodo mas chico.
  function filterRecords(from, to) {
    return records.filter(function (r) {
      var p = r[dateField];
      if (!p) return from === minPeriod && to === maxPeriod;
      return p >= from && p <= to;
    });
  }

  function aggregate(rows, groupBy, aggs) {
    var map = {}, order = [];
    rows.forEach(function (r) {
      var k = r[groupBy];
      if (!(k in map)) { map[k] = {}; map[k][groupBy] = k; order.push(k); }
      aggs.forEach(function (a) {
        if (a.op === 'count') {
          map[k][a.key] = (map[k][a.key] || 0) + 1;
        } else if (a.op === 'sum') {
          map[k][a.key] = (map[k][a.key] || 0) + (Number(r[a.field]) || 0);
        } else if (a.op === 'nunique') {
          map[k].__sets = map[k].__sets || {};
          map[k].__sets[a.key] = map[k].__sets[a.key] || {};
          map[k].__sets[a.key][r[a.field]] = true;
          map[k][a.key] = Object.keys(map[k].__sets[a.key]).length;
        }
      });
    });
    return order.map(function (k) { return map[k]; });
  }

  function sortRows(rows, sortSpec) {
    if (!sortSpec) return rows;
    var key = sortSpec.key, dir = sortSpec.dir === 'asc' ? 1 : -1;
    return rows.slice().sort(function (a, b) {
      var av = a[key], bv = b[key];
      if (av == null) av = dir === 1 ? Infinity : -Infinity;
      if (bv == null) bv = dir === 1 ? Infinity : -Infinity;
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return 0;
    });
  }

  // Puerto 1:1 de bar_chart_svg() (html_report.py) para que el grafico
  // recalculado en JS se vea identico al que se dibujaba en Python.
  function barChartSvg(categorias, valores, opts) {
    opts = opts || {};
    var valueFmt = opts.fmt || 'int';
    var colors = opts.colors;
    var n = categorias.length;
    if (!n) return '<p>Sin datos.</p>';
    var width = Math.max(560, n * 70);
    var padLeft = 50, padRight = 20, padTop = 20, labelH = 46, chartH = opts.height || 260;
    var plotH = chartH - padTop - labelH, plotW = width - padLeft - padRight;
    var maxVal = Math.max.apply(null, valores) || 1;
    var barGap = 10, barW = Math.max(18, (plotW / n) - barGap);

    var gridlines = [], gridLabels = [];
    var steps = 4;
    for (var i = 0; i <= steps; i++) {
      var frac = i / steps;
      var y = padTop + plotH - frac * plotH;
      gridlines.push('<line class="gridline" x1="' + padLeft + '" x2="' + (width - padRight) + '" y1="' + y.toFixed(1) + '" y2="' + y.toFixed(1) + '" />');
      gridLabels.push('<text x="' + (padLeft - 8) + '" y="' + (y + 4).toFixed(1) + '" text-anchor="end">' + esc(fmt(valueFmt, maxVal * frac)) + '</text>');
    }

    var bars = [];
    for (var j = 0; j < n; j++) {
      var cat = categorias[j], val = valores[j];
      var x = padLeft + j * (plotW / n) + ((plotW / n) - barW) / 2;
      var barH = maxVal ? (val / maxVal) * plotH : 0;
      var yTop = padTop + plotH - barH;
      var baselineY = padTop + plotH;
      var color = colors ? (colors[cat] || 'var(--series-1)') : 'var(--series-1)';
      var squaredH = Math.min(4, barH);
      bars.push(
        '<g>' +
        '<rect class="hit" x="' + (x - 4).toFixed(1) + '" y="' + padTop.toFixed(1) + '" width="' + (barW + 8).toFixed(1) + '" height="' + plotH.toFixed(1) + '" data-label="' + esc(cat) + '" data-value="' + esc(fmt(valueFmt, val)) + '" />' +
        '<rect x="' + x.toFixed(1) + '" y="' + yTop.toFixed(1) + '" width="' + barW.toFixed(1) + '" height="' + barH.toFixed(1) + '" rx="4" ry="4" fill="' + color + '" pointer-events="none" />' +
        '<rect x="' + x.toFixed(1) + '" y="' + (baselineY - squaredH).toFixed(1) + '" width="' + barW.toFixed(1) + '" height="' + squaredH.toFixed(1) + '" fill="' + color + '" pointer-events="none" />' +
        '<text x="' + (x + barW / 2).toFixed(1) + '" y="' + (baselineY + 18).toFixed(1) + '" text-anchor="middle" transform="rotate(-40 ' + (x + barW / 2).toFixed(1) + ' ' + (baselineY + 18).toFixed(1) + ')">' + esc(cat) + '</text>' +
        '</g>'
      );
    }
    var baselineY2 = padTop + plotH;
    return '<svg class="chart" viewBox="0 0 ' + width + ' ' + chartH + '" preserveAspectRatio="xMinYMin meet">' +
      gridlines.join('') + gridLabels.join('') +
      '<line class="baseline" x1="' + padLeft + '" x2="' + (width - padRight) + '" y1="' + baselineY2.toFixed(1) + '" y2="' + baselineY2.toFixed(1) + '" />' +
      bars.join('') + '</svg>';
  }

  // Puerto 1:1 de hbar_chart_svg() (html_report.py).
  function hbarChartSvg(categorias, valores, opts) {
    opts = opts || {};
    var valueFmt = opts.fmt || 'int';
    var rowH = opts.rowH || 28;
    var n = categorias.length;
    if (!n) return '<p>Sin datos.</p>';
    var maxLen = 0;
    categorias.forEach(function (c) { maxLen = Math.max(maxLen, String(c).length); });
    var labelW = Math.min(260, Math.max(120, maxLen * 6.4 + 10));
    var maxChars = Math.floor((labelW - 10) / 6.4);
    var padRight = 90, width = 760;
    var plotW = width - labelW - padRight;
    var height = n * rowH + 20;
    var maxVal = Math.max.apply(null, valores) || 1;

    var rows = [];
    for (var i = 0; i < n; i++) {
      var cat = categorias[i], val = valores[i];
      var y = 10 + i * rowH;
      var barW = maxVal ? (val / maxVal) * plotW : 0;
      var etiqueta = truncar(cat, maxChars);
      rows.push(
        '<g>' +
        '<text x="' + (labelW - 10) + '" y="' + (y + rowH / 2 + 4).toFixed(1) + '" text-anchor="end">' + esc(etiqueta) + '</text>' +
        '<rect class="hit" x="0" y="' + y.toFixed(1) + '" width="' + width.toFixed(1) + '" height="' + (rowH - 6).toFixed(1) + '" data-label="' + esc(cat) + '" data-value="' + esc(fmt(valueFmt, val)) + '" />' +
        '<rect x="' + labelW + '" y="' + y.toFixed(1) + '" width="' + Math.max(barW, 2).toFixed(1) + '" height="' + (rowH - 6).toFixed(1) + '" rx="4" ry="4" fill="var(--series-1)" pointer-events="none" />' +
        '<text x="' + (labelW + barW + 8).toFixed(1) + '" y="' + (y + rowH / 2 + 4).toFixed(1) + '" text-anchor="start">' + esc(fmt(valueFmt, val)) + '</text>' +
        '</g>'
      );
    }
    return '<svg class="chart" viewBox="0 0 ' + width + ' ' + height + '" preserveAspectRatio="xMinYMin meet">' + rows.join('') + '</svg>';
  }

  function renderStatTiles(mountId, items) {
    var el = document.getElementById(mountId);
    if (!el) return;
    el.innerHTML = items.map(function (it) {
      var sub = it.sublabel ? '<div class="sublabel">' + esc(it.sublabel) + '</div>' : '';
      return '<div class="stat-tile"><div class="label">' + esc(it.label) + '</div><div class="value">' + esc(it.value) + '</div>' + sub + '</div>';
    }).join('');
  }

  function renderTable(mountId, columns, rows, numericCols) {
    var el = document.getElementById(mountId);
    if (!el) return;
    var head = columns.map(function (c) {
      return '<th class="' + (numericCols.indexOf(c[0]) >= 0 ? 'num' : '') + '">' + esc(c[1]) + '</th>';
    }).join('');
    var body = rows.map(function (r) {
      var cells = columns.map(function (c) {
        var v = r[c[0]];
        if (numericCols.indexOf(c[0]) >= 0) {
          return '<td class="num">' + (v == null ? '' : esc(fmtMoney(v))) + '</td>';
        }
        return '<td>' + (v == null ? '' : esc(v)) + '</td>';
      }).join('');
      return '<tr>' + cells + '</tr>';
    }).join('');
    el.innerHTML = '<table class="report-table"><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table>';
  }

  function renderAll() {
    var from = (elDesde && elDesde.value) || minPeriod;
    var to = (elHasta && elHasta.value) || maxPeriod;
    if (from && to && from > to) { to = from; if (elHasta) elHasta.value = from; }
    var rows = filterRecords(from, to);

    if (spec.statTiles) {
      var items = spec.statTiles.map(function (t) {
        var subset = rows;
        if (t.filter) subset = subset.filter(function (r) { return r[t.filter.field] === t.filter.equals; });
        var val;
        if (t.kind === 'count') {
          val = subset.length;
        } else if (t.kind === 'sum') {
          val = 0; subset.forEach(function (r) { val += Number(r[t.field]) || 0; });
        } else if (t.kind === 'nunique') {
          var seen = {}; subset.forEach(function (r) { seen[r[t.field]] = true; });
          val = Object.keys(seen).length;
        } else if (t.kind === 'ratio') {
          var num = 0, den = 0;
          subset.forEach(function (r) { num += Number(r[t.num]) || 0; den += Number(r[t.den]) || 0; });
          val = den ? (num / den) * 100 : 0;
        }
        return { label: t.label, value: fmt(t.fmt, val) };
      });
      renderStatTiles('stat-tiles', items);
    }

    (spec.charts || []).forEach(function (c) {
      var agg = aggregate(rows, c.groupBy, [{ key: 'value', op: c.agg, field: c.field }]);
      if (c.groupBy === dateField) {
        agg.sort(function (a, b) { return String(a[c.groupBy]).localeCompare(String(b[c.groupBy])); });
      } else if (c.order) {
        var ordered = [];
        c.order.forEach(function (o) { ordered = ordered.concat(agg.filter(function (a) { return a[c.groupBy] === o; })); });
        var rest = agg.filter(function (a) { return c.order.indexOf(a[c.groupBy]) === -1; });
        agg = ordered.concat(rest);
      } else {
        agg.sort(function (a, b) { return b.value - a.value; });
      }
      if (c.topN) agg = agg.slice(0, c.topN);
      var cats = agg.map(function (a) { return a[c.groupBy]; });
      var vals = agg.map(function (a) { return a.value; });
      var svg = c.type === 'hbar' ? hbarChartSvg(cats, vals, { fmt: c.fmt }) : barChartSvg(cats, vals, { fmt: c.fmt, colors: c.colors });
      var el = document.getElementById(c.mount);
      if (el) el.innerHTML = svg;
    });

    (spec.tables || []).forEach(function (t) {
      var tableRows = t.groupBy ? sortRows(aggregate(rows, t.groupBy, t.aggs), t.sort) : sortRows(rows, t.sort);
      renderTable(t.mount, t.columns, tableRows, t.numericCols || []);
    });

    if (elCoverage) {
      var totalTxt = minPeriod ? (minPeriod + ' a ' + maxPeriod) : 'sin fechas';
      var showTxt = (from && to) ? (from + ' a ' + to) : 'sin fechas';
      elCoverage.innerHTML = 'Datos disponibles: <strong>' + esc(totalTxt) + '</strong> &middot; Mostrando: <strong>' + esc(showTxt) + '</strong> (' + rows.length + ' registros)';
    }
  }

  if (elDesde) elDesde.addEventListener('change', renderAll);
  if (elHasta) elHasta.addEventListener('change', renderAll);
  if (elReset) elReset.addEventListener('click', function () {
    if (elDesde) elDesde.value = minPeriod;
    if (elHasta) elHasta.value = maxPeriod;
    renderAll();
  });

  renderAll();
})();
"""


def dashboard_bundle(records: list, spec: dict) -> str:
    """JSON de datos + spec + motor JS. Se agrega una sola vez por pagina,
    despues de todos los mounts (filter_bar_html/stat_tiles_mount/mount)."""
    return (
        f'<script type="application/json" id="report-records">{json.dumps(records, ensure_ascii=False)}</script>\n'
        f'<script type="application/json" id="report-spec">{json.dumps(spec, ensure_ascii=False)}</script>\n'
        f'<script>{DASHBOARD_JS}</script>'
    )
