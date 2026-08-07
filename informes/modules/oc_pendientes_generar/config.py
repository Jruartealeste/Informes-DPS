"""
Configuracion del modulo "OCs Pendientes de Generar" (shortcut del menu
"Cuentas y Produccion" en Advertys; vista real
ViewID=EstimadoDetalle_ListView_OC_Pendientes,
ObjectClassName=DPS_SAS_SR.Module.EstimadoDetalle).

Es una vista PROPIA de Advertys que ya filtra a los items de Estimado de
Costos que tienen Proveedor cargado pero todavia no tienen una Orden de
Compra emitida -- exactamente la regla de negocio "item con proveedor sin
OC" acordada con Javier (2026-07-21) para marcar una OT como bloqueada para
el cierre (ver modules/pendientes/). No hace falta reconstruir esa logica
a mano item por item: Advertys ya la resuelve en esta grilla.

Mapeo verificado contra un export real (2026-07-21, 4 filas). Nombres de
columna con simbolo de grado: esta vista usa "N° Estimado" con "°"
(U+00B0) -- confirmado byte a byte, mismo simbolo que
modules/estimados_costos/config.py.

Esta tabla NO trae columna de item/ID propio (una fila = un item de un
estimado, sin identificador estable entre corridas) -- por eso
ingest.py REEMPLAZA la tabla entera en cada corrida en vez de hacer
upsert por clave (ver nota en ingest.py: es un snapshot de "lo que falta
ahora mismo", un item que se resuelve deja de aparecer en el export).
"""

# --- Mapeo de columnas: "Nombre en el Excel de Advertys" -> "nombre_interno" ---
COLUMN_MAP = {
    "Fecha Analisis": "periodo",
    "N° Estimado": "numero_estimado",
    "Detalle": "detalle",
    "Rubro Produccion": "rubro_produccion",
    "Proveedor": "proveedor",
    "Costo": "costo",
    "Ganancia": "ganancia",
    "Total Facturado": "total_facturado",
    "Anunciante": "anunciante",
    "Nombre del Cliente": "nombre_cliente",
    "Estado": "estado",
    "Requiere Autor.OC": "requiere_autorizacion_oc",
}

# Columnas obligatorias para que un registro se cargue
REQUIRED_COLUMNS = ["numero_estimado"]

# No hay clave unica real en este export (ver docstring) -- este modulo no
# usa UNIQUE_KEY_COLUMN, ingest.py reemplaza la tabla entera.

DATE_COLUMNS = []
NUMERIC_COLUMNS = ["costo", "ganancia", "total_facturado"]

# --- Rutas ---
DB_TABLE = "oc_pendientes_generar"
