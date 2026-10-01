"""
Configuracion del modulo Facturacion-ALUAR: ventas a ALUAR por concepto
contable y tipo de venta (Produccion/Medios), mes a mes.

Origen (Javier, 2026-09-28): ya existia un analisis puntual de esto (un
artifact HTML armado a mano en otra sesion, "Ventas ALUAR por Concepto",
jul-2025 a ago-2026) y pidio sumarlo al dashboard como modulo vivo, que se
recalcule solo en cada refresh en vez de quedar congelado.

A diferencia del resto de los modulos, este NO tiene su propio export.py
de Advertys: reusa datos que YA ingesta el pipeline --
    - `facturas` (modules/facturas) filtrada a Cliente LIKE 'ALUAR%',
      para saber que documentos son de este cliente.
    - El export CRUDO de Imputaciones (`exploracion/iibb_export.xlsx`,
      generado por `modules/iibb/export.py`, TODAS las cuentas sin
      filtrar -- mismo archivo que ya reusa modules/balance_mensual, ver
      su nota en el README) para el detalle contable por cuenta.
Por eso antes de correr este modulo hace falta `facturas` al dia y un
`python -m modules.iibb.export` reciente (no hace falta el ingest de IIBB
en si, solo el .xlsx crudo).

Cuentas de ingreso 411xxx relevadas para ALUAR y su categoria de negocio
(mapeo confirmado con Javier, mismo que ya usa el analisis original):
    411010 FEE                          -> Servicio de Agencia / Fee
    411020 SERVICIO AGENCIA PRODUCCION  -> Servicio de Agencia / Fee
    411070 SERVICIO AGENCIA MEDIOS      -> Servicio de Agencia / Fee
    411030 VTA SERVICIOS PROPIOS        -> Servicios propios
    411035 VTA X DIFERENCIA SERV 3EROS  -> Margen sobre terceros
    411038 MARK UP PRODUCCION           -> Margen sobre terceros
    411076 VENTA MARKUP MEDIOS          -> Margen sobre terceros
    411040 VTA SERVICIOS DE TERCEROS(OC)-> Recupero costo terceros (sin margen)
    411075 VTA SERVICIOS MEDIOS (OP)    -> Recupero costo terceros (sin margen)
El "concepto" (nombre legible de cada cuenta) NO se hardcodea: sale de la
columna "Nombre Cuenta" del export crudo (moda por cuenta), para no
desincronizarse si Advertys le cambia el texto.

Facturas canceladas (hallazgo real, verificado 2026-09-28): Advertys
registra la cancelacion de una factura como un documento CONTABLE nuevo
(TR='CA' en vez de 'FA' en Imputaciones) que revierte linea por linea a
la factura original, y a veces la reemplaza por una factura nueva en un
mes distinto (visto en vivo: factura de jul-2026 cancelada y reemitida en
ago-2026 con el mismo importe). Sumar Imputaciones con signo (sin abs())
ya neta la mayoria de estos pares automaticamente porque Advertys usa el
MISMO monto con signo contrario -- pero cuando el reemplazo cae en un mes
distinto al original, sumar por mes calendario deja el monto pegado al
mes viejo en vez del nuevo. La sola cancelacion (TR='CA') SIEMPRE hay que
excluirla de la suma (nunca es venta real), y ademas hay que excluir la
factura ORIGINAL que cancela -- si no, un reemplazo en otro mes duplica
el monto (una vez en el mes viejo, otra en el nuevo).

La unica forma confiable de saber que factura original cancela cada CA es
el campo "Factura Relacionada" del detalle de la factura en Advertys (no
sale de ningun export bulk) -- confirmado en vivo que vive en la pestana
"Datos Generales" (la que abre por default, sin click extra) tanto para
facturas Produccion (DPS_Factura, TR=CA ej. 000500000017 -> Factura
Relacionada 000500000555) como Medios (FacturasMedios, TR=CA ej.
000500000015 -> Factura Relacionada 000500000538 -- mismo caso que ya
documenta el README en la seccion de gotchas de IIBB). Ver
crawl_facturas_relacionadas.py: crawl de solo lectura, acotado a los
documentos TR='CA' de ALUAR (15 en toda la historia relevada 2026-09-28,
corre en minutos).

Ajuste manual conocido (factura 000500001377, "Hosting x 10 Meses INFA",
31/3/2026, USD 640): facturada a costo puro sin fee ni markup, Advertys la
neteo directo contra la cuenta de costo 510010 en vez de una cuenta de
venta 411xxx -- la unica factura de ALUAR con este patron (confirmado
2026-09-16 en el analisis original). Como nunca cae en ninguna cuenta de
CUENTAS_INGRESO, no aparece sola en la ingesta normal: se suma a mano en
ingest.py via AJUSTE_MANUAL_USD_HOSTING, solo si esa factura sigue
existiendo en `facturas` (si se anula alguna vez, deja de sumarse solo).
"""

CLIENTE_LIKE = "ALUAR%"

# Cuenta -> categoria de negocio (ver docstring). El nombre de cada cuenta
# (columna "concepto" del informe) sale del dato real, no de aca.
CATEGORIA_POR_CUENTA = {
    411010: "Servicio de Agencia / Fee",
    411020: "Servicio de Agencia / Fee",
    411070: "Servicio de Agencia / Fee",
    411030: "Servicios propios",
    411035: "Margen sobre terceros",
    411038: "Margen sobre terceros",
    411076: "Margen sobre terceros",
    411040: "Recupero costo terceros (sin margen)",
    411075: "Recupero costo terceros (sin margen)",
}

CUENTAS_INGRESO = tuple(CATEGORIA_POR_CUENTA)

# Cuenta que solo aparece en Produccion durante la reclasificacion temporal
# de Advertys (confirmado con Javier, ver README): si un mes/tipo_venta
# tiene algun monto en esta cuenta, todas sus filas de Servicios
# propios/Margen sobre terceros de ese mes se marcan reclasificado=True
# (el reparto entre esas 2 categorias no es confiable ese mes, aunque el
# total si). Deteccion dinamica, no una fecha hardcodeada -- si Advertys
# repite este esquema en el futuro, se marca solo.
CUENTA_RECLASIFICACION = 411038
CUENTAS_AFECTADAS_POR_RECLASIFICACION = (411030, 411035, 411038)

TA_TIPO_VENTA = {"FP": "Producción", "FM": "Medios"}

# Ajuste manual conocido -- ver docstring. numero_referencia identifica la
# factura real en `facturas`; si no existe (se anulo), ingest.py no lo suma.
AJUSTE_MANUAL_USD_HOSTING = {
    "numero_referencia": "000500001377",
    "tipo_asiento": "FP",
    "monto": 892160.0,
    "categoria": "Recupero costo terceros (sin margen)",
    "concepto": "Hosting INFA x 10 Meses (facturado a costo puro, neteado contra cuenta de costo 510010 -- sin linea 411xxx, ver notas del modulo)",
}

IMPUTACIONES_EXPORT_PATH = "exploracion/iibb_export.xlsx"

# --- Rutas ---
DB_TABLE = "facturacion_aluar"
DB_TABLE_RELACIONADAS = "facturas_relacionadas_aluar"
REPORT_HTML_OUTPUT_PATH = "salida/informe_facturacion_aluar.html"
