"""
Configuracion del modulo Estimados de Costo (Cuentas y Produccion >
Estimado Costos en Advertys).

Mapeo verificado contra un export real (ViewID=EstimadoCostos_ListView,
ObjectClassName=DPS_SAS_SR.Module.EstimadoCostos), 506 filas.

Cada Estimado de Costo cuelga de una Orden de Trabajo (columna "N° OT" del
export, sin nulos en el relevamiento real) -- es la clave que permite cruzar
esta tabla con "ordenes_trabajo" para el informe de Pendientes (ver
modules/pendientes/). A su vez cada Orden de Compra Produccion referencia a
un Estimado por numero (ver modules/ordenes_compra/config.py).

Ojo con el simbolo de grado: este export usa "N° Estimado" / "N° OT" con
"°" (U+00B0), mientras que Ordenes de Compra usa "N° O.C." con "º" (U+00BA,
ordinal masculino) -- no son el mismo caracter, confirmar bytes si un mapeo
nuevo tira KeyError (mismo gotcha que Compras/Facturas, ver README).

"Fecha Analisis" en este export NO es una fecha real: es un periodo AAAAMM
(igual concepto que Compras), la fecha real de la solicitud esta en
"Solicita" (timestamp). Se mapean por separado.
"""

# --- Mapeo de columnas: "Nombre en el Excel de Advertys" -> "nombre_interno" ---
COLUMN_MAP = {
    "N° Estimado": "numero_estimado",
    "N° OT": "numero_ot",
    "Fecha Analisis": "periodo",
    "Solicita": "fecha_solicita",
    "Anunciante": "anunciante",
    "Grupo Anunciante": "grupo_anunciante",
    "Cliente": "cliente",
    "Producto": "producto",
    "Titulo": "titulo",
    "Moneda": "moneda",
    "Sub Total": "sub_total",
    "Neto": "neto",
    "Total Comprado": "total_comprado",
    "Total Facturado": "total_facturado",
    "Total Ordenado": "total_ordenado",
    "Estado": "estado",
}

# Columnas obligatorias para que un registro se cargue
REQUIRED_COLUMNS = ["numero_estimado", "numero_ot"]

# Columna que identifica un registro de forma unica
UNIQUE_KEY_COLUMN = "numero_estimado"

DATE_COLUMNS = ["fecha_solicita"]
NUMERIC_COLUMNS = ["sub_total", "neto", "total_comprado", "total_facturado", "total_ordenado"]

# --- Rutas ---
DB_TABLE = "estimados_costos"
