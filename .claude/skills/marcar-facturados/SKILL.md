---
name: marcar-facturados
description: Use when Javier pide pasar a CERRADO (o "marcar facturadas"), en la app ot/, las tareas cuyos Estimados ya están facturados en Advertys (Facturado total, Facturado manual o Finalizado). Ej. "marcá las tareas facturadas", "actualizá el estado de facturación de la app", "¿qué tareas ya se facturaron en Advertys?". Refresca estimados_costos, muestra qué se marcaría y solo con OK explícito aplica. No escribe en Advertys.
---

## Qué hace

Cruza los Estimados de la app `ot/` (producción) con `estimados_costos` de
Advertys y pasa a `CERRADO` las tareas de los Estimados facturados.
CERRADO es el único estado de facturación que solo fija este agente (en la
app no se puede elegir ni sacar a mano); `FACTURADO` sí se elige a mano, y
el agente igual lo pasa a CERRADO cuando el Estimado ya está facturado.
Fuente de verdad completa:
[workflows/marcar_facturados.md](../../../informes/workflows/marcar_facturados.md)
— si algo acá y el workflow difieren, gana el workflow (releerlo).

No escribe en Advertys: la escritura es solo sobre la base de `ot/`.

## Pasos

Todo parado en `informes/` (`cd informes` si la sesión arrancó en la raíz).

1. **Refrescar** (siempre descargar export nuevo):
   `python -m modules.estimados_costos.export` y después
   `python -m modules.estimados_costos.ingest exploracion/estimados_costos_export.xlsx`.
2. **Dry-run** contra prod, sin `--aplicar`:
   `OT_SYNC_URL=https://ot-sand-iota.vercel.app OT_SYNC_TOKEN=<SYNC_TOKEN de ot/.env> python -m modules.sync_tareas_app.marcar_facturados`
   (leer el token del archivo sin imprimirlo; usar `PYTHONIOENCODING=utf-8`
   si la consola rompe con acentos).
3. **Presentar a Javier** los tres bloques (a marcar / todavía no facturados /
   no están en advertys.db) y **esperar su OK explícito**. Si hay Estimados
   "Finalizado" con `facturado/neto=0%`, resaltarlos: entran igual por regla,
   pero conviene que los vea.
4. Con el OK: mismo comando + `--aplicar`. Verificar corriendo el dry-run de
   nuevo (debe dar 0 a marcar) y reportar cuántas tareas se marcaron.

## Notas

- Nunca toca tareas anuladas, ya facturadas ni "no corresponde".
- Si aparecen Estimados "NO ESTÁN en advertys.db", la ingesta quedó vieja:
  repetir el paso 1 antes de decidir nada.
- `python`/`py` apuntan al alias de Microsoft Store: usar la ruta completa de
  Python 3.12 indicada en `informes/CLAUDE.md`.
- El criterio de "facturado" (estados de Advertys) vive en
  `ESTADOS_FACTURADO` de `modules/sync_tareas_app/marcar_facturados.py`.
