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
