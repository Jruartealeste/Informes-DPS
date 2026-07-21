---
name: refresh-dashboard
description: Use when Javier pide refrescar o regenerar todos los informes y el dashboard general a la vez, no un módulo puntual. Ej: "actualizá todo el dashboard", "regenerá todos los informes", "refrescá el panel completo".
argument-hint: (sin argumentos, o lista de módulos con export nuevo)
---

## Qué hace

Regenera todos los `informes/informe_<modulo>.html` y el
`informes/dashboard.html` que los agrupa en una sola pasada. Útil cuando hay exports nuevos para varios
módulos el mismo día, o cuando se tocó `html_report.py`/
`generate_dashboard.py` y hace falta refrescar todo el set de una vez. No
tiene workflow propio en `workflows/` — combina
[actualizar_informe.md](../../../workflows/actualizar_informe.md) con
`generate_dashboard.py`.

## Pasos

1. Si Javier trajo exports `.xlsx` nuevos para uno o más módulos, cargarlos
   primero con el skill `actualizar-informe`, uno por módulo — respetando
   el caso especial de `pendientes` (primero `ordenes_trabajo` /
   `estimados_costos` / `ordenes_compra` / `oc_pendientes_generar` /
   `estimados_pendientes_facturar`, recién después `pendientes`).
   `items_pendientes_oc` no tiene Excel propio: solo re-correrlo
   (`python -m modules.ordenes_trabajo.crawl_items_pendientes`, tarda
   unos minutos) si Javier pide específicamente refrescar ese dato o pasó
   bastante tiempo desde la última corrida.
2. Regenerar el resto de los informes desde los datos ya en `advertys.db`
   (sin re-ingest) para los módulos con `generate_html_report.py`:
   - `python -m modules.ordenes_trabajo.generate_html_report`
   - `python -m modules.compras.generate_html_report`
   - `python -m modules.facturas.generate_html_report`
   - `python -m modules.pendientes.generate_html_report`
   Antes de asumir que esta lista sigue completa, chequear la lista
   `MODULOS` en `generate_dashboard.py` — puede haberse sumado un módulo
   nuevo vía el skill `relevar-modulo`.
3. `python generate_dashboard.py` — regenera `informes/dashboard.html` con
   el sidebar actualizado.
4. Si hubo cambios de CSS/layout en esta sesión, correr el skill
   `verificar-visual` sobre `informes/dashboard.html` y sobre los informes
   que cambiaron.
5. Reportar qué módulos se actualizaron y con qué rango de datos cada uno.

## Notas

- No re-ingerir datos de un módulo si no hay export nuevo para él — este
  skill por default solo regenera HTML desde lo que ya está en
  `advertys.db`.
- `estimados_costos`, `ordenes_compra`, `oc_pendientes_generar`,
  `estimados_pendientes_facturar` y `items_pendientes_oc` son *feeder* de
  `pendientes` (no tienen `generate_html_report.py` propio ni entrada en
  el dashboard) — no intentar regenerarles un informe propio.
