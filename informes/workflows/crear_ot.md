# Crear (dar de alta) una OT nueva en Advertys

**Objetivo:** correr `modules/ordenes_trabajo/crear_ot.py` para dar de alta
el encabezado de una OT nueva en Advertys — nunca Estimados ni Órdenes de
Compra, solo el alta de OT en sí.

**Cuándo usar:** Javier pide algo como "creá una OT en Advertys", "dale de
alta una OT nueva", "generá una OT para <cliente>", "necesito una OT de
prueba en Advertys" o "alta de OT". Si en cambio pide crear una **OT
interna** (`ot_interna`) dentro de la app `ot/` — sin tocar Advertys — ese
es un pedido distinto, ver `ot/CLAUDE.md`, no este workflow.

**Salvaguarda:** este script escribe en Advertys real (crea un registro
nuevo, numeración incluida) — no es de solo lectura, y no es fácilmente
reversible (Javier tiene que anular/borrar la OT a mano en Advertys si fue
de prueba, como pasó con la OT 298 el 2026-09-23). Por eso:

- **Nunca correrlo sin que Javier confirme explícitamente los 4 datos
  concretos de esa corrida puntual** (Anunciante, Resumen, Producto, Centro
  Costo — y Equipo si aplica). Una autorización anterior (aunque haya sido
  "OT de prueba" el mismo día) no vale para la siguiente corrida — cada
  alta es una confirmación nueva.
- Si Javier pide "una OT de prueba" sin más datos, no inventar valores —
  preguntarle con qué Anunciante/Resumen/Producto/Centro Costo quiere
  probar (puede ser un cliente real con un Resumen tipo "Prueba" para
  poder identificarla y borrarla después).
- Nunca ampliar el alcance del script a Estimados de Costo, Órdenes de
  Compra, o edición/borrado de una OT existente — eso es
  `modules/estimados_costos/crear_estimado.py` (otro script, otro
  workflow) o directamente fuera de alcance.

**Campos:**

- **Obligatorios:** Anunciante, Resumen, Producto, Centro Costo.
- **Opcional:** Equipo (si no se pasa, Advertys lo deja en "N / D").
- **Centro Costo** es un combo fijo de 4 valores exactos: `ADMINISTRACION`,
  `AGENCIA - ESTRUCTURA`, `CREATIVIDAD - PRODUCCION`, `MEDIOS`.
- **Producto** es un catálogo propio de cada Anunciante (no una lista
  global) — ver `modules/ordenes_trabajo/productos_por_anunciante.json`.
  Si el Anunciante ya está relevado ahí, el script valida el valor antes de
  correr contra Advertys; si no está relevado, no bloquea (deja que
  Advertys sea la última palabra) — avisarle a Javier que ese Anunciante
  todavía no tiene catálogo de Producto relevado, por si el alta falla por
  "Falta Producto" con un valor inventado.
- **Producto, Tag y Contacto Anunciante** del lado de Advertys quedan
  siempre sin completar salvo Producto (que Advertys exige) — se cargan a
  mano después si hace falta.

**Tools a usar (parado en `informes/`, no en la raíz del repo — `cd
informes` primero si hace falta):**

1. Confirmar con Javier, para esta corrida puntual: Anunciante, Resumen,
   Producto, Centro Costo, y Equipo si aplica.
2. `python -m modules.ordenes_trabajo.crear_ot "<anunciante>" "<resumen>" "<producto>" "<centro_costo>" [--equipo "<equipo>"]`
   — busca y selecciona el Anunciante por el popup de búsqueda (corta con
   error si no resuelve a exactamente una fila), completa Resumen +
   Producto + Centro Costo + Equipo (opcional), clickea "Guardar", y lee el
   número de OT nuevo del campo "Nro OT".
3. Reportarle a Javier el número de OT resultante y recordarle que, si era
   de prueba, la tiene que anular/borrar en Advertys cuando quiera (este
   agente no lo hace).

**Manejo de errores:**

- `"Falta Producto"` (o cualquier mensaje de campo obligatorio faltante) —
  Advertys cortó el Guardar sin persistir nada; no reintentar a ciegas,
  confirmar el valor correcto con Javier.
- La búsqueda de Anunciante no resuelve a exactamente una fila — el script
  corta con error antes de tocar nada más; confirmar el nombre exacto con
  Javier en vez de adivinar cuál fila era.
- El popup de Anunciante puede cerrarse solo al clickear la fila (sin pasar
  por "Aceptar") — ya contemplado en `seleccionar_anunciante`, no es un
  error real si el campo del formulario principal terminó con el valor
  correcto.

**Salida esperada:** el número de OT nueva (ej. "OT 298"), confirmado
leyéndolo directo del campo del formulario después de Guardar — nunca
asumir éxito solo porque el script no tiró excepción.
