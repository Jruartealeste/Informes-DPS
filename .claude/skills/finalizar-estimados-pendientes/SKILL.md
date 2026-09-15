---
name: finalizar-estimados-pendientes
description: Use when Javier pide revisar o pasar a Finalizado los Estimados de Costo que ya están facturados y con sus O.C. cruzadas, según el informe de Estimados Pendientes — a diferencia de cerrar-pendientes, cubre estimados de cualquier OT (abierta o cerrada), no solo los de OT abiertas. Ej. "probá el agente de cierre de estimados", "revisá qué estimados se pueden pasar a Finalizado", "¿hay estimados facturados sin finalizar?".
---

## Qué hace

Revisa el semáforo del informe de Estimados Pendientes
(`modules/estimados_pendientes/`), arma una propuesta de qué Estimados de
Costo se pueden pasar a `Finalizado` en Advertys, te la presenta, y **solo
después de tu confirmación explícita** ejecuta esos cambios uno por uno.
Fuente de verdad completa: [workflows/finalizar_estimados_pendientes.md](../../../informes/workflows/finalizar_estimados_pendientes.md)
— si algo acá y el workflow difieren, gana el workflow (releerlo).

Este flujo escribe en Advertys. El único script con permiso para eso es
`modules/ordenes_trabajo/cerrar_ot.py`, con reglas duras ya aprobadas:
nunca "Anulado"/"Provisorio", solo Estimado→Finalizado, un paso por vez con
revisión intermedia. Este skill **nunca cierra una OT** (eso es
`cerrar-pendientes`) — solo finaliza estimados puntuales.

## Diferencia con `cerrar-pendientes`

- `cerrar-pendientes` parte de OT **abiertas** y además cierra la OT.
- `finalizar-estimados-pendientes` parte de TODOS los estimados no
  terminales (cualquier OT, abierta o cerrada) y solo finaliza estimados —
  cubre el caso de un estimado que quedó facturado sin el click final a
  Finalizado en una OT que ya se cerró.

Si Javier pide "cerrar lo que está pendiente" en general, corré los dos
flujos (uno cierra OT, el otro limpia estimados sueltos de OT ya cerradas).

## Pasos

1. Si `estimados_costos`/`ordenes_compra`/`oc_pendientes_generar`/
   `estimados_pendientes_facturar`/`ordenes_trabajo` no están al día en
   esta sesión, correr primero el skill `refresh-dashboard`.
2. `python -m modules.ordenes_trabajo.cerrar_ot listar-candidatos-estimados`
   (solo lectura) para obtener: estimados listos para finalizar (con la OT
   marcada si ya está Cerrada), y estimados bloqueados con motivo.
3. Presentarte la propuesta y **esperar tu OK explícito** antes de escribir
   nada — modo "proponer y confirmar" (no autopilot).
4. Recién con tu confirmación: `finalizar-estimado <ot> <estimado>` de a
   uno para cada estimado aprobado — revisando la captura de cada paso
   antes de seguir con el siguiente.
5. Si algo sale bloqueado o Advertys rechaza una transición: parar y
   reportar el motivo real, no reintentar a ciegas.
6. Reportar qué se finalizó, qué quedó bloqueado (y por qué), y dónde están
   las capturas (`exploracion/screenshots/`).

## Notas

- Comandos parados en `informes/` (la raíz del pipeline, no la raíz del
  repo — que también contiene `ot/`): `cd informes` primero si la sesión
  arrancó en la raíz del repo.
- Nunca amplíes el alcance de escritura más allá de Estimado→Finalizado —
  cualquier otra cosa (cerrar la OT, reasignar OC, corregir imputaciones)
  es manual o corresponde a otro flujo (`cerrar-pendientes`).
- `python`/`py` en esta terminal apuntan al alias de Microsoft Store — si
  falla, usar la ruta completa indicada en CLAUDE.md.
