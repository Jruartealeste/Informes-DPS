---
name: crear-factura-manual-produccion
description: Use when Javier pide crear/armar una factura manual de Producción en Advertys (Administración > Facturación > Producción > Factura Manual) dictando cliente, producto, conceptos e importes, sin estimado detrás. Ej. "armá una factura manual a ALUAR por el fee de diciembre", "cargá una factura de producción manual", "dejame en borrador una factura a X por $Y". Deja la factura en BORRADOR (nunca autoriza, factura ni pide CAE), corre primero en modo prueba y pide OK explícito antes de guardar. ESCRIBE en Advertys real. No es para facturar desde Estimados o Fee, ni Medios, ni notas de crédito.
argument-hint: <cliente, concepto e importe>
---

## Qué hace

Crea una Factura Producción Manual en **Borrador** con
`modules/facturas/crear_factura_manual.py`. Receta, mapeos y gotchas:
[workflows/crear_factura_manual.md](../../../informes/workflows/crear_factura_manual.md)
(si algo acá y el workflow difieren, gana el workflow).

## Flujo

1. **Juntar los datos** con Javier: cliente, anunciante (por defecto el mismo nombre
   que el cliente; Advertys sugiere otro y el script lo corrige), producto (depende
   del anunciante), título
   opcional y por ítem: cuenta (ej. `411010-FEE`), detalle, cantidad, precio unitario
   **sin IVA**, % IVA (default 21,00) y tipo de facturación opcional. Si no está claro
   qué servicio se factura, preguntar.
2. **Armar el spec** en `informes/exploracion/factura_manual_<cliente>_<dd.mm.aa>.json`
   (formato en el docstring del script).
3. **Modo prueba**, parado en `informes/`:
   `python -m modules.facturas.crear_factura_manual <spec>.json`
   (Python: `/c/Users/javie/AppData/Local/Programs/Python/Python312/python.exe`).
4. **Mostrar la factura armada** (cliente, producto, ítems, neto, IVA y total) y pedir
   **OK explícito**. Una autorización anterior no vale para la factura siguiente.
5. Correr con `--guardar` y reportar el ObjectKey, el link al Borrador y el neto
   verificado en la grilla.
6. Recordarle a Javier que Autorizar → Facturar → Solicitar CAE lo hace él en Advertys.

## Reglas

- Solo facturas por **servicios reales prestados**. No armar facturas nominales, de
  prueba con CAE, ni facturas pensadas para anularse con nota de crédito (por ejemplo,
  para cortar la numeración). El script rechaza netos menores a $10.000; no se baja
  ese piso ni se esquiva.
- Nunca clickear Autorizar, Facturar, Solicitar CAE ni Clona Comprobante.
- Si el script falla después de guardar la cabecera, informar el ObjectKey del
  Borrador a medias y no relanzar sin revisar (crearía otro). Borrarlo es decisión
  de Javier.
- La primera corrida real con `--guardar` valida la carga de ítems: revisar el
  Borrador en pantalla y documentar en el workflow lo que haga falta ajustar.
