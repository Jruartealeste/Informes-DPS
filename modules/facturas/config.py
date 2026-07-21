"""
Configuracion del modulo Facturas (Consultas > Facturacion > Facturas en
Advertys).

Mapeo verificado contra un export real (ViewID=DPS_Factura_ListView,
ObjectClassName=DPS_SAS_SR.Module.DPS_Factura), 1074 filas, abr-2024 a
jul-2026, con el filtro de la vista puesto en "Todos" (el default de esa
vista es "Mes Actual", que solo trae el mes en curso — ver
modules/facturas/explore.py).

Igual que en Compras, no hay una columna con clave unica propia: "N° Asiento"
se repite entre TA distintos. La clave real es la combinacion
(TA, N° Asiento, TR, N° Referencia), unica en todo el dataset relevado.
Se arma como columna sintetica "clave_factura" en ingest.py.

Ojo: Advertys NO es consistente entre modulos con el caracter que usa para
"N°/Nº": en Compras exporta con "Nº" (masculine ordinal indicator, U+00BA)
y aca con "N°" (degree sign, U+00B0). Si un mapeo de columnas falla con
"KeyError" para una columna que visualmente existe, revisar el caracter
exacto (ver bytes UTF-8) antes de asumir que cambio el nombre.

Nota: "Anunciante" y "Cliente" NO son lo mismo aca (a diferencia de Ordenes
de Trabajo, donde el anunciante es directamente "el cliente"): "Anunciante"
es la marca/unidad de negocio (ej. "FATE - MARKETING"), "Cliente" es la
razon social que se factura (ej. "FATE S.A.I.C.I."). Util para cruces
futuros: "Cliente"+"Cuit" es la entidad facturable real.

Tambien: "Total ML" no siempre es exactamente "Subtotal ML" + "Impuestos ML"
(hay diferencias de hasta ~27000 en el dataset relevado, probablemente por
conceptos no desglosados en este export, ej. percepciones). Se cargan las
tres columnas tal cual vienen, sin recalcular ninguna a partir de las otras.
"""

# --- Mapeo de columnas: "Nombre en el Excel de Advertys" -> "nombre_interno" ---
COLUMN_MAP = {
    "AAAAMM": "periodo",
    "Fecha": "fecha",
    "FCE": "fce",
    "TR": "tipo_referencia",
    "N° Referencia": "numero_referencia",
    "Anunciante": "anunciante",
    "Cliente": "cliente",
    "Cuit": "cuit",
    "TA": "tipo_asiento",
    "N° Asiento": "numero_asiento",
    "Cai": "cai",
    "Producto": "producto",
    "Subtotal ML": "subtotal_ml",
    "Impuestos ML": "impuestos_ml",
    "Total ML": "total_ml",
    "Moneda": "moneda",
    "Cotizacion": "cotizacion",
    "Subtotal ME": "subtotal_me",
    "Impuestos ME": "impuestos_me",
    "Total ME": "total_me",
    "Estado": "estado",
    "Tiene NCND": "tiene_ncnd",
    "Tiene IC": "tiene_ic",
    "Tiene Items Impresion": "tiene_items_impresion",
}

# Columnas obligatorias para que un registro se cargue
REQUIRED_COLUMNS = ["numero_referencia", "cliente", "fecha"]

# Columnas que arman la clave unica compuesta (ver docstring)
CLAVE_COMPUESTA = ["tipo_asiento", "numero_asiento", "tipo_referencia", "numero_referencia"]

DATE_COLUMNS = ["fecha"]
NUMERIC_COLUMNS = [
    "subtotal_ml", "impuestos_ml", "total_ml",
    "cotizacion", "subtotal_me", "impuestos_me", "total_me",
]

# --- Rutas ---
DB_TABLE = "facturas"
REPORT_OUTPUT_PATH = "informe_facturas.xlsx"
REPORT_HTML_OUTPUT_PATH = "informes/informe_facturas.html"
