"""
Configuracion del modulo "Estim.Pendientes Facturar" (shortcut del menu
"Cuentas y Produccion" en Advertys; vista real
ViewID=EstimadoCostos_ListView_Pendiente_de_Facturar,
ObjectClassName=DPS_SAS_SR.Module.EstimadoCostos).

Es una vista PROPIA de Advertys que ya filtra a los Estimados de Costo que
todavia tienen saldo pendiente de facturar (columna "Pendiente Facturar" >
0) -- la contracara de la regla "sin factura contabilizada" acordada con
Javier (2026-07-21): si un estimado sigue en esta lista, todavia no se le
puede considerar facturado/contabilizado, y por lo tanto no puede
Finalizarse (ver modules/pendientes/).

Mapeo verificado contra un export real (2026-07-21, 16 filas). Ojo: el
simbolo de grado varia DENTRO del mismo export -- "N° Estimado" y "N° OT"
usan "°" (U+00B0), pero "Nº Cliente" usa "º" (U+00BA, ordinal masculino).
Confirmado byte a byte -- no asumir que todas las columnas "N°/Nº" de un
mismo archivo usan el mismo caracter.

Esta tabla SI tiene una clave natural (numero_estimado, una fila por
estimado) pero igual se reemplaza entera en cada corrida (ver ingest.py):
es un snapshot de "que esta pendiente ahora mismo", y un estimado que se
termina de facturar desaparece del export -- si hicieramos upsert quedaria
marcado como pendiente para siempre.
"""

# --- Mapeo de columnas: "Nombre en el Excel de Advertys" -> "nombre_interno" ---
COLUMN_MAP = {
    "Fecha Analisis": "periodo",
    "N° Estimado": "numero_estimado",
    "Nº Cliente": "numero_cliente",
    "N° OT": "numero_ot",
    "Anunciante": "anunciante",
    "Producto": "producto",
    "Titulo": "titulo",
    "Total Costo": "total_costo",
    "Total Ganancia": "total_ganancia",
    "Total Facturado": "total_facturado",
    "Pendiente Facturar": "pendiente_facturar",
    "Estado": "estado",
    "Moneda": "moneda",
}

# Columnas obligatorias para que un registro se cargue
REQUIRED_COLUMNS = ["numero_estimado"]

# No se usa upsert por clave (ver docstring), pero numero_estimado es la
# clave natural para cruzar con estimados_costos.numero_estimado.
UNIQUE_KEY_COLUMN = "numero_estimado"

DATE_COLUMNS = []
NUMERIC_COLUMNS = ["total_costo", "total_ganancia", "total_facturado", "pendiente_facturar"]

# --- Rutas ---
DB_TABLE = "estimados_pendientes_facturar"
