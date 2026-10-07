# QA ot/ — Anular (bloqueo), Crear, Editar y regresión de Duplicar (2026-10-07, 2ª pasada)

## Entorno y alcance
- Server `:8123` sobre Postgres local `ot-qa-pg` reseteado, con el código posterior a los commits `12590c4` y `c8f1368`. Nunca `:8000`.
- UI real (clicks en "+ Nueva", checkboxes, Guardar) combinada con fetch/htmx desde la página para POST/PATCH directos.
- El seed no tiene tareas FACTURADO; se dejó la tarea 7 en FACTURADO con `POST /tareas/7/facturacion`.
- **No probado:** responsive, tema, filtros, OT internas, mail, sync, auth, "Duplicar → misma OT", revisión visual, tipo inexistente en el catálogo.

## Altos
Ninguno.

## Medios
- **El servidor acepta `detalle` vacío.** `POST /tareas` con `detalle=''` devuelve 200 e inserta la tarea (id 42). El navegador lo frena con `required`; OT, fecha, tipo y responsables sí devuelven 422. Falta la validación en `ot/app/routers/tareas.py` (crear y probablemente PATCH).

## Bajos
Ninguno. La consola solo mostró los 409/404/422 provocados a propósito.

## Regresión de conocidos
- Duplicar → OT nueva con dos aperturas y dos guardados: **corregido** (OT 4169 y 4170).
- 404 en id inexistente: **corregido**.
- Anular facturadas: **corregido** (409 + botón deshabilitado).

## Funcionó bien
- Anular: tareas 3 (PARA_FACTURAR) y 7 (FACTURADO) con botón deshabilitado y tooltip con el motivo; POST directo → 409 con estado intacto; id inexistente → 404; tarea 1 (FINALIZADO) muestra el confirm "FINALIZADA" y queda ANULADA.
- Crear: form vacío no inserta; guardado completo deja el drawer abierto en modo edición con Enviar mail y Anular habilitados, fila en la tabla y uniones exactas.
- "+ Nueva" dos veces y dos aperturas de forms: tareas en OT distintas, sin pegarse a OT ajena.
- Editar: cambiar tipos y quitar/sumar/dejar responsables sin 500, uniones exactas; la OT asignada no cambia con PATCH directo.

## Ideas
- Validar `detalle` no vacío en el servidor con el mismo 422 que los otros obligatorios.
