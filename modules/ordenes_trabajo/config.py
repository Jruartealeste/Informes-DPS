"""
Configuracion del modulo Ordenes de Trabajo.

Mapeo verificado contra un export real de "Orden Trabajo" desde Advertys
(ALESTE ADS S.A., srv23.advertys.com.ar). Si Advertys agrega o renombra
columnas, ajustar COLUMN_MAP y sumarlas en ingest.py (SCHEMA) y en
generate_report.py si se quieren reflejar.
"""

# --- Mapeo de columnas: "Nombre en el Excel de Advertys" -> "nombre_interno" ---
COLUMN_MAP = {
    "Nro OT": "numero_ot",
    "Id": "id_advertys",
    "Negocio": "negocio",
    "Anunciante": "anunciante",
    "Marca": "marca",
    "Producto": "producto",
    "Resumen": "resumen",
    "F.Abierta": "fecha_abierta",
    "F.Cerrada": "fecha_cerrada",
    "Abierta por...": "responsable",
    "Equipo": "equipo",
    "Estado": "estado",
    "Renta Teorica": "renta_teorica",
    "Renta Real": "renta_real",
}

# Columnas que son obligatorias para que un registro se cargue (ajustable)
REQUIRED_COLUMNS = ["numero_ot", "anunciante", "fecha_abierta"]

# Columna que identifica un registro de forma unica (para no duplicar al
# volver a importar el mismo export, o uno mas nuevo que lo pisa)
UNIQUE_KEY_COLUMN = "numero_ot"

# Columnas de fecha (se van a convertir a formato ISO al importar)
DATE_COLUMNS = ["fecha_abierta", "fecha_cerrada"]

# Columnas numericas (se van a convertir a float, tolerando "$", "." de miles, etc.)
NUMERIC_COLUMNS = ["renta_teorica", "renta_real"]

# --- Rutas ---
DB_TABLE = "ordenes_trabajo"
REPORT_OUTPUT_PATH = "informe_dinamico.xlsx"
REPORT_HTML_OUTPUT_PATH = "informes/informe_dinamico.html"

# Carpeta donde caeria el export si en algun momento se logra automatizar
# (por ahora se usa manualmente pasando la ruta al script ingest.py)
WATCH_FOLDER = "exports_pendientes"
