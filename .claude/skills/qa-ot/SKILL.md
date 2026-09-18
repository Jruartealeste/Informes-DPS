---
name: qa-ot
description: Use when Javier pide QA de la interfaz de ot/ (Órdenes de Trabajo/Tareas), probar los últimos cambios de UI antes de darlos por terminados, o pedir ideas de mejora de diseño para esas pantallas. Ej: "hacé QA de lo último que cambiamos en ot", "probá la sheet de tareas y decime si algo se ve mal", "dame ideas para mejorar el diseño de OT internas".
argument-hint: [pantalla o cambio puntual a revisar]
---

## Qué hace

QA funcional + visual de las pantallas de `ot/`, interactuando de verdad
(clicks, forms, drawers, filtros — no solo capturas estáticas) contra un
servidor descartable con datos ficticios de ALUAR
(`ot/tools/qa_server.py`, sqlite propio, nunca `.env` real ni Neon de
producción). Usa el browser pane (`mcp__Claude_Browser__*`, Playwright por
debajo) para navegar, y el skill `frontend-design` para fundamentar las
ideas de mejora que propone.

## Cuándo esto vs. `captura-visual`

- **`captura-visual`**: una captura puntual y rápida de una vista de `ot/`
  ya corriendo (server real en `:8000`), sin login bypass ni checklist —
  sirve mientras se está diseñando algo en curso.
- **Este skill**: pasada de QA real — login, interacción, varias pantallas,
  consola/red, responsive, claro/oscuro, y un veredicto con bugs + ideas de
  mejora. Corre contra su propio servidor descartable (`:8123`), nunca
  contra el `:8000` real.

## Una pantalla vs. una pasada completa

Para **una revisión puntual de una sola pantalla o interacción** (ej. "¿el
drawer de tarea valida bien los campos obligatorios nuevos?"), seguir
inline los pasos de abajo — el overhead de un subagent nuevo no se
justifica para eso. Para **una pasada completa tras un cambio de CSS/JS
compartido, o cuando Javier pide explícitamente "QA" o "ideas de mejora"**,
delegar al subagent `ot-qa` (`.claude/agents/ot-qa.md`, solo lectura sobre
el código real) para mantener las capturas y la exploración fuera de la
conversación principal — devuelve un veredicto corto en vez de volcar todo
acá.

## Pasos (revisión inline)

1. `preview_start({name: "ot-qa"})` — levanta `ot/tools/qa_server.py` en
   `:8123` (reusa el proceso si ya estaba arriba). Si el modelo de datos
   cambió desde la última corrida, `preview_stop` + borrar
   `ot/tools/.qa_data/qa_ot.db` antes de volver a levantarlo.
2. `navigate` a `http://localhost:8123/auth/qa-login` (login simulado, sin
   pasar por Google OAuth real).
3. Recorrer la(s) pantalla(s) relevante(s), interactuando de verdad
   (`computer`, `find`, `form_input`), revisando consola/red
   (`read_console_messages`, `read_network_requests`) y responsive/tema si
   aplica (`resize_window`, cookie `tema`).
4. Si algo se ve mal o rompe, corregir en la conversación principal,
   regenerar y repetir. Para ideas de diseño, cargar el skill
   `frontend-design` antes de opinar.

## Notas

- **Nunca contra `http://localhost:8000`** (el uvicorn real de desarrollo,
  si está corriendo) — ese sí puede estar apuntando a Neon compartido. Este
  skill y el subagent `ot-qa` solo tocan el `:8123` descartable.
- Datos del server de QA: mismo dataset realista de `scripts/seed.py`
  (~34 tareas de ALUAR, variedad de estados, OT ambiguas y OT que
  comparten `numero_ot_advertys`) — no hace falta armar fixtures a mano.
- `ot/tools/.qa_data/` es descartable/regenerable (gitignorado vía el
  `*.db` de `ot/.gitignore`), igual que `exploracion/` en `informes/`.
