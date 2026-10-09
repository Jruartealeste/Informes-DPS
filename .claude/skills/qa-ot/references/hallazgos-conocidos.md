# Hallazgos conocidos de QA de ot/

Sirve para no reportar de nuevo lo ya visto y para probar regresión: en cada
pasada, probar cada uno; si ya no se reproduce, marcarlo "corregido"; si
sigue, "persiste". Agregar acá los hallazgos nuevos al cerrar cada informe
(fecha, dónde, esperado vs real, estado).

## Altos
_(ninguno registrado todavía — se llena con el primer informe)_

## Altos
- **Comando `crear_estimado.py` sin escapar** (2026-10-09): `_comando_crear_estimado` pone el título entre comillas dobles y las fechas sin comillas (`$(…)`/backticks/comillas). Mismo bug que el de OT. Estado: **corregido 2026-10-09** (`_arg_shell` en título, OT y fechas). Informe `INFORME-QA-OT-2026-10-09.md`.

## Medios (Estimados, 2026-10-09, **corregidos 2026-10-09** salvo el último ítem; regresión en `ot/tests/test_estimados.py`)
- `cargar-numero` ignora un pedido PENDIENTE (resolver después pisa el número en silencio).
- Tarea ANULADA sigue en el Estimado, en `/facturacion` y como candidata para armar uno nuevo.
- Fechas del pedido de alta sin validar: >10 caracteres da 500.
- `tarea_ids` no numérico → 422; Estimado sin tareas no genera pedido; con pedido PENDIENTE no se agregan/quitan tareas (409). Fechas D/M/AAAA validadas (422) y con `pattern` en el form. ANULADA queda fuera de candidatas y de `/facturacion` (NULL legado sigue entrando). **Abierto (no es bug, es feature):** el título de un BORRADOR no se puede editar.

## Medios
- **Colisión de número interno en "Duplicar → OT nueva"** (confirmado 2026-10-07): `duplicar_form` calcula `siguiente_numero_interno()` al abrir sin reservar; dos aperturas dan el mismo número y al guardar la segunda tarea se pega en silencio a la `ot_interna` de la primera. `ot/app/routers/tareas.py` (`duplicar_form`, `_resolver_ot_interna`). Estado: **corregido 2026-10-07** (sin commit aún): el form manda `ot_generada` y `crear_tarea` asigna el siguiente libre si el número ya lo ocupó otra OT. Regresión: dos aperturas + dos guardados → OT 4164 y 4165, una tarea cada una.
- **Anular sin bloqueo en servidor** (2026-10-07): el POST directo anulaba tareas FACTURADO/PARA_FACTURAR. Javier decidió que esas no se anulan. Estado: **corregido 2026-10-07**: 409 en el servidor y botón deshabilitado con motivo; FINALIZADO sigue anulable con advertencia. Regresión: POST directo a `/anular` en una tarea facturada → 409 y estado intacto.

- **Servidor acepta `detalle` vacío** (2026-10-07): `POST /tareas` con `detalle=''` inserta la tarea; solo el `required` del navegador lo frena. OT, fecha, tipo y responsables sí dan 422. Estado: **corregido 2026-10-07** (422 en crear y editar, `detalle` en blanco incluido).

- **asignar-lote/reasignar ignoran `solicitud_alta_id`** (2026-10-07): una OT con solicitud PENDIENTE acepta número manual; al resolver se pisa en silencio. `ot/app/routers/ordenes_trabajo.py`. Estado: **corregido 2026-10-07**: 409 en asignar-lote y reasignar si la OT tiene pedido PENDIENTE. Regresión: generar solicitud, luego asignar número a esa OT → 409 y base intacta.
- **Solicitud RESUELTA desincronizada** (2026-10-07): reasignar deja `solicitud_alta_id` viejo; `generar-ot` (l.263) rechaza con "pedido pendiente" aunque esté resuelta. Estado: **corregido 2026-10-07**: el chequeo mira solo PENDIENTE y reasignar a un número distinto del resuelto desvincula la OT. Regresión: resolver, reasignar/vaciar, volver a generar → 303.
- **Comando `crear_ot.py` sin escapar** (2026-10-07): comillas/`$var`/backticks en Anunciante o Resumen rompen o expanden el comando pegado en terminal. `ot/app/viewmodels.py` (`_arg_shell`). Estado: **corregido 2026-10-07**: comillas simples (PowerShell y bash no expanden nada), apóstrofe duplicado, saltos de línea a espacio. Límite: en bash un apóstrofe interno se pierde (`''` se lee como concatenación); el equipo corre en PowerShell.

## Bajos
- `POST /tareas/{id}/anular` con id inexistente → 500 en vez de 404 (`db.get` None → `puede_anular(None)`); probable igual en `/estado` y `/facturacion`. Estado: **corregido 2026-10-07** para `/tareas/{id}/anular|estado|facturacion|PATCH` (404). Verificar `estimados.py:248` y `facturacion.py:121`, que usan el mismo `db.get(Tarea, …)` sin chequeo.

- Panel de OT de sistema (2026-10-07), bajos abiertos: "correrCrear_ot.py" sin espacio (`list.html:107`, **corregido 2026-10-07**); asignar-lote con OT inexistente da 303 sin hacer nada; `/reasignar` sin confirm ni required; badge "SINCRONIZADA" estático; error rojo del panel no se oculta al corregir; errores de servidor como JSON crudo; panel inutilizable en mobile 375px (**corregido 2026-10-07**, ver abajo).

## Verificado y funciona (no volver a abrir sin cambio de código)
- Duplicar "Misma OT": precarga, no guarda antes de confirmar, tarea nueva coherente (2026-10-07).
- Anular tarea abierta desde el drawer: confirmación, refresco, solo cambia el estado (2026-10-07).
- Crear tarea (drawer queda abierto, uniones exactas), editar tipos/responsables sin 500, y "+ Nueva" dos veces con guardados en OT distintas (2026-10-07).
- Panel de OT de sistema: modos existente, manual y generar (solo crea solicitud, no toca Advertys), Resolver/Cancelar y reasignar desde el detalle, con sus validaciones 422/409/404 (2026-10-07).
- Mobile ≤720px (2026-10-07): el sidebar pasa a barra superior con menú a pantalla completa; el panel de OT de sistema apila los 3 modos en una fila ("Existente / Generar / Cargar"), inputs de 44 px y botón principal a todo el ancho; drawer con pie que envuelve; detalle de OT sin desborde. Verificado a 375px en OT internas (modos existente y generar), Tareas (tabla y drawer), Estimados, Facturación y detalle de OT; escritorio (1280px) sin cambios. Regresión: a 375px `scrollWidth == 375` en esas pantallas.
