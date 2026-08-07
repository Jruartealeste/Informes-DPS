"""
Utilidades compartidas para generar informes HTML autocontenidos: un solo
archivo, sin CDN ni dependencias externas, pensado para abrir con doble
click y usar "Imprimir > Guardar como PDF" del navegador. Cada modulo arma
su propio generate_html_report.py llamando a estas funciones y sobreescribe
siempre la misma ruta de salida (no acumula archivos).
"""
import json
import uuid
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

# Boton claro/oscuro manual (independiente del prefers-color-scheme del SO).
# El icono se resuelve solo con CSS (ver .theme-toggle mas abajo en PAGE_CSS)
# segun el tema activo -- no depende de que el JS corra para verse correcto.
_TOGGLE_ICON_STROKE = 'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'
SUN_ICON_SVG = (
    '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
    f'<circle cx="12" cy="12" r="4.5" {_TOGGLE_ICON_STROKE}/>'
    f'<path d="M12 2.5v2.5M12 19v2.5M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M2.5 12h2.5M19 12h2.5M4.6 19.4l1.8-1.8M17.6 6.4l1.8-1.8" {_TOGGLE_ICON_STROKE}/>'
    "</svg>"
)
MOON_ICON_SVG = (
    '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
    f'<path d="M20 14.5A8.5 8.5 0 019.5 4a8.5 8.5 0 1010.5 10.5z" {_TOGGLE_ICON_STROKE}/>'
    "</svg>"
)
THEME_TOGGLE_BTN = (
    '<button type="button" class="theme-toggle no-print" data-theme-toggle '
    'title="Cambiar tema claro/oscuro" aria-label="Cambiar tema claro/oscuro">'
    f'<span class="icon icon-sun">{SUN_ICON_SVG}</span>'
    f'<span class="icon icon-moon">{MOON_ICON_SVG}</span>'
    "</button>"
)

PAGE_CSS = """
:root {
  color-scheme: light;
  --surface-1:      #fcfcfb;
  --page-plane:     #f1f0eb;
  --text-primary:   #0b0b0b;
  --text-secondary: #52514e;
  --text-muted:     #898781;
  --gridline:       #e1e0d9;
  --baseline:       #c3c2b7;
  --border:         rgba(11,11,11,0.10);
  --brand:          #f63200;
  --brand-tint:     rgba(246,50,0,0.08);
  --series-1:       #f63200;
}
/* El tema por defecto sigue el prefers-color-scheme del SO. data-theme en
   <html> (seteado por THEME_INIT_JS/THEME_JS al togglear el boton) fuerza
   un tema explicito que gana por sobre la preferencia del SO en cualquier
   direccion -- por eso el bloque de "dark" de mas abajo se excluye con
   :not([data-theme="light"]) en vez de repetir logica en JS. */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface-1:      #1a1a19;
    --page-plane:     #0d0d0d;
    --text-primary:   #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted:     #898781;
    --gridline:       #2c2c2a;
    --baseline:       #383835;
    --border:         rgba(255,255,255,0.10);
    --brand-tint:     rgba(255,122,69,0.14);
    --series-1:       #ff7a45;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface-1:      #1a1a19;
  --page-plane:     #0d0d0d;
  --text-primary:   #ffffff;
  --text-secondary: #c3c2b7;
  --text-muted:     #898781;
  --gridline:       #2c2c2a;
  --baseline:       #383835;
  --border:         rgba(255,255,255,0.10);
  --brand-tint:     rgba(255,122,69,0.14);
  --series-1:       #ff7a45;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Public Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  background: var(--page-plane);
  color: var(--text-primary);
  font-size: 14px;
}
.page {
  max-width: 1440px;
  margin: 0 auto;
  padding: 32px 40px 64px;
}
/* Grid de secciones: por defecto cada .report-section ocupa una columna
   (quedan de a 2 lado a lado en pantallas anchas); .report-section--full
   (charts de serie temporal, comparaciones y tablas) fuerza el ancho
   completo. minmax(480px,1fr) esta calibrado para que .page a 1440px de
   max-width resuelva siempre en exactamente 2 columnas, no 3 -- asi los
   pares de charts "half" (Estado/Tipo, Proveedores/Clientes, etc.) quedan
   prolijos en vez de dejar un hueco vacio en la fila. */
.section-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
  gap: 20px;
  align-items: start;
}
.section-grid > .stat-grid,
.section-grid > .filter-bar,
.section-grid > .report-section--full {
  grid-column: 1 / -1;
}
.section-grid > .report-section { margin-bottom: 0; }
@media print {
  .section-grid { display: block; }
  .section-grid > .report-section { margin-bottom: 20px; }
}
header.report-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 32px;
  padding-bottom: 24px;
  border-bottom: 2px solid var(--text-primary);
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
  color: var(--brand);
}
header.report-header .brand-logo svg {
  display: block;
  width: 100%;
  height: auto;
}
header.report-header .eyebrow {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin: 0 0 6px;
}
header.report-header h1 {
  font-size: 27px;
  font-weight: 700;
  letter-spacing: -0.01em;
  margin: 0 0 4px;
}
header.report-header .meta {
  color: var(--text-secondary);
  font-size: 13px;
}
.header-actions { display: flex; align-items: center; gap: 8px; }

button.print-btn {
  border: 1px solid var(--border);
  background: var(--surface-1);
  color: var(--text-primary);
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
}
button.print-btn:hover { background: var(--page-plane); border-color: var(--brand); color: var(--brand); }

button.theme-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border: 1px solid var(--border);
  background: var(--surface-1);
  color: var(--text-primary);
  border-radius: 8px;
  cursor: pointer;
}
button.theme-toggle:hover { background: var(--page-plane); border-color: var(--brand); color: var(--brand); }
button.theme-toggle .icon { width: 18px; height: 18px; display: block; }
button.theme-toggle .icon svg { display: block; width: 100%; height: 100%; }
/* Por defecto (sin data-theme, SO en claro) se ve el sol -- clickear pasa a
   oscuro. El icono espeja el tema activo, no cambia con JS: ver el bloque
   :not([data-theme="light"]) / [data-theme="dark"] de mas arriba. */
button.theme-toggle .icon-moon { display: none; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) button.theme-toggle .icon-sun { display: none; }
  :root:not([data-theme="light"]) button.theme-toggle .icon-moon { display: block; }
}
:root[data-theme="dark"] button.theme-toggle .icon-sun { display: none; }
:root[data-theme="dark"] button.theme-toggle .icon-moon { display: block; }

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 28px;
}
.stat-tile {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px 18px;
}
.stat-tile .label {
  display: block;
  font-size: 13px;
  font-weight: 400;
  color: var(--text-secondary);
  margin-bottom: 6px;
}
.stat-tile .value {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.01em;
  font-variant-numeric: tabular-nums;
}
.stat-tile .sublabel {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 6px;
}

section.report-section {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
}
section.report-section h2 {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.01em;
  margin: 0 0 14px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--gridline);
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
  padding: 10px 14px;
  border-bottom: 1px solid var(--gridline);
}
table.report-table th {
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 11px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border-bottom: 1px solid var(--baseline);
}
table.report-table td.num, table.report-table th.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
table.report-table tr { break-inside: avoid; }
table.report-table tbody tr:hover { background: var(--page-plane); }
table.report-table th.sortable { cursor: pointer; user-select: none; }
table.report-table th.sortable:hover { color: var(--text-primary); }
table.report-table tr.row-hidden { display: none; }

/* Tabla agrupada con detalle desplegable (ver hr.dashboard_bundle /
   DASHBOARD_JS renderGroupedTable) -- fila resumen (una por grupo,
   clickeable) + fila de detalle (tabla anidada, oculta hasta expandir). */
tr.group-row { cursor: pointer; }
tr.group-row:hover { background: var(--page-plane); }
tr.group-row td.group-toggle { width: 20px; text-align: center; color: var(--text-muted); }
tr.group-detail-row { display: none; }
tr.group-detail-row.open { display: table-row; }
tr.group-detail-row > td { padding: 0 0 14px 14px; border-bottom: 1px solid var(--gridline); }
table.report-table--nested { font-size: 12px; background: var(--page-plane); border-radius: 8px; }
table.report-table--nested th, table.report-table--nested td { padding: 6px 10px; }

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
  /* Imprimir siempre en claro, sin importar el tema elegido en pantalla --
     el selector repite [data-theme] para igualar la especificidad de los
     bloques de arriba ({dark via prefers-color-scheme} y :root[data-theme]);
     como este bloque va despues en el archivo, gana el empate. */
  :root, :root[data-theme="dark"], :root[data-theme="light"] {
    color-scheme: light;
    --surface-1: #ffffff;
    --page-plane: #ffffff;
    --text-primary: #0b0b0b;
    --text-secondary: #3a3936;
    --text-muted: #6a6963;
    --gridline: #d8d7d0;
    --baseline: #9a988f;
    --border: rgba(11,11,11,0.15);
    --series-1: #f63200;
  }
  .no-print { display: none !important; }
  .page { max-width: none; padding: 0; }
  section.report-section { break-inside: avoid; border: 1px solid #ddd; box-shadow: none; }
  .stat-tile { box-shadow: none; }
  table.report-table tr { break-inside: avoid; }
  thead { display: table-header-group; }
  /* El tope de TABLE_LIMIT filas (ver DASHBOARD_JS) es una limitacion de
     pantalla: al imprimir/guardar PDF siempre va el detalle completo. */
  table.report-table tr.row-hidden { display: table-row; }
  /* Mismo criterio para la tabla agrupada: el detalle desplegable de cada
     grupo va siempre visible al imprimir, sin importar que quedo
     colapsado en pantalla. */
  tr.group-detail-row { display: table-row !important; }
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
.filter-bar .period-select {
  border: 1px solid var(--border);
  background: var(--page-plane);
  color: var(--text-primary);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 13px;
  font-family: inherit;
}
.filter-bar .period-select:focus { outline: none; border-color: var(--brand); }
.filter-bar button {
  border: 1px solid var(--border);
  background: var(--page-plane);
  color: var(--text-primary);
  border-radius: 6px;
  padding: 5px 12px;
  font-size: 13px;
  cursor: pointer;
}
.filter-bar button:hover { background: var(--surface-1); border-color: var(--brand); }
.filter-coverage { color: var(--text-muted); }
.filter-coverage strong { color: var(--text-primary); font-weight: 600; }

.chart-toolbar { display: flex; justify-content: flex-end; margin-bottom: 10px; }
.segmented {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 2px;
  background: var(--page-plane);
}
.segmented button {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
}
.segmented button.active { background: var(--surface-1); color: var(--brand); font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,0.08); }

.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.table-search {
  border: 1px solid var(--border);
  background: var(--page-plane);
  color: var(--text-primary);
  border-radius: 6px;
  padding: 5px 10px;
  font-size: 13px;
  font-family: inherit;
  min-width: 220px;
}
.table-search:focus { outline: none; border-color: var(--brand); }
.table-count { color: var(--text-muted); font-size: 12px; white-space: nowrap; }
.table-more { margin-top: 10px; }
.table-more-btn {
  display: block;
  width: 100%;
  text-align: left;
  border: 1px solid var(--border);
  background: var(--page-plane);
  color: var(--text-secondary);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}
.table-more-btn:hover { border-color: var(--brand); color: var(--brand); background: var(--surface-1); }
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

# THEME_INIT_JS corre sincronico en <head>, antes de pintar body, para poner
# el data-theme guardado (si el usuario ya lo eligio antes) sin flash de
# color equivocado. THEME_JS (bottom de body, junto a TOOLTIP_JS) maneja el
# click del boton y la sincronizacion con el iframe del dashboard_shell via
# postMessage -- no via localStorage compartido, porque cada archivo
# informe_<modulo>.html/dashboard.html puede quedar en un origen file://
# distinto segun el navegador y localStorage no cruza esa frontera de forma
# confiable.
THEME_INIT_JS = """
(function () {
  try {
    var t = localStorage.getItem('aleste-theme');
    if (t === 'light' || t === 'dark') document.documentElement.setAttribute('data-theme', t);
  } catch (e) {}
})();
"""

THEME_JS = """
(function () {
  var STORAGE_KEY = 'aleste-theme';
  var root = document.documentElement;

  function currentTheme() {
    var explicit = root.getAttribute('data-theme');
    if (explicit === 'light' || explicit === 'dark') return explicit;
    var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    return prefersDark ? 'dark' : 'light';
  }

  function setTheme(theme, opts) {
    opts = opts || {};
    root.setAttribute('data-theme', theme);
    if (opts.persist !== false) {
      try { localStorage.setItem(STORAGE_KEY, theme); } catch (e) {}
    }
    if (opts.propagate !== false) {
      var frame = document.getElementById('shell-frame');
      if (frame && frame.contentWindow) {
        try { frame.contentWindow.postMessage({ type: 'aleste-theme', theme: theme }, '*'); } catch (e) {}
      }
      if (window.parent && window.parent !== window) {
        try { window.parent.postMessage({ type: 'aleste-theme', theme: theme }, '*'); } catch (e) {}
      }
    }
  }

  setTheme(currentTheme(), { persist: false, propagate: false });

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-theme-toggle]');
    if (!btn) return;
    setTheme(currentTheme() === 'dark' ? 'light' : 'dark');
  });

  window.addEventListener('message', function (e) {
    var data = e.data;
    if (data && data.type === 'aleste-theme' && (data.theme === 'light' || data.theme === 'dark')) {
      // No persistir: esto es al shell empujando SU tema al iframe que
      // recien cargo (o viceversa), no una eleccion del usuario en este
      // documento puntual -- persistirlo pisaba para siempre el "seguir al
      // SO" del informe standalone con lo ultimo que mostro el shell.
      setTheme(data.theme, { persist: false, propagate: false });
    }
  });

  // dashboard_shell: al cambiar de modulo (nuevo src en el iframe) le avisa
  // el tema activo al informe recien cargado, que arranca sin saberlo.
  var shellFrame = document.getElementById('shell-frame');
  if (shellFrame) {
    shellFrame.addEventListener('load', function () {
      try { shellFrame.contentWindow.postMessage({ type: 'aleste-theme', theme: currentTheme() }, '*'); } catch (e) {}
    });
  }
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
<script>{THEME_INIT_JS}</script>
</head>
<body>
<div class="page">
  <header class="report-header">
    <div class="brand">
      <div class="brand-logo">{LOGO_SVG}</div>
      <div>
        <div class="eyebrow">{escape(subtitulo)}</div>
        <h1>{escape(titulo)}</h1>
        <div class="meta">Generado: {generado}</div>
      </div>
    </div>
    <div class="header-actions no-print">
      {THEME_TOGGLE_BTN}
      <button class="print-btn" onclick="window.print()">Imprimir / Guardar PDF</button>
    </div>
  </header>
  <div class="section-grid">{secciones_html}</div>
  <footer class="report-footer">Informe generado automaticamente desde advertys.db. Volve a correr el script para reflejar el ultimo export.</footer>
