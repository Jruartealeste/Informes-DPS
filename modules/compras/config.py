"""
Configuracion del modulo Compras (Administracion > Compras en Advertys).

Mapeo verificado contra un export real (ViewID=DocumentoProveedor_ListView,
ObjectClassName=DPS_SAS_SR.Module.DocumentoProveedor), 2913 filas, jun-2024 a
jul-2026.

Aviso importante: el Excel de Advertys trae DOS columnas con el mismo
nombre literal "Importe s/IVA" (posiciones 9 y 16 del export). La primera es
el importe siempre positivo; la segunda viene con signo contable (negativo
en notas de credito/anulaciones). Por eso ese caso especial no se resuelve
con COLUMN_MAP (que requiere nombres unicos) sino a mano en ingest.py,
renombrando la columna en la posicion 16 antes de aplicar el resto del mapeo.

No hay una clave unica de una sola columna: "N Asiento" se reinicia por
tipo/periodo y se repite. La clave real es la combinacion
(TA, N Asiento, TR, N Referencia), que sí es unica en todo el dataset
relevado. Se arma como columna sintetica "clave_compra" en ingest.py.
"""

# --- Mapeo de columnas: "Nombre en el Excel de Advertys" -> "nombre_interno" ---
# Nota: NO incluye la segunda "Importe s/IVA" (con signo) — se maneja aparte.
COLUMN_MAP = {
    "AAAAMM": "periodo",
    "Tipo Compra": "tipo_compra",
    "Tipo Proveedor": "tipo_proveedor",
    "Proveedor": "proveedor",
    "TA": "tipo_asiento",
    "Nº Asiento": "numero_asiento",
    "TR": "tipo_referencia",
    "N° Referencia": "numero_referencia",
    "Fecha Factura": "fecha_factura",
    "Importe s/IVA": "importe_sin_iva",
    "Total Impositivo": "total_impositivo",
    "Moneda": "moneda",
    "Empleado": "empleado",
    "Orden Compra Generica": "orden_compra_generica",
    "Leyenda": "leyenda",
    "Estado": "estado",
    "Tiene Adjunto": "tiene_adjunto",
}

# Nombre interno de la segunda columna "Importe s/IVA" (con signo contable)
COLUMNA_IMPORTE_SIGNADO = "importe_sin_iva_signado"

# Columnas obligatorias para que un registro se cargue
REQUIRED_COLUMNS = ["numero_referencia", "proveedor", "fecha_factura"]

# Columnas que arman la clave unica compuesta (ver docstring)
CLAVE_COMPUESTA = ["tipo_asiento", "numero_asiento", "tipo_referencia", "numero_referencia"]

DATE_COLUMNS = ["fecha_factura"]
NUMERIC_COLUMNS = ["importe_sin_iva", "total_impositivo", COLUMNA_IMPORTE_SIGNADO]

# --- Rutas ---
DB_TABLE = "compras"
REPORT_OUTPUT_PATH = "informe_compras.xlsx"
REPORT_HTML_OUTPUT_PATH = "informe_compras.html"
