# Flujos de ot/ a probar y qué verificar en la base

Para cada flujo: hacerlo por la interfaz y **después consultar la base**
(`docker exec ot-qa-pg psql -U postgres -d ot_qa -tAc "..."`). Lo que dice
el cartel o la tabla HTMX no alcanza: hay que confirmar que lo guardado es lo
que se ve. Antes de cada flujo anotar el estado de partida (conteos o la fila
involucrada); si se hace algo destructivo a propósito, limpiar con SQL o
`--reset` antes del siguiente.

Tablas: `tareas`, `ot_interna`, `tarea_tipos_tarea`, `tarea_responsables`,
`tarea_mails`, `clientes`, `responsables`, `tipos_tarea`, `estimados`,
`solicitudes_alta_ot`, `solicitudes_alta_estimado`.

## 1. Crear tarea (`POST /tareas`)
- Completar OT interna, fecha de pedido, tipo, responsables, guardar.
- Esperado: el drawer **queda abierto en modo edición** (con Enviar mail y
  Anular habilitados), la tabla de atrás muestra la fila nueva.
- Base: una fila nueva en `tareas`; `tarea_tipos_tarea` y `tarea_responsables`
  con exactamente lo elegido (sin duplicados); `ot_interna_id` correcto o
  `ot_ambigua` coherente con el input.
- Validación: guardar con OT, fecha, tipo o responsables vacío → avisa y **no
  inserta nada** (contar filas antes/después). Tipo inexistente en el
  catálogo: se rechaza o se crea el faltante del catálogo, según el commit
  `dd0a943`.

## 2. Editar tarea (`PATCH /tareas/{id}`)
- Cambiar tipos y responsables (quitar uno, sumar otro, dejar uno igual).
- Esperado: sin 500 por UNIQUE (sincroniza por diferencia, commit `389345e`).
- Base: tablas de unión con exactamente el set final.
- La OT ya asignada es de solo lectura (salvo `ot_ambigua`): verificar que
  mandar otro `ot_numero` a mano no la cambia.

## 3. Duplicar tarea (`GET /tareas/{id}/duplicar` + `/duplicar/form`)
- Probar las dos ramas: **misma OT** y **OT nueva**.
- Esperado: abre el form con datos precargados y NO guarda nada hasta
  confirmar; fecha de pedido, estado y facturación arrancan de cero; la sheet
  de elección se cierra.
- Base: antes de confirmar el conteo de `tareas` no cambia; con "nueva" el
  número interno es el siguiente correcto (sin colisión si se abre el form
  dos veces seguidas sin guardar — ver hallazgos-conocidos).

## 4. Anular (`POST /tareas/{id}/anular`)
- Tarea abierta: anula (confirmación nativa `window.confirm` → ejecutar
  `window.confirm = () => true` antes) y estado queda `ANULADA`.
- Facturación `FACTURADO` / `PARA_FACTURAR`: **no se puede anular** (decisión
  de Javier 2026-10-07). El botón queda deshabilitado con el motivo en el
  `title` y el POST directo devuelve 409 sin cambiar nada.
- `FINALIZADO` (sin facturación): se puede anular, con `hx-confirm` de
  advertencia "FINALIZADA".
- Id inexistente: 404.
- Base: `estado_tarea` y que nada más se haya tocado.

## 5. Estado y facturación sueltos (`/tareas/{id}/estado`, `/facturacion`)
- Cambiar desde la fila/drawer. Base: solo ese campo cambió.

## 6. Mail a responsables
- Sheet "Enviar mail": checkbox de misma cadena de Gmail (destildable),
  borrador. **Nunca enviar de verdad** (no hay credenciales Gmail en el
  entorno de QA: debe fallar con error claro, no 500 ni dejar `tarea_mails`
  en estado inconsistente).

## 7. OT internas (`/ordenes-trabajo`, `/ordenes-trabajo/{numero_interno}`)
- Listado, buscador y filtros. Detalle de una OT con hermana por
  `numero_ot_advertys` compartido (el seed NO trae hermanas: armarlas
  asignando el mismo número a 2 OT con el panel de la lista).
- Reasignar OT de sistema: afecta solo a esa `ot_interna`; base: otras OT no
  cambian y la hermana sigue coherente.

## 8. Filtros de /tareas
- Estado, facturación, responsable, "⚠ Necesitan revisión", combinados.
- Contrastar el conteo de la tabla con un `select count(*)` equivalente.

## 9. Sync desde Informes (`/api/sync/*`)
- Sin token → 401; con `qa-local-sync-token-not-real` → upsert por
  `numero_ot` (actualiza, no duplica). Base: `ordenes_trabajo_espejo`,
  `sync_log`.

## 10. Auth
- Sin sesión toda ruta redirige a login (307); `/auth/qa-login` solo existe
  en el server de QA.

## 11. Panel de OT de sistema (`/ordenes-trabajo`, 3 modos)
- Usar existente / Cargar número / Generar OT en Advertys. "Generar" solo crea
  una `solicitudes_alta_ot` (la app no tiene credenciales de Advertys): nunca
  correr `crear_ot.py` desde el QA.
- Base: `ot_interna.numero_ot_advertys`, `ot_interna.solicitud_alta_id`,
  `solicitudes_alta_ot.estado`. Validar 422/409/404 por POST directo. Todas las
  OT del seed son de ALUAR: para "clientes distintos" crear una OT de otro
  cliente por `POST /tareas`.
