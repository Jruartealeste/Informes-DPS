# QA ot/ — 2026-10-14 — Combo Producto en "Generar OT en Advertys"

## Entorno y alcance
- `ot/tools/qa_server.py --sqlite --reset` en :8123 (Docker no estaba corriendo: **no se ejercitó Postgres**).
- Catálogo real de `informes/advertys.db` (83 productos, 35 anunciantes) cargado a mano en `productos_advertys` del sqlite de QA.
- Probado: precarga del Anunciante (ALUAR) → combo con 12 productos; Anunciante abreviado "aluar aluminio arg." → infiere "ALUAR ALUMINIO ARGENTINO SOCIEDAD ANONIM"; envío → `solicitudes_alta_ot` guarda el nombre inferido y el producto elegido; Anunciante sin catálogo → combo deshabilitado y el envío se bloquea con aviso (no se crea solicitud); consola sin errores.
- No probado: mobile 375px, tema oscuro, Postgres.

## Altos
- Ninguno.

## Medios
- Ninguno.

## Bajos
- Texto del combo deshabilitado se cortaba ("sin productos de Advertys para este A…"). **Corregido** a "Producto: sin catálogo en Advertys".

## Lo que funcionó bien
- Inferencia del Anunciante y guardado del nombre real de Advertys en el pedido (lo que necesita `crear_ot.py`).
- "FATE" a secas no se adivina (empate entre 6 anunciantes) — hay que elegir uno.

---

# Segunda pasada (2026-10-14) — Producto según el cliente del sidebar

Rediseño pedido por Javier: el Anunciante ya no se tipea; el cliente es el del sidebar y el combo Producto lista el catálogo de los Anunciantes de Advertys de ese cliente (`app/anunciantes.py`), agrupado por Anunciante cuando son varios. El Anunciante del pedido sale del Producto elegido.

## Entorno y alcance
- `qa_server.py --sqlite --reset` (Docker apagado: **no se ejercitó Postgres**), catálogo real (83 productos). Cliente de seed "Fundación Aurora Austral" renombrado a "FAA" y agregado "FATE" para probar.
- Probado: ALUAR → 12 productos, sin campo Anunciante; FATE → 22 productos en 6 grupos (uno por Anunciante); FAA → "CAMPAÑAS VARIAS" de FUNDACIÓN AURORA AUSTRAL (por siglas); FAA activo con una OT de ALUAR tildada → bloquea con "no son de FAA (el cliente elegido en el sidebar)"; ALUAR → pedido creado (303) con anunciante "ALUAR ALUMINIO ARGENTINO SOCIEDAD ANONIM", producto Hosting.
- No probado: mobile 375px, tema oscuro, Postgres.

## Altos / Medios
- Ninguno.

## Bajos
- El listado de OT internas no se filtraba por el cliente del sidebar (conocido desde 2026-09-24). **Corregido**: listado, contadores, kicker y picker de "OT de sistema existente" filtran por el cliente activo (verificado: FAA → solo OT 5001, "FAA · 1 OT interna"; ALUAR → sus 26).
- **Preexistente, corregido:** el "?" de ayuda dentro de un `<p class="form-nota">` tiraba `TypeError ... reading 'style'` al abrirlo — el `<div class="info-tip__panel">` dentro de `<p>` hace que el parser cierre el `<p>` y deje el panel fuera del `.info-tip`. Pasado a `<span>` en `ordenes_trabajo/list.html`, `ordenes_trabajo/solicitudes.html` y `estimados/solicitudes.html`; verificado que abre sin errores.

---

# Tercera pasada (2026-10-14) — botones a íconos (subagent ot-qa)

## Entorno y alcance
- Server de QA en :8123 sobre sqlite (Docker apagado: **no Postgres**), sesión ADMIN, ALUAR activo. 375 px y escritorio (pane de 800 px); tema claro y oscuro en drawer de Tareas, Solicitudes de Estimados y OT internas.
- El server no tenía el último cambio de `clientes.py` (sin reload): el 0/0 del sidebar en /anunciantes es probablemente eso. Reiniciar antes de la próxima pasada.
- Escribió en la base de QA: Estimado 1 "QA iconos" (BORRADOR, OT de sistema 285) y su solicitud de alta 1 (PENDIENTE).
- No probado: Postgres, guardar/editar tarea (PATCH, 409 de versión), Anular, guardar Duplicar, enviar mail, Agrupar por OT, panel de Filtros, acciones que escriben en OT internas, alta/desactivar/reactivar anunciante, tablet, 1280 px.

