"""
Genera salida/informe_facturacion_aluar.html a partir de la tabla
facturacion_aluar (ver ingest.py). Reusa el diseño del analisis puntual
original ("Ventas ALUAR por Concepto", armado a mano en otra sesion,
pedido de Javier 2026-09-28: "copies este mismo informe y lo incluyas al
dashboard") -- mismo look (tiles, grafico de barras apiladas por
categoria, comparativo Produccion/Medios, tabla ordenable/paginada,
timeline de "Consideraciones importantes"), pero con los datos vivos en
vez de un array embebido a mano.

A diferencia del resto de los informes de este pipeline, este NO usa
html_report.page_shell() (ese es el diseño compartido del resto del
dashboard) -- mantiene su propio CSS/JS bespoke tal como los aprobo
Javier en el artifact original. Si reusa dos cosas puntuales de
html_report para que el informe respete el tema claro/oscuro que elige el
sidebar del dashboard: THEME_INIT_JS (evita el flash de tema equivocado
al cargar) y THEME_JS (escucha el postMessage que manda dashboard_shell
al cambiar de tema).

Uso:
    python -m modules.facturacion_aluar.generate_html_report
"""
import json
import sqlite3
from datetime import datetime

import db
import html_report as hr
from . import config

TEMPLATE = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Facturación ALUAR</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Public+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<script>__THEME_INIT_JS__</script>
<style>
  :root{
    --page:#f9f9f7; --surface:#fcfcfb;
    --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781;
    --grid:#e1e0d9; --baseline:#c3c2b7; --border:rgba(11,11,11,.10);
    --brand:#f63200; --brand-ink:#ffffff;
    --cat-recupero:#2a78d6; --cat-fee:#1baf7a; --cat-markup:#f63200;
    --cat-propios:#4a3aa7;
    --tv-produccion:#2a78d6; --tv-medios:#f63200;
    --shadow: 0 1px 2px rgba(11,11,11,.04), 0 8px 24px -12px rgba(11,11,11,.12);
  }
  @media (prefers-color-scheme: dark){
    :root:not([data-theme="light"]){
      --page:#0d0d0d; --surface:#1a1a19;
      --ink:#ffffff; --ink-2:#c3c2b7; --muted:#898781;
      --grid:#2c2c2a; --baseline:#383835; --border:rgba(255,255,255,.10);
      --brand:#f63200; --brand-ink:#ffffff;
      --cat-recupero:#3987e5; --cat-fee:#199e70; --cat-markup:#f63200;
      --cat-propios:#9085e9;
      --tv-produccion:#3987e5; --tv-medios:#f63200;
      --shadow: 0 1px 2px rgba(0,0,0,.3), 0 8px 24px -12px rgba(0,0,0,.5);
    }
  }
  :root[data-theme="dark"]{
    --page:#0d0d0d; --surface:#1a1a19;
    --ink:#ffffff; --ink-2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --baseline:#383835; --border:rgba(255,255,255,.10);
    --brand:#f63200; --brand-ink:#ffffff;
    --cat-recupero:#3987e5; --cat-fee:#199e70; --cat-markup:#f63200;
    --cat-propios:#9085e9;
    --tv-produccion:#3987e5; --tv-medios:#f63200;
    --shadow: 0 1px 2px rgba(0,0,0,.3), 0 8px 24px -12px rgba(0,0,0,.5);
  }

  *{box-sizing:border-box;}
  html{scroll-padding-top:12px;}
  body{
    margin:0; background:var(--page); color:var(--ink);
    font-family:"Public Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
    padding-inline:20px; padding-block:28px 60px;
  }
  .wrap{ max-width:1180px; margin:0 auto; display:flex; flex-direction:column; gap:22px; }

  .eyebrow{
    font-family:"IBM Plex Mono", monospace; font-size:11.5px; font-weight:600;
    letter-spacing:.09em; text-transform:uppercase; color:var(--brand);
  }
  h1{
    font-family:"Fraunces", Georgia, serif; font-optical-sizing:auto;
    font-weight:600; font-size:clamp(1.6rem, 1.2rem + 1.6vw, 2.35rem);
    line-height:1.08; margin:.2em 0 .1em; text-wrap:balance; letter-spacing:-.01em;
  }
  .subtitle{ color:var(--ink-2); font-size:14.5px; max-width:64ch; line-height:1.5; }
  .subtitle b{ color:var(--ink); font-weight:600; }

  .card{
    background:var(--surface); border:1px solid var(--border); border-radius:12px;
    box-shadow:var(--shadow); padding:18px 20px;
  }

  .header-row{ display:flex; align-items:flex-start; justify-content:space-between; gap:16px; flex-wrap:wrap; }
  .header-actions{ display:flex; gap:8px; flex:none; }
  .print-btn{
    font:inherit; font-family:"Public Sans",sans-serif; font-weight:600; font-size:12.5px;
    color:var(--ink-2); background:var(--surface); border:1px solid var(--border); border-radius:8px;
    padding:8px 12px; cursor:pointer;
  }
  .print-btn:hover{ color:var(--ink); border-color:var(--muted); }

  /* Boton de tema: mismo markup/CSS que html_report.THEME_TOGGLE_BTN (ver
     generate_html_report.py) para no duplicar la logica de iconos. */
  button.theme-toggle{
    display:flex; align-items:center; justify-content:center; width:36px; height:36px; padding:0;
    border:1px solid var(--border); background:var(--surface); color:var(--ink); border-radius:8px; cursor:pointer;
  }
  button.theme-toggle:hover{ background:var(--page); border-color:var(--brand); color:var(--brand); }
  button.theme-toggle .icon{ width:18px; height:18px; display:block; }
  button.theme-toggle .icon svg{ display:block; width:100%; height:100%; }
  button.theme-toggle .icon-moon{ display:none; }
  @media (prefers-color-scheme: dark){
    :root:not([data-theme="light"]) button.theme-toggle .icon-sun{ display:none; }
    :root:not([data-theme="light"]) button.theme-toggle .icon-moon{ display:block; }
  }
  :root[data-theme="dark"] button.theme-toggle .icon-sun{ display:none; }
  :root[data-theme="dark"] button.theme-toggle .icon-moon{ display:block; }

  /* ---- filtros ---- */
  .filters{ display:flex; flex-wrap:wrap; gap:16px 28px; align-items:flex-end; }
  .filter-group{ display:flex; flex-direction:column; gap:6px; }
  .filter-label{
    font-family:"IBM Plex Mono", monospace; font-size:10.5px; font-weight:600;
    letter-spacing:.07em; text-transform:uppercase; color:var(--muted);
  }
  .segmented{ display:inline-flex; background:var(--page); border:1px solid var(--border); border-radius:9px; padding:3px; gap:2px; }
  .segmented button{
    font:inherit; font-family:"Public Sans",sans-serif; font-weight:600; font-size:13px;
    color:var(--ink-2); background:transparent; border:none; border-radius:6px;
    padding:7px 14px; cursor:pointer; transition:background .12s,color .12s;
  }
  .segmented button:hover{ color:var(--ink); }
  .segmented button.active{ background:var(--brand); color:var(--brand-ink); }
  .segmented button:focus-visible, select:focus-visible, th button:focus-visible, .tile.toggle:focus-visible, .pagination button:focus-visible{
    outline:2px solid var(--brand); outline-offset:2px;
  }
  @media (prefers-reduced-motion: reduce){ *{ transition:none !important; } }
  .month-range{ display:flex; align-items:center; gap:8px; }
  select{
    font:inherit; font-family:"IBM Plex Mono",monospace; font-size:13px; color:var(--ink);
    background:var(--page); border:1px solid var(--border); border-radius:7px;
    padding:7px 10px; cursor:pointer;
  }
  .month-range span{ color:var(--muted); font-size:13px; }

  /* ---- tiles / categoria toggles ---- */
  .tiles{ display:grid; grid-template-columns:1.3fr repeat(4, 1fr); gap:12px; }
  @media (max-width:920px){ .tiles{ grid-template-columns:repeat(2,1fr); } }
  @media (max-width:520px){ .tiles{ grid-template-columns:1fr; } }
  .tile{
    background:var(--surface); border:1px solid var(--border); border-radius:12px;
    box-shadow:var(--shadow); padding:15px 16px; display:flex; flex-direction:column; gap:6px;
    min-width:0;
  }
  .tile.hero{ background:var(--brand); color:var(--brand-ink); border-color:transparent; }
  .tile.hero .tile-label{ color:rgba(255,255,255,.75); }
  .tile.hero .tile-pct{ color:rgba(255,255,255,.75); }
  .tile.toggle{ cursor:pointer; text-align:left; border:none; font:inherit; appearance:none; }
  .tile.toggle:hover{ box-shadow:var(--shadow), 0 0 0 1px var(--border) inset; }
  .tile.off{ opacity:.42; }
  .tile-label{
    display:flex; align-items:center; gap:7px;
    font-size:12px; color:var(--ink-2); font-weight:600; line-height:1.25;
  }
  .swatch{ width:10px; height:10px; border-radius:3px; flex:none; }
  .tile-value{
    font-family:"IBM Plex Mono", monospace; font-weight:600; font-variant-numeric:tabular-nums;
    font-size:clamp(15px, 1.6vw, 19px); letter-spacing:-.01em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  }
  .tile.hero .tile-value{ font-size:clamp(22px, 2.6vw, 30px); }
  .tile-pct{ font-size:12px; color:var(--muted); font-family:"IBM Plex Mono",monospace; }

  /* ---- charts ---- */
  .chart-card h2{ font-family:"Fraunces",serif; font-weight:600; font-size:17px; margin:0 0 2px; }
  .chart-caption{ color:var(--muted); font-size:12.5px; margin-bottom:12px; }
  .warn-flag{ color:#b8860b; cursor:help; margin-left:4px; }
  .adj-flag{ color:#2a78d6; cursor:help; margin-left:4px; }

  /* ---- consideraciones / timeline ---- */
  .considerations h2{ font-family:"Fraunces",serif; font-weight:600; font-size:17px; margin:0 0 2px; }
  .considerations .chart-caption{ margin-bottom:16px; }
  .timeline{ display:flex; flex-direction:column; }
  .tl-row{ display:flex; gap:16px; }
  .tl-clickable{ cursor:pointer; border-radius:8px; margin:0 -10px; padding:0 10px; transition:background .12s; }
  .tl-clickable:hover{ background:rgba(137,135,129,.08); }
  .tl-clickable:hover .tl-line{ background:var(--muted); }
  .tl-link{
    font-size:11px; font-weight:600; color:var(--brand); margin-left:10px;
    opacity:0; transition:opacity .12s; letter-spacing:0; text-transform:none;
  }
  .tl-clickable:hover .tl-link, .tl-clickable:focus-visible .tl-link{ opacity:1; }
  .tl-clickable:focus-visible{ outline:2px solid var(--brand); outline-offset:2px; }
  .tl-rail{ display:flex; flex-direction:column; align-items:center; width:12px; flex:none; }
  .tl-dot{ width:12px; height:12px; border-radius:50%; flex:none; box-shadow:0 0 0 3px var(--surface); }
  .tl-dot.st-neutral{ background:var(--muted); }
  .tl-dot.st-transition{ background:var(--cat-recupero); }
  .tl-dot.st-warn{ background:#b8860b; }
  .tl-dot.st-good{ background:#1baf7a; }
  .tl-line{ flex:1; width:2px; background:var(--border); margin-top:2px; }
  .tl-body{ padding-bottom:22px; }
  .tl-row:last-child .tl-body{ padding-bottom:0; }
  .tl-period{
    font-family:"IBM Plex Mono",monospace; font-size:11.5px; font-weight:600;
    letter-spacing:.03em; color:var(--ink); margin-bottom:3px;
  }
  .tl-status{ font-size:11px; font-weight:600; letter-spacing:.03em; }
  .tl-status.st-neutral{ color:var(--muted); }
  .tl-status.st-transition{ color:var(--cat-recupero); }
  .tl-status.st-warn{ color:#b8860b; }
  .tl-status.st-good{ color:#1baf7a; }
  .tl-text{ font-size:13px; color:var(--ink-2); line-height:1.55; max-width:72ch; margin-top:3px; }
  .tl-text b{ color:var(--ink); font-weight:600; }
  .considerations .medios-note{
    margin-top:18px; padding-top:16px; border-top:1px solid var(--border);
    font-size:13px; color:var(--ink-2); line-height:1.55;
  }
  .considerations .medios-note b{ color:var(--ink); }
  .fixed-note{
    margin-top:16px; padding:14px 16px; border-radius:10px;
    background:rgba(27,175,122,.09); border:1px solid rgba(27,175,122,.3);
  }
  .fixed-title{ font-weight:700; color:#1baf7a; font-size:13px; margin-bottom:6px; }
  .fixed-note p{ font-size:12.5px; color:var(--ink-2); line-height:1.55; margin:0; }
  .fixed-note p b{ color:var(--ink); }
  .fixed-note.blue{ background:rgba(42,120,214,.09); border:1px solid rgba(42,120,214,.3); }
  .fixed-note.blue .fixed-title{ color:#2a78d6; }
  .legend{ display:flex; flex-wrap:wrap; gap:12px 18px; margin-bottom:10px; }
  .legend-item{ display:flex; align-items:center; gap:6px; font-size:12.5px; color:var(--ink-2); }
  svg.chart{ width:100%; height:auto; display:block; overflow:visible; }
  .axis-label{ font-family:"IBM Plex Mono",monospace; font-size:10.5px; fill:var(--muted); }
  .gridline{ stroke:var(--grid); stroke-width:1; }
  .baseline{ stroke:var(--baseline); stroke-width:1; }
  .seg{ cursor:pointer; }
  .seg:hover{ filter:brightness(1.08); }

  .tooltip{
    position:fixed; pointer-events:none; z-index:50; background:var(--ink); color:var(--page);
    font-size:12.5px; padding:9px 11px; border-radius:8px; box-shadow:var(--shadow);
    max-width:240px; opacity:0; transition:opacity .08s; line-height:1.45;
  }
  :root[data-theme="dark"] .tooltip, :root:not([data-theme="light"]) .tooltip{ background:#050505; }
  .tooltip.show{ opacity:1; }
  .tooltip .tt-title{ font-weight:700; margin-bottom:3px; }
  .tooltip .tt-row{ display:flex; justify-content:space-between; gap:14px; font-family:"IBM Plex Mono",monospace; font-variant-numeric:tabular-nums; }

  /* ---- table ---- */
  .table-wrap{ overflow-x:auto; }
  table{ width:100%; border-collapse:collapse; font-size:13px; min-width:640px; }
  thead th{
    text-align:left; padding:9px 10px; border-bottom:2px solid var(--border);
    font-family:"IBM Plex Mono",monospace; font-size:10.5px; letter-spacing:.06em;
    text-transform:uppercase; color:var(--muted); white-space:nowrap;
  }
  thead th button{
    font:inherit; background:none; border:none; color:inherit; cursor:pointer;
    display:inline-flex; align-items:center; gap:4px; padding:0;
  }
  thead th button:hover{ color:var(--ink); }
  tbody td{ padding:8px 10px; border-bottom:1px solid var(--border); }
  tbody tr:nth-child(even){ background:rgba(137,135,129,.06); }
  tbody tr.row-hidden{ display:none; }
  td.num{ text-align:right; font-family:"IBM Plex Mono",monospace; font-variant-numeric:tabular-nums; }
  td.cat-cell{ display:flex; align-items:center; gap:7px; }
  tfoot td{ padding:10px; font-weight:700; border-top:2px solid var(--border); }
  .table-caption{ color:var(--muted); font-size:12.5px; margin-bottom:10px; }
  .pagination{ display:flex; align-items:center; justify-content:center; gap:6px; flex-wrap:wrap; margin-top:14px; }
  .pagination button{
    font:inherit; font-family:"IBM Plex Mono",monospace; font-size:12.5px; font-weight:600;
    color:var(--ink-2); background:var(--page); border:1px solid var(--border); border-radius:6px;
    padding:6px 11px; cursor:pointer;
  }
  .pagination button:hover:not(:disabled){ color:var(--ink); border-color:var(--muted); }
  .pagination button:disabled{ opacity:.4; cursor:default; }
  .pagination button.active{ background:var(--brand); color:var(--brand-ink); border-color:var(--brand); }
  .pagination .pg-pages{ display:flex; gap:6px; }
  .pagination .pg-ellipsis{ color:var(--muted); padding:0 2px; }

  footer.card{ font-size:12.5px; color:var(--ink-2); line-height:1.6; }
  footer.card b{ color:var(--ink); }
  footer.card .foot-grid{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px 28px; }

  /* Imprimir siempre en claro, sin importar el tema elegido en pantalla --
     mismo criterio que html_report.PAGE_CSS: repetir el selector
     [data-theme] para igualar la especificidad de los bloques de arriba
     (dark via prefers-color-scheme y :root[data-theme="dark"]); como este
     bloque va despues en el archivo, gana el empate. */
  @media print{
    :root, :root[data-theme="dark"], :root[data-theme="light"]{
      color-scheme:light;
      --page:#f9f9f7; --surface:#fcfcfb;
      --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781;
      --grid:#e1e0d9; --baseline:#c3c2b7; --border:rgba(11,11,11,.10);
      --brand:#f63200; --brand-ink:#ffffff;
      --cat-recupero:#2a78d6; --cat-fee:#1baf7a; --cat-markup:#f63200; --cat-propios:#4a3aa7;
      --tv-produccion:#2a78d6; --tv-medios:#f63200;
    }
    body{ background:#fff; }
    .no-print{ display:none !important; }
    .card{ box-shadow:none; border:1px solid #ddd; break-inside:avoid; }
    svg.chart{ break-inside:avoid; }
    table tr{ break-inside:avoid; }
    /* Detalle completo al imprimir/PDF, sin importar la pagina que
       quedo en pantalla -- ver renderTable() en el script. */
    tbody tr.row-hidden{ display:table-row; }
  }
</style>
</head><body>

<div class="wrap">
  <header class="header-row">
    <div>
      <div class="eyebrow">ALESTE ADS S.A. · Cuenta ALUAR</div>
      <h1>Ventas a ALUAR por concepto contable</h1>
      <p class="subtitle">Facturación cruzada con el libro de Imputaciones (Advertys), desagregada por
        <b>categoría de negocio</b> y por <b>tipo de venta</b> (Producción / Medios), mes a mes.
        Datos disponibles: <b id="ventanaTexto">—</b>.</p>
    </div>
    <div class="header-actions no-print">
      __THEME_TOGGLE_BTN__
      <button type="button" class="print-btn" onclick="window.print()">Imprimir / Guardar PDF</button>
    </div>
  </header>

  <div class="card filters no-print">
    <div class="filter-group">
      <span class="filter-label">Tipo de venta</span>
      <div class="segmented" id="tvSeg" role="group" aria-label="Tipo de venta"></div>
    </div>
    <div class="filter-group">
      <span class="filter-label">Rango de mes</span>
      <div class="month-range">
        <select id="mesDesde"></select>
        <span>–</span>
        <select id="mesHasta"></select>
      </div>
    </div>
  </div>

  <div class="tiles" id="tiles"></div>

  <section class="card chart-card">
    <h2>Evolución mensual por categoría</h2>
    <p class="chart-caption">Apilado — clickeá una categoría arriba para incluirla/excluirla del gráfico y la tabla. Los meses con borde punteado tienen una salvedad, ver "Consideraciones importantes" al final.</p>
    <div id="barLegend" class="legend"></div>
    <svg class="chart" id="barChart" viewBox="0 0 980 400" preserveAspectRatio="xMidYMid meet"></svg>
  </section>

  <section class="card chart-card">
    <h2>Producción vs. Medios</h2>
    <p class="chart-caption">Todos los conceptos — responde al rango de mes, no al filtro de tipo de venta de arriba (para poder comparar ambos siempre).</p>
    <svg class="chart" id="lineChart" viewBox="0 0 980 320" preserveAspectRatio="xMidYMid meet"></svg>
  </section>

  <section class="card">
    <h2 style="font-family:'Fraunces',serif;font-weight:600;font-size:17px;margin:0 0 2px;">Detalle por mes, tipo de venta y cuenta contable</h2>
    <p class="table-caption" id="tableCaption"></p>
    <div class="table-wrap">
      <table>
        <thead><tr id="theadRow"></tr></thead>
        <tbody id="tbody"></tbody>
        <tfoot><tr id="tfootRow"></tr></tfoot>
      </table>
    </div>
    <div class="pagination no-print" id="pagination"></div>
  </section>

  <section class="card considerations">
    <h2>Consideraciones importantes</h2>
    <p class="chart-caption">Cómo se resuelven dos problemas reales de origen contable en Advertys al armar este informe.</p>
    <div class="timeline">
      <div class="tl-row">
        <div class="tl-rail"><span class="tl-dot st-warn"></span><span class="tl-line"></span></div>
        <div class="tl-body">
          <div class="tl-period">RECLASIFICACIÓN TEMPORAL DE CUENTAS (Producción)</div>
          <div class="tl-status st-warn">⚠ SE DETECTA AUTOMÁTICAMENTE</div>
          <div class="tl-text">Advertys usó en algún momento una cuenta especial (<b>411038 - MARK UP
            PRODUCCIÓN</b>) que mezcla <b>Servicios propios</b> y <b>Margen sobre terceros</b> en una sola
            línea, en vez de mantenerlas separadas. Cuando eso pasa, el reparto entre esas dos categorías en
            ese mes puntual no es confiable (marcado con ⚠ en el gráfico y la tabla) — el <b>total</b> de
            Producción de ese mes sí lo es. Esto se detecta solo, mes a mes: cualquier mes donde aparezca
            algo en la cuenta 411038 queda marcado, sin fecha fija.</div>
        </div>
      </div>
      <div class="tl-row">
        <div class="tl-rail"><span class="tl-dot st-good"></span></div>
        <div class="tl-body">
          <div class="tl-period">FACTURAS CANCELADAS Y REEMITIDAS</div>
          <div class="tl-status st-good">✔ SE EXCLUYEN AUTOMÁTICAMENTE</div>
          <div class="tl-text">Advertys registra la cancelación de una factura como un documento contable
            nuevo (no la borra), que a veces reemplaza por una factura nueva en un <b>mes distinto</b> al
            original. Un script de solo lectura (<code>crawl_facturas_relacionadas.py</code>) lee el campo
            real "Factura Relacionada" de cada cancelación en Advertys y excluye tanto la cancelación como la
            factura original que reemplaza, para que el monto quede una sola vez, en el mes del reemplazo —
            se recalcula en cada actualización del informe, no es una corrección puntual congelada en una fecha.</div>
        </div>
      </div>
    </div>
    __AJUSTE_MANUAL_BOX__
  </section>

  <footer class="card">
    <div class="foot-grid">
      <div><b>Fuente</b><br>Facturas + Imputaciones contables de Advertys (ERP), cruzadas por
        clave TA+Asiento+TR+N° Referencia. Cuentas de ingreso 411xxx únicamente.</div>
      <div><b>Categorías</b><br>Agrupación de cuentas contables: Recupero de costo (411040/411075),
        Margen sobre terceros (411035/411038/411076), Servicio de Agencia/Fee (411010/411020/411070),
        Servicios propios (411030).</div>
      <div><b>Generado</b><br>__GENERADO_TS__ · se recalcula en cada corrida de
        <code>python -m modules.facturacion_aluar.ingest</code>, no es una foto congelada.</div>
    </div>
  </footer>
</div>

<div class="tooltip" id="tooltip"></div>

<script>
const DATA = __DATA_JSON__;

const CATEGORIAS = [
  {key:"Recupero costo terceros (sin margen)", short:"Recupero de costo", color:"var(--cat-recupero)"},
  {key:"Margen sobre terceros", short:"Margen s/terceros", color:"var(--cat-markup)"},
  {key:"Servicio de Agencia / Fee", short:"Agencia / Fee", color:"var(--cat-fee)"},
  {key:"Servicios propios", short:"Servicios propios", color:"var(--cat-propios)"},
];
const NOTA_RECLASIF = "Este mes, Advertys mezcló Servicios propios y Margen sobre terceros en una sola cuenta (411038) -- el reparto entre esas 2 categorías no es confiable, el total del mes sí. Ver \"Consideraciones importantes\".";
const NOTA_AJUSTE_USD = __NOTA_AJUSTE_USD_JSON__;
const CAT_COLOR = Object.fromEntries(CATEGORIAS.map(c=>[c.key,c.color]));
const MESES = [...new Set(DATA.map(d=>d.mes))].sort();
const MESES_LARGO = {1:"ene",2:"feb",3:"mar",4:"abr",5:"may",6:"jun",7:"jul",8:"ago",9:"sep",10:"oct",11:"nov",12:"dic"};

function fmtMes(m){ const [y,mo]=m.split("-"); return MESES_LARGO[+mo]+" "+y.slice(2); }
function fmtMoney(v){ return "$ " + Math.round(v).toLocaleString("es-AR"); }
function fmtMoneyShort(v){ return "$ " + (v/1e6).toLocaleString("es-AR",{minimumFractionDigits:1,maximumFractionDigits:1}) + " M"; }
function fmtPct(v){ return (v*100).toFixed(1).replace(".",",") + "%"; }

const PAGE_SIZE = 20;

const state = {
  tipoVenta: "todos", // todos | Producción | Medios
  mesDesde: MESES[0] || null,
  mesHasta: MESES[MESES.length-1] || null,
  activeCats: new Set(CATEGORIAS.map(c=>c.key)),
  sort: {key:"mes", dir:-1},
  page: 1,
};

document.getElementById("ventanaTexto").textContent = MESES.length ? (fmtMes(MESES[0]) + " – " + fmtMes(MESES[MESES.length-1])) : "sin datos";

// ---------- filtros UI ----------
const tvSeg = document.getElementById("tvSeg");
["todos","Producción","Medios"].forEach(v=>{
  const b = document.createElement("button");
  b.textContent = v==="todos" ? "Todos" : v;
  b.className = state.tipoVenta===v ? "active" : "";
  b.onclick = ()=>{ state.tipoVenta=v; state.page=1; render(); };
  b.dataset.v = v;
  tvSeg.appendChild(b);
});

const selDesde = document.getElementById("mesDesde");
const selHasta = document.getElementById("mesHasta");
MESES.forEach(m=>{
  selDesde.appendChild(new Option(fmtMes(m), m));
  selHasta.appendChild(new Option(fmtMes(m), m));
});
selDesde.value = state.mesDesde;
selHasta.value = state.mesHasta;
selDesde.onchange = ()=>{
  state.mesDesde = selDesde.value;
  if(state.mesDesde > state.mesHasta){ state.mesHasta = state.mesDesde; selHasta.value = state.mesHasta; }
  state.page = 1;
  render();
};
selHasta.onchange = ()=>{
  state.mesHasta = selHasta.value;
  if(state.mesHasta < state.mesDesde){ state.mesDesde = state.mesHasta; selDesde.value = state.mesDesde; }
  state.page = 1;
  render();
};

// ---------- data helpers ----------
function inWindow(d){ return d.mes >= state.mesDesde && d.mes <= state.mesHasta; }
function windowRows(){ return DATA.filter(d => inWindow(d) && (state.tipoVenta==="todos" || d.tipo_venta===state.tipoVenta)); }
function visibleRows(){ return windowRows().filter(d => state.activeCats.has(d.categoria)); }
function sum(rows){ return rows.reduce((a,d)=>a+d.monto,0); }

const tooltip = document.getElementById("tooltip");
function showTooltip(html, x, y){
  tooltip.innerHTML = html;
  const pad = 14, tw = 240, th = 90;
  let left = x + pad, top = y + pad;
  if(left + tw > window.innerWidth) left = x - tw - pad;
  if(top + th > window.innerHeight) top = y - th - pad;
  tooltip.style.left = left+"px"; tooltip.style.top = top+"px";
  tooltip.classList.add("show");
}
function hideTooltip(){ tooltip.classList.remove("show"); }

// ---------- tiles ----------
const tilesEl = document.getElementById("tiles");
function renderTiles(){
  const wr = windowRows();
  const total = sum(wr);
  tilesEl.innerHTML = "";
  const hero = document.createElement("div");
  hero.className = "tile hero";
  hero.innerHTML = `<span class="tile-label">Total facturado</span><span class="tile-value" title="${fmtMoney(total)}">${fmtMoneyShort(total)}</span><span class="tile-pct">${wr.length} líneas de imputación</span>`;
  tilesEl.appendChild(hero);

  CATEGORIAS.forEach(c=>{
    const v = sum(wr.filter(d=>d.categoria===c.key));
    const active = state.activeCats.has(c.key);
    const btn = document.createElement("button");
    btn.className = "tile toggle" + (active?"":" off");
    btn.innerHTML = `<span class="tile-label"><span class="swatch" style="background:${c.color}"></span>${c.short}</span>
      <span class="tile-value" title="${fmtMoney(v)}">${fmtMoneyShort(v)}</span>
      <span class="tile-pct">${total>0?fmtPct(v/total):"—"}</span>`;
    btn.onclick = ()=>{
      if(active && state.activeCats.size===1) return; // al menos una activa
      active ? state.activeCats.delete(c.key) : state.activeCats.add(c.key);
      state.page = 1;
      render();
    };
    tilesEl.appendChild(btn);
  });
}

// ---------- bar chart ----------
const barLegend = document.getElementById("barLegend");
function renderBarLegend(){
  barLegend.innerHTML = CATEGORIAS.map(c=>`<span class="legend-item"><span class="swatch" style="background:${c.color}"></span>${c.short}</span>`).join("");
}

function niceMax(v){
  if(v<=0) return 1;
  const mag = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v/mag;
  const step = n<=1?1:n<=2?2:n<=5?5:10;
  return step*mag;
}

function renderBarChart(){
  const svg = document.getElementById("barChart");
  svg.innerHTML = "";
  const W=980, H=400, ML=64, MR=16, MT=16, MB=40;
  const plotW = W-ML-MR, plotH = H-MT-MB;
  const mesesEnRango = MESES.filter(m=>m>=state.mesDesde && m<=state.mesHasta);
  const vr = visibleRows().filter(d=>mesesEnRango.includes(d.mes));

  const porMes = mesesEnRango.map(m=>{
    const rows = vr.filter(d=>d.mes===m);
    const byCat = {}, flagCat = {};
    CATEGORIAS.forEach(c=>{
      const rowsCat = rows.filter(d=>d.categoria===c.key);
      byCat[c.key] = sum(rowsCat);
      flagCat[c.key] = rowsCat.some(d=>d.reclasificado);
    });
    return {mes:m, byCat, flagCat, total: sum(rows)};
  });
  const maxTotal = niceMax(Math.max(1,...porMes.map(p=>p.total)));
  const y = v => MT + plotH - (v/maxTotal)*plotH;
  const n = mesesEnRango.length || 1;
  const bw = Math.min(46, plotW/n*0.62);
  const step = plotW/n;

  const ns = "http://www.w3.org/2000/svg";
  const g = document.createElementNS(ns,"g");

  const ticks = 4;
  for(let i=0;i<=ticks;i++){
    const v = maxTotal*i/ticks;
    const yy = y(v);
    const line = document.createElementNS(ns,"line");
    line.setAttribute("x1",ML); line.setAttribute("x2",W-MR);
    line.setAttribute("y1",yy); line.setAttribute("y2",yy);
    line.setAttribute("class", i===0?"baseline":"gridline");
    g.appendChild(line);
    const label = document.createElementNS(ns,"text");
    label.setAttribute("x",ML-8); label.setAttribute("y",yy+4);
    label.setAttribute("text-anchor","end"); label.setAttribute("class","axis-label");
    label.textContent = v>=1e6? (v/1e6).toFixed(v>=1e7?0:1).replace(".",",")+"M" : Math.round(v).toLocaleString("es-AR");
    g.appendChild(label);
  }

  porMes.forEach((p,i)=>{
    const x0 = ML + step*i + (step-bw)/2;
    let acc = 0;
    CATEGORIAS.forEach(c=>{
      const v = p.byCat[c.key];
      if(v<=0) return;
      const yTop = y(acc+v), yBot = y(acc);
      const gap = 1.5;
      const rect = document.createElementNS(ns,"rect");
      rect.setAttribute("x",x0);
      rect.setAttribute("y",yTop+gap/2);
      rect.setAttribute("width",bw);
      rect.setAttribute("height",Math.max(0,(yBot-yTop)-gap));
      rect.style.fill = c.color;
      rect.setAttribute("class","seg");
      rect.setAttribute("rx", acc+v>=p.total-0.01 ? 3:0);
      const flagged = p.flagCat[c.key];
      if(flagged){
        rect.style.stroke = "#b8860b";
        rect.style.strokeWidth = "2";
        rect.style.strokeDasharray = "3,2";
      }
      rect.addEventListener("pointerenter",(e)=>{
        showTooltip(`<div class="tt-title">${fmtMes(p.mes)} · ${c.short}</div>
          <div class="tt-row"><span>Monto</span><span>${fmtMoney(v)}</span></div>
          <div class="tt-row"><span>% del mes</span><span>${p.total>0?fmtPct(v/p.total):"—"}</span></div>
          ${flagged ? `<div style="margin-top:6px;padding-top:6px;border-top:1px solid rgba(255,255,255,.2);color:#e8c766;font-size:11.5px;">⚠ ${NOTA_RECLASIF}</div>` : ""}`, e.clientX, e.clientY);
      });
      rect.addEventListener("pointermove",(e)=>showTooltip(tooltip.innerHTML,e.clientX,e.clientY));
      rect.addEventListener("pointerleave",hideTooltip);
      g.appendChild(rect);
      acc += v;
    });
    const label = document.createElementNS(ns,"text");
    label.setAttribute("x",x0+bw/2); label.setAttribute("y",H-MB+18);
    label.setAttribute("text-anchor","middle"); label.setAttribute("class","axis-label");
    label.textContent = fmtMes(p.mes);
    g.appendChild(label);
  });

  svg.appendChild(g);
}

// ---------- line chart: Produccion vs Medios ----------
function renderLineChart(){
  const svg = document.getElementById("lineChart");
  svg.innerHTML = "";
  const W=980, H=320, ML=64, MR=90, MT=20, MB=36;
  const plotW=W-ML-MR, plotH=H-MT-MB;
  const mesesEnRango = MESES.filter(m=>m>=state.mesDesde && m<=state.mesHasta);
  const rows = DATA.filter(d=>mesesEnRango.includes(d.mes) && state.activeCats.has(d.categoria));

  const series = ["Producción","Medios"].map(tv=>({
    tv, color: tv==="Producción"?"var(--tv-produccion)":"var(--tv-medios)",
    values: mesesEnRango.map(m=> sum(rows.filter(d=>d.mes===m && d.tipo_venta===tv)))
  }));
  const maxV = niceMax(Math.max(1,...series.flatMap(s=>s.values)));
  const n = mesesEnRango.length||1;
  const x = i => ML + (n===1?plotW/2:plotW*i/(n-1));
  const y = v => MT + plotH - (v/maxV)*plotH;

  const ns="http://www.w3.org/2000/svg";
  const g = document.createElementNS(ns,"g");

  for(let i=0;i<=4;i++){
    const v=maxV*i/4, yy=y(v);
    const line=document.createElementNS(ns,"line");
    line.setAttribute("x1",ML); line.setAttribute("x2",W-MR);
    line.setAttribute("y1",yy); line.setAttribute("y2",yy);
    line.setAttribute("class", i===0?"baseline":"gridline");
    g.appendChild(line);
    const label=document.createElementNS(ns,"text");
    label.setAttribute("x",ML-8); label.setAttribute("y",yy+4);
    label.setAttribute("text-anchor","end"); label.setAttribute("class","axis-label");
    label.textContent = v>=1e6?(v/1e6).toFixed(v>=1e7?0:1).replace(".",",")+"M":Math.round(v).toLocaleString("es-AR");
    g.appendChild(label);
  }
  mesesEnRango.forEach((m,i)=>{
    if(i%Math.ceil(n/12)!==0 && i!==n-1) return;
    const label=document.createElementNS(ns,"text");
    label.setAttribute("x",x(i)); label.setAttribute("y",H-MB+18);
    label.setAttribute("text-anchor","middle"); label.setAttribute("class","axis-label");
    label.textContent = fmtMes(m);
    g.appendChild(label);
  });

  const endLabels = [];
  series.forEach(s=>{
    const pts = s.values.map((v,i)=>[x(i),y(v)]);
    const path = document.createElementNS(ns,"path");
    path.setAttribute("d", pts.map((p,i)=>(i===0?"M":"L")+p[0].toFixed(1)+","+p[1].toFixed(1)).join(" "));
    path.setAttribute("fill","none"); path.style.stroke = s.color;
    path.setAttribute("stroke-width","2.5"); path.setAttribute("stroke-linejoin","round"); path.setAttribute("stroke-linecap","round");
    g.appendChild(path);
    pts.forEach((p,i)=>{
      const hit=document.createElementNS(ns,"circle");
      hit.setAttribute("cx",p[0]); hit.setAttribute("cy",p[1]); hit.setAttribute("r",9);
      hit.setAttribute("fill","transparent");
      hit.addEventListener("pointerenter",(e)=>{
        showTooltip(`<div class="tt-title">${fmtMes(mesesEnRango[i])} · ${s.tv}</div>
          <div class="tt-row"><span>Monto</span><span>${fmtMoney(s.values[i])}</span></div>`, e.clientX, e.clientY);
      });
      hit.addEventListener("pointermove",(e)=>showTooltip(tooltip.innerHTML,e.clientX,e.clientY));
      hit.addEventListener("pointerleave",hideTooltip);
      g.appendChild(hit);
      const dot=document.createElementNS(ns,"circle");
      dot.setAttribute("cx",p[0]); dot.setAttribute("cy",p[1]);
      dot.setAttribute("r", i===pts.length-1?5:3);
      dot.style.fill = s.color; dot.style.stroke = "var(--surface)"; dot.setAttribute("stroke-width","1.5");
      dot.style.pointerEvents="none";
      g.appendChild(dot);
    });
    const last = pts[pts.length-1];
    endLabels.push({x:last[0]+10, y:last[1]+4, color:s.color, text:s.tv});
  });
  endLabels.sort((a,b)=>a.y-b.y);
  const MIN_GAP = 15;
  for(let i=1;i<endLabels.length;i++){
    if(endLabels[i].y - endLabels[i-1].y < MIN_GAP){
      const mid = (endLabels[i].y + endLabels[i-1].y)/2;
      endLabels[i-1].y = mid - MIN_GAP/2;
      endLabels[i].y = mid + MIN_GAP/2;
    }
  }
  endLabels.forEach(lb=>{
    const lbl = document.createElementNS(ns,"text");
    lbl.setAttribute("x", lb.x); lbl.setAttribute("y", lb.y);
    lbl.style.fill = lb.color; lbl.setAttribute("font-family","IBM Plex Mono, monospace");
    lbl.setAttribute("font-size","12.5"); lbl.setAttribute("font-weight","600");
    lbl.textContent = lb.text;
    g.appendChild(lbl);
  });

  svg.appendChild(g);
}

// ---------- table ----------
const COLS = [
  {key:"mes", label:"Mes", fmt:fmtMes},
  {key:"tipo_venta", label:"Tipo de venta"},
  {key:"cuenta", label:"Cuenta", num:true},
  {key:"concepto", label:"Concepto"},
  {key:"categoria", label:"Categoría", cat:true},
  {key:"monto", label:"Monto", num:true, fmt:fmtMoney},
];
function renderTableHead(){
  const tr = document.getElementById("theadRow");
  tr.innerHTML = "";
  COLS.forEach(c=>{
    const th = document.createElement("th");
    if(c.num) th.style.textAlign="right";
    const btn = document.createElement("button");
    const arrow = state.sort.key===c.key ? (state.sort.dir===1?"▲":"▼") : "";
    btn.innerHTML = c.label + (arrow?` <span style="color:var(--brand)">${arrow}</span>`:"");
    btn.onclick = ()=>{
      if(state.sort.key===c.key) state.sort.dir *= -1; else state.sort = {key:c.key, dir:1};
      state.page = 1;
      render();
    };
    th.appendChild(btn);
    tr.appendChild(th);
  });
}
function sortedVisibleRows(){
  return visibleRows().slice().sort((a,b)=>{
    const k=state.sort.key, d=state.sort.dir;
    if(a[k]<b[k]) return -1*d; if(a[k]>b[k]) return 1*d; return 0;
  });
}
function renderTable(){
  const rows = sortedVisibleRows();

  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  if(state.page > totalPages) state.page = totalPages;
  if(state.page < 1) state.page = 1;
  const start = (state.page - 1) * PAGE_SIZE;
  const end = start + PAGE_SIZE;

  // Se renderizan TODAS las filas (no solo la pagina actual) y las que
  // quedan fuera de la pagina se ocultan con una clase CSS -- no con JS
  // de paginación -- para que @media print pueda forzarlas visibles con
  // pura CSS (tools/screenshot.py emula el media type sin disparar los
  // eventos beforeprint/afterprint, mismo criterio que TABLE_LIMIT en
  // html_report.py, ver CLAUDE.md "Screenshot Workflow").
  const tbody = document.getElementById("tbody");
  tbody.innerHTML = rows.map((r,i)=>`<tr class="${i>=start && i<end ? "" : "row-hidden"}">
    <td>${fmtMes(r.mes)}</td>
    <td>${r.tipo_venta}</td>
    <td class="num">${r.cuenta}</td>
    <td>${r.concepto}</td>
    <td class="cat-cell"><span class="swatch" style="background:${CAT_COLOR[r.categoria]}"></span>${r.categoria}${r.reclasificado ? `<span class="warn-flag" title="${NOTA_RECLASIF}">⚠</span>` : ""}${r.ajuste_manual ? `<span class="adj-flag" title="${NOTA_AJUSTE_USD}">●</span>` : ""}</td>
    <td class="num">${fmtMoney(r.monto)}</td>
  </tr>`).join("");
  document.getElementById("tfootRow").innerHTML =
    `<td colspan="5">Total (${rows.length} líneas)</td><td class="num">${fmtMoney(sum(rows))}</td>`;
  document.getElementById("tableCaption").textContent =
    `Mostrando ${Math.min(PAGE_SIZE, rows.length - start)} de ${rows.length} líneas de imputación agregadas por mes/cuenta — no factura por factura.`;

  renderPagination(totalPages);
}

function renderPagination(totalPages){
  const el = document.getElementById("pagination");
  if(totalPages <= 1){ el.innerHTML = ""; return; }
  const p = state.page;
  const btn = (label, page, disabled, active) =>
    `<button ${disabled?"disabled":""} data-page="${page}" class="${active?"active":""}">${label}</button>`;
  let pages = [];
  const addPage = n => pages.push(btn(n, n, false, n===p));
  addPage(1);
  if(p > 3) pages.push(`<span class="pg-ellipsis">…</span>`);
  for(let n=Math.max(2,p-1); n<=Math.min(totalPages-1,p+1); n++) addPage(n);
  if(p < totalPages-2) pages.push(`<span class="pg-ellipsis">…</span>`);
  if(totalPages > 1) addPage(totalPages);
  el.innerHTML = `
    ${btn("‹ Anterior", p-1, p===1, false)}
    <span class="pg-pages">${pages.join("")}</span>
    ${btn("Siguiente ›", p+1, p===totalPages, false)}
  `;
  el.querySelectorAll("button[data-page]:not([disabled])").forEach(b=>{
    b.onclick = ()=>{ state.page = parseInt(b.dataset.page, 10); renderTable(); document.querySelector(".table-wrap").scrollIntoView({block:"nearest"}); };
  });
}

// ---------- render ----------
function render(){
  [...tvSeg.children].forEach(b=>b.classList.toggle("active", b.dataset.v===state.tipoVenta));
  renderTiles();
  renderBarLegend();
  renderBarChart();
  renderLineChart();
  renderTableHead();
  renderTable();
}
render();

__THEME_JS__
</script>

</body></html>
"""


def _ajuste_manual_box(registros: list[dict]) -> str:
    ajustes = [r for r in registros if r.get("ajuste_manual")]
    if not ajustes:
        return ""
    detalle = "; ".join(f"{r['mes']} ({r['tipo_venta']}, {r['concepto']}, {r['monto']:,.2f})" for r in ajustes)
    return f"""
    <div class="fixed-note blue">
      <div class="fixed-title">● Ajuste manual documentado</div>
      <p>{len(ajustes)} factura(s) facturadas a costo puro, sin línea de venta 411xxx propia (Advertys las
        neteó directo contra la cuenta de costo) -- se suman a mano porque nunca aparecerían solas en la
        ingesta normal. Se agregan solo si la factura sigue existiendo en Advertys. Detalle: {detalle}.</p>
    </div>
    """


def cargar_registros() -> list[dict]:
    with db.get_connection() as conn:
        try:
            filas = conn.execute(
                f"SELECT mes, tipo_venta, cuenta, concepto, categoria, monto, reclasificado, ajuste_manual "
                f"FROM {config.DB_TABLE} ORDER BY mes, tipo_venta, cuenta"
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    return [
        {
            "mes": f["mes"],
            "tipo_venta": f["tipo_venta"],
            "cuenta": f["cuenta"],
            "concepto": f["concepto"],
            "categoria": f["categoria"],
            "monto": f["monto"],
            "reclasificado": bool(f["reclasificado"]),
            "ajuste_manual": bool(f["ajuste_manual"]),
        }
        for f in filas
    ]


def generar_html() -> str:
    registros = cargar_registros()
    nota_ajuste = config.AJUSTE_MANUAL_USD_HOSTING["concepto"].replace('"', "&quot;")

    html = TEMPLATE
    html = html.replace("__THEME_INIT_JS__", hr.THEME_INIT_JS)
    html = html.replace("__THEME_JS__", hr.THEME_JS)
    html = html.replace("__THEME_TOGGLE_BTN__", hr.THEME_TOGGLE_BTN)
    html = html.replace("__AJUSTE_MANUAL_BOX__", _ajuste_manual_box(registros))
    html = html.replace("__GENERADO_TS__", datetime.now().strftime("%Y-%m-%d %H:%M"))
    html = html.replace("__DATA_JSON__", json.dumps(registros, ensure_ascii=False))
    html = html.replace("__NOTA_AJUSTE_USD_JSON__", json.dumps(nota_ajuste, ensure_ascii=False))
    return html


def main():
    html = generar_html()
    with open(config.REPORT_HTML_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK: informe generado en {config.REPORT_HTML_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
