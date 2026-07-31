---
name: refresh-dashboard
description: Use when Javier pide refrescar o regenerar todos los informes y el dashboard general a la vez, no un módulo puntual. Ej: "actualizá todo el dashboard", "regenerá todos los informes", "refrescá el panel completo".
argument-hint: (sin argumentos, o lista de módulos con export nuevo)
---

## Qué hace

Exporta en vivo desde Advertys (login + navegar + descargar XLSX vía
Playwright) y carga en `advertys.db` los 7 módulos que tienen
`modules/<modulo>/export.py` — `compras`, `facturas`, `estimados_costos`,
`ordenes_compra`, `oc_pendientes_generar`, `estimados_pendientes_facturar`,
`ordenes_trabajo` — y después regenera todos los `informes/informe_<modulo>.html`
y el `informes/dashboard.html` que los agrupa, en una sola pasada. El
export ya no es manual para estos 7 módulos (era el comportamiento viejo
de este skill; `tools/actualizar_todo.py` es el que reemplaza ese paso).

**IIBB queda afuera de este script a propósito** — su export es mucho más
pesado (~22.700 filas vs. cientos en el resto de los módulos) y además
tiene su propio crawl lento aparte (`crawl_oc_por_factura.py`, "unos
minutos"). Sigue actualizándose con el flujo manual de siempre.

## Pasos

1. Correr `python -m tools.actualizar_todo` (desde la raíz del proyecto,
   con `-m` para que `modules` sea importable) — hace login a Advertys una
   vez por módulo, exporta y carga los 7 módulos de arriba, y al final
   regenera los 4 `generate_html_report.py` existentes
   (`ordenes_trabajo`, `compras`, `facturas`, `pendientes`) y
   `generate_dashboard.py`. Un fallo puntual en un módulo no aborta el
   resto — al final del stdout hay un resumen con qué módulos quedaron OK
   y cuáles fallaron (y por qué). Antes de asumir que la lista de 7
   módulos sigue completa, chequear `MODULOS` en `tools/actualizar_todo.py`
   — puede haberse sumado un módulo nuevo vía el skill `relevar-modulo`
   (si el módulo nuevo tiene su propio `export.py`, agregarlo ahí también).
2. **Fallback manual** — si Advertys está caído, el login falla, o Javier
   ya trae un Excel puntual en vez de dejar que el script lo exporte: usar
   el skill `actualizar-informe` para ese módulo en particular en lugar
   del paso 1, respetando el caso especial de `pendientes` (primero
   `ordenes_trabajo` / `estimados_costos` / `ordenes_compra` /
   `oc_pendientes_generar` / `estimados_pendientes_facturar`, recién
   después `pendientes`).
3. **IIBB** siempre se actualiza aparte con el skill `actualizar-informe`
   (export manual, como siempre) — no lo toca `tools/actualizar_todo.py`.
4. `items_pendientes_oc` no tiene Excel propio y sigue siendo opt-in: solo
   re-correrlo (`python -m modules.ordenes_trabajo.crawl_items_pendientes`,
   tarda unos minutos) si Javier pide específicamente refrescar ese dato o
   pasó bastante tiempo desde la última corrida.
5. Si hubo cambios de CSS/layout en esta sesión, verificar visualmente
   `informes/dashboard.html` y los informes que cambiaron: si es uno solo,
   con el skill `verificar-visual` inline; si son 2+ (lo típico cuando el
   cambio fue en `html_report.py` compartido), delegar al subagent
   `informe-visual-qa` para no inflar el hilo principal con capturas de
   cada módulo.
6. Reportar qué módulos se actualizaron (y cuáles fallaron, si los hubo)
   con qué rango de datos cada uno.

## Notas

- `tools/actualizar_todo.py` corre headless, sin ventana visible, igual
  que ya corrían los `explore.py` de cada módulo — cada `export.py` es
  una copia productiva y recortada del `explore.py` correspondiente
  (mismos selectores ya verificados, sin las capturas de debug de más).
  Ver `tools/advertys_session.py` para el login compartido.
- `estimados_costos`, `ordenes_compra`, `oc_pendientes_generar`,
  `estimados_pendientes_facturar` y `items_pendientes_oc` son *feeder* de
  `pendientes` (no tienen `generate_html_report.py` propio ni entrada en
  el dashboard) — no intentar regenerarles un informe propio.
- Si en algún momento se agrega un `export.py` nuevo (módulo nuevo, o
  IIBB deja de ser manual), sumarlo a `MODULOS` en
  `tools/actualizar_todo.py` — no hay detección automática.
