# QA ot/ — Panel de asignación de OT de sistema, 3 modos (2026-10-07, 3ª pasada)

## Entorno y alcance
- Server `:8123` sobre Postgres local `ot-qa-pg` reseteado. Nunca `:8000`. No se corrió `crear_ot.py` ni nada de `informes/`: "Generar OT en Advertys" solo crea una `solicitudes_alta_ot`.
- UI real + POST directo para validaciones de servidor; cada paso verificado en la base. Probados A (usar existente), B (cargar número), C (generar), Resolver/Cancelar solicitud, reasignar desde el detalle, hermanas, consola/red, mobile 375px en la lista, tema claro/oscuro en la lista.
- **No probado:** tema y mobile en `/solicitudes` y en el detalle; filtros combinados con selección; botón "Copiar" del comando; regresión de `hallazgos-conocidos.md`.
- Nota de datos: el seed NO tiene OT que compartan `numero_ot_advertys` (5 con número, todos distintos) y todas son de ALUAR; el agente creó la OT 4170 (INFA) para probar clientes distintos.

## Altos
Ninguno por la UI normal.

## Medios
1. **asignar-lote y reasignar ignoran `solicitud_alta_id`** (`ordenes_trabajo.py:183-211`). Una OT con solicitud PENDIENTE puede recibir un número manual y queda con `numero_ot_advertys` y `solicitud_alta_id` a la vez; al resolver la solicitud se pisa el número en silencio, y al cancelar queda el manual. La UI no avisa.
2. **Solicitud RESUELTA queda desincronizada y bloquea regenerar con mensaje falso.** Reasignar una OT de una solicitud resuelta deja `solicitud_alta_id` apuntando a la vieja (la página de solicitudes muestra un número que ya no es el real). Si además se vacía el número, `generar-ot` la rechaza con "ya tienen un pedido de alta pendiente" aunque la solicitud esté resuelta (el chequeo mira `solicitud_alta_id` sin mirar el estado, l.263).
3. **Comando `crear_ot.py` sin escapar** (`viewmodels.py:168-181`, `_comando_crear_ot`). Comillas dobles internas rompen el comando y `$var`, backticks y `$(...)` se expanden al pegarlo en la terminal. Es texto libre del usuario.

## Bajos
4. Texto "correrCrear_ot.py" sin espacio (`list.html:107`, `display:flex` inline).
5. `asignar-lote` con OT inexistente responde 303 "éxito" sin hacer nada (generar-ot da 422); ids repetidos dan un 422 engañoso.
6. `/reasignar` en el detalle no confirma ni exige valor (la lista sí confirma); hermanas como texto plano, no links.
7. Badge "SINCRONIZADA" estático: aparece con cualquier número aunque `ordenes_trabajo_espejo` esté vacía.
8. El error rojo del panel queda visible aunque se corrija el campo.
9. Errores de servidor al saltar la validación cliente se ven como JSON crudo en pantalla completa.
10. Mobile 375px: sidebar sin colapsar, card de ~100px, segmentado apilado, inputs de la grilla recortados. "Generar OT" inutilizable desde el celular (probable en toda la app, solo verificado en esta pantalla).

## Funcionó bien
- A: asigna solo las OT seleccionadas; el confirm de reasignación lista solo la conflictiva; "Cancelar" no envía nada.
- B: vacío y espacios frenan en cliente y dan 422 por POST.
- C: crea 1 solicitud PENDIENTE con las OT vinculadas y redirige a `/solicitudes` con el comando; 422 correctos para OT con número, con solicitud pendiente, clientes distintos, centro de costo/equipo inválido, campos vacíos, OT inexistente y sin selección.
- Resolver y Cancelar: propagan o liberan correctamente; repetir da 409, vacío 422, inexistente 404.
- Reasignar desde el detalle mantiene coherentes las hermanas.
- Consola sin errores JS ni 5xx.

## Ideas
1. Regla única "OT con solicitud pendiente bloqueada" (chip "pedido #N pendiente", checkbox deshabilitado en A/B, 409 en el servidor); cierra medios 1 y 2.
2. Rediseño responsive del panel (sidebar colapsable, segmentado en una fila, grilla a 1 columna).
3. `shlex.quote` en el comando y bloque de verificación previa en `/solicitudes`.
4. Hermanas clickeables y badge de sincronización real.
