"""
Configuracion del modulo Orden Publicidad (Medios > Ordenes Publicidad >
Navegacion en Advertys).

Mapeo verificado contra un export real (ViewID=OrdenPublicidad_ListView,
ObjectClassName=DPS_SAS_SR.Module.OrdenPublicidad), 1295 filas, filtro
"Todos".

**Por que "Navegacion" y no "Consulta"** (el otro nodo hoja bajo "Ordenes
Publicidad", ver explore.py): la grilla de "Consulta" no trae NINGUNA
columna de monto (solo Año OP/Mes OP/Orden/Barra/Pauta/Proveedor/Medio/
Estado/Ordenando/Fecha) -- confirmado exportando esa vista real. Solo
"Navegacion" expone "Total Orden" (el importe real de la orden, SIN IVA,
independiente del estado) y "Saldo" (el saldo pendiente actual, que
Advertys pisa a 0 en cuanto la orden pasa a "Utilizada" -- no sirve para
"cuanto valia la orden", solo para "cuanto falta resolver hoy").

**Motivacion (2026-08-04):** modules/cobranza_proveedores necesitaba el
importe sin IVA real de cada Orden de Publicidad para la columna "Saldo a
Pagar", y hasta ahora lo parseaba del texto crudo que Advertys muestra en
la celda "Orden Compra" de cada factura Medios (formato "<numero> -
<proveedor> -$<monto> - <estado>"). Se confirmo que ese texto trae el
SALDO actual, no el importe original -- exactamente $0,00 para el 100% de
las OP en estado "Utilizada" de una muestra real. Este modulo reemplaza
ese parseo con el dato real de Advertys.

**Gotcha real: "Orden" NO es una clave unica por si sola.** Es un
correlativo que arranca de nuevo cada año (ej. Orden 1001 existe tanto en
2025 como en 2026, con proveedores distintos) -- confirmado: de 1295
filas, 1288 combinaciones unicas de (Año OP, Orden); la clave real es
compuesta. Peor: el texto crudo que ya cruza `cobranza_proveedores` (el
que arma `orden_compra_raw`) SOLO trae el numero de Orden pelado, sin
año -- de una muestra real de 164 numero_oc referenciados desde facturas,
116 (71%) colisionan con mas de una fila en esta tabla si se busca sin
año. `cobranza_proveedores._oc_por_factura()` desambigua cruzando tambien
por Proveedor (texto ya parseado de `orden_compra_raw`): reduce la
colision a 12/164 (7%), que quedan marcados "ambiguo" (mismo criterio que
ya usa `_matchear_facturas` para el caso FP/FM de Facturas). Aun asi, 2 de
1288 combinaciones (Año OP, Orden) tienen mas de una fila real en Advertys
incluso con año (ej. Orden 4001 de 2024: 6 proveedores/medios distintos
bajo el mismo numero -- parece un caso real de datos superpuestos en
Advertys, no un error de este script); `ingest.py` se queda con la ultima
fila leida para esos casos (mismo criterio silencioso que ya usan
`ON CONFLICT DO UPDATE` en el resto de los modulos).

Ojo con el simbolo "Año" -- viene con "ñ" (U+00F1) normal, no es el
gotcha usual de "N°"/"Nº" de otros modulos.
"""

# --- Mapeo de columnas: "Nombre en el Excel de Advertys" -> "nombre_interno" ---
COLUMN_MAP = {
    "Año OP": "ano_op",
    "Mes OP": "mes_op",
    "Fecha": "fecha",
    "Orden": "numero_oc",
    "Barra": "barra",
    "Pauta": "pauta",
    "Proveedor": "proveedor",
    "Cliente": "cliente",
    "Anunciante": "anunciante",
    "Medio": "medio",
    "Alicuota Iva": "alicuota_iva",
    "Total Orden": "importe_sin_iva",
    "Saldo": "saldo",
    "Importe Final": "importe_con_iva",
    "Estado": "estado",
    "Facturado": "facturado",
    "Comprado": "comprado",
    "Cobrado": "cobrado",
    "Pagado": "pagado",
    "Ajustado": "ajustado",
    "Cartel Error": "cartel_error",
}

# Columnas obligatorias para que un registro se cargue
REQUIRED_COLUMNS = ["ano_op", "numero_oc"]

# Clave unica real: compuesta (ver docstring, "Orden" solo no alcanza)
UNIQUE_KEY_COLUMNS = ["ano_op", "numero_oc"]

DATE_COLUMNS = ["fecha"]
NUMERIC_COLUMNS = [
    "alicuota_iva", "importe_sin_iva", "saldo", "importe_con_iva",
    "facturado", "comprado", "cobrado", "pagado", "ajustado",
]

# --- Rutas ---
DB_TABLE = "ordenes_publicidad"
