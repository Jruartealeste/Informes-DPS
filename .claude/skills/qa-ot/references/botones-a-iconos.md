# Simplificación de la interfaz: botones → íconos y textos explicativos → "?"

Pedido de Javier (2026-10-14, ampliado 2026-10-16): que la interfaz ocupe
menos **sin volverse confusa**. Son dos análisis que se hacen **en cada
corrida de `/qa-ot`, sea cual sea el pedido**, sobre las pantallas que se
recorrieron:

1. **Botones con texto → ícono** (criterio abajo).
2. **Textos explicativos → ícono "?"** (sección "Textos explicativos").

**Quién aplica:**
- **Inline en la conversación principal** (lo normal al usar `/qa-ot`): se
  **aplican** los cambios que cumplen el criterio sin dudas (riesgo de
  confusión bajo) y se listan los dudosos como propuesta para Javier.
- **Subagent `ot-qa`** (solo lectura): devuelve todo como propuesta; los
  aplica después la conversación principal.

## Criterio: ¿se puede pasar a ícono?

**Sí, ícono solo**, cuando se cumplen las tres:
1. La acción tiene un ícono universal que nadie duda (✕ cerrar, lápiz
   editar, copiar, ojo ver, chevron/flecha volver, más "+" agregar, filtro,
   buscar, menú).
2. Se repite mucho en la misma pantalla (una por fila de tabla, una por
   card) o está en un lugar donde el contexto ya dice qué hace (ej. "Editar"
   en la fila de un anunciante).
3. No es destructiva ni irreversible.

**La regla por defecto es ícono solo** (Javier, 2026-10-16: "que pasen a
simplemente ícono siempre y cuando sea claro"), en escritorio y en mobile.
Ícono + texto corto queda solo para lo que con el ícono no alcanza:
acciones con nombre propio del dominio ("Nueva OT/tarea", "Agrupar por
OT"). Clases `.btn--icono` / `.btn--solo-icono` / `.solo-escritorio` /
`.solo-mobile` y macro `icono` de `templates/_iconos.html`.

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
  se aplica.
- Mismo ícono para la misma acción en toda la app (revisar
  `templates/_iconos.html` antes de dibujar uno nuevo). SVG inline de
  trazo 2, como el resto (sin librerías ni CDN).
- Área de toque ≥ 32 px en escritorio y ≥ 44 px en mobile (≤720 px).
- Contraste y estado hover/focus visibles en tema claro **y** oscuro.

## Textos explicativos → "?"

Un texto explicativo es una ayuda que dice *cómo funciona* o *por qué*
algo: hints debajo de un campo, párrafos de intro arriba de un formulario o
tabla, notas tipo "Se completa en Fase 2…". Ocupan lugar todo el tiempo y
se leen una vez. Van dentro del componente `info-tip` que ya existe
(`base.html` + `.info-tip` en `app.css`; ejemplo en
`templates/clientes/form.html`), al lado del label o título que explican:

```html
<span class="info-tip">
  <button type="button" class="info-tip__btn" aria-expanded="false" aria-label="Más información">?</button>
  <span class="info-tip__panel" role="note">El texto explicativo.</span>
</span>
```

El panel es `<span>`, nunca `<div>`: dentro de un `<p>` o label el parser
cierra el contenedor y se rompe (ver `hallazgos-conocidos.md`).

**Sí pasan a "?"**: explicaciones permanentes del funcionamiento (qué hace
un campo, de dónde sale un dato, reglas de negocio) e intros de pantalla
que el usuario ya conoce tras la primera vez.

**No pasan, quedan visibles:**
- Mensajes de **estado o error** ("La OT 4120 ya existe en ALUAR", "Falta
  completar…", avisos de mes anterior, 422/409 mostrados al usuario): son
  información del momento, no ayuda.
- **Advertencias antes de algo irreversible** (confirmación de Anular,
  "esto no se puede deshacer"): el texto es parte de la salvaguarda.
- Placeholders y labels: son la etiqueta, no una explicación.
- Textos de 2-4 palabras pegados al control (ej. "opcional"): esconderlos
  no ahorra nada.
- Estados vacíos ("No hay tareas con estos filtros"): son el contenido.

Requisitos: `aria-label` en el "?", un "?" por bloque de texto (no uno por
oración), y que el panel se lea bien a 375 px y en claro/oscuro.

## Cómo revisarlo

En cada pantalla recorrida, `find`/`read_page` con filtro `interactive` para
listar los `button` y los `a.btn` con texto, y medir cuánto ocupan
(`javascript_tool` con `getBoundingClientRect`, sobre todo en mobile 375 px,
donde más se nota). Priorizar lo que más espacio libera: acciones repetidas
por fila y barras de acciones que se parten en dos líneas en mobile.

Para los textos explicativos: buscar en las plantillas de esas pantallas
`field-hint`, `hint`, párrafos `muted` y textos sueltos dentro de cards o
drawers; y en la página, textos de más de ~8 palabras que no sean datos.

## Qué devolver (sección del veredicto / informe)

Tabla corta, solo con candidatos reales (no listar cada botón de la app),
con una columna de qué se hizo:

| Pantalla | Elemento actual | Propuesta | Ícono | Riesgo de confusión | Hecho |
|---|---|---|---|---|---|
| Anunciantes | "Editar" (por fila) | ícono solo | lápiz | bajo: está en la fila | aplicado |
| Tareas (drawer) | nota "Se completa en Fase 2…" | a "?" junto al título | ? | bajo | aplicado |

Y aparte, en una línea, lo que conviene **dejar como está** y por qué
(sobre todo si alguien podría querer simplificarlo). Si no hay candidatos
nuevos respecto de `hallazgos-conocidos.md`, decirlo así de corto.
