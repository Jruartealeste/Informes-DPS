---
name: acelerar-crawl
description: Use when Javier pide acelerar, optimizar o hacer incremental un refresh lento de algún informe, o cuando un crawl de Playwright de modules/ (los que borran su tabla y recorren todo cada vez) tarda demasiado. Ej: "IIBB tarda mucho, hacelo como cobranza", "aplicá lo de cobranza al resto de los dashboards", "hacé incremental el crawl de items pendientes", "¿qué otros refresh se pueden acelerar?". Es el método para el desarrollador (convierte un crawl en incremental + paralelo con tools/crawl_comun.py); para correr el refresh de cobranza usar refresh-cobranza.
argument-hint: <crawl o módulo a acelerar, p.ej. modules/iibb/crawl_oc_por_factura.py>
---

## Por qué existe

Los crawls de Advertys son lentos por tres motivos que se repiten en todos:
(1) `DELETE` total + recrawl de todo en cada corrida, (2) por cada ítem
recargan el listado, reabren el filtro y buscan de nuevo, (3) esperas fijas
y `networkidle`. En cobranza esto sumaba ~70 min por ~214 visitas, aunque
casi nada hubiera cambiado. La solución vive en
`informes/tools/crawl_comun.py` (tests: `python -m tests.test_crawl_comun`);
esta skill es la receta para aplicarla a otro crawl. Plan original y
razones: `C:\Users\javie\.claude\plans\zesty-skipping-island.md`.

Salvaguarda: todo sigue siendo **solo lectura** contra Advertys (ver
`informes/CLAUDE.md`); nada de lo de acá agrega clicks sobre
Nuevo/Editar/Guardar/Eliminar.

## Receta (en este orden)

1. **Medir antes.** Anotar visitas y tiempo de la corrida actual (o leer el
   docstring del script: suele tener el número). Sin línea base no se sabe
   si se mejoró. Todo cambio se valida contra la corrida vieja.
2. **Elegir la clave** del ítem (`recibo`, `numero_referencia` de factura,
   `numero_oc`...) y la **firma**: los campos de cabecera que ya trae el
   export/ingest del módulo (estado, total, saldo, comprado/pagado). Si la
   firma cambia, el ítem cambió. `crawl_comun.firma(...)` la arma.
3. **Elegir la política** (`Politica`) según qué tan inmutable es el ítem:
   - Registro contable con fecha (recibo, factura): `congelar_mes_cerrado=True`.
     Un mes cierra el día 15–20 del siguiente (`DIA_CIERRE = 20`); después
     no se tocan asientos de ese mes. Sumar `dias_recientes=7` para lo que
     todavía se edita.
   - Órdenes (OC/OP) y todo lo que puede recibir movimientos nuevos después:
     `congelar_mes_cerrado=False`. **La fecha de la orden no congela** — una
     orden de marzo puede recibir una factura de compra en octubre. Manda la
     firma + `reintentar_sin_ok=True` para lo que no tiene resultado útil.
   - Estado que cambia seguido (OT abiertas): el cierre de mes no ayuda,
     manda solo la firma.
4. **Convertir el crawl:**
   - `CrawlCache(modulo)` + `seleccionar(candidatos, cache, politica)` →
     qué visitar y por qué (loguear el desglose por motivo).
   - Guardar cada resultado con `cache.guardar(clave, firma, fecha, n_filas, n_ok)`,
     **incluidos los de 0 filas** (si no, se recrawlean para siempre).
   - Escribir con `reemplazar_por_clave(...)` en vez de `DELETE` total, y
     `cache.olvidar_fuera_de(...)` para lo que salió de la ventana.
   - Visitar con `correr_en_paralelo(items, procesar, n_workers)`: cada hilo
     tiene su navegador y login; el hilo principal es el único que escribe a
     SQLite.
   - Reemplazar `networkidle`/sleeps por `esperar_grid`/`esperar_sin_carga`, y
     entre ítems intentar `volver_o_recargar` (el `goto` completo queda como
     fallback, nunca peor que antes). Conservar los guardas anti-bug del
     script original (p.ej. click acotado a la fila en `tabla_visible()`
     cuando un N° se repite entre TA distintos).
