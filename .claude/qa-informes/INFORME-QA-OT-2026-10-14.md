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
