---
name: qa-ot
description: Use when Javier pide QA de la interfaz de ot/ (Órdenes de Trabajo/Tareas), probar los últimos cambios de UI antes de darlos por terminados, o pedir ideas de mejora de diseño para esas pantallas. Ej: "hacé QA de lo último que cambiamos en ot", "probá la sheet de tareas y decime si algo se ve mal", "dame ideas para mejorar el diseño de OT internas".
argument-hint: [pantalla o cambio puntual a revisar]
---

## Qué hace

QA funcional + visual de las pantallas de `ot/`, interactuando de verdad
(clicks, forms, drawers, filtros — no solo capturas estáticas) contra un
servidor descartable con datos ficticios de ALUAR
(`ot/tools/qa_server.py` sobre un **Postgres local en Docker**, contenedor
`ot-qa-pg` en `127.0.0.1:54329`, nunca `.env` real ni Neon de producción) y,
a diferencia de una revisión solo visual, **cierra cada flujo consultando la
base**: lo que importa es lo que se ve bien y está mal guardado. Usa el browser pane (`mcp__Claude_Browser__*`, Playwright por
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

1. `bash .claude/skills/qa-ot/scripts/levantar-entorno.sh` — levanta/reusa el
   Postgres `ot-qa-pg` (idempotente, no descarga nada, no toca Neon ni el
   Supabase de otros proyectos). Requiere Docker corriendo.
2. `preview_start({name: "ot-qa"})` — corre `ot/tools/qa_server.py`: aplica
   `alembic upgrade head` (así también se prueban las migraciones), siembra si
   está vacía y sirve en `:8123`. Si el modelo/migraciones cambiaron
   (`git diff --stat HEAD -- ot/app/models.py ot/migrations`), parar el server
   y volver a lanzarlo con `--reset` (`ot/.venv/Scripts/python.exe
   ot/tools/qa_server.py --reset` desde Bash en background) para no arrastrar
   schema viejo. `--sqlite` queda como plan B sin
   Docker, pero no ejercita Postgres.
3. `navigate` a `http://localhost:8123/auth/qa-login` (login simulado).
4. Recorrer según `references/flujos.md`, interactuando de verdad (`computer`,
   `find`, `form_input`), revisando consola/red y responsive/tema si aplica.
   **Después de cada flujo que escribe, consultar la base**:
   `docker exec ot-qa-pg psql -U postgres -d ot_qa -tAc "..."`.
5. Regresión: probar cada punto de `references/hallazgos-conocidos.md`.
6. Informe: escribir `.claude/qa-informes/INFORME-QA-OT-AAAA-MM-DD.md`
   (Entorno y alcance — incluyendo **qué no se probó** —, Altos, Medios, Bajos,
   Lo que funcionó bien) y actualizar `hallazgos-conocidos.md`.
7. Si algo rompe: reportar y proponer; el fix se discute en la conversación
   principal. Para ideas de diseño, cargar `frontend-design` antes de opinar.

## Notas

- **Guardarraíl de base:** `qa_server.py` aborta si la base no es localhost;
  igual, antes de operar confirmar con
  `docker exec ot-qa-pg psql -U postgres -d ot_qa -tAc "select 1"` que el
  Postgres local responde. Nunca poner credenciales de Neon/Advertys acá.
- **Nunca contra `http://localhost:8000`** (el uvicorn real de desarrollo,
  si está corriendo) — ese sí puede estar apuntando a Neon compartido. Este
  skill y el subagent `ot-qa` solo tocan el `:8123` descartable.
- Datos del server de QA: mismo dataset realista de `scripts/seed.py`
  (~34 tareas de ALUAR, variedad de estados, OT ambiguas y OT que
  comparten `numero_ot_advertys`) — no hace falta armar fixtures a mano.
- Los datos viven en el volumen Docker `ot-qa-pgdata`; para empezar de cero:
  `levantar-entorno.sh --reset` (borra contenedor y volumen) o
  `qa_server.py --reset` (re-migra y re-siembra en el mismo contenedor).
  `ot/tools/.qa_data/` solo se usa con `--sqlite`.
- Los flujos de QA y sus verificaciones SQL están en `references/flujos.md`;
  los hallazgos previos en `references/hallazgos-conocidos.md`.