</div>
<div id="viz-tooltip"></div>
<script>{TOOLTIP_JS}{THEME_JS}</script>
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


def section(titulo: str, contenido_html: str, *, wide: bool = False) -> str:
    """`wide=True` fuerza ancho completo dentro del grid de 2 columnas de
    .section-grid -- usalo para series temporales, comparaciones de periodo
    y tablas; dejalo en False (default) para charts categoricos chicos que
    conviene mostrar de a pares lado a lado."""
    css_class = "report-section report-section--full" if wide else "report-section"
    return f"""<section class="{css_class}">
    <h2>{escape(titulo)}</h2>
    {contenido_html}
  </section>"""


def _text_w(texto: str, px_per_char: float = 6.5) -> float:
    """Ancho aproximado de un string en el font-size chico (11px) que usan
    los charts -- suficiente para dimensionar padding, no para layout exacto."""
    return len(str(texto)) * px_per_char


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
    max_val = max(valores) or 1
    steps = 4
    grid_values = [value_fmt(max_val * (i / steps)) for i in range(steps + 1)]
    # pad_left se dimensiona segun el label mas ancho del eje Y (montos
    # grandes formateados) para que el numero no se salga del viewBox por
    # izquierda -- antes era un valor fijo (50) y con "$ 1.234.567" el texto
    # colgaba fuera de la card.
    pad_left = max(50, max(_text_w(v) for v in grid_values) + 18)
    pad_right, pad_top = 20, 20
    label_h = 34
    chart_h = height
    plot_h = chart_h - pad_top - label_h
    plot_w = width - pad_left - pad_right

    bar_gap = 10
    bar_w = max(18, (plot_w / n) - bar_gap)
    slot_w = plot_w / n
    max_chars = max(3, int(slot_w / 6.2))

    gridlines = []
    grid_labels = []
    for i, txt in enumerate(grid_values):
        y = pad_top + plot_h - (i / steps) * plot_h
        gridlines.append(f'<line class="gridline" x1="{pad_left}" x2="{width - pad_right}" y1="{y:.1f}" y2="{y:.1f}" />')
        grid_labels.append(f'<text x="{pad_left - 8}" y="{y + 4:.1f}" text-anchor="end">{txt}</text>')

    # Gradiente vertical por barra (opaco arriba, mas suave abajo) en vez de
    # relleno solido plano -- da profundidad sin cambiar la paleta.
    chart_uid = uuid.uuid4().hex[:8]
    bars = []
    defs = []
    for i, (cat, val) in enumerate(zip(categorias, valores)):
        x = pad_left + i * (plot_w / n) + ((plot_w / n) - bar_w) / 2
        bar_h = (val / max_val) * plot_h if max_val else 0
        y = pad_top + plot_h - bar_h
        baseline_y = pad_top + plot_h
        color = colors[i] if colors else "var(--series-1)"
        grad_id = f"bg-{chart_uid}-{i}"
        defs.append(
            f'<linearGradient id="{grad_id}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" style="stop-color:{color};stop-opacity:0.95" />'
            f'<stop offset="100%" style="stop-color:{color};stop-opacity:0.55" />'
            f'</linearGradient>'
        )
        squared_h = min(4, bar_h)
        etiqueta = _truncar(str(cat), max_chars)
        bars.append(f"""<g>
      <rect class="hit" x="{x - 4:.1f}" y="{pad_top:.1f}" width="{bar_w + 8:.1f}" height="{plot_h:.1f}" data-label="{escape(str(cat))}" data-value="{escape(value_fmt(val))}" />
      <rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="4" ry="4" fill="url(#{grad_id})" pointer-events="none" />
      <rect x="{x:.1f}" y="{baseline_y - squared_h:.1f}" width="{bar_w:.1f}" height="{squared_h:.1f}" fill="{color}" pointer-events="none" />
      <text x="{x + bar_w / 2:.1f}" y="{baseline_y + 18:.1f}" text-anchor="middle">{escape(etiqueta)}</text>
    </g>""")

    baseline_y = pad_top + plot_h
    return f"""<svg class="chart" viewBox="0 0 {width} {chart_h}" preserveAspectRatio="xMinYMin meet">
    <defs>{''.join(defs)}</defs>
    {''.join(gridlines)}
    {''.join(grid_labels)}
    <line class="baseline" x1="{pad_left}" x2="{width - pad_right}" y1="{baseline_y:.1f}" y2="{baseline_y:.1f}" />
    {''.join(bars)}
  </svg>"""


def _truncar(texto: str, max_chars: int) -> str:
    return texto if len(texto) <= max_chars else texto[: max_chars - 1].rstrip() + "…"


