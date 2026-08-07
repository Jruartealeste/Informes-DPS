---
name: cerrar-pendientes
description: Use when Javier pide cerrar OTs o estimados que ya están listos según el informe de Pendientes, revisar qué OTs ya se pueden cerrar en Advertys, o hacer limpieza de Pendientes. Ej. "cerrá las OTs que ya están listas", "revisá qué estimados se pueden finalizar", "¿qué OT están para cerrar?".
---

## Qué hace

Revisa el semáforo del informe de Pendientes, arma una propuesta de qué
Estimados de Costo se pueden pasar a `Finalizado` y qué Órdenes de Trabajo
se pueden `Cerrar` en Advertys, te la presenta, y **solo después de tu
confirmación explícita** ejecuta esos cambios uno por uno. Fuente de verdad
completa: [workflows/cerrar_pendientes.md](../../../informes/workflows/cerrar_pendientes.md)
— si algo acá y el workflow difieren, gana el workflow (releerlo).

Este flujo escribe en Advertys (a diferencia de casi todo el resto del
pipeline, que es de solo lectura). El único script con permiso para eso es
`modules/ordenes_trabajo/cerrar_ot.py`, ya aprobado por vos con reglas
duras: nunca "Anulado"/"Provisorio", solo Estimado→Finalizado y
OT→Cerrada, un paso por vez con revisión intermedia.

## Pasos

1. Si `ordenes_trabajo`/`estimados_costos`/`ordenes_compra` no están al día
   en esta sesión, correr primero el skill `refresh-dashboard`.
2. `python -m modules.ordenes_trabajo.cerrar_ot listar-candidatos` (solo
   lectura) para obtener: OT listas para cerrar directamente, estimados
   listos para finalizar, y estimados bloqueados con motivo.
3. Presentarte la propuesta y **esperar tu OK explícito** antes de escribir
   nada — modo "proponer y confirmar" (no autopilot).
4. Recién con tu confirmación: `finalizar-estimado <ot> <estimado>` de a
   uno para cada estimado aprobado, y `cerrar-ot <ot>` para las OT que
   queden con todo terminal — revisando la captura de cada paso antes de
   seguir con el siguiente.
5. Si algo sale bloqueado o Advertys rechaza una transición: parar y
   reportar el motivo real, no reintentar a ciegas.
6. Reportar qué se cerró, qué quedó bloqueado (y por qué), y dónde están
   las capturas (`exploracion/screenshots/`).

## Notas

- Comandos parados en `informes/` (la raíz del pipeline, no la raíz del
  repo — que también contiene `ot/`): `cd informes` primero si la sesión
  arrancó en la raíz del repo.
- Nunca amplíes el alcance de escritura más allá de Estimado→Finalizado /
  OT→Cerrada — cualquier otra cosa (reasignar OC, corregir imputaciones)
  es manual en Advertys.
- `python`/`py` en esta terminal apuntan al alias de Microsoft Store — si
  falla, usar la ruta completa indicada en CLAUDE.md.
