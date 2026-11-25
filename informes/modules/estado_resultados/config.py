"""
Configuracion del modulo Estado de Resultados (EERR).

Fuente principal: el export "Reporte Balance Mensual" de Advertys
(modules/balance_mensual/export.py -> exploracion/balance_mensual_export.csv),
agregado por cuenta x mes. Es la misma fuente que alimenta la pestana
"BCE Mensual 2026" de la planilla Google "EERR ALESTE" (pestana "EERR Nuevo"),
y este modulo replica esa estructura -- con las correcciones del 2026-11-25
(ver README, seccion Estado de Resultados).

Fuente secundaria (manual): inputs.json, con lo que NO sale de Advertys:
- staff_freelance / staff_blanco: salen de la planilla "Gastos RRHH".
- retiro_socio_estimado: numero estimado, solo para que el EERR sea mas real.

Criterios decididos por Javier (2026-11-25):
- Staff Freelance va corrido un mes A PROPOSITO: la factura llega a
  principios del mes siguiente por el sueldo del mes anterior y se imputa
  por criterio devengado. No es un bug. inputs.json ya guarda los valores
  imputados al mes devengado; "meses_incompletos" marca los meses que
  todavia no tienen todas las facturas.
- Retiro socio: estimado, queda dentro del RESULTADO (rotulado "estimado").
- Medios se muestra de dos maneras: bruto (con pass-through OP) y neto.
"""
from pathlib import Path

BALANCE_CSV = Path("exploracion/balance_mensual_export.csv")
INPUTS_JSON = Path(__file__).with_name("inputs.json")
REPORT_HTML_OUTPUT_PATH = "salida/informe_estado_resultados.html"
ANIO_DEFAULT = 2026

# --- Ingresos (codigo de cuenta -> seccion) ---------------------------------
INGRESOS_PRODUCCION = {
    411010, 411020, 411030, 411035, 411038, 411040, 411050, 411051, 411098, 411099,
}
INGRESOS_MEDIOS = {411070, 411071, 411075, 411076, 411080, 411095, 411097}
# Medios NETO = lo que es ingreso propio de la agencia (servicio + markup +
# bonificaciones). El resto de Medios es pass-through (venta OP, se factura
# al cliente lo que se paga al medio).
INGRESOS_MEDIOS_NETO = {411070, 411071, 411076, 411080, 411097}
INGRESOS_MEDIOS_PASSTHROUGH = {411075, 411095}

# --- Costos directos --------------------------------------------------------
COSTOS_MEDIOS = {510020, 510021, 510023, 510040}
COSTOS_PRODUCCION = {510010, 510011, 510022, 510050, 517122, 517250, 517260}

# --- Costos fijos (codigo -> grupo) -----------------------------------------
GRUPOS_FIJOS = {
    "Agencia": {517320, 517330, 517430, 517570, 522011, 517517, 517580, 517585},
    "Alquiler": {517515},
    "Honorarios": {515010, 515050, 515070},
    "MyV": {517120, 519040, 519041},
    "Servicios": {517210, 517220, 517230, 517231, 517410, 517530, 517596},
    "Sistema": {515020, 517545, 517597},
    "Imprenta": {517540, 517550, 517555},
    "Varios": {517571},
}
ORDEN_GRUPOS_FIJOS = list(GRUPOS_FIJOS)

# Cuentas del libro que NO suman al EERR porque su monto sale de inputs.json
# (el libro las trae por factura, el EERR las imputa por devengado) o porque
# se muestran aparte. Se informan como control, no se pierden en silencio.
CUENTAS_STAFF_LIBRO = {515060, 510030}
# 511xxx = sueldos/cargas sociales en el libro (hoy sin movimientos; Staff
# Blanco sale de "Gastos RRHH"). Si algun dia aparecen con saldo, el informe
# avisa para no duplicar.
PREFIJO_SUELDOS_LIBRO = "511"
