---
name: registrar-cobranzas
description: Use when Javier pide registrar/cargar una cobranza (un Recibo Cliente) en Advertys a partir del PDF de pago de un cliente guardado en la carpeta de Drive "comprobantes de cobro" (ej. "cobro aluar 16.11.26"). Ej: "registrá el cobro de ALUAR", "cargá la cobranza del 16.11", "pasá este cobro a Advertys". Lee el PDF (orden de pago + certificados de retención), arma el recibo, pregunta la fecha del cobro y pide OK antes de escribir. ESCRIBE en Advertys real. No es refresh-cobranza (informe Cobranza x Proveedores, solo lectura).
argument-hint: <cliente y fecha del cobro, o nombre del PDF>
---

## Qué hace

Carga un Recibo Cliente en Advertys (Administración > Tesorería > Recibo
Cliente) con `modules/recibos/crear_recibo.py`. Receta completa, mapeos y
gotchas: [workflows/registrar_cobranza.md](../../../informes/workflows/registrar_cobranza.md)
(si algo acá y el workflow difieren, gana el workflow).

## Flujo

1. **Ubicar el PDF** en Drive (carpeta `1WV4XRLNh8LOH3aCz-uksCxgOvGIwckdr`,
   subcarpeta del cliente) con `search_files` y leerlo con
   `read_file_content`. Nombre esperado: `cobro <cliente> dd.mm.aa $monto.pdf`;
   si no sigue el formato, renombrarlo al terminar (pedir OK).
2. **Extraer y verificar**: facturas, certificados de retención (número, tipo,
   base, importe), neto. Chequear que la suma de netos = monto del nombre.
3. **Preguntar a Javier la fecha del cobro** (siempre; no asumir la de emisión
   del PDF). Formato dd/mm/aaaa.
4. **Mostrar el recibo armado** (facturas a cancelar, retenciones por tipo,
   Otros Valores Galicia/Transferencia/neto) y **pedir OK explícito** antes de
   escribir; una autorización anterior no vale para el recibo siguiente.
5. Armar el spec JSON (ver ejemplo en el workflow) y correr, parado en
   `informes/`:
   `python -m modules.recibos.crear_recibo <spec>.json --guardar`
   (Python: `/c/Users/javie/AppData/Local/Programs/Python/Python312/python.exe`).
   Guarda solo si los totales cuadran; si no cuadra, informar y no guardar.
6. **Verificar en el listado** Recibo Cliente y reportar número, fecha y
   totales. Si el script dejó un Borrador a medias, decirlo (borrarlo es
   decisión de Javier).

## Reglas

- Número de referencia de Otros Valores: 0 (no acepta el N° de OP).
- Solo se completa un recibo en Borrador; el "Nuevo" de las pestañas crea el
  Borrador apenas se abre.
- El recibo queda en Borrador (la contabilización no es parte de este flujo).
- Clientes distintos de ALUAR: la cuenta/tipos de retención pueden variar;
  confirmar con Javier antes de la primera corrida de cada cliente.
