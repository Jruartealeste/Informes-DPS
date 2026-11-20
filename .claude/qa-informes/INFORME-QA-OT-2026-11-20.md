# QA ot/ — 2026-11-20 — Estimados: agrupado por OT interna y "Desenlazar de Advertys"

## Entorno y alcance
- Server de QA `:8123` (Postgres descartable `ot-qa-pg`), datos ficticios. Nunca `:8000` ni Neon.
- Dos pasadas con el subagent `ot-qa`:
  1. Selector "Nuevo Estimado" por OT de sistema, lista de tareas agrupada por OT interna con tilde por
     grupo (`/estimados/nuevo` y "Agregar tareas" del detalle), detalle agrupado.
  2. Botón "Desenlazar de Advertys" (`POST /estimados/{id}/desenlazar`) en un Estimado GENERADO.
- Escrituras verificadas contra la base (estimado_id de las tareas; `estado`, `numero_estimado` y
  `solicitud_alta_id` del Estimado; borrado de la solicitud resuelta). Las dos vías de GENERADO: pedido resuelto y
  "Cargar número" manual.
- Claro/oscuro y 375 px. Consola sin errores JS.
- **No se probó:** tablet, Estimado con items cargados en Advertys, concurrencia de dos usuarios, Estimado no
  editable en la pasada 1, regresión completa de `hallazgos-conocidos.md`.
- Nota: el uvicorn de QA ya levantado no veía rutas nuevas; hay que reiniciarlo (preview_stop/start) tras
  cambiar routers.

## Altos
Ninguno.

## Medios (corregidos)
- Móvil: la tabla de selección de tareas no tenía wrapper con scroll horizontal; Tipo y "Desdoblar" quedaban
  inalcanzables. Se envolvió en `.table-scroll`.

## Bajos
- Select "OT de sistema…" desentonaba en oscuro → clase `.select-app` (corregido).
- Selector listaba OT de sistema sin tareas libres → filtra por tareas libres (corregido, con test).
- Eyebrow largo de "Agregar tareas" → título corto (corregido).
- Texto de la tarjeta "Vínculo con Advertys" ocupaba 5 líneas en móvil → pasó a "?" (corregido).
- 409 de `/desenlazar` sobre un BORRADOR devuelve JSON crudo; consistente con el resto de la app, casi
  inalcanzable desde la UI (pendiente, baja prioridad).
- Encabezado de grupo `.row-grupo--estimado-detalle` no es sticky con scroll horizontal (pendiente).

## Simplificación
| Candidato | Propuesta | Estado |
|---|---|---|
| Párrafo de la tarjeta "Vínculo con Advertys" | "?" (info-tip), dejando "Enlazado al Estimado N° X" | Aplicado |
| Eyebrow "Agregar más tareas…" | Título corto | Aplicado |
| Párrafos de `list.html` y `nuevo.html` de Estimados | "?" | Propuesta |
| Botón "Desenlazar de Advertys" | Dejar con texto (acción con confirm; el ícono no es universal) | Se deja |
| "Desdoblar" por fila | Ícono tijera/dividir con title | Propuesta (riesgo medio-bajo) |

## Ideas de diseño (no aplicadas)
- Contador pegajoso "N tareas tildadas" junto a "Crear resumen" / "Agregar tildadas".
- "+ N tareas libres" en cada opción del selector.
- Encabezado de grupo con más jerarquía (barra lateral de color, número en mono).
- Tabla de selección a ancho completo, como la del detalle.
- Tarjeta "Vínculo con Advertys" más abajo o como franja compacta, y botón en estilo secundario/peligro suave.

## Lo que funcionó bien
- Crear, agregar y desdoblar escriben bien; tilde de grupo con estado indeterminado.
- Desenlazar: vuelve a BORRADOR, conserva tareas, limpia la solicitud huérfana; se puede cargar otro número o
  pedir alta nueva; lista y Facturación muestran BORRADOR sin número. No toca Advertys.
