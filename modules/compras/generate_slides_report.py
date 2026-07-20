"""
Genera la version "presentacion" (slides tipo poster) del informe de Compras:
mismo dataset y motor de filtro/agregacion que generate_html_report.py, pero
mostrado como un deck de pantallas navegables con varias tarjetas chicas por
pantalla -- resumen ejecutivo, no el detalle completo.

No reemplaza informe_compras.html -- son dos entregables paralelos: este es
para presentar/proyectar un resumen, el otro sigue siendo la referencia con
el detalle fila por fila.

Uso:
    python -m modules.compras.generate_slides_report
"""
import html_report as hr
from . import config
from .generate_html_report import ESTADO_COLOR, ESTADO_ORDEN, cargar_datos

# Paleta categorica (dataviz skill / references/palette.md, slots 1-3: blue,
# green, magenta) para "tipo de compra" -- NO es la identidad ALESTE (esa
# queda para el acento de marca y las series de una sola magnitud). Orden
# fijo por entidad, no por magnitud, para que el color no cambie si el
# usuario filtra el periodo.
TIPO_COLOR = {
    "Medios": {"light": "#2a78d6", "dark": "#3987e5"},
    "Gastos": {"light": "#008300", "dark": "#008300"},
    "Produccion": {"light": "#e87ba4", "dark": "#d55181"},
}
TIPO_ORDEN = ["Medios", "Gastos", "Produccion"]


def main():
    df = cargar_datos()
    if df.empty:
        print("No hay datos cargados todavia. Corre 'python -m modules.compras.ingest' primero.")
        return

    records = hr.records_from_df(df, [
        "proveedor", "tipo_compra", "tipo_proveedor", "numero_referencia", "fecha_factura",
        "moneda", "importe_sin_iva_signado", "total_impositivo", "estado", "_periodo",
    ])

    spec = {
        "dateField": "_periodo",
        "statTiles": [
            {"label": "Compras (todos los estados)", "kind": "count", "fmt": "int"},
            {"label": "Compras contabilizadas", "kind": "count", "fmt": "int", "filter": {"field": "estado", "equals": "Contabilizado"}},
            {"label": "Total impositivo (contabilizadas)", "kind": "sum", "field": "total_impositivo", "fmt": "money", "filter": {"field": "estado", "equals": "Contabilizado"}},
            {"label": "Proveedores distintos", "kind": "nunique", "field": "proveedor", "fmt": "int"},
        ],
        "charts": [
            {"mount": "chart-mes", "type": "line", "groupBy": "_periodo", "agg": "sum", "field": "total_impositivo", "fmt": "money", "height": 220},
            {"mount": "chart-estado", "type": "bar", "groupBy": "estado", "agg": "count", "fmt": "int", "colors": ESTADO_COLOR, "order": ESTADO_ORDEN, "height": 200},
            {"mount": "chart-tipo", "type": "stacked100", "groupBy": "tipo_compra", "agg": "sum", "field": "total_impositivo", "fmt": "money", "colors": TIPO_COLOR, "order": TIPO_ORDEN},
            {"mount": "chart-proveedores", "type": "hbar", "groupBy": "proveedor", "agg": "sum", "field": "total_impositivo", "fmt": "money", "topN": 10, "rowH": 32},
        ],
        "tables": [
            {
                "mount": "tabla-proveedores", "groupBy": "proveedor",
                "aggs": [
                    {"key": "compras", "op": "count"},
                    {"key": "importe_sin_iva", "op": "sum", "field": "importe_sin_iva_signado"},
                    {"key": "total_impositivo", "op": "sum", "field": "total_impositivo"},
                ],
                "columns": [["proveedor", "Proveedor"], ["compras", "Compras"], ["importe_sin_iva", "Importe s/IVA"], ["total_impositivo", "Total impositivo"]],
                "numericCols": ["importe_sin_iva", "total_impositivo"],
                "sort": {"key": "total_impositivo", "dir": "desc"},
                "topN": 12,
            },
        ],
    }

    slides = [
        hr.cover_slide(
            "Informe de Compras",
            "ALESTE ADS S.A. - Advertys",
            "Resumen ejecutivo del periodo",
        ),
        hr.slide(
            hr.slide_header("Resumen", "KPIs, evolucion y composicion")
            + hr.poster_grid([
                hr.poster_card("Resumen ejecutivo", hr.stat_tiles_mount(), css_class="poster-kpis"),
                hr.poster_card("Total impositivo por mes", hr.mount("chart-mes")),
                hr.poster_card("Compras por estado", hr.mount("chart-estado")),
                hr.poster_card("Compras por tipo", hr.mount("chart-tipo")),
            ], cols=2),
            css_class="slide-poster",
        ),
        hr.slide(
            hr.slide_header("Ranking", "Proveedores")
            + hr.poster_grid([
                hr.poster_card("Top 10 proveedores por total impositivo", hr.mount("chart-proveedores")),
                hr.poster_card("Top 12 proveedores (detalle)", hr.mount("tabla-proveedores")),
            ], cols=1),
            css_class="slide-poster",
        ),
        hr.closing_slide(
            "Fin del resumen",
            "Informe generado automaticamente desde advertys.db. Para el detalle fila por fila, "
            "buscador y exportacion, ver informe_compras.html.",
        ),
    ]

    html = hr.slide_shell("Informe de Compras", "ALESTE ADS S.A. - Advertys", slides, records, spec)

    with open(config.REPORT_SLIDES_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK: presentacion generada en {config.REPORT_SLIDES_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
