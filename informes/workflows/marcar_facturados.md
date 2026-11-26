# Pasar a CERRADO las tareas de Estimados ya facturados en Advertys

## Objetivo

Que el estado de facturación de las tareas de la app `ot/` refleje lo que
realmente pasó en Advertys: toda tarea agrupada en un Estimado que Advertys
ya tiene en estado **Facturado total**, **Facturado manual** o **Finalizado**
pasa a `CERRADO` (desde 2026-11-26; antes era `FACTURADO`, que ahora se elige a mano en la app). Criterio confirmado por Javier (2026-11-20).

**No escribe en Advertys**: solo lee `estimados_costos` (ya ingestada en
`advertys.db`) y le pide a `ot/` que actualice sus propias tareas. El export
de refresh sí navega Advertys, pero solo en lectura.

## Qué nunca toca

Tareas anuladas, ya `CERRADO` o `NO_CORRESPONDE` (las `FACTURADO` a mano sí se cierran). Estimados en cualquier
otro estado (Provisorio, Definitivo, Ok cliente, Autorizado AFacturar,
Rechazado, Anulado). El % `facturado/neto` se muestra solo como dato: no
decide, porque el neto incluye conceptos que no se facturan (~90% típico).

## Pasos (parado en `informes/`)

1. **Refrescar** `estimados_costos` (siempre bajar el export nuevo, no
   alcanza con regenerar):
   ```
   python -m modules.estimados_costos.export
   python -m modules.estimados_costos.ingest exploracion/estimados_costos_export.xlsx
   ```
2. **Dry-run** (default, no cambia nada). Apuntar al `ot/` de producción
   sobreescribiendo las variables del `.env` (que apunta a localhost):
   ```
   OT_SYNC_URL=https://ot-sand-iota.vercel.app OT_SYNC_TOKEN=<SYNC_TOKEN de ot/.env> \
   python -m modules.sync_tareas_app.marcar_facturados
   ```
   Imprime tres bloques: A MARCAR FACTURADO, TODAVÍA NO FACTURADOS, y NO ESTÁN
   en advertys.db (si aparece alguno, la ingesta quedó vieja: repetir el
   paso 1).
3. **Mostrarle a Javier la lista y esperar su OK** (mismo patrón que el resto
   de los flujos que modifican datos).
4. Con el OK, repetir el comando agregando `--aplicar`. Devuelve
   `tareas_marcadas`; correr el dry-run otra vez debe dar 0 para marcar.

## Notas

- El `SYNC_TOKEN` de prod es el mismo que el de `ot/.env`; leerlo del
  archivo sin imprimirlo en pantalla.
- Un Estimado con tareas desdobladas aparece más de una vez (mismo número,
  varios Estimados de la app): al marcarlo se marcan las tareas de todos.
- Los endpoints viven en `ot/app/routers/sync.py`
  (`GET /api/sync/estimados-a-facturar`, `POST /api/sync/estimados-facturados`)
  con tests en `ot/tests/test_estimados_facturados_api.py`. Para probar sin
  tocar prod: `ot-qa-manual` (puerto 8125, token `qa-local-sync-token-not-real`).
- Si Advertys cambia el nombre de un estado, ajustar `ESTADOS_FACTURADO` en
  `modules/sync_tareas_app/marcar_facturados.py`.
