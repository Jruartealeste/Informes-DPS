"""
Configuracion del modulo Recibo Cliente (Administracion > Recibo Cliente en
Advertys).

Mapeo verificado contra un export real (ViewID=IC_ReciboCliente_ListView,
ObjectClassName=DPS_SAS_SR.Module.IC_ReciboCliente), 405 filas, con el
filtro de la vista puesto en "Todas" (es el historico completo, no hay
volumen para justificar una ventana rodante en la ingesta misma -- el
recorte a 6 meses lo hace generate_html_report.py del modulo de cruce).

"Nº Recibo" es clave unica de una sola columna (confirmado 0 duplicados en
el relevamiento real) -- a diferencia de Compras/Facturas/Ordenes de Compra
Produccion, esta vista SI trae un identificador propio sin necesidad de
armar una clave compuesta.

Ojo simbolo de grado: esta vista usa "Nº" con "º" (U+00BA, ordinal
masculino), igual que Compras y Ordenes de Compra Produccion (las dos son
vistas de "Administracion"/"Ordenes de Compra"); Facturas e IIBB usan "N°"
(U+00B0, grados) porque son vistas de "Consultas" -- mismo gotcha de
siempre, revisar bytes exactos si un mapeo nuevo tira KeyError.

Este modulo SOLO carga la cabecera del recibo (un recibo = una fila). El
detalle de que factura(s) cancela cada recibo vive en la pestana
"Referencias Canceladas" de cada recibo individual -- esa pestana NO viene
en este export en bloque (confirmado en vivo, 2026-08-04: el export de la
grilla trae unicamente las columnas de cabecera de abajo). Por eso ese
detalle se releva aparte con
modules/recibos/crawl_referencias_canceladas.py (crawl Playwright por
recibo, igual patron que modules/iibb/crawl_oc_por_factura.py).
"""

# --- Mapeo de columnas: "Nombre en el Excel de Advertys" -> "nombre_interno" ---
COLUMN_MAP = {
    "AAAAMM": "periodo",
    "Fecha": "fecha",
    "Nº Asiento": "numero_asiento",
    "Nº Recibo": "numero_recibo",
    "Cliente": "cliente",
    "Moneda": "moneda",
    "Anticipo": "anticipo",
    "Cancelaciones": "cancelaciones",
    "Retenciones": "retenciones",
    "CH Terceros": "ch_terceros",
    "CH Dif.Cliente": "ch_dif_cliente",
    "Efvo.Otros": "efvo_otros",
    "Estado": "estado",
    "Fecha Timbrado": "fecha_timbrado",
    "Dif Cambio": "dif_cambio",
    "Es Moneda Local": "es_moneda_local",
}

# Columnas obligatorias para que un registro se cargue
REQUIRED_COLUMNS = ["numero_recibo", "cliente", "fecha"]

# Columna que identifica un registro de forma unica
UNIQUE_KEY_COLUMN = "numero_recibo"

DATE_COLUMNS = ["fecha", "fecha_timbrado"]
NUMERIC_COLUMNS = [
    "anticipo", "cancelaciones", "retenciones", "ch_terceros",
    "ch_dif_cliente", "efvo_otros", "dif_cambio",
]

# --- Rutas ---
DB_TABLE = "recibos"
