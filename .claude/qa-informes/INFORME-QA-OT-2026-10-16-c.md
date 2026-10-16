# Informe QA ot/ — 2026-10-16 (c): sección OT internas

## Entorno y alcance
- `ot/tools/qa_server.py` en `:8123` sobre Postgres local `ot-qa-pg`
  (127.0.0.1:15433), reiniciado tras los cambios de Python. Login simulado.
- Recorrido: listado (buscador, filtro rápido Sin/Con, panel Filtros, leyenda
  del semáforo como filtro), panel de OT de sistema (Usar existente →
  hermanas; Generar → pedido), detalle de OT con hermanas y reasignar,
  validaciones por POST directo, "?" (info-tip), escritorio 1280, claro y
  oscuro, sidebar contraído y celular 375 px. Cada escritura verificada en la
  base.
- Nuevo en esta vuelta: marca en el ítem "OT internas" del sidebar cuando hay
  pedidos de alta pendientes (y punto en el ☰ en celular). El cartel que se
  probó arriba de la lista se sacó después a pedido de Javier: alcanza con el
  botón "Solicitudes de alta N" resaltado.
- **No se probó:** modo "Cargar número" por la interfaz (sí por POST), OT de
  otro cliente en el panel, Estimados desde el detalle. Capturas con Playwright
  headless (el panel del navegador dejó de dibujar a mitad de la corrida).

## Altos
_(ninguno)_

## Medios — corregidos en esta pasada
- **Buscar un número de OT de sistema en la vista "Sin OT de sistema" daba
  "Ninguna OT interna coincide"** aunque el placeholder ofrece buscar por OT
  de sistema. Ahora, si la búsqueda solo coincide en la otra vista, aparece
  "Ver N en «Con OT de sistema»" y al tocarlo cambia de vista.
- **Celular: la marca de pedidos pendientes quedaba dentro del menú.** Se
  agregó un punto en el ☰ (se oculta con el menú abierto).
- **Celular: la leyenda del semáforo, ahora filtro, tenía 21 px de alto.**
  Pasa a pastillas de 32 px con borde.

## Bajos
- Al bloquear "Generar" con campos vacíos, el mensaje aparece pero el foco
  no va al primer campo vacío. Abierto.
- `asignar-lote` con una OT inexistente → 303 sin hacer nada (ya conocido,
  **persiste**).
- Badge "SINCRONIZADA" del detalle sigue estático (ya conocido, **persiste**).

## Simplificación
| Elemento | Decisión |
|---|---|
| Nota del modo Generar ("No crea nada en Advertys todavía — …") | **Aplicado:** acortada a una línea ("Arma un pedido: la OT se crea en Advertys después, corriendo el alta con Claude."); el detalle de cliente/Producto sigue en el "?" |
| "Solicitudes de alta N" del header + "Ver solicitudes" del aviso | **Propuesta:** con pendientes hay dos accesos a lo mismo; se podría ocultar el del header mientras se ve el aviso. Se deja por ahora (es el acceso fijo cuando no hay pendientes) |
| "Asignar OT de sistema", "Generar OT en Advertys", "Reasignar OT de sistema" | Quedan con texto (acción principal) |
| Filtros | Ya es ícono solo |

## Lo que funcionó bien
- Sin pedidos pendientes no hay aviso ni marca; con 1 pedido: aviso "1 OT
  espera crearse en Advertys" con "Ver solicitudes", marca "1" en el sidebar
  (también contraído y en /tareas).
- Buscador, Sin/Con, Estado, OT de sistema puntual (pasa a "Con"),
  leyenda-filtro sincronizada con el select del panel, Limpiar.
- Usar existente: 258 asignada a 4159 y 4160 (4132 ya la tenía); el detalle
  muestra "compartida con 2 OT internas más". Reasignar 4160 → 259 cambió solo
  esa fila en la base.
- Validaciones: 422 en lote vacío, número vacío, generar sobre OT con número,
  Producto fuera de catálogo, Centro Costo inválido, título vacío o >60; 404
  en reasignar OT inexistente.
- "?" de la pantalla abren y cierran sin errores de JS. 375 px sin scroll
  horizontal en OT internas, Solicitudes y Tareas. Consola sin errores.
- `pytest`: 148 en verde.
