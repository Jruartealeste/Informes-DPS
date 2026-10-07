# Hallazgos conocidos de QA de ot/

Sirve para no reportar de nuevo lo ya visto y para probar regresión: en cada
pasada, probar cada uno; si ya no se reproduce, marcarlo "corregido"; si
sigue, "persiste". Agregar acá los hallazgos nuevos al cerrar cada informe
(fecha, dónde, esperado vs real, estado).

## Altos
_(ninguno registrado todavía — se llena con el primer informe)_

## Medios
- **Colisión de número interno en "Duplicar → OT nueva"** (confirmado 2026-10-07): `duplicar_form` calcula `siguiente_numero_interno()` al abrir sin reservar; dos aperturas dan el mismo número y al guardar la segunda tarea se pega en silencio a la `ot_interna` de la primera. `ot/app/routers/tareas.py` (`duplicar_form`, `_resolver_ot_interna`). Estado: **corregido 2026-10-07** (sin commit aún): el form manda `ot_generada` y `crear_tarea` asigna el siguiente libre si el número ya lo ocupó otra OT. Regresión: dos aperturas + dos guardados → OT 4164 y 4165, una tarea cada una.
- **Anular sin bloqueo en servidor** (2026-10-07): el POST directo anulaba tareas FACTURADO/PARA_FACTURAR. Javier decidió que esas no se anulan. Estado: **corregido 2026-10-07**: 409 en el servidor y botón deshabilitado con motivo; FINALIZADO sigue anulable con advertencia. Regresión: POST directo a `/anular` en una tarea facturada → 409 y estado intacto.

## Bajos
- `POST /tareas/{id}/anular` con id inexistente → 500 en vez de 404 (`db.get` None → `puede_anular(None)`); probable igual en `/estado` y `/facturacion`. Estado: **corregido 2026-10-07** para `/tareas/{id}/anular|estado|facturacion|PATCH` (404). Verificar `estimados.py:248` y `facturacion.py:121`, que usan el mismo `db.get(Tarea, …)` sin chequeo.

## Verificado y funciona (no volver a abrir sin cambio de código)
- Duplicar "Misma OT": precarga, no guarda antes de confirmar, tarea nueva coherente (2026-10-07).
- Anular tarea abierta desde el drawer: confirmación, refresco, solo cambia el estado (2026-10-07).
