# QA ot/ — Duplicar y Anular (2026-10-07)

## Entorno y alcance
- Server `:8123` sobre Postgres local `ot-qa-pg` (alembic head + seed). Nunca `:8000`.
- Probado: flujo 3 (Duplicar, misma OT y OT nueva), flujo 4 (Anular) y el hallazgo de colisión de número.
- UI real: drawer, sheet de Duplicar "Misma OT", guardar, anular desde el drawer. El resto con `fetch` a los mismos endpoints.
- **No probado:** responsive, tema, mail, edición, filtros, OT internas; la rama "OT nueva" por la sheet de la UI (solo el endpoint); dos pestañas reales (se simuló con dos fetch seguidos).

## Altos
Ninguno.

## Medios
1. **Colisión de número en Duplicar → OT nueva (confirmado).** Dos aperturas sin guardar entre medio devuelven el mismo `ot_numero` (4164). Al guardar ambas no hay error: la segunda tarea se pega en silencio a la `ot_interna` de la primera. Causa: `duplicar_form` llama a `siguiente_numero_interno()` sin reservar; `_resolver_ot_interna` trata un número existente como "reusar" (`ot/app/routers/tareas.py`).
2. **Anular no se bloquea en el servidor (decisión de diseño a confirmar).** `puede_anular` (`ot/app/viewmodels.py`) solo bloquea las ya ANULADA (commit 1d4262e: "Anular habilitado con advertencia"). El POST directo anuló tareas FINALIZADO, PARA_FACTURAR y FACTURADO; la advertencia vive solo en el cliente (`hx-confirm`).

## Bajos
- `POST /tareas/{id}/anular` con id inexistente da 500 (`db.get` → None). Debería ser 404; probablemente igual en `/estado` y `/facturacion` (no verificado).

## Regresión de conocidos
- Colisión de número en Duplicar → OT nueva: persiste.

## Funcionó bien
- Duplicar "Misma OT": sheet se cierra, título "duplicada de", datos precargados, fecha vacía, no guarda hasta confirmar (conteo 34 intacto), tarea nueva con OT interna correcta, estado NULL, SIN_FACTURAR, tipos/responsables coherentes.
- Anular tarea abierta: confirmación, drawer cierra, tabla refresca, solo cambia el estado a ANULADA.
- Consola sin errores salvo el 500 provocado a propósito.

## Ideas
1. Asignar el número al guardar (no al abrir) y avisar si el número ya existe con N tareas.
2. Decidir si Anular FACTURADA/PARA_FACTURAR se bloquea con 409 en el servidor.
3. 404 en `/tareas/{id}/...` cuando el id no existe.
