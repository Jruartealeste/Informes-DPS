"""
Configuracion del modulo Orden Compra Produccion (seccion "Ordenes de
Compra" > "O.C. Produccion" en Advertys).

Mapeo verificado contra un export real (ViewID=OrdenCompraProduccion_ListView,
ObjectClassName=DPS_SAS_SR.Module.OrdenCompraProduccion), 201 filas.

Solo se releva "Orden Compra Produccion" (no "Orden Compra Gastos" ni
"Orden Compra Generica"): es la unica de las tres que trae la columna
"Estimado Costos" -- el vinculo real con un Estimado (y por transitividad,
con la OT). "O.C. Gastos" es administrativo interno (sin relacion a
OT/cliente) y "Orden Compra Generica" no expone ese vinculo en su grilla.

La columna "Estimado Costos" del export no es un ID: es texto libre con el
formato "<numero_estimado>-<titulo del estimado>" (ej.
"508-Realizacion de retratos en la planta de San Fernando"). Se parsea en
ingest.py con una regex (numero antes del primer "-") para armar la columna
sintetica numero_estimado y poder cruzar con estimados_costos.numero_estimado
-- confirmado 0 filas fuera de ese patron en el relevamiento real (201/201).

Ojo con el simbolo de grado: esta vista usa "N° O.C." con "º" (U+00BA,
ordinal masculino), mientras que Estimado Costos usa "N° Estimado"/"N° OT"
con "°" (U+00B0) -- no son el mismo caracter (mismo gotcha que
Compras/Facturas, ver README).
"""

# --- Mapeo de columnas: "Nombre en el Excel de Advertys" -> "nombre_interno" ---
COLUMN_MAP = {
    "Nº O.C.": "numero_oc",
    "Detalle": "detalle",
    "Rubro": "rubro",
    "Proveedor": "proveedor",
    "Cliente": "cliente",
    "Anunciante": "anunciante",
    "Grupo Anunciante": "grupo_anunciante",
    "Fecha Analisis": "periodo",
    "Estimado Costos": "estimado_costos_raw",
    "Fecha": "fecha",
    "Importe s/IVA": "importe_sin_iva",
    "Saldo": "saldo",
    "Ajustado": "ajustado",
    "Facturado": "facturado",
    "Comprado": "comprado",
    "Cobrado": "cobrado",
    "Pagado": "pagado",
    "Estado": "estado",
}

# Columnas obligatorias para que un registro se cargue
REQUIRED_COLUMNS = ["numero_oc"]

# Columna que identifica un registro de forma unica
UNIQUE_KEY_COLUMN = "numero_oc"

DATE_COLUMNS = ["fecha"]
NUMERIC_COLUMNS = ["importe_sin_iva", "saldo", "ajustado", "facturado", "comprado", "cobrado", "pagado"]

# --- Rutas ---
DB_TABLE = "ordenes_compra_produccion"