5. **Conservar la corrida vieja.** Renombrar el `main()` original a
   `main_legacy()` sin tocarlo y exponerlo con `--legacy`; sumar `--completo`
   (ignora caché, con upsert) y `--workers N` (default 1 hasta validar).
   Javier pidió explícitamente que la vieja quede opcional.
6. **Validar** (no dar por terminado sin esto):
   - Sembrar la caché desde las tablas que dejó una corrida legacy reciente
     → la primera corrida incremental debe visitar ~0–5 ítems y el informe
     HTML debe salir idéntico (hash).
   - `--completo --workers 1` sobre ~10 ítems vs `--legacy`: diff fila a
     fila de las tablas resultado.
   - `--workers 3` vs `--workers 1`: mismas filas. Si Advertys expulsa
     sesiones simultáneas con el mismo usuario, dejar el default en 1.
7. **Medir después** y reportar antes/después (visitas, minutos). Actualizar
   README y `workflows/actualizar_informe.md` con los flags y la regla de
   cierre, y la skill operativa del flujo (como `refresh-cobranza`).

## Aplicabilidad al resto de los dashboards

| Crawl | Hoy | Cómo aplicar |
|---|---|---|
| `modules/iibb/crawl_oc_por_factura.py` (2 tablas, ventana 6 meses, `tools.actualizar_iibb`) | `DELETE` total en `items_factura_oc` y `detalle_impositivo_factura` | Clave = factura, firma = total/estado, congelar mes cerrado. La mayor ganancia después de cobranza. |
| `modules/ordenes_trabajo/crawl_items_pendientes.py` | `DELETE` total, opt-in | OT abiertas cambian seguido: firma = estado/importes de la cabecera; sin congelar por mes. |
| `modules/facturacion_aluar/crawl_facturas_relacionadas.py` | `DELETE` total | Clave = factura Aluar; mismo patrón que cobranza. |
| `tools/actualizar_todo.py` | un login por módulo (+3 de Notas de Crédito) | No es un crawl: el cuello es el login y la exportación en serie. Medir primero; la vía es reutilizar sesión y exportar en paralelo, no la caché. |

Orden sugerido: cobranza → IIBB → el resto, cada uno validado contra su
propia corrida vieja antes de pasar al siguiente.

## Resultado de cobranza (2026-10-13) y lecciones

Cadena completa en modo incremental: 200 s (antes ~70 min). `--completo
--workers 3`: recibos 31 en 146 s, facturas 69 en 258 s, órdenes 100 en 441 s.
Las 3 tablas salieron idénticas fila a fila entre incremental y completo.
Lo que costó descubrir:

- **Un "no encontrado" nunca se cachea ni pisa lo guardado** (el procesar
  devuelve `None`). Corolario para validar: que la tabla salga idéntica NO
  prueba nada si hubo "no encontradas" (conservan las filas viejas); exigir
  también 0 no encontradas.
- **`Listado` verifica la vista (ViewID) en la URL.** El `go_back` puede caer
  en otro listado si el crawl alterna vistas (OC Producción ↔ OP Publicidad);
  sin ese chequeo todo lo posterior daba falsos "no encontrado".
- **Buscar = esperar a que la búsqueda se aplicó** (todas las filas visibles
  contienen el texto), no solo al spinner: la grilla vieja sin filtrar seguía
  visible y contó 20 "facturas" con el mismo N° de referencia.
- **El combo de filtro necesita reintentos**: el input existe antes de que el
  cliente lo inicialice y el primer click no abre el desplegable.
- **El paralelismo rinde poco** (el servidor de Advertys es el límite:
  ~12 s por ítem con 3 hilos vs ~6 s con 1, o sea ~1.3x). Lo grande es la
  caché. Default `--workers 1`; 3 funciona y da los mismos datos.

## Gotchas

- Si otra sesión está corriendo la cadena, **no editar** los `crawl_*.py` ni
  el orquestador: se lanzan como subprocesos que importan el módulo recién
  al arrancar cada paso, y un cambio a mitad de corrida lo afecta.
- No hacer pruebas en vivo con Playwright mientras otra corrida usa el mismo
  usuario de Advertys (sesiones simultáneas no validadas).
- Los selectores de `esperar_grid` (`.dxgvEmptyData`, `DXEmptyRow`) hay que
  confirmarlos contra Advertys real la primera vez que se usan.