def hbar_chart_svg(categorias, valores, *, value_fmt=None, row_h=28, height=None):
    """Grafico de barras horizontales, para rankings (top N por categoria).
    `height` (opcional) fuerza el alto total del viewBox -- usalo para que
    quede del mismo tamano que un chart vecino (bar/line) en un par lado a
    lado, cuando el numero de filas no llega a llenar esa altura."""
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
    height = max(height or 0, n * row_h + 20)
    max_val = max(valores) or 1

    grad_id = f"hbg-{uuid.uuid4().hex[:8]}"
    rows = []
    for i, (cat, val) in enumerate(zip(categorias, valores)):
        y = 10 + i * row_h
        bar_w = (val / max_val) * plot_w if max_val else 0
        etiqueta = _truncar(str(cat), max_chars)
        rows.append(f"""<g>
      <text x="{label_w - 10}" y="{y + row_h / 2 + 4:.1f}" text-anchor="end">{escape(etiqueta)}</text>
      <rect class="hit" x="0" y="{y:.1f}" width="{width:.1f}" height="{row_h - 6:.1f}" data-label="{escape(str(cat))}" data-value="{escape(value_fmt(val))}" />
      <rect x="{label_w}" y="{y:.1f}" width="{max(bar_w, 2):.1f}" height="{row_h - 6:.1f}" rx="4" ry="4" fill="url(#{grad_id})" pointer-events="none" />
      <text x="{label_w + bar_w + 8:.1f}" y="{y + row_h / 2 + 4:.1f}" text-anchor="start">{value_fmt(val)}</text>
    </g>""")

    return f"""<svg class="chart" viewBox="0 0 {width} {height}" preserveAspectRatio="xMinYMin meet">
    <defs>
      <linearGradient id="{grad_id}" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" style="stop-color:var(--series-1);stop-opacity:0.95" />
        <stop offset="100%" style="stop-color:var(--series-1);stop-opacity:0.6" />
      </linearGradient>
    </defs>
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


def period_compare_mount(mount_id: str) -> str:
    """Mount para un chart de tipo 'period_compare' (spec.charts): barras
    agrupadas por mes/trimestre, una serie por anio. Trae un toggle
    Mensual/Trimestral que solo repinta ese chart puntual (ver DASHBOARD_JS,
    renderPeriodCompare) -- no dispara el recalculo completo del filtro."""
    return f"""<div class="chart-toolbar no-print">
    <div class="segmented" data-toggle-for="{mount_id}">
      <button type="button" class="active" data-granularity="month">Mensual</button>
      <button type="button" data-granularity="quarter">Trimestral</button>
    </div>
  </div>
  <div id="{mount_id}"></div>"""


_MESES = [
    ("01", "Ene"), ("02", "Feb"), ("03", "Mar"), ("04", "Abr"),
    ("05", "May"), ("06", "Jun"), ("07", "Jul"), ("08", "Ago"),
    ("09", "Sep"), ("10", "Oct"), ("11", "Nov"), ("12", "Dic"),
]


def filter_bar_html() -> str:
    """Barra de filtro de periodo (Desde/Hasta editable + texto de cobertura).
    Cada limite es un par de <select> Mes/Anio en vez de <input type="month">
    nativo: el spinner de anio del input nativo obliga a clickear de a un
    anio por vez (inutilizable en Windows/Chrome con datos de varios anios,
    reportado por Javier). El <select> de Mes es fijo (1-12); el de Anio se
    puebla dinamicamente en DASHBOARD_JS con los anios presentes en los
    datos. Van en no-print asi no aparecen al imprimir/PDF, pero el texto de
    cobertura ("Datos disponibles" / "Mostrando") queda visible en el
    impreso para que quede claro que periodo contempla el informe."""
    meses = "".join(f'<option value="{v}">{l}</option>' for v, l in _MESES)
    return f"""<div class="filter-bar">
    <div class="filter-controls no-print">
      <label>Desde
        <select class="period-select" id="f-desde-mes">{meses}</select>
        <select class="period-select" id="f-desde-anio"></select>
      </label>
      <label>Hasta
        <select class="period-select" id="f-hasta-mes">{meses}</select>
        <select class="period-select" id="f-hasta-anio"></select>
      </label>
      <button type="button" id="f-reset">Ver todo el periodo</button>
    </div>
    <div class="filter-coverage" id="f-coverage">Calculando periodos disponibles...</div>
  </div>"""


def category_filters_html(filters: list[dict]) -> str:
    """Barra de filtros categoricos (dropdown "Todos" + valores unicos del
    dato, ej. Cliente/Proveedor/N° Recibo) -- complementa el filtro de
    periodo de filter_bar_html(). Las opciones de cada <select> se pueblan
    en DASHBOARD_JS con los valores distintos presentes en `records` (no
    hace falta pasarlos desde Python). `filters` es una lista de dicts
    {"field": "...", "label": "..."} -- mismo formato que spec["categoryFilters"]
    que lee DASHBOARD_JS para saber que filtrar y por que campo.

    Igual que el filtro de periodo, actua sobre TODO el informe (stat tiles,
    charts y tablas), a diferencia del buscador en vivo de cada tabla
    (`renderTable`) que solo filtra esa tabla puntual."""
    if not filters:
        return ""
    campos = "".join(
        f'<label>{escape(f["label"])}'
        f'<select class="period-select cat-filter-select" id="f-cat-{f["field"]}" data-field="{f["field"]}">'
        f'<option value="">Todos</option></select></label>'
        for f in filters
    )
    return f"""<div class="filter-bar cat-filter-bar no-print">
    <div class="filter-controls">
      {campos}
    </div>
  </div>"""


DASHBOARD_JS = """
(function () {
  var recordsEl = document.getElementById('report-records');
  var specEl = document.getElementById('report-spec');
  if (!recordsEl || !specEl) return;
  var records = JSON.parse(recordsEl.textContent);
  var spec = JSON.parse(specEl.textContent);
  var dateField = spec.dateField;
  var tableState = {};
  var groupedTableState = {};
  var TABLE_LIMIT = 50;
  var lastFilteredRows = [];
  var lastFilterRange = { from: null, to: null };
  var prefersDark = !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
  // El filtro de periodo se persiste por archivo (location.pathname) para
  // sobrevivir a un reload del iframe -- el shell del dashboard (SHELL_JS)
  // recarga el iframe entero cada vez que se cambia de pestana y se vuelve,
  // lo que reseteaba el filtro a "todo el periodo" (reportado por Javier).
  var FILTER_KEY = 'aleste-filtro:' + location.pathname;

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
  function textW(s, pxPerChar) { return String(s).length * (pxPerChar || 6.5); }

  var periods = records.map(function (r) { return r[dateField]; }).filter(Boolean).sort();
  var minPeriod = periods.length ? periods[0] : null;
  var maxPeriod = periods.length ? periods[periods.length - 1] : null;

  var elDesdeMes = document.getElementById('f-desde-mes');
  var elDesdeAnio = document.getElementById('f-desde-anio');
  var elHastaMes = document.getElementById('f-hasta-mes');
  var elHastaAnio = document.getElementById('f-hasta-anio');
  var elReset = document.getElementById('f-reset');
  var elCoverage = document.getElementById('f-coverage');

  // Filtros categoricos (Cliente/Proveedor/N° Recibo/etc, ver
  // hr.category_filters_html): un <select> "Todos" + valores unicos del
  // campo, poblado desde `records` (no hace falta pasarlos desde Python).
  // A diferencia del buscador en vivo de cada tabla (solo esa tabla),
  // estos filtros actuan sobre statTiles/charts/tablas por igual, como el
  // filtro de periodo.
  var categoryFilters = spec.categoryFilters || [];
  var categoryFilterEls = categoryFilters.map(function (f) {
    var sel = document.getElementById('f-cat-' + f.field);
    if (!sel) return null;
    var valores = {};
    records.forEach(function (r) {
      var v = r[f.field];
      if (v !== null && v !== undefined && v !== '') valores[v] = true;
    });
    var opciones = Object.keys(valores).sort(function (a, b) { return String(a).localeCompare(String(b), 'es'); });
    opciones.forEach(function (v) {
      var opt = document.createElement('option');
      opt.value = v; opt.textContent = v;
      sel.appendChild(opt);
    });
    sel.addEventListener('change', renderAll);
    return { field: f.field, el: sel };
  }).filter(Boolean);

  function applyCategoryFilters(rows) {
    categoryFilterEls.forEach(function (cf) {
      if (!cf.el.value) return;
      rows = rows.filter(function (r) { return String(r[cf.field]) === cf.el.value; });
    });
    return rows;
  }

  function populateYearSelect(sel, years, selected) {
    if (!sel) return;
    sel.innerHTML = years.map(function (y) { return '<option value="' + y + '">' + y + '</option>'; }).join('');
    sel.value = selected;
  }
  function getPeriod(mesEl, anioEl) {
    if (!mesEl || !anioEl || !anioEl.value) return null;
    return anioEl.value + '-' + mesEl.value;
  }
  function setPeriod(mesEl, anioEl, period) {
    if (!mesEl || !anioEl || !period) return;
    anioEl.value = period.slice(0, 4);
    mesEl.value = period.slice(5, 7);
  }

  if (minPeriod) {
    var years = [];
    for (var y = parseInt(minPeriod.slice(0, 4), 10); y <= parseInt(maxPeriod.slice(0, 4), 10); y++) years.push(String(y));
    populateYearSelect(elDesdeAnio, years, minPeriod.slice(0, 4));
    populateYearSelect(elHastaAnio, years, maxPeriod.slice(0, 4));

    var initialFrom = minPeriod, initialTo = maxPeriod;
    var storedFilter = null;
    try { storedFilter = JSON.parse(localStorage.getItem(FILTER_KEY) || 'null'); } catch (e) {}
    if (storedFilter && storedFilter.from && storedFilter.to &&
        storedFilter.from >= minPeriod && storedFilter.from <= maxPeriod &&
        storedFilter.to >= minPeriod && storedFilter.to <= maxPeriod &&
        storedFilter.from <= storedFilter.to) {
      initialFrom = storedFilter.from;
      initialTo = storedFilter.to;
    }
    setPeriod(elDesdeMes, elDesdeAnio, initialFrom);
    setPeriod(elHastaMes, elHastaAnio, initialTo);
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

  var gradSeq = 0;

  // Puerto 1:1 de bar_chart_svg() (html_report.py) para que el grafico
  // recalculado en JS se vea identico al que se dibujaba en Python.
  function barChartSvg(categorias, valores, opts) {
    opts = opts || {};
    var valueFmt = opts.fmt || 'int';
    var colors = opts.colors;
    var n = categorias.length;
    if (!n) return '<p>Sin datos.</p>';
    var width = Math.max(560, n * 70);
    var maxVal = Math.max.apply(null, valores) || 1;
    var steps = 4;
    var gridValues = [];
    for (var i = 0; i <= steps; i++) gridValues.push(fmt(valueFmt, maxVal * (i / steps)));
    var maxLabelW = 0;
    gridValues.forEach(function (v) { maxLabelW = Math.max(maxLabelW, textW(v)); });
    var padLeft = Math.max(50, maxLabelW + 18);
    var padRight = 20, padTop = 20, labelH = 34, chartH = opts.height || 260;
    var plotH = chartH - padTop - labelH, plotW = width - padLeft - padRight;
    var barGap = 10, barW = Math.max(18, (plotW / n) - barGap);
    var maxChars = Math.max(3, Math.floor((plotW / n) / 6.2));

    var gridlines = [], gridLabels = [];
    for (var i2 = 0; i2 <= steps; i2++) {
      var y = padTop + plotH - (i2 / steps) * plotH;
      gridlines.push('<line class="gridline" x1="' + padLeft + '" x2="' + (width - padRight) + '" y1="' + y.toFixed(1) + '" y2="' + y.toFixed(1) + '" />');
      gridLabels.push('<text x="' + (padLeft - 8) + '" y="' + (y + 4).toFixed(1) + '" text-anchor="end">' + esc(gridValues[i2]) + '</text>');
    }

    var chartUid = 'c' + (gradSeq++);
    var bars = [], defs = [];
    for (var j = 0; j < n; j++) {
      var cat = categorias[j], val = valores[j];
      var x = padLeft + j * (plotW / n) + ((plotW / n) - barW) / 2;
      var barH = maxVal ? (val / maxVal) * plotH : 0;
      var yTop = padTop + plotH - barH;
      var baselineY = padTop + plotH;
      var color = colors ? (colors[cat] || 'var(--series-1)') : 'var(--series-1)';
      var gradId = 'bg-' + chartUid + '-' + j;
      defs.push('<linearGradient id="' + gradId + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" style="stop-color:' + color + ';stop-opacity:0.95" /><stop offset="100%" style="stop-color:' + color + ';stop-opacity:0.55" /></linearGradient>');
      var squaredH = Math.min(4, barH);
      var etiqueta = truncar(cat, maxChars);
      bars.push(
        '<g>' +
        '<rect class="hit" x="' + (x - 4).toFixed(1) + '" y="' + padTop.toFixed(1) + '" width="' + (barW + 8).toFixed(1) + '" height="' + plotH.toFixed(1) + '" data-label="' + esc(cat) + '" data-value="' + esc(fmt(valueFmt, val)) + '" />' +
        '<rect x="' + x.toFixed(1) + '" y="' + yTop.toFixed(1) + '" width="' + barW.toFixed(1) + '" height="' + barH.toFixed(1) + '" rx="4" ry="4" fill="url(#' + gradId + ')" pointer-events="none" />' +
        '<rect x="' + x.toFixed(1) + '" y="' + (baselineY - squaredH).toFixed(1) + '" width="' + barW.toFixed(1) + '" height="' + squaredH.toFixed(1) + '" fill="' + color + '" pointer-events="none" />' +
        '<text x="' + (x + barW / 2).toFixed(1) + '" y="' + (baselineY + 18).toFixed(1) + '" text-anchor="middle">' + esc(etiqueta) + '</text>' +
        '</g>'
      );
    }
    var baselineY2 = padTop + plotH;
    return '<svg class="chart" viewBox="0 0 ' + width + ' ' + chartH + '" preserveAspectRatio="xMinYMin meet">' +
      '<defs>' + defs.join('') + '</defs>' +
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
    var height = Math.max(opts.height || 0, n * rowH + 20);
    var maxVal = Math.max.apply(null, valores) || 1;

    var gradId = 'hbg-' + (gradSeq++);
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
        '<rect x="' + labelW + '" y="' + y.toFixed(1) + '" width="' + Math.max(barW, 2).toFixed(1) + '" height="' + (rowH - 6).toFixed(1) + '" rx="4" ry="4" fill="url(#' + gradId + ')" pointer-events="none" />' +
        '<text x="' + (labelW + barW + 8).toFixed(1) + '" y="' + (y + rowH / 2 + 4).toFixed(1) + '" text-anchor="start">' + esc(fmt(valueFmt, val)) + '</text>' +
        '</g>'
      );
    }
    var defsHtml = '<defs><linearGradient id="' + gradId + '" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" style="stop-color:var(--series-1);stop-opacity:0.95" /><stop offset="100%" style="stop-color:var(--series-1);stop-opacity:0.6" /></linearGradient></defs>';
    return '<svg class="chart" viewBox="0 0 ' + width + ' ' + height + '" preserveAspectRatio="xMinYMin meet">' + defsHtml + rows.join('') + '</svg>';
  }

  // Linea/area para tendencia en el tiempo (una sola serie). Rotula todos los
  // puntos como eje (igual que barChartSvg) pero solo pone texto de etiqueta
  // cada N puntos para no saturar una tarjeta angosta del poster.
  function lineAreaChartSvg(categorias, valores, opts) {
    opts = opts || {};
    var valueFmt = opts.fmt || 'int';
    var n = categorias.length;
    if (!n) return '<p>Sin datos.</p>';
    var width = Math.max(480, n * 34);
    var maxVal = Math.max.apply(null, valores) || 1;
    var steps = 4;
    var gridValues = [];
    for (var i = 0; i <= steps; i++) gridValues.push(fmt(valueFmt, maxVal * (i / steps)));
    var maxLabelW = 0;
    gridValues.forEach(function (v) { maxLabelW = Math.max(maxLabelW, textW(v)); });
    // padLeft segun el label mas ancho del eje Y (igual que barChartSvg).
    // padRight segun el ancho real del rotulo del ultimo punto (endLabel
    // mas abajo cuelga a la derecha del punto) -- antes era fijo (84) y
    // con montos grandes el numero se cortaba contra el borde de la card.
    var padLeft = Math.max(50, maxLabelW + 18);
    var padRight = Math.max(40, textW(fmt(valueFmt, valores[n - 1])) + 24);
    var padTop = 20, labelH = 34, chartH = opts.height || 240;
    var plotH = chartH - padTop - labelH, plotW = width - padLeft - padRight;
    var slot = plotW / n;

    var gridlines = [], gridLabels = [];
    for (var i2 = 0; i2 <= steps; i2++) {
      var y = padTop + plotH - (i2 / steps) * plotH;
      gridlines.push('<line class="gridline" x1="' + padLeft + '" x2="' + (width - padRight) + '" y1="' + y.toFixed(1) + '" y2="' + y.toFixed(1) + '" />');
      gridLabels.push('<text x="' + (padLeft - 8) + '" y="' + (y + 4).toFixed(1) + '" text-anchor="end">' + esc(gridValues[i2]) + '</text>');
    }

    var pts = [];
    for (var j = 0; j < n; j++) {
      var x = padLeft + j * slot + slot / 2;
      var y = padTop + plotH - (maxVal ? (valores[j] / maxVal) * plotH : 0);
      pts.push([x, y]);
    }
    var baselineY = padTop + plotH;
    var linePath = pts.map(function (p, idx) { return (idx === 0 ? 'M' : 'L') + p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join(' ');
    var areaPath = linePath +
      ' L' + pts[n - 1][0].toFixed(1) + ',' + baselineY.toFixed(1) +
      ' L' + pts[0][0].toFixed(1) + ',' + baselineY.toFixed(1) + ' Z';

    var labelEvery = Math.max(1, Math.ceil(n / 8));
    var labelMaxChars = Math.max(3, Math.floor((slot * labelEvery) / 6.2));
    var hits = [], labels = [];
    pts.forEach(function (p, idx) {
      hits.push('<circle class="hit" cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) + '" r="14" data-label="' + esc(categorias[idx]) + '" data-value="' + esc(fmt(valueFmt, valores[idx])) + '" />');
      if (idx % labelEvery === 0 || idx === n - 1) {
        labels.push('<text x="' + p[0].toFixed(1) + '" y="' + (baselineY + 18).toFixed(1) + '" text-anchor="middle">' + esc(truncar(categorias[idx], labelMaxChars)) + '</text>');
      }
    });
    var last = pts[n - 1];
    var endDot = '<circle cx="' + last[0].toFixed(1) + '" cy="' + last[1].toFixed(1) + '" r="5" fill="var(--series-1)" stroke="var(--surface-1)" stroke-width="2" pointer-events="none" />';
    var endLabel = '<text x="' + (last[0] + 10).toFixed(1) + '" y="' + (last[1] - 8).toFixed(1) + '" text-anchor="start" font-weight="600" fill="var(--text-primary)">' + esc(fmt(valueFmt, valores[n - 1])) + '</text>';

    return '<svg class="chart" viewBox="0 0 ' + width + ' ' + chartH + '" preserveAspectRatio="xMinYMin meet">' +
      gridlines.join('') + gridLabels.join('') +
      '<line class="baseline" x1="' + padLeft + '" x2="' + (width - padRight) + '" y1="' + baselineY.toFixed(1) + '" y2="' + baselineY.toFixed(1) + '" />' +
      '<path d="' + areaPath + '" fill="var(--series-1)" fill-opacity="0.12" stroke="none" />' +
      '<path d="' + linePath + '" fill="none" stroke="var(--series-1)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />' +
      endDot + endLabel + labels.join('') + hits.join('') +
      '</svg>';
  }

  // Barra apilada 100% (part-to-whole categorico, orden fijo por entidad --
  // ver spec.charts[].order, nunca por magnitud). Etiqueta el % adentro del
  // segmento solo si entra con padding; si no, queda solo en la leyenda (que
  // usa texto en tinta de texto, nunca en el color de la serie).
  function stacked100BarSvg(categorias, valores, colors, opts) {
    opts = opts || {};
    var valueFmt = opts.fmt || 'int';
    var n = categorias.length;
    if (!n) return '<p>Sin datos.</p>';
    var total = valores.reduce(function (a, b) { return a + b; }, 0) || 1;
    var width = 520, barH = 30, gap = 2;
    var height = barH + 46;
    var clipId = 'sc-' + (gradSeq++);

    var segs = [], hits = [], x = 0;
    categorias.forEach(function (cat, i) {
      var w = (valores[i] / total) * width;
      var segW = Math.max(w - (i < n - 1 ? gap : 0), 0);
      var color = (colors && colors[cat]) || 'var(--series-1)';
      var pct = Math.round((valores[i] / total) * 100);
      segs.push('<rect x="' + x.toFixed(1) + '" y="0" width="' + segW.toFixed(1) + '" height="' + barH + '" fill="' + color + '" />');
      if (segW > 40) {
        segs.push('<text x="' + (x + segW / 2).toFixed(1) + '" y="' + (barH / 2 + 4.5).toFixed(1) + '" text-anchor="middle" fill="#fff" font-weight="600" font-size="12">' + pct + '%</text>');
      }
      hits.push('<rect class="hit" x="' + x.toFixed(1) + '" y="0" width="' + Math.max(w, 1).toFixed(1) + '" height="' + barH + '" fill="transparent" data-label="' + esc(cat) + '" data-value="' + esc(fmt(valueFmt, valores[i])) + ' (' + pct + '%)" />');
      x += w;
    });

    var legend = categorias.map(function (cat, i) {
      var color = (colors && colors[cat]) || 'var(--series-1)';
      var pct = Math.round((valores[i] / total) * 100);
      return '<g transform="translate(' + Math.round(i * (width / n)) + ', ' + (barH + 24) + ')">' +
        '<rect width="10" height="10" rx="2" fill="' + color + '" />' +
        '<text x="16" y="9" fill="var(--text-secondary)" font-size="12">' + esc(cat) + ' · ' + pct + '%</text>' +
        '</g>';
    }).join('');

    return '<svg class="chart" viewBox="0 0 ' + width + ' ' + height + '" preserveAspectRatio="xMinYMin meet">' +
      '<defs><clipPath id="' + clipId + '"><rect x="0" y="0" width="' + width + '" height="' + barH + '" rx="6" ry="6" /></clipPath></defs>' +
      '<g clip-path="url(#' + clipId + ')">' + segs.join('') + '</g>' +
      hits.join('') + legend +
      '</svg>';
  }

  // Comparacion periodo a periodo (mes a mes / trimestre a trimestre): barras
  // agrupadas por mes|trimestre del anio, una serie por anio. El anio es un
  // dato ordenado (no categorico) asi que la serie mas vieja arranca mas
  // transparente y la mas reciente en opacidad plena, en vez de una paleta
  // categorica arcoiris -- mismo tinte (var(--series-1)) en todos los anios.
  function groupedBarChartSvg(categorias, years, seriesByYear, opts) {
    opts = opts || {};
    var valueFmt = opts.fmt || 'int';
    var n = categorias.length, nSeries = years.length;
    if (!n || !nSeries) return '<p>Sin datos.</p>';
    var width = Math.max(560, n * 90);
    var maxVal = 0;
    years.forEach(function (y) { seriesByYear[y].forEach(function (v) { maxVal = Math.max(maxVal, v); }); });
    maxVal = maxVal || 1;
    var steps = 4;
    var gridValues = [];
    for (var i = 0; i <= steps; i++) gridValues.push(fmt(valueFmt, maxVal * (i / steps)));
    var maxLabelW = 0;
    gridValues.forEach(function (v) { maxLabelW = Math.max(maxLabelW, textW(v)); });
    var padLeft = Math.max(50, maxLabelW + 18);
    var padRight = 20, padTop = 20, labelH = 34, legendH = 26;
    var chartH = (opts.height || 260) + legendH;
    var plotH = chartH - padTop - labelH - legendH, plotW = width - padLeft - padRight;

    var groupGap = 16, barGap = 3;
    var groupW = plotW / n;
    var barW = Math.max(6, (groupW - groupGap - (nSeries - 1) * barGap) / nSeries);

    var gridlines = [], gridLabels = [];
    for (var i2 = 0; i2 <= steps; i2++) {
      var y = padTop + plotH - (i2 / steps) * plotH;
      gridlines.push('<line class="gridline" x1="' + padLeft + '" x2="' + (width - padRight) + '" y1="' + y.toFixed(1) + '" y2="' + y.toFixed(1) + '" />');
      gridLabels.push('<text x="' + (padLeft - 8) + '" y="' + (y + 4).toFixed(1) + '" text-anchor="end">' + esc(gridValues[i2]) + '</text>');
    }

    function opacityFor(s) { return nSeries === 1 ? 1 : (0.35 + 0.65 * (s / (nSeries - 1))); }

    var baselineY = padTop + plotH;
    var bars = [], catLabels = [];
    for (var j = 0; j < n; j++) {
      var groupX = padLeft + j * groupW + groupGap / 2;
      for (var s = 0; s < nSeries; s++) {
        var val = seriesByYear[years[s]][j];
        var barH = maxVal ? (val / maxVal) * plotH : 0;
        var x = groupX + s * (barW + barGap);
        var yTop = padTop + plotH - barH;
        bars.push(
          '<rect class="hit" x="' + (x - 1).toFixed(1) + '" y="' + padTop.toFixed(1) + '" width="' + (barW + 2).toFixed(1) + '" height="' + plotH.toFixed(1) + '" data-label="' + esc(years[s] + ' - ' + categorias[j]) + '" data-value="' + esc(fmt(valueFmt, val)) + '" />' +
          '<rect x="' + x.toFixed(1) + '" y="' + yTop.toFixed(1) + '" width="' + barW.toFixed(1) + '" height="' + barH.toFixed(1) + '" rx="3" ry="3" fill="var(--series-1)" fill-opacity="' + opacityFor(s).toFixed(2) + '" pointer-events="none" />'
        );
      }
      catLabels.push('<text x="' + (groupX + (groupW - groupGap) / 2).toFixed(1) + '" y="' + (baselineY + 18).toFixed(1) + '" text-anchor="middle">' + esc(categorias[j]) + '</text>');
    }

    var legend = years.map(function (y, s) {
      return '<g transform="translate(' + (padLeft + s * 64) + ',' + (chartH - legendH + 8) + ')">' +
        '<rect width="10" height="10" rx="2" fill="var(--series-1)" fill-opacity="' + opacityFor(s).toFixed(2) + '" />' +
        '<text x="16" y="9" font-size="12" fill="var(--text-secondary)">' + esc(y) + '</text>' +
        '</g>';
    }).join('');

    return '<svg class="chart" viewBox="0 0 ' + width + ' ' + chartH + '" preserveAspectRatio="xMinYMin meet">' +
      gridlines.join('') + gridLabels.join('') +
      '<line class="baseline" x1="' + padLeft + '" x2="' + (width - padRight) + '" y1="' + baselineY.toFixed(1) + '" y2="' + baselineY.toFixed(1) + '" />' +
      bars.join('') + catLabels.join('') + legend +
      '</svg>';
  }

  var MONTH_LABELS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
  var QUARTER_LABELS = ['T1', 'T2', 'T3', 'T4'];
  var periodCompareState = {};
  var periodCompareSpecs = {};

  // period_compare NO usa las filas ya filtradas por el filtro de periodo:
  // siempre compara el rango elegido (por numero de mes, sin importar el
  // anio) contra el mismo rango corrido 1 anio atras, aunque ese anio
  // anterior no este dentro del filtro (pedido de Javier 2026-07-22). Por
  // eso lee de `records` completo, no de `rows`.
  function addMonths(period, delta) {
    var y = parseInt(period.slice(0, 4), 10);
    var m = parseInt(period.slice(5, 7), 10);
    var total = y * 12 + (m - 1) + delta;
    var ny = Math.floor(total / 12);
    var nm = total - ny * 12 + 1;
    return ny + '-' + (nm < 10 ? '0' + nm : '' + nm);
  }

  function renderPeriodCompare(c, from, to) {
    var granularity = periodCompareState[c.mount] || c.granularity || 'month';
    var catLabelsAll = granularity === 'quarter' ? QUARTER_LABELS : MONTH_LABELS;
    var el = document.getElementById(c.mount);
    if (!from || !to) { if (el) el.innerHTML = '<p>Sin datos.</p>'; return; }

    function bucketKey(period) {
      var m = parseInt(period.slice(5, 7), 10);
      return granularity === 'quarter' ? (Math.ceil(m / 3) - 1) : (m - 1);
    }

    // Periodos (YYYY-MM) cubiertos por el filtro, en orden cronologico.
    var periodsInRange = [];
    var p = from, guard = 0;
    while (p <= to && guard < 1200) { periodsInRange.push(p); p = addMonths(p, 1); guard++; }

    // Orden de aparicion de cada bucket (respeta el orden cronologico del
    // rango elegido, ej. Nov,Dic,Ene,Feb en vez de Ene..Dic fijo).
    var bucketOrder = [], seen = {};
    periodsInRange.forEach(function (per) {
      var k = bucketKey(per);
      if (!seen[k]) { seen[k] = true; bucketOrder.push(k); }
    });
    var catLabels = bucketOrder.map(function (k) { return catLabelsAll[k]; });

    var sumByPeriod = {};
    records.forEach(function (r) {
      var d = r[dateField];
      if (!d || d.length < 7) return;
      var per = d.slice(0, 7);
      sumByPeriod[per] = (sumByPeriod[per] || 0) + (Number(r[c.field]) || 0);
    });

    var actual = bucketOrder.map(function () { return 0; });
    var anterior = bucketOrder.map(function () { return 0; });
    periodsInRange.forEach(function (per) {
      var idx = bucketOrder.indexOf(bucketKey(per));
      actual[idx] += sumByPeriod[per] || 0;
      anterior[idx] += sumByPeriod[addMonths(per, -12)] || 0;
    });

    var anioDesde = parseInt(from.slice(0, 4), 10), anioHasta = parseInt(to.slice(0, 4), 10);
    var labelActual = anioDesde === anioHasta ? String(anioDesde) : (anioDesde + '-' + anioHasta);
    var labelAnterior = anioDesde === anioHasta ? String(anioDesde - 1) : ((anioDesde - 1) + '-' + (anioHasta - 1));

    var years = [labelAnterior, labelActual];
    var seriesByYear = {};
    seriesByYear[labelAnterior] = anterior;
    seriesByYear[labelActual] = actual;

    var svg = groupedBarChartSvg(catLabels, years, seriesByYear, { fmt: c.fmt, height: c.height });
    if (el) el.innerHTML = svg;
  }

  function renderStatTiles(mountId, items) {
    var el = document.getElementById(mountId);
    if (!el) return;
    el.innerHTML = items.map(function (it) {
      var sub = it.sublabel ? '<div class="sublabel">' + esc(it.sublabel) + '</div>' : '';
      return '<div class="stat-tile"><div class="label">' + esc(it.label) + '</div><div class="value">' + esc(it.value) + '</div>' + sub + '</div>';
    }).join('');
  }

  // Agrupa `rows` por `groupField` y calcula, por grupo, los campos de
  // `aggs` (lista de {key, field, op, filter?}) -- ops: 'first' (valor de
  // la primera fila, para columnas de exhibicion como fecha/cliente),
  // 'count', 'sum', 'nunique' (igual semantica que aggregate(), pero esta
  // ademas conserva las filas originales del grupo en `_rows` para el
  // detalle desplegable, cosa que aggregate() no hace), y 'sum_unique'
  // (suma `field` una sola vez por cada valor distinto de `dedupeField` --
  // para cuando el grupo tiene varias filas de detalle que repiten la
  // misma entidad, ej. una misma OC referenciada por dos items de la
  // misma factura, y sumar `field` tal cual la contaria dos veces).
  // `filter` opcional por agg (mismo shape que spec.statTiles[].filter)
  // para, ej., contar solo las filas con OC vinculada en vez de todas las
  // del grupo.
  function groupRows(rows, groupField, aggs) {
    var map = {}, order = [];
    rows.forEach(function (r) {
      var k = r[groupField];
      if (!(k in map)) { map[k] = { _rows: [] }; map[k][groupField] = k; order.push(k); }
      map[k]._rows.push(r);
    });
    order.forEach(function (k) {
      var g = map[k];
      (aggs || []).forEach(function (a) {
        var sub = a.filter ? g._rows.filter(function (r) { return r[a.filter.field] === a.filter.equals; }) : g._rows;
        if (a.op === 'first') {
          g[a.key] = sub.length ? sub[0][a.field] : null;
        } else if (a.op === 'count') {
          g[a.key] = sub.length;
        } else if (a.op === 'sum') {
          var s = 0; sub.forEach(function (r) { s += Number(r[a.field]) || 0; });
          g[a.key] = s;
        } else if (a.op === 'nunique') {
          var seen = {}; sub.forEach(function (r) { if (r[a.field] != null) seen[r[a.field]] = true; });
          g[a.key] = Object.keys(seen).length;
        } else if (a.op === 'sum_unique') {
          var seenU = {}, su = 0;
          sub.forEach(function (r) {
            var dk = r[a.dedupeField];
            if (dk != null && seenU[dk]) return;
            if (dk != null) seenU[dk] = true;
            su += Number(r[a.field]) || 0;
          });
          g[a.key] = su;
        }
      });
    });
    return order.map(function (k) { return map[k]; });
  }

  // Tabla agrupada con detalle desplegable: una fila resumen por grupo
  // (clickeable, ver groupRows) + una fila de detalle (tabla anidada con
  // las filas originales) que se muestra/oculta con una clase 'open'
  // guardada en groupedTableState -- mismo espiritu que el toggle sin JS
  // externo que ya usa modules/pendientes (`_ROW_TOGGLE_JS`), pero armado
  // ac dinamicamente porque esta tabla vive bajo el motor de filtros
  // (periodo + categoricos) y hay que re-agrupar en cada filtrado.
  function renderGroupedTable(mountId, t, rows) {
    var el = document.getElementById(mountId);
    if (!el) return;
    if (!groupedTableState[mountId]) groupedTableState[mountId] = { search: '', open: {} };
    if (!el.dataset.built) {
      el.innerHTML =
        '<div class="table-toolbar no-print">' +
          '<input type="search" class="table-search" placeholder="Buscar en la tabla...">' +
          '<span class="table-count"></span>' +
        '</div>' +
        '<div class="table-inner"></div>';
      el.dataset.built = '1';
      var searchInput = el.querySelector('.table-search');
      searchInput.addEventListener('input', function () {
        groupedTableState[mountId].search = searchInput.value;
        paintGroupedTable(mountId, t, el._groups || []);
      });
    }
    var groups = groupRows(rows, t.groupField, t.groupAggs);
    if (t.sort) groups = sortRows(groups, t.sort);
    el._groups = groups;
    paintGroupedTable(mountId, t, groups);
  }

  function _celdaHtml(v, isNum) {
    if (v == null) return '<td' + (isNum ? ' class="num"' : '') + '></td>';
    return '<td' + (isNum ? ' class="num"' : '') + '>' + esc(isNum ? fmtMoney(v) : v) + '</td>';
  }

  function paintGroupedTable(mountId, t, groups) {
    var el = document.getElementById(mountId);
    if (!el) return;
    var st = groupedTableState[mountId];
    var q = (st.search || '').trim().toLowerCase();
    var matchCols = function (obj, cols) {
      return cols.some(function (c) {
        var v = obj[c[0]];
        return v != null && String(v).toLowerCase().indexOf(q) !== -1;
      });
    };
    var filtered = q ? groups.filter(function (g) {
      return matchCols(g, t.groupColumns) || g._rows.some(function (r) { return matchCols(r, t.detailColumns); });
    }) : groups;

    var headHtml = '<tr>' + t.groupColumns.map(function (c) {
      var isNum = t.groupNumericCols && t.groupNumericCols.indexOf(c[0]) >= 0;
      return '<th' + (isNum ? ' class="num"' : '') + '>' + esc(c[1]) + '</th>';
    }).join('') + '<th class="group-toggle-col"></th></tr>';

    var detailHead = '<tr>' + t.detailColumns.map(function (c) {
      var isNum = t.detailNumericCols && t.detailNumericCols.indexOf(c[0]) >= 0;
      return '<th' + (isNum ? ' class="num"' : '') + '>' + esc(c[1]) + '</th>';
    }).join('') + '</tr>';

    var bodyHtml = filtered.map(function (g) {
      var key = String(g[t.groupField]);
      var isOpen = !!st.open[key];
      var cells = t.groupColumns.map(function (c) {
        return _celdaHtml(g[c[0]], t.groupNumericCols && t.groupNumericCols.indexOf(c[0]) >= 0);
      }).join('');
      var summaryRow = '<tr class="group-row' + (isOpen ? ' open' : '') + '" data-gkey="' + esc(key) + '">' +
        cells + '<td class="group-toggle">' + (isOpen ? '▾' : '▸') + '</td></tr>';
      var detailBody = g._rows.map(function (r) {
        return '<tr>' + t.detailColumns.map(function (c) {
          return _celdaHtml(r[c[0]], t.detailNumericCols && t.detailNumericCols.indexOf(c[0]) >= 0);
        }).join('') + '</tr>';
      }).join('');
      var detailRow = '<tr class="group-detail-row' + (isOpen ? ' open' : '') + '"><td colspan="' + (t.groupColumns.length + 1) + '">' +
        '<table class="report-table report-table--nested"><thead>' + detailHead + '</thead><tbody>' + detailBody + '</tbody></table>' +
        '</td></tr>';
      return summaryRow + detailRow;
    }).join('');

    var inner = el.querySelector('.table-inner');
    inner.innerHTML = '<table class="report-table report-table--grouped"><thead>' + headHtml + '</thead><tbody>' + bodyHtml + '</tbody></table>';
    inner.querySelectorAll('tr.group-row').forEach(function (tr) {
      tr.addEventListener('click', function () {
        var key = tr.dataset.gkey;
        st.open[key] = !st.open[key];
        paintGroupedTable(mountId, t, groups);
      });
    });

    var countEl = el.querySelector('.table-count');
    if (countEl) {
      var noun = t.groupNoun || { one: 'fila', many: 'filas' };
      countEl.textContent = filtered.length + ' ' + (filtered.length === 1 ? noun.one : noun.many);
    }
  }

  // Tabla con buscador en vivo + orden por columna + tope de TABLE_LIMIT filas
  // (con boton "mostrar todas"). El buscador/orden se arman UNA sola vez por
  // mount (el.dataset.built) y solo se repinta '.table-inner' en cada cambio,
  // para no perder el foco del input mientras el usuario tipea.
  function renderTable(mountId, columns, rows, numericCols, tableSpec) {
    var el = document.getElementById(mountId);
    if (!el) return;
    if (!tableState[mountId]) {
      tableState[mountId] = { search: '', expanded: false, sort: (tableSpec && tableSpec.sort) || null };
    }
    if (!el.dataset.built) {
      el.innerHTML =
        '<div class="table-toolbar no-print">' +
          '<input type="search" class="table-search" placeholder="Buscar en la tabla...">' +
          '<span class="table-count"></span>' +
        '</div>' +
        '<div class="table-inner"></div>' +
        '<div class="table-more no-print" style="display:none"><button type="button" class="table-more-btn"></button></div>';
      el.dataset.built = '1';
      var searchInput = el.querySelector('.table-search');
      searchInput.addEventListener('input', function () {
        tableState[mountId].search = searchInput.value;
        tableState[mountId].expanded = false;
        paintTable(mountId);
      });
      el.querySelector('.table-more-btn').addEventListener('click', function () {
        tableState[mountId].expanded = !tableState[mountId].expanded;
        paintTable(mountId);
      });
    }
    el._allColumns = columns;
    el._allRows = rows;
    el._numericCols = numericCols;
    paintTable(mountId);
  }

  function paintTable(mountId) {
    var el = document.getElementById(mountId);
    if (!el) return;
    var columns = el._allColumns, rows = el._allRows, numericCols = el._numericCols;
    var st = tableState[mountId];

    var sorted = st.sort ? sortRows(rows, st.sort) : rows;

    var q = (st.search || '').trim().toLowerCase();
    var filtered = q ? sorted.filter(function (r) {
      return columns.some(function (c) {
        var v = r[c[0]];
        return v != null && String(v).toLowerCase().indexOf(q) !== -1;
      });
    }) : sorted;

    var showAll = st.expanded || filtered.length <= TABLE_LIMIT;

    var head = columns.map(function (c) {
      var key = c[0], label = c[1];
      var cls = (numericCols.indexOf(key) >= 0 ? 'num sortable' : 'sortable');
      var arrow = (st.sort && st.sort.key === key) ? (st.sort.dir === 'asc' ? ' ↑' : ' ↓') : '';
      return '<th class="' + cls + '" data-key="' + esc(key) + '">' + esc(label) + arrow + '</th>';
    }).join('');
    // Las filas mas alla de TABLE_LIMIT se quedan en el DOM (no se cortan del
    // array) y solo se ocultan con la clase row-hidden: asi @media print
    // (html_report.py) las vuelve a mostrar siempre, sin depender de que el
    // evento JS 'beforeprint' llegue a disparar (en Chromium headless no lo
    // hace; en un navegador de escritorio real si, pero mejor no apostar el
    // PDF real a eso).
    var body = filtered.map(function (r, i) {
      var cells = columns.map(function (c) {
        var v = r[c[0]];
        if (numericCols.indexOf(c[0]) >= 0) {
          return '<td class="num">' + (v == null ? '' : esc(fmtMoney(v))) + '</td>';
        }
        return '<td>' + (v == null ? '' : esc(v)) + '</td>';
      }).join('');
      var rowCls = (!showAll && i >= TABLE_LIMIT) ? ' class="row-hidden"' : '';
      return '<tr' + rowCls + '>' + cells + '</tr>';
    }).join('');

    var inner = el.querySelector('.table-inner');
    inner.innerHTML = '<table class="report-table"><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table>';
    inner.querySelectorAll('th.sortable').forEach(function (th) {
      th.addEventListener('click', function () {
        var key = th.dataset.key;
        if (st.sort && st.sort.key === key) {
          st.sort = { key: key, dir: st.sort.dir === 'asc' ? 'desc' : 'asc' };
        } else {
          st.sort = { key: key, dir: 'desc' };
        }
        paintTable(mountId);
      });
    });

    var countEl = el.querySelector('.table-count');
    if (countEl) {
      countEl.textContent = (filtered.length === rows.length)
        ? (rows.length + (rows.length === 1 ? ' fila' : ' filas'))
        : (filtered.length + ' de ' + rows.length + ' filas');
    }

    var moreWrap = el.querySelector('.table-more');
    var moreBtn = el.querySelector('.table-more-btn');
    if (filtered.length > TABLE_LIMIT) {
      moreWrap.style.display = '';
      moreBtn.textContent = showAll ? ('▴ Mostrar solo las primeras ' + TABLE_LIMIT) : ('▾ Mostrar todas (' + filtered.length + ')');
    } else {
      moreWrap.style.display = 'none';
    }
  }

  function renderAll() {
    var from = getPeriod(elDesdeMes, elDesdeAnio) || minPeriod;
    var to = getPeriod(elHastaMes, elHastaAnio) || maxPeriod;
    if (from && to && from > to) { to = from; setPeriod(elHastaMes, elHastaAnio, from); }
    var rows = applyCategoryFilters(filterRecords(from, to));
    try { localStorage.setItem(FILTER_KEY, JSON.stringify({ from: from, to: to })); } catch (e) {}

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

    lastFilteredRows = rows;
    lastFilterRange = { from: from, to: to };

    (spec.charts || []).forEach(function (c) {
      if (c.type === 'period_compare') {
        periodCompareSpecs[c.mount] = c;
        renderPeriodCompare(c, from, to);
        return;
      }
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
      var svg;
      if (c.type === 'hbar') {
        svg = hbarChartSvg(cats, vals, { fmt: c.fmt, rowH: c.rowH, height: c.height });
      } else if (c.type === 'line') {
        svg = lineAreaChartSvg(cats, vals, { fmt: c.fmt, height: c.height });
      } else if (c.type === 'stacked100') {
        var resolvedColors = {};
        Object.keys(c.colors || {}).forEach(function (k) {
          var v = c.colors[k];
          resolvedColors[k] = (v && typeof v === 'object') ? (prefersDark ? v.dark : v.light) : v;
        });
        svg = stacked100BarSvg(cats, vals, resolvedColors, { fmt: c.fmt });
      } else {
        svg = barChartSvg(cats, vals, { fmt: c.fmt, colors: c.colors, height: c.height });
      }
      var el = document.getElementById(c.mount);
      if (el) el.innerHTML = svg;
    });

    (spec.tables || []).forEach(function (t) {
      if (t.mode === 'grouped') {
        renderGroupedTable(t.mount, t, rows);
        return;
      }
      var tableRows = t.groupBy ? aggregate(rows, t.groupBy, t.aggs) : rows;
      if (t.topN) {
        tableRows = sortRows(tableRows, t.sort);
      }
      renderTable(t.mount, t.columns, t.topN ? tableRows.slice(0, t.topN) : tableRows, t.numericCols || [], t);
    });

    if (elCoverage) {
      var totalTxt = minPeriod ? (minPeriod + ' a ' + maxPeriod) : 'sin fechas';
      var showTxt = (from && to) ? (from + ' a ' + to) : 'sin fechas';
      elCoverage.innerHTML = 'Datos disponibles: <strong>' + esc(totalTxt) + '</strong> &middot; Mostrando: <strong>' + esc(showTxt) + '</strong> (' + rows.length + ' registros)';
    }
  }

  [elDesdeMes, elDesdeAnio, elHastaMes, elHastaAnio].forEach(function (el) {
    if (el) el.addEventListener('change', renderAll);
  });
  if (elReset) elReset.addEventListener('click', function () {
    setPeriod(elDesdeMes, elDesdeAnio, minPeriod);
    setPeriod(elHastaMes, elHastaAnio, maxPeriod);
    renderAll();
  });

  // Toggle Mensual/Trimestral de un chart period_compare: repinta solo ese
  // chart con las filas ya filtradas, sin pasar por renderAll().
  document.querySelectorAll('.segmented[data-toggle-for]').forEach(function (seg) {
    var mountId = seg.dataset.toggleFor;
    seg.querySelectorAll('button[data-granularity]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        seg.querySelectorAll('button').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        periodCompareState[mountId] = btn.dataset.granularity;
        var c = periodCompareSpecs[mountId];
        if (c) renderPeriodCompare(c, lastFilterRange.from, lastFilterRange.to);
      });
    });
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


# --- Formato presentacion (slides) ---
#
# Capa alternativa al dashboard de una sola pantalla (page_shell): en vez de
# secciones apiladas, arma un "deck" de pantallas completas navegables
# (flechas, scroll con snap, puntitos), pensado para mostrar/proyectar un
# resumen ejecutivo en vez del detalle completo. Reutiliza el mismo motor de
# datos (DASHBOARD_JS/dashboard_bundle, records_from_df, bar_chart_svg specs)
# -- solo cambia el shell HTML/CSS/JS alrededor. Sigue siendo un archivo
# autocontenido: se abre con doble click y se imprime a PDF (una slide por
# pagina) igual que el dashboard.

SLIDE_CSS = """
.slides-body { overflow: hidden; height: 100vh; }
.deck {
  scroll-snap-type: y mandatory;
  overflow-y: auto;
  height: 100vh;
  scroll-behavior: smooth;
}
.slide {
  min-height: 100vh;
  scroll-snap-align: start;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 64px 88px;
  box-sizing: border-box;
  position: relative;
}
.slide-header { margin-bottom: 28px; }
.slide-header h2 { font-size: 30px; font-weight: 700; margin: 4px 0 0; letter-spacing: -0.01em; }
.slide-header .eyebrow { margin: 0; }

.slide-cover { align-items: flex-start; background: linear-gradient(160deg, var(--surface-1), var(--page-plane)); }
.slide-cover .cover-logo { width: 76px; color: var(--brand); margin-bottom: 28px; }
.slide-cover .cover-logo svg { display: block; width: 100%; height: auto; }
.slide-cover .eyebrow { margin: 0 0 10px; }
.slide-cover h1 { font-size: 54px; font-weight: 800; letter-spacing: -0.02em; margin: 0 0 18px; max-width: 800px; }
.slide-cover .cover-meta { font-size: 17px; color: var(--text-secondary); max-width: 640px; margin-bottom: 6px; }
.slide-cover .cover-generated { font-size: 13px; color: var(--text-muted); position: absolute; bottom: 48px; left: 88px; }

.slide-closing { align-items: center; text-align: center; }
.slide-closing h2 { font-size: 34px; margin: 0 0 14px; }
.slide-closing p { max-width: 620px; color: var(--text-secondary); font-size: 15px; margin: 0 auto; }

.slide-kpis .stat-grid { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 24px; margin-bottom: 0; }
.slide-kpis .stat-tile { padding: 26px 28px; }
.slide-kpis .stat-tile .label { font-size: 12px; }
.slide-kpis .stat-tile .value { font-size: 52px; }

.slide-chart-full .chart-mount, .slide-chart-full > div:last-child { flex: 1; display: flex; align-items: center; }

.slide-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; flex: 1; align-items: center; }
.slide-grid-2 .slide-panel h3 { font-size: 13px; font-weight: 600; letter-spacing: 0.02em; text-transform: uppercase; margin: 0 0 14px; color: var(--text-secondary); }

.slide-nav {
  position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
  display: flex; align-items: center; gap: 14px;
  background: var(--surface-1); border: 1px solid var(--border); border-radius: 999px;
  padding: 8px 18px; box-shadow: 0 4px 14px rgba(0,0,0,0.14); z-index: 20;
  font-size: 13px; color: var(--text-secondary); font-variant-numeric: tabular-nums;
}
.slide-nav-btn { border: none; background: transparent; color: var(--text-primary); font-size: 20px; cursor: pointer; line-height: 1; padding: 2px 8px; }
.slide-nav-btn:hover { color: var(--brand); }

.slide-dots { position: fixed; right: 22px; top: 50%; transform: translateY(-50%); display: flex; flex-direction: column; gap: 9px; z-index: 20; }
.slide-dots .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--baseline); border: none; cursor: pointer; padding: 0; }
.slide-dots .dot.active { background: var(--brand); transform: scale(1.35); }

.slide-filter { position: fixed; top: 18px; right: 18px; z-index: 20; max-width: 380px; }
.slide-filter .filter-bar { margin-bottom: 0; font-size: 12px; padding: 8px 14px; }
.slide-theme-toggle { position: fixed; top: 18px; left: 18px; z-index: 20; }

.slide-poster { justify-content: flex-start; padding-top: 56px; padding-bottom: 56px; }
.poster-grid { display: grid; gap: 20px; flex: 1; align-content: start; }
.poster-grid.cols-2 { grid-template-columns: repeat(2, 1fr); }
.poster-grid.cols-1 { grid-template-columns: 1fr; }
.poster-card {
  background: var(--surface-1); border: 1px solid var(--border); border-radius: 14px;
  overflow: hidden; display: flex; flex-direction: column;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.poster-card-header {
  background: var(--text-primary); color: var(--surface-1);
  padding: 10px 16px; font-size: 12px; font-weight: 700; letter-spacing: 0.04em;
  text-transform: uppercase; display: flex; align-items: center; gap: 8px;
}
.poster-card-header .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--brand); flex-shrink: 0; }
.poster-card-body { padding: 16px 18px 18px; flex: 1; display: flex; flex-direction: column; }
.poster-card-note { font-size: 11.5px; color: var(--text-muted); margin-top: 10px; }
.poster-kpis .stat-grid { grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 0; }
.poster-kpis .stat-tile { padding: 14px 16px; }
.poster-kpis .stat-tile .value { font-size: 30px; }

@media print {
  .slide-poster { padding-top: 24px; padding-bottom: 24px; }
}

@media print {
  .slides-body { overflow: visible; height: auto; }
  .deck { height: auto; overflow: visible; scroll-snap-type: none; }
  .slide { min-height: auto; height: auto; page-break-after: always; break-after: page; padding: 24px 0; }
  .slide:last-child { page-break-after: auto; break-after: auto; }
  .slide-nav, .slide-dots { display: none !important; }
  .slide-filter { position: static; margin: 0 0 16px; box-shadow: none; border: none; max-width: none; }
  /* .cover-generated esta absoluto contra el piso de una slide de 100vh en
     pantalla; en print la slide se achica a su contenido y ese "bottom:48px"
     termina superpuesto con el subtitulo. Vuelve al flujo normal. */
  .slide-cover .cover-generated { position: static; margin-top: 14px; }
}
"""

SLIDE_NAV_JS = """
(function () {
  var deck = document.getElementById('deck');
  if (!deck) return;
  var slides = Array.prototype.slice.call(deck.querySelectorAll('.slide'));
  var dotsWrap = document.getElementById('slide-dots');
  var counterEl = document.getElementById('slide-current');
  var prevBtn = document.getElementById('nav-prev');
  var nextBtn = document.getElementById('nav-next');
  var current = 0;

  slides.forEach(function (s, i) {
    var dot = document.createElement('button');
    dot.type = 'button';
    dot.className = 'dot' + (i === 0 ? ' active' : '');
    dot.setAttribute('aria-label', 'Slide ' + (i + 1));
    dot.addEventListener('click', function () { goTo(i); });
    dotsWrap.appendChild(dot);
  });
  var dots = Array.prototype.slice.call(dotsWrap.querySelectorAll('.dot'));

  function setActive(i) {
    current = i;
    if (counterEl) counterEl.textContent = String(i + 1);
    dots.forEach(function (d, j) { d.classList.toggle('active', j === i); });
  }

  function goTo(i) {
    i = Math.max(0, Math.min(slides.length - 1, i));
    slides[i].scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  if (prevBtn) prevBtn.addEventListener('click', function () { goTo(current - 1); });
  if (nextBtn) nextBtn.addEventListener('click', function () { goTo(current + 1); });

  document.addEventListener('keydown', function (e) {
    if (e.target && ['INPUT', 'TEXTAREA'].indexOf(e.target.tagName) !== -1) return;
    if (e.key === 'ArrowDown' || e.key === 'PageDown' || e.key === ' ') { e.preventDefault(); goTo(current + 1); }
    else if (e.key === 'ArrowUp' || e.key === 'PageUp') { e.preventDefault(); goTo(current - 1); }
    else if (e.key === 'Home') { e.preventDefault(); goTo(0); }
    else if (e.key === 'End') { e.preventDefault(); goTo(slides.length - 1); }
  });

  if ('IntersectionObserver' in window) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting && entry.intersectionRatio > 0.6) {
          setActive(slides.indexOf(entry.target));
        }
      });
    }, { root: deck, threshold: [0.6] });
    slides.forEach(function (s) { observer.observe(s); });
  }
})();
"""


def slide(inner_html: str, *, css_class: str = "") -> str:
    """Envuelve el contenido de una pantalla completa del deck."""
    cls = f"slide {css_class}".strip()
    return f'<section class="{cls}" data-slide>{inner_html}</section>'


def slide_header(eyebrow: str, titulo: str) -> str:
    return f'<div class="slide-header"><div class="eyebrow">{escape(eyebrow)}</div><h2>{escape(titulo)}</h2></div>'


def poster_card(titulo: str, mount_html: str, *, nota: str = None, css_class: str = "") -> str:
    """Tarjeta chica para un deck tipo poster: header en negro (identidad
    ALESTE) con un punto de acento en el rojo de marca, cuerpo con el mount
    del grafico/tabla. `css_class` es para variantes de tamaño de tile
    (ver .poster-kpis en SLIDE_CSS)."""
    nota_html = f'<div class="poster-card-note">{escape(nota)}</div>' if nota else ""
    cls = f"poster-card {css_class}".strip()
    return f"""<div class="{cls}">
    <div class="poster-card-header"><span class="dot"></span>{escape(titulo)}</div>
    <div class="poster-card-body">{mount_html}{nota_html}</div>
  </div>"""


def poster_grid(cards: list, *, cols: int = 2) -> str:
    return f'<div class="poster-grid cols-{cols}">{"".join(cards)}</div>'


def cover_slide(titulo: str, subtitulo: str, meta: str = "") -> str:
    generado = datetime.now().strftime("%Y-%m-%d %H:%M")
    meta_html = f'<div class="cover-meta">{escape(meta)}</div>' if meta else ""
    return slide(
        f'<div class="cover-logo">{LOGO_SVG}</div>'
        f'<div class="eyebrow">{escape(subtitulo)}</div>'
        f'<h1>{escape(titulo)}</h1>'
        f'{meta_html}'
        f'<div class="cover-generated">Generado: {generado}</div>',
        css_class="slide-cover",
    )


def closing_slide(titulo: str, texto: str) -> str:
    return slide(f'<h2>{escape(titulo)}</h2><p>{escape(texto)}</p>', css_class="slide-closing")


def slide_shell(titulo: str, subtitulo: str, slides_html: list, records: list, spec: dict) -> str:
    n = len(slides_html)
    deck = "".join(slides_html)
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{escape(titulo)}</title>
<style>{PAGE_CSS}{DASHBOARD_CSS}{SLIDE_CSS}</style>
<script>{THEME_INIT_JS}</script>
</head>
<body class="slides-body">
<div class="deck" id="deck">
{deck}
</div>
<div class="slide-nav no-print">
  <button type="button" class="slide-nav-btn" id="nav-prev" aria-label="Anterior">&lsaquo;</button>
  <div class="slide-counter"><span id="slide-current">1</span>&nbsp;/&nbsp;{n}</div>
  <button type="button" class="slide-nav-btn" id="nav-next" aria-label="Siguiente">&rsaquo;</button>
</div>
<div class="slide-dots no-print" id="slide-dots"></div>
<div class="slide-theme-toggle no-print">{THEME_TOGGLE_BTN}</div>
<div class="slide-filter">{filter_bar_html()}</div>
<div id="viz-tooltip"></div>
<script>{TOOLTIP_JS}{SLIDE_NAV_JS}{THEME_JS}</script>
{dashboard_bundle(records, spec)}
</body>
</html>"""


# --- Shell: dashboard multi-modulo (sidebar + iframe) ---
#
# "Home" que agrupa todos los informe_<modulo>.html bajo un sidebar estilo
# Mantis. Cada informe sigue siendo un HTML autocontenido que se puede abrir
# suelto con doble click, igual que hoy -- el shell solo agrega navegacion
# por encima (un <iframe> que apunta al archivo del modulo activo), no
# cambia como cada modulo genera su archivo. Lo arma generate_dashboard.py
# (raiz del repo) con la lista de modulos dados de alta.

SHELL_CSS = """
.shell-body { margin: 0; height: 100vh; overflow: hidden; }
.shell-layout { display: flex; height: 100vh; }
.shell-sidebar {
  width: 260px;
  flex-shrink: 0;
  background: var(--surface-1);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 20px 12px;
  overflow-y: auto;
  overflow-x: hidden;
  transition: width 0.15s ease;
}
.shell-sidebar.collapsed { width: 68px; }
.shell-sidebar .brand { display: flex; align-items: center; gap: 12px; padding: 0 8px 20px; }
.shell-sidebar .brand-logo { width: 34px; flex-shrink: 0; color: var(--brand); }
.shell-sidebar .brand-logo svg { display: block; width: 100%; height: auto; }
.shell-sidebar .brand-title { font-size: 13px; font-weight: 700; letter-spacing: -0.01em; white-space: nowrap; }
.shell-sidebar .brand-subtitle { font-size: 11px; color: var(--text-muted); white-space: nowrap; }
.shell-sidebar.collapsed .brand { justify-content: center; padding: 0 0 20px; }
.shell-sidebar.collapsed .brand-text { display: none; }
.sidebar-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  font-family: inherit;
  padding: 8px 12px;
  margin-bottom: 10px;
  border-radius: 8px;
  cursor: pointer;
}
.sidebar-toggle:hover { background: var(--page-plane); color: var(--text-primary); }
.sidebar-toggle .icon { width: 16px; height: 16px; flex-shrink: 0; transition: transform 0.15s ease; }
.sidebar-toggle .icon svg { display: block; width: 100%; height: 100%; }
.sidebar-toggle-label { white-space: nowrap; }
.shell-sidebar.collapsed .sidebar-toggle { justify-content: center; padding: 8px 0; }
.shell-sidebar.collapsed .sidebar-toggle .icon { transform: rotate(180deg); }
.shell-sidebar.collapsed .sidebar-toggle-label { display: none; }
.shell-nav { display: flex; flex-direction: column; gap: 2px; }
.shell-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 12px;
  border-radius: 8px;
  border: none;
  border-right: 2px solid transparent;
  background: transparent;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  text-align: left;
  cursor: pointer;
}
.shell-nav-item:hover { background: var(--page-plane); }
.shell-nav-item.active {
  background: var(--brand-tint);
  border-right-color: var(--brand);
  color: var(--brand);
  font-weight: 600;
}
.shell-nav-item .nav-icon { width: 18px; height: 18px; flex-shrink: 0; opacity: 0.85; }
.shell-nav-item .nav-icon svg { display: block; width: 100%; height: 100%; }
.shell-nav-item.active .nav-icon { opacity: 1; }
.shell-nav-item .nav-label { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.shell-sidebar.collapsed .shell-nav-item { justify-content: center; padding: 9px 0; gap: 0; }
.shell-sidebar.collapsed .nav-label { display: none; }
.shell-main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.shell-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--surface-1);
}
.shell-topbar h1 { font-size: 15px; font-weight: 600; margin: 0; }
.shell-frame-wrap { flex: 1; min-height: 0; }
.shell-frame-wrap iframe { width: 100%; height: 100%; border: none; display: block; background: var(--page-plane); }

@media print {
  .shell-sidebar, .shell-topbar { display: none !important; }
  .shell-layout, .shell-main, .shell-frame-wrap { height: auto; display: block; }
  .shell-frame-wrap iframe { height: 100vh; }
}
"""

SHELL_JS = """
(function () {
  var items = Array.prototype.slice.call(document.querySelectorAll('.shell-nav-item'));
  var frame = document.getElementById('shell-frame');
  var titleEl = document.getElementById('shell-title');
  var STORAGE_KEY = 'aleste-dashboard-modulo';
  var COLLAPSE_KEY = 'aleste-dashboard-sidebar-collapsed';

  var sidebar = document.querySelector('.shell-sidebar');
  var toggleBtn = document.getElementById('shell-sidebar-toggle');
  var toggleLabel = toggleBtn ? toggleBtn.querySelector('.sidebar-toggle-label') : null;

  function setCollapsed(collapsed) {
    if (!sidebar) return;
    sidebar.classList.toggle('collapsed', collapsed);
    if (toggleLabel) toggleLabel.textContent = collapsed ? 'Expandir' : 'Contraer';
    if (toggleBtn) {
      var text = collapsed ? 'Expandir menu' : 'Contraer menu';
      toggleBtn.title = text;
      toggleBtn.setAttribute('aria-label', text);
    }
    try { localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0'); } catch (e) {}
  }

  if (toggleBtn) {
    toggleBtn.addEventListener('click', function () {
      setCollapsed(!sidebar.classList.contains('collapsed'));
    });
  }
  var storedCollapsed = null;
  try { storedCollapsed = localStorage.getItem(COLLAPSE_KEY); } catch (e) {}
  setCollapsed(storedCollapsed === '1');

  function activate(id) {
    var item = items.filter(function (it) { return it.dataset.id === id; })[0];
    if (!item || !frame) return;
    items.forEach(function (it) { it.classList.toggle('active', it === item); });
    frame.src = item.dataset.src;
    if (titleEl) titleEl.textContent = item.dataset.label;
    try { localStorage.setItem(STORAGE_KEY, id); } catch (e) {}
  }

  items.forEach(function (it) {
    it.addEventListener('click', function () { activate(it.dataset.id); });
  });

  var stored = null;
  try { stored = localStorage.getItem(STORAGE_KEY); } catch (e) {}
  var initial = (stored && items.some(function (it) { return it.dataset.id === stored; }))
    ? stored
    : (items[0] && items[0].dataset.id);
  if (initial) activate(initial);

  var printBtn = document.getElementById('shell-print');
  if (printBtn) printBtn.addEventListener('click', function () {
    // iframes de otro archivo local (file://) a veces bloquean el acceso a
    // contentWindow segun el navegador -- si tira SecurityError, se cae a
    // imprimir el shell (mejor eso que un boton roto).
    try {
      if (frame && frame.contentWindow) {
        frame.contentWindow.focus();
        frame.contentWindow.print();
        return;
      }
    } catch (e) {}
    window.print();
  });
})();
"""


_ICON_STROKE = 'fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"'

# Un icono de linea por modulo (id -> SVG interno, sin el wrapper <svg>) para
# poder diferenciar cada pestana cuando el sidebar esta contraido y solo
# queda el icono visible (el label de texto se oculta, ver .nav-label).
# Modulo nuevo que no esta en este mapa cae a NAV_ICON_DEFAULT (circulo) en
# vez de romper -- pero conviene sumarle su propio icono aca al darlo de alta.
NAV_ICONS = {
    "pendientes": f'<circle cx="12" cy="12" r="8.5" {_ICON_STROKE}/><path d="M12 7.5V12l3 2" {_ICON_STROKE}/>',
    "ordenes_trabajo": (
        f'<rect x="5" y="4" width="14" height="17" rx="2" {_ICON_STROKE}/>'
        f'<path d="M9 4.5V3a1 1 0 011-1h4a1 1 0 011 1v1.5" {_ICON_STROKE}/>'
        f'<path d="M8.5 11.5h7M8.5 15h7M8.5 18.5h4" {_ICON_STROKE}/>'
    ),
    "compras": (
        f'<path d="M7 8h10l-1 12a2 2 0 01-2 2H10a2 2 0 01-2-2L7 8z" {_ICON_STROKE}/>'
        f'<path d="M9 8V6a3 3 0 016 0v2" {_ICON_STROKE}/>'
    ),
    "facturas": (
        f'<path d="M7 3h7l4 4v13a1 1 0 01-1 1H7a1 1 0 01-1-1V4a1 1 0 011-1z" {_ICON_STROKE}/>'
        f'<path d="M14 3v4a1 1 0 001 1h4" {_ICON_STROKE}/>'
        f'<path d="M9 12.5h6M9 15.5h6M9 18.5h3" {_ICON_STROKE}/>'
    ),
}
NAV_ICON_DEFAULT = f'<circle cx="12" cy="12" r="4" fill="currentColor"/>'

_CHEVRON_ICON = f'<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M15 18l-6-6 6-6" {_ICON_STROKE}/></svg>'


def _nav_icon_svg(id_: str) -> str:
    inner = NAV_ICONS.get(id_, NAV_ICON_DEFAULT)
    return f'<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">{inner}</svg>'


def dashboard_shell(modules: list) -> str:
    """`modules`: lista de (id, label, archivo_html). Arma el shell con
    sidebar de navegacion + iframe que carga el informe del modulo activo."""
    nav_items = "".join(
        f'<button type="button" class="shell-nav-item" data-id="{escape(id_)}" '
        f'data-src="{escape(archivo)}" data-label="{escape(label)}" title="{escape(label)}">'
        f'<span class="nav-icon">{_nav_icon_svg(id_)}</span>'
        f'<span class="nav-label">{escape(label)}</span></button>'
        for id_, label, archivo in modules
    )
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Dashboard ALESTE ADS</title>
<style>{PAGE_CSS}{SHELL_CSS}</style>
<script>{THEME_INIT_JS}</script>
</head>
<body class="shell-body">
<div class="shell-layout">
  <nav class="shell-sidebar no-print">
    <div class="brand">
      <div class="brand-logo">{LOGO_SVG}</div>
      <div class="brand-text">
        <div class="brand-title">ALESTE ADS</div>
        <div class="brand-subtitle">Dashboard Advertys</div>
      </div>
    </div>
    <button type="button" class="sidebar-toggle" id="shell-sidebar-toggle" title="Contraer menu" aria-label="Contraer menu">
      <span class="icon">{_CHEVRON_ICON}</span>
      <span class="sidebar-toggle-label">Contraer</span>
    </button>
    <div class="shell-nav">{nav_items}</div>
  </nav>
  <div class="shell-main">
    <div class="shell-topbar no-print">
      <h1 id="shell-title">Dashboard</h1>
      <div class="header-actions">
        {THEME_TOGGLE_BTN}
        <button type="button" class="print-btn" id="shell-print">Imprimir / Guardar PDF</button>
      </div>
    </div>
    <div class="shell-frame-wrap">
      <iframe id="shell-frame" title="Informe"></iframe>
    </div>
  </div>
</div>
<script>{SHELL_JS}{THEME_JS}</script>
</body>
</html>"""
