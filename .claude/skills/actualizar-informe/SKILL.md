---
name: actualizar-informe
description: Use when Javier pide cargar un export de Advertys, actualizar/regenerar un informe existente, o refrescar los datos de un módulo ya armado (compras, facturas, ordenes_trabajo, pendientes, etc). Ej: "cargá el último export de Compras", "regenerá el informe de Facturas", "actualizá Pendientes".
argument-hint: [modulo] [ruta-al-xlsx]
---

## Qué hace

Carga un export `.xlsx` nuevo de Advertys en un módulo ya armado y regenera
`salida/informe_<modulo>.html`. Fuente de verdad completa:
[workflows/actualizar_informe.md](../../../informes/workflows/actualizar_informe.md)
— si algo acá y el workflow difieren, gana el workflow (releerlo).

## Pasos

1. Determinar el módulo (`$0`) y la ruta al xlsx (`$1`). Si `$0` no vino o
   no es un módulo reconocido, revisar la tabla de "Módulos armados hasta
   ahora" en README.md antes de asumir.
2. **Caso especial `iibb`:** si no vino `$1` (Javier no dio una ruta xlsx
   puntual), NO uses los pasos 4-5 genéricos — corré
   `python -m tools.actualizar_iibb` en su lugar. El informe de IIBB no
   depende solo del export de Imputaciones: también necesita
   `facturas`/`ordenes_compra`/`ordenes_publicidad` frescas y el crawl
   `modules/iibb/crawl_oc_por_factura.py` corrido después (para el N° de
   OC/OP de cada factura, con Proveedor/Monto vía `oc_resolver.py`); ese
   script encadena los 5 pasos en el orden correcto y al final avisa por
   número de factura si algo quedó sin detalle de OC/OP — ver su
   docstring y `workflows/actualizar_informe.md` para el detalle. Si
   Javier sí trae un xlsx puntual de Imputaciones, usar
   `python -m modules.iibb.export` para el export en vivo queda de lado;
   cargar ese xlsx con el paso 4 normal y correr igual el resto de
   `tools/actualizar_iibb.py` (o sus pasos por separado) para no dejar
   facturas/ordenes_compra/ordenes_publicidad/crawl atrasados. Si el
   export en vivo corta con `ExportError` sobre el combo de Filtro, no
   reintentar a ciegas — el ID de ese combo ya cambió una vez
   (2026-08-12); ver la nota en `modules/iibb/export.py` y
   `workflows/actualizar_informe.md` para el procedimiento de
   diagnóstico.
3. **Caso especial `pendientes`:** no tiene `ingest.py` propio, cruza
   `ordenes_trabajo` + `estimados_costos` + `ordenes_compra` +
   `oc_pendientes_generar` + `estimados_pendientes_facturar` +
   `items_pendientes_oc`. Si el módulo es `pendientes`, correr primero el
   `ingest.py` de los módulos que tengan export nuevo y recién después el
   paso 5 (sin paso 4 propio). `items_pendientes_oc` es distinto: no tiene
   Excel que cargar, se refresca corriendo
   `python -m modules.ordenes_trabajo.crawl_items_pendientes` (navega
   Advertys en vivo, tarda unos minutos) — solo hace falta si pasó un
   rato desde la última corrida y puede haber cambiado el estado de algún
   Proveedor/O.C. en un estimado no-terminal.
4. Si el módulo no es `pendientes`:
   `python -m modules.<modulo>.ingest "$1"`
5. `python -m modules.<modulo>.generate_html_report`
6. Solo si hubo cambios de CSS/layout en esta sesión (no un refresh de
   datos puro): invocar el skill `verificar-visual` sobre
   `salida/informe_<modulo>.html`.
7. Reportar filas cargadas y el rango de fechas cubierto por el informe
   resultante.

## Manejo de errores

Ver la sección "Manejo de errores" de
[workflows/actualizar_informe.md](../../../informes/workflows/actualizar_informe.md):
`KeyError` de columna (Advertys cambió un nombre o usa "N°"/"Nº" con byte
distinto) o conteo de filas sospechosamente bajo (filtro de vista no
ampliado antes de exportar). No inventar una causa genérica — la causa
real casi siempre es una de esas dos.

## Notas

- Siempre parado en `informes/` (la raíz del pipeline, no la raíz del
  repo — que también contiene `ot/`): `python -m modules.<modulo>.<script>`,
  nunca `python archivo.py` directo. Si la sesión arrancó en la raíz del
  repo, `cd informes` primero.
- `python`/`py` en esta terminal apuntan al alias de Microsoft Store — si
  falla, usar la ruta completa indicada en CLAUDE.md.
- El informe se sobrescribe en cada corrida — no se acumulan versiones
  viejas, es el comportamiento esperado.