## Altos
- Ninguno.

## Medios
- **Mobile: drawer y sheets fuera de pantalla.** Con la lista scrolleada, el drawer abre en `top=-539`; con un sheet abierto, el scroll mueve la lista y deja un hueco. Causa: `.drawer-overlay { position: absolute; inset: 0 }` dentro de `.main`, que en mobile es el que scrollea (`app.css` ~1099 y ~2579). Fix propuesto: overlay `position: fixed` a ≤720 px, `overscroll-behavior: contain`, bloquear el scroll de `.main` con drawer abierto.

## Bajos
- Escape no cierra drawer ni sheets.
- La ✕ del drawer es un glifo de texto de 28 px sin `aria-label`/`title` (`_detalle.html:17`, `_duplicar_sheet.html:9`, `_mail_sheet.html:10`, `responsables/_sheet.html:9`); reutilizar el SVG de `sidebar__menu-cerrar`.
- Badge "Tareas" del sidebar: 32 en /tareas (por anunciante) y 34 en el resto (`_total_tareas` global en ordenes_trabajo/estimados/facturacion).
- Título pegado a la card en mobile en /estimados/nuevo y /anunciantes/{id}.
- "Cargar número" se parte en dos líneas en /estimados/solicitudes a 375 px.
- /anunciantes: la tabla mide 959 px y las acciones quedan fuera de vista (también en 800 px).
- El motivo de "Anular" deshabilitado está solo en `title` (no se ve en táctil).
- Áreas de toque < 44 px en mobile: `.combo__toggle`, `btn--small`, "?" (17 px), "← OT internas", segmentado Sin/Con (32), copiar (30).
- En el sidebar, "Anunciante · pronto" (deshabilitado) junto a "Anunciantes" confunde; "Solicitudes de alta" usa estilos distintos en Estimados y OT internas.

## Botones a íconos
Medición a 375 px: en /tareas la lista empieza en y=325 (barra de acciones 36 px + filtros 128 px en 2 filas); el pie del drawer ocupa 112 px en 2 filas; en /ordenes-trabajo filtros 145 px en 3 filas, panel 220 px (440 en Generar), tabla en y=495.

| Pantalla | Botón actual | Propuesta | Ícono | Riesgo de confusión |
|---|---|---|---|---|
| Tareas / OT internas | "Filtros" | ícono solo en mobile | sliders (ya existe) | bajo; badge si hay filtros activos |
| Tareas | "⚠ Necesitan revisión 13" | ícono + número en mobile | alerta (ya existe) | medio: title/aria-label obligatorios |
| Tareas | "Agrupar por OT" | ícono solo en mobile, aria-pressed | capas | medio: no es universal |
| Tareas | "Nueva OT/tarea" | "+ Nueva" en mobile | + | bajo |
| Drawer de tarea | "Enviar mail" | ícono (o + "Mail") | sobre | bajo |
| Drawer de tarea | "Duplicar" | ícono solo | dos rectángulos | medio: puede leerse como copiar |
| Drawer y sheets | "✕" glifo | SVG + aria-label "Cerrar", 44 px mobile | ✕ del sidebar | bajo |
| Anunciantes | "Editar" | ícono solo | lápiz (ya existe en Responsables) | bajo |
| Anunciantes | "Ver" | ícono solo | ojo | bajo |
| Detalle de Estimado | "Quitar" | ícono solo o dejar | menos en círculo | medio: puede leerse como anular |

Dejar con texto: acciones principales (Guardar, Crear, Asignar OT de sistema, Generar en Advertys), lo destructivo (Anular, Desactivar/Reactivar, Cancelar pedido), acciones de dominio (Cargar número/título, Reasignar, Armar Estimado, Agregar tildadas, Solicitudes de alta), segmentados y chips de estado.

## Ideas de mejora
1. Panel de asignación de OT internas en mobile como barra inferior que aparece al tildar.
2. Un solo set de íconos SVG (macro/partial) para toda la app.
3. En "OT de sistema", "—" atenuado en vez del badge "sin OT de sistema" repetido.
4. Pie del drawer en mobile en una fila: Guardar, secundarias como íconos, Anular separado.

## Lo que funcionó bien
- Sin errores de consola nuevos ni 4xx/5xx en lo recorrido; tema claro/oscuro OK; copiar comando OK; labels cortos del panel OK en mobile; regresión del "?" corregida (0 errores).

