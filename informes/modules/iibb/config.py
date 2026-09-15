"""
Configuracion del modulo IIBB (Consultas > Contabilidad > Imputaciones en
Advertys).

Origen del pedido: ALESTE ADS S.A. es agencia (comisionista) y puede
deducir de la base imponible de IIBB los montos de Ordenes de Compra
(produccion) y Ordenes de Publicidad (medios) que factura a sus clientes a
modo de recupero de costo, sin margen. El informe final (ver
generate_html_report.py) es esa planilla para informar a ARBA: por
factura de venta, N° Factura + Cliente + Subtotal s/IVA + Monto OC/OP
deducible + Base imponible neta.

Se descarto un cruce por Orden de Compra individual (relevado en vivo
2026-07-22/23): Facturas no tiene columna de OC relacionada en su export
plano, y esa relacion solo aparece dentro de la grilla "Items Facturas" de
cada factura individual (no exportable en bulk, habria que abrir cada
factura una por una). Tambien se descarto el analisis pre-armado en
Advertys "Informe IIBB" (Informes > Analisis): es un Pivot Grid vacio sin
configurar, y el proveedor (Advertys/sistemas) informo que agregarle
filas/columnas por default requeria desarrollo pago.

La vista real que resuelve esto es "Imputaciones" (el libro de asientos
contables, Consultas > Contabilidad > Imputaciones): cada linea de
imputacion comparte la MISMA clave compuesta que ya usa modules/facturas
para armar "clave_factura" -- (TA, Asiento, TR, N° Referencia) -- asi que
se puede cruzar directo sin abrir facturas una por una.

Confirmado contra un export real (ViewID=Imputacion_ListView,
ObjectClassName=DPS_SAS_SR.Module.Imputacion, filtro "Todos"), 22685 filas,
abr-2024 a jul-2026. El default de la vista es "Mes Actual" (mismo gotcha
que Facturas/Compras) -- ver explore.py.

Plan de cuentas de ingresos relevado (Cuenta/Nombre Cuenta, clase
INGRESOS) y confirmado con Javier (2026-07-23): estas dos cuentas son el
"recupero de costo de terceros" deducible por IIBB, porque son la
contrapartida de venta -- sin margen -- de lo que el cliente le compra a
un tercero a traves de la agencia:
    411040 - VTA SERVICIOS DE TERCEROS (OC)   -> recupero produccion
    411075 - VTA SERVICIOS MEDIOS (OP)        -> recupero medios

Actualizacion confirmada con Javier (2026-08-18): el importe de "Servicio
de Agencia" tambien se descuenta de la base imponible, ademas del recupero
de terceros de arriba. Sale de:
    411020 - SERVICIO AGENCIA PRODUCCION
    411070 - SERVICIO AGENCIA MEDIOS
En Medios esta cuenta aparece siempre (confirmado contra la factura
000500001458: subtotal_ml = recupero 411075 + 411070 exacto). En
Produccion NO siempre hay una linea 411020 -- ej. la factura
000500001455 no tiene esa cuenta, el cargo de agencia esta ahi bajo FEE
(411010, item "Honorarios sobre produccion audiovisual"). Por eso, si una
factura no tiene ninguna linea 411020/411070, se usa como fallback su
linea de cuenta 411010 (FEE) -- ver CUENTA_FEE_FALLBACK y
generate_html_report._servicio_agencia_por_factura(). El resto de las
cuentas 411xxx/412xxx (VTA SERVICIOS PROPIOS, VTA X DIFERENCIA DE SERV
3EROS, MARK UP, BONIFICACIONES, INTERESES GANADOS) sigue siendo
margen/comision propia de la agencia que NO se descuenta.

Esta tabla se filtra a estas cuentas al ingestar (no se guarda el libro
mayor completo: este modulo es de un solo proposito, igual que
oc_pendientes_generar/estimados_pendientes_facturar) y se REEMPLAZA entera
en cada corrida (DELETE + INSERT), no upsert: no hay columna de ID de
linea en el export, y como es un recorte tiene sentido tratarlo como
snapshot del ultimo export en vez de mantener historial de upserts con una
clave sintetica fragil.

El informe final NO usa el filtro de periodo dinamico de los demas
modulos: se recorta en Python a los ultimos 6 meses (por fecha de factura)
en cada corrida de generate_html_report.py, no es un rango que el usuario
elija -- pedido explicito de Javier (2026-07-23).
"""

# --- Mapeo de columnas: "Nombre en el Excel de Advertys" -> "nombre_interno" ---
COLUMN_MAP = {
    "Clase": "clase",
    "Sub Clase": "sub_clase",
    "Rubro": "rubro",
    "Sub Rubro": "sub_rubro",
    "Mes": "periodo",
    "Cuenta": "cuenta",
    "Nombre Cuenta": "nombre_cuenta",
    "Sub.Cta.": "sub_cta",
    "Fecha": "fecha",
    "TA": "tipo_asiento",
    "Fecha Analisis": "fecha_analisis",
    "Asiento": "numero_asiento",
    "TR": "tipo_referencia",
    "N° Referencia": "numero_referencia",
    "Moneda": "moneda",
    "Centro Costo": "centro_costo",
    "Cotizacion": "cotizacion",
    "Importe": "importe",
    "Leyenda": "leyenda",
}

# Cuentas de ingreso que representan recupero de costo de terceros (OC/OP)
# deducible de IIBB -- ver docstring arriba. Cuenta llega como int desde
# Advertys (ej. 411040), no como texto.
CUENTAS_DEDUCIBLES = (411040, 411075)

# Cuentas de "Servicio de Agencia" (Produccion/Medios) -- tambien deducible
# de la base imponible, ver docstring arriba (actualizacion 2026-08-18).
CUENTAS_SERVICIO_AGENCIA = (411020, 411070)

# Si una factura no tiene ninguna linea 411020/411070, se usa su linea de
# FEE como fallback del cargo de agencia -- ver docstring arriba.
CUENTA_FEE_FALLBACK = 411010

# Todas las cuentas que efectivamente se guardan en la tabla (ver ingest.py)
CUENTAS_A_CARGAR = CUENTAS_DEDUCIBLES + CUENTAS_SERVICIO_AGENCIA + (CUENTA_FEE_FALLBACK,)

# Columnas obligatorias para que un registro se cargue
REQUIRED_COLUMNS = ["numero_referencia", "tipo_asiento", "numero_asiento", "tipo_referencia", "importe"]

# Columnas que arman la clave compuesta para cruzar con facturas.clave_factura
# (mismo orden que modules/facturas.config.CLAVE_COMPUESTA)
CLAVE_COMPUESTA = ["tipo_asiento", "numero_asiento", "tipo_referencia", "numero_referencia"]

DATE_COLUMNS = ["fecha", "fecha_analisis"]
NUMERIC_COLUMNS = ["cotizacion", "importe"]

# --- Rutas ---
DB_TABLE = "imputaciones_iibb"
REPORT_HTML_OUTPUT_PATH = "salida/informe_iibb.html"
