# Botones con texto → íconos (revisión de diseño)

Pedido de Javier (2026-10-14): reemplazar botones con texto por íconos para
que ocupen menos, **sin que se vuelvan confusos**. En cada pasada de QA,
listar qué botones de las pantallas revisadas son candidatos y cuáles no.
Es una **propuesta**: no se cambia nada sin que Javier la apruebe en la
conversación principal.

## Criterio: ¿se puede pasar a ícono?

**Sí, ícono solo**, cuando se cumplen las tres:
1. La acción tiene un ícono universal que nadie duda (✕ cerrar, lápiz
   editar, copiar, ojo ver, chevron/flecha volver, más "+" agregar, filtro,
   buscar, menú).
2. Se repite mucho en la misma pantalla (una por fila de tabla, una por
   card) o está en un lugar donde el contexto ya dice qué hace (ej. "Editar"
   en la fila de un anunciante).
3. No es destructiva ni irreversible.

**Ícono + texto corto** (o ícono solo en mobile y con texto en escritorio,
mismo patrón `lbl-largo`/`lbl-corto` que ya usa el panel de OT internas),
cuando el ícono ayuda pero solo no alcanza: acciones frecuentes con nombre
propio del dominio ("+ Nueva" OT interna, "Nueva OT/tarea", "Filtros").

**Dejar con texto**, siempre:
- La acción principal de un formulario o panel (Guardar, Crear anunciante,
  Generar OT en Advertys, Asignar OT de sistema).
- Lo destructivo o sin vuelta atrás: Anular, Desactivar, Cancelar pedido,
  Eliminar. El texto es parte de la salvaguarda.
- Acciones del dominio sin ícono reconocible (Armar Estimado, Reasignar OT
  de sistema, Cargar número, Enviar mail si hay varias acciones de mail).
- Selectores de modo (`.segmented`): el texto es la opción.

## Requisitos si se pasa a ícono

- `aria-label` **y** `title` (tooltip) con el texto que se saca. Sin eso no
  se propone.
- Mismo ícono para la misma acción en toda la app (revisar si ya existe:
  el copiar de `.cmd-box__copiar` en Solicitudes, el ✕ del drawer, los SVG
  del sidebar). SVG inline de trazo 2, como el resto (sin librerías ni CDN).
- Área de toque ≥ 32 px en escritorio y ≥ 44 px en mobile (≤720 px).
- Contraste y estado hover/focus visibles en tema claro **y** oscuro.

## Cómo revisarlo

En cada pantalla recorrida, `find`/`read_page` con filtro `interactive` para
listar los `button` y los `a.btn` con texto, y medir cuánto ocupan
(`javascript_tool` con `getBoundingClientRect`, sobre todo en mobile 375 px,
donde más se nota). Priorizar lo que más espacio libera: acciones repetidas
por fila y barras de acciones que se parten en dos líneas en mobile.

## Qué devolver (sección del veredicto / informe)

Tabla corta, solo con candidatos reales (no listar cada botón de la app):

| Pantalla | Botón actual | Propuesta | Ícono | Riesgo de confusión |
|---|---|---|---|---|
| Anunciantes | "Editar" (por fila) | ícono solo | lápiz | bajo: está en la fila |

Y aparte, en una línea, los que conviene **dejar con texto** y por qué
(sobre todo si alguien podría querer simplificarlos). Si no hay candidatos
nuevos respecto de `hallazgos-conocidos.md`, decirlo así de corto.
