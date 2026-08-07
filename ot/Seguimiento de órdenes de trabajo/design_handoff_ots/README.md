# Handoff: App de seguimiento de órdenes de trabajo (OTs)

## Overview

Reemplazo de un Google Sheet compartido donde ~10 personas de la agencia (diseño, producción, redacción, cuentas, gestión) cargan y siguen tareas por cliente. Fase 1 migra **sólo la pestaña ALUAR**. La app agrupa **tareas** bajo **OT internas** (el número de OT que usa el equipo), vincula esas OT internas con la **OT de sistema de Advertys** (el ERP de facturación) y expone una **cola de facturación**.

El detalle funcional completo (modelo de datos, fases, integración con Advertys, roles, reglas de migración) está en `PRODUCT_SPEC.md`, en esta misma carpeta. Este README describe **el diseño**; el spec describe **el producto**. Ante una contradicción, gana el spec para lógica de negocio y gana este README para lo visual.

## About the Design Files

Los archivos de `design/` son **referencias de diseño hechas en HTML**: prototipos que muestran el look y el comportamiento buscados. **No son código de producción para copiar tal cual.** La tarea es **recrear estos diseños en el entorno del codebase destino** (React, Vue, Svelte, etc.) con sus patrones y librerías establecidos. Si todavía no hay codebase, elegir el stack adecuado (para esto recomendaría React + TypeScript, con TanStack Table para la grilla y una capa de datos server-side; ver "Notas de implementación") e implementar ahí.

Importante sobre el formato: los `.dc.html` son componentes de un runtime propio de la herramienta de diseño (`support.js`, tags `<sc-for>`, `<sc-if>`, `renderVals()`). **No portar ese runtime.** Leerlos como fuente de verdad de layout, medidas, colores y copy, y reimplementar con el framework destino. Abrir `design/Seguimiento de OTs.dc.html` en un navegador funciona y es la mejor forma de recorrer el prototipo.

## Fidelity

**Alta fidelidad (hifi).** Colores, tipografía, espaciados, densidad de tabla, estados y copy son definitivos y están pensados para replicarse con precisión. Los datos son reales (últimas ~30 filas de la pestaña ALUAR) pero están hardcodeados en el prototipo: el backend real los reemplaza.

Lo que **no** está resuelto y hay que definir en implementación: responsive/mobile (el prototipo asume escritorio ≥1100px), edición inline en la grilla, permisos finos, y toda la integración real con Advertys.

## Design Tokens

Todo el tema se resuelve con CSS custom properties sobre `[data-tema="dark"|"light"]`. Dark es el default. Copiar estas dos paletas tal cual; ningún componente debe hardcodear un hex.

### Dark (default)

| Token | Valor | Uso |
| --- | --- | --- |
| `--bg` | `#14161a` | fondo de la app |
| `--surface` | `#1b1e24` | cards, sidebar, topbars, tablas |
| `--surface2` | `#22262e` | headers de tabla, footers de panel, chips neutros |
| `--raised` | `#1f232a` | fila de encabezado de grupo OT, inputs de sólo lectura |
| `--line` | `#2a2e36` | bordes de card y separadores fuertes |
| `--line-soft` | `#22262e` | separador entre filas de tabla |
| `--line-strong` | `#3a4048` | bordes de controles (inputs, botones secundarios) |
| `--text` | `#e8e6e1` | texto principal |
| `--muted` | `#9aa0a8` | texto secundario, celdas de apoyo |
| `--faint` | `#6b7280` | labels, metadatos, contadores |
| `--ghost` | `#4a5058` | iconos deshabilitados, glifos vacíos |
| `--accent` | `#d99a3f` | acento único (ámbar) |
| `--accent-ink` | `#14161a` | texto sobre acento sólido |
| `--accent-soft` | `rgba(217,154,63,.16)` | fondos tintados de acento |
| `--accent-text` | `#e7b463` | texto/números en acento |
| `--accent-hover` | `#e5aa54` | hover de botón primario |
| `--ok` | `#7fa87a` | barras de progreso, verde |
| `--ok-soft` | `rgba(127,168,122,.2)` | chip FINALIZADO / FACTURADO |
| `--ok-text` | `#9dc298` | texto sobre ok-soft |
| `--warn` | `#c95a3a` | rojo/terracota |
| `--warn-soft` | `rgba(201,90,58,.18)` | chip PENDIENTE OK, avisos |
| `--warn-text` | `#e08f6d` | texto sobre warn-soft |
| `--warn-line` | `rgba(201,90,58,.5)` | borde de avisos |
| `--hover` | `rgba(232,230,225,.045)` | hover de fila |
| `--sel` | `rgba(217,154,63,.1)` | fila seleccionada (checkbox on) |
| `--overlay` | `rgba(0,0,0,.55)` | backdrop del panel de detalle |
| `--shadow` | `0 10px 34px rgba(0,0,0,.45)` | elevación de panel/modal |
| `--chrome` | `#0f1114` | barra superior del prototipo, rail lateral |
| `--chrome-text` | `#e8e6e1` | texto sobre chrome |

### Light

Mismos nombres, distintos valores:

`--bg #f4f4f2` · `--surface #ffffff` · `--surface2 #ececea` · `--raised #fafaf9` · `--line #dcdcd7` · `--line-soft #eeeeea` · `--line-strong #c9c9c3` · `--text #1b1d20` · `--muted #5f636a` · `--faint #8d9299` · `--ghost #bcbfc4` · `--accent #9a6a1c` · `--accent-ink #ffffff` · `--accent-soft #f7ecd8` · `--accent-text #7d5413` · `--accent-hover #7d5413` · `--ok #4f7a4a` · `--ok-soft #e4ece2` · `--ok-text #33512f` · `--warn #a8442a` · `--warn-soft #f7e4dd` · `--warn-text #8a3620` · `--warn-line #ddb3a3` · `--hover rgba(27,29,32,.04)` · `--sel #f9f1e2` · `--overlay rgba(27,29,32,.35)` · `--shadow 0 10px 30px rgba(27,29,32,.16)` · `--chrome #1b1d20` · `--chrome-text #f4f4f2`

Nota: en light el acento baja a `#9a6a1c` para mantener contraste de texto sobre blanco. No usar `#d99a3f` sobre fondo claro.

### Tipografía

- `--font`: `"IBM Plex Sans", system-ui, sans-serif` — toda la UI.
- `--mono`: `"IBM Plex Mono", ui-monospace, monospace` — **obligatorio** en: números de OT, fechas, contadores, KPIs numéricos, labels de columna, chips de estado y facturación, valores de progreso (`1/2`), y labels tipo eyebrow en mayúsculas.
- Google Fonts: `IBM+Plex+Mono:wght@400;500;600` y `IBM+Plex+Sans:wght@400;500;600;700`.
- Escala: body 14px/1.5 · celdas de tabla 13px · labels y metadatos 11–12px · labels de columna y eyebrows 10px con `letter-spacing:.08–.10em` y `text-transform:uppercase` · chips 10–11px · h1 de pantalla 22px/600/`-.015em` · títulos de card 14–15px/600 · KPIs 24px mono/500 · número de OT en detalle 20px mono/500.
- `-webkit-font-smoothing: antialiased` en body.

### Radios, espaciado, sombras

- Radios: cards y paneles `9px` · botones e inputs `7px` · chips, badges y checkboxes `4px` · avatares e iconos cuadrados `6–7px` · barras de progreso `2–4px`. **Nada de pills.** Nada de radios > 10px.
- Espaciado: padding de pantalla `18px 20px` · padding de card `14px 16px` (KPI) a `18px 20px` (paneles) · celda de tabla `6px 14px` en densidad compacta, `11px 14px` en cómoda · gap de columnas de tabla `10px` · gap de filtros `7px` · gap de cards `10–14px`.
- Sombras: sólo `--shadow`, y sólo en el panel de detalle y el card de login. Las cards de contenido usan `1px solid var(--line)`, no sombra.
- Focus: `:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }`. Nunca el anillo azul del browser.
- Links: `a { color: var(--accent-text) }`, `a:hover { color: var(--accent) }`.

## Screens / Views

El prototipo trae una **barra superior de prototipo** (`--chrome`, 40px) con switches de navegación A/B/C, rol, tema y densidad. **Esa barra no va a producción**: es andamiaje para comparar variantes. En producción se elige UNA navegación, el rol viene del backend, y el tema y la densidad son preferencias de usuario persistidas.

### 0. Login

- Layout: card centrada de 404px, `--surface`, borde `--line`, radio 9px, `--shadow`, padding `36px 34px 30px`.
- Contenido: cuadrado de marca 34px (radio 8px, `--accent`, texto `--accent-ink`, mono 13px/600, "OT"); h1 23px/600 "Órdenes de trabajo"; párrafo 13px `--muted` con el dominio `@aleste.ar` en `--text`/600; botón primario full-width "Continuar con Google" (fondo `--accent`, texto `--accent-ink`, 14px/600, radio 7px, padding `11px 18px`, hover `--accent-hover`) con cuadrito "G" de 18px invertido; separador `1px solid var(--line)` y nota mono 11px `--faint`: "Se valida el claim hd del id_token en el servidor."
- Comportamiento: OAuth Google. La validación de dominio se hace **en el servidor** contra el claim `hd`, nunca por el sufijo del mail. Ver `PRODUCT_SPEC.md`.

### 1. Tareas (pantalla principal — el reemplazo del Sheet)

Es la vista más importante. Header, barra de filtros, tabla.

**Header** (`padding:18px 20px 0`): eyebrow mono 10px uppercase `--faint` ("ALUAR · 32 tareas") + h1 22px/600 ("Tareas del equipo"); a la derecha, botón secundario "Ver plana" / "Agrupar por OT" (borde `--line-strong`, radio 7px, `7px 13px`) y botón primario "Nueva tarea".

**Barra de filtros** (`padding:14px 20px 12px`, flex `gap:7px`, wrap):
- Buscador 266px, placeholder "Buscar en detalle, OT, responsable…", fondo `--surface`, borde `--line-strong`, radio 7px, `7px 12px`, focus `border-color: var(--accent)`. Busca sobre detalle + nº OT + responsables + pidió + tipo.
- Tres selects: Estado, Facturación, Responsable (opciones derivadas de los datos; el de responsables se arma partiendo por `/`).
- Toggle "⚠ Necesitan revisión N": inactivo con borde `--line-strong`; activo con fondo `--warn-soft`, borde `--warn-line`, texto `--warn-text`.
- A la derecha: contador mono 11px `--faint` "X de Y tareas · Z OT" y, si hay filtros activos, un link "Limpiar".

**Tabla — vista agrupada (default).** Card `--surface`, borde `--line`, radio 9px, `min-width:1040px`. El scroll horizontal vive en el contenedor de la vista (`overflow:auto`), **no** en la card: la card no debe tener `overflow:hidden` o clipearía las últimas columnas.

Grilla de 10 columnas, `gap:10px`:
`26px | 56px | 120px | minmax(200px,1fr) | 74px | 112px | 40px | 52px | 112px | 124px`
→ (caret) · Pedido · Tipo · Detalle · Pidió · Resp. · Drive · Presup · Estado · Facturación

- Header de columnas: fondo `--surface2`, borde inferior `--line`, mono 10px uppercase `letter-spacing:.08em` `--muted`, `position:sticky; top:0; z-index:2`.
- **Fila de grupo OT** (`--raised`, `padding:8px 14px`, clickeable para colapsar): caret ▸ que rota 90° con `transition:transform .12s`; "OT 4085" en mono 13px/500 `--accent-text`; badge de estado de OT (`ABIERTA` → `--accent-soft`/`--accent-text`; `CERRADA` → `--surface2`/`--faint`), mono 10px `letter-spacing:.07em`, radio 4px; badge de OT de sistema ("OT sistema 260" → `--ok-soft`/`--ok-text`; "sin OT de sistema" → transparente con borde `1px dashed var(--line-strong)` y texto `--faint`); si la OT es ambigua, badge "⚠ Revisar: OT ambigua" en `--warn-soft`/`--warn-text`/borde `--warn-line`. A la derecha: antigüedad ("abierta el 22/09" o "sin fecha de apertura") 11px `--faint`; barra de progreso de facturación de 146px (track 4px `--line`, fill `--ok`) + "1/2" en mono 11px; botón "Ver OT".
- **Fila de tarea**: `padding:6px 14px` compacta / `11px 14px` cómoda; borde superior `--line-soft`; hover `--hover`; click abre el panel de detalle. Glifo `↳` en `--ghost`; fecha en mono 12px `--muted`; tipo y responsables en `--muted` con ellipsis; detalle en `--text` con ellipsis; Drive es una flecha `↗` (`--accent-text` si hay link, `--ghost` si no); Presup "Si"/"No"/"—" (`--text` si Si, `--ghost` si no); Estado y Facturación como chips.

**Chips de Estado** (mono 10px, `letter-spacing:.04em`, radio 4px, `padding:3px 8px`, con ellipsis):

| Estado | Fondo | Texto |
| --- | --- | --- |
| PARA INICIAR | `--surface2` | `--muted` |
| EN PROCESO | `--accent-soft` | `--accent-text` |
| PAUSADO | `--surface2` | `--faint` |
| PENDIENTE OK | `--warn-soft` | `--warn-text` |
| FINALIZADO | `--ok-soft` | `--ok-text` |
| APROBADO | `--ok-soft` | `--ok-text` |

**Chips de Facturación** (igual, más `1px solid`):

| Facturación | Fondo | Texto | Borde |
| --- | --- | --- | --- |
| SIN FACTURAR | transparente | `--faint` | `--line-strong` |
| PARA FACTURAR | `--accent` | `--accent-ink` | `--accent` |
| FALTA OK CLIENTE | `--warn-soft` | `--warn-text` | `--warn-line` |
| FACTURADO | `--ok-soft` | `--ok-text` | `--ok` |
| NO CORRESPONDE | transparente | `--ghost` | transparente |

`PARA FACTURAR` es el único chip con fill sólido de acento: es la acción que hay que ver de lejos.

**Tabla — vista plana.** Mismo tratamiento, `min-width:1160px`, 11 columnas:
`56px | 76px | 72px | 120px | minmax(190px,1fr) | 74px | 112px | 40px | 52px | 112px | 124px`
→ Pedido · OT · OT DPS · Tipo · Detalle · Pidió · Resp. · Drive · Presup · Estado · Facturación
La columna OT muestra el número en mono 12px/500 y, si es ambigua, un `⚠` en `--warn-text` con `title="OT ambigua — revisar"`. OT DPS muestra el número de OT de sistema o `—`.

Estado vacío: `Ninguna tarea coincide con los filtros.` 13px `--muted`.

### 2. Panel de detalle / edición de tarea

Drawer derecho de 436px sobre backdrop `--overlay`. Click en el backdrop cierra; click adentro no propaga. `--surface`, `border-left:1px solid var(--line)`, `--shadow`.

- **Header** (`18px 20px 14px`, borde inferior `--line`): eyebrow mono 10px "Tarea · fila 169 del Sheet" (la trazabilidad al Sheet importa durante la migración) + el detalle como título 17px/600; botón ✕ de 28px.
- **Cuerpo** (`16px 20px 22px`, `flex-direction:column; gap:13px`). Todos los campos de sólo lectura usan la misma caja: fondo `--raised`, borde `--line-strong`, radio 7px, `8px 12px`, 13px.
  - **OT interna**: caja con "OT 4085" en mono/500 `--accent-text` + "ALUAR" 12px `--faint`, y botón "Ver OT" al lado. Si la OT es ambigua, debajo un aviso `--warn-soft`/`--warn-line`: `Valor crudo del Sheet: 4086/4110. Puede ser dos OT internas reales agrupadas — resolver a mano, no descartar.`
  - **Fecha de pedido** (con mes escrito: "17/07 (17 jul)") y **Pedido por**, en fila de dos.
  - **Detalle**: caja de texto, `line-height:1.5`.
  - **Tipo de tarea**: chips `--ok-soft`/`--ok-text` mono 11px + botón `+ tipo` con borde dashed.
  - **Responsables**: chips con avatar cuadrado de 18px (radio 4px, `--ok-soft`/`--ok-text`, mono 9px, iniciales) + `+ responsable`.
  - **Estado** y **Facturación**: dos `<select>` reales, mismo estilo de caja. Bajo Estado, si el valor original del Sheet tenía typo, nota 11px `--faint`: `En el Sheet decía «PENDIETE OK»`.
  - **Link Drive** (mono 12px, `--accent-text` o `--faint` "Sin link") y **Presupuestado** (112px).
  - **Número de factura**: bloque `--surface2` radio 8px con eyebrow y `Se completa en Fase 2, cuando Advertys devuelve el CAE.`
  - **Historial**: eyebrow + lista de eventos con bullet de 5px `--accent`: actor en 600, acción en `--muted`, timestamp en `--faint`. En el prototipo son ejemplos; en producción es el audit log real.
- **Footer** (`12px 20px`, `--surface2`, borde superior `--line`): primario "Guardar", secundario "Cancelar", y a la derecha un link "Duplicar".

### 3. OT interna

- Fila superior de dos cards. **Card principal** (flex 1, min 420px): badge de estado de OT + antigüedad; grid de 2 columnas con "OT interna" (mono 20px/500 `--accent-text`) y "Cliente" (ALUAR + "Anunciante Advertys: ALUAR ALUMINIO ARG."); separador; bloque **OT de sistema (Advertys)**:
  - Con OT: número mono 20px, badge `SINCRONIZADA` (`--ok-soft`), texto "compartida con N OT interna(s) más", botón "Reasignar OT de sistema".
  - Sin OT: bloque `--accent-soft` con borde `--line-strong`, radio 8px: título "Todavía no tiene OT de sistema" en `--accent-text`, explicación, y dos botones — primario **"Generar OT en Advertys"** y secundario "Agrupar con otras OT". Ambos llevan a la pantalla de agrupar.
- **Card de facturación** (288px): eyebrow, progreso "1/2" en mono 26px, nota "tareas facturadas. Se factura de a partes; la OT sigue abierta.", barra 5px, y desglose de chips de facturación con su conteo (sólo los que tienen > 0).
- **Card de tareas de la OT** (`min-width:1010px`): mismas 9 columnas que la vista agrupada sin el caret.

### 4. Agrupar OT internas

Resuelve el caso "varias OT internas comparten una sola OT de sistema".

- Bajada 13px `--muted`, max 660px.
- **Izquierda**: card con header `--surface2` mono uppercase "OT internas sin OT de sistema" + conteo. Filas grid `20px | 82px | minmax(0,1fr) | 74px | auto`: checkbox 18px (radio 4px; activo = fondo `--accent`, check `--accent-ink`), número de OT en mono/500 `--accent-text`, resumen de tareas con ellipsis, "N tareas", y badge "⚠ Ambigua" si aplica. Fila seleccionada: fondo `--sel`.
- **Derecha** (326px): formulario "Alta en Advertys" con nota "Solo el encabezado de la OT. No se crean Estimados de Costo ni Órdenes de Compra."; bloque `--surface2` "Agrupa" con chips "OT 4085" (`--accent-soft`) o el vacío "Ninguna seleccionada todavía"; campos Cliente/anunciante, Marca, Producto, Resumen (autocompletado con los resúmenes de las OT elegidas, truncado a 150 chars), Responsable, Equipo; botón primario full-width "Generar 1 OT en Advertys" (`opacity:.45` y `cursor:not-allowed` sin selección); nota final 11px centrada: "Pide confirmación antes de escribir. La numeración la asigna Advertys."

El label del botón debe reflejar la cantidad real de OTs de sistema a crear (siempre 1 en este flujo).

### 5. Facturación (sólo rol Gestión)

- Cuatro KPI cards (min 168px): eyebrow mono uppercase, número mono 24px/500, nota 12px `--muted`. Son: Para facturar / Falta OK cliente / OT involucradas / Sin OT de sistema.
- Card "Listas para facturar" con header `--surface2`, contador de seleccionadas y botón primario "Preparar factura" (deshabilitado sin selección). Agrupada por OT: subheader `--raised` con nº OT, badge de OT de sistema y "N en cola"; filas grid `20px | 56px | minmax(0,1fr) | 112px | 112px | 124px` con checkbox, fecha, detalle, responsables, chip de estado y chip de facturación. Fila seleccionada `--sel`.
- Nota al pie: card con bullet `--accent` — "Fase 2: al aprobar, Advertys crea la factura en **borrador**. El CAE se pide recién después de la revisión humana, y el número resultante vuelve acá pegado a estas tareas."

Sólo entran a la cola las tareas con facturación `PARA FACTURAR` o `FALTA OK CLIENTE`.

### 6. Cliente (dashboard)

- Cuatro KPI cards: OT internas (+ "N abiertas") / Tareas (+ "N en proceso") / Para facturar / A revisar (+ "datos sucios del Sheet").
- **Tareas por estado**: barras horizontales; label de 126px con el chip del estado, track 7px `--line`, fill con el color base del estado, y el número a la derecha en mono. Las barras se normalizan contra el máximo, no contra el total.
- **OT que piden atención** (310px): botones-fila `--raised` con borde `--line` (hover `border-color: var(--accent)`) con el nº de OT y el motivo ("sin OT de sistema" / "OT ambigua en el Sheet"). Navegan a la OT.

## Navegación — tres variantes

Hay que **elegir una**. El prototipo las trae las tres para decidir.

- **A · Secciones (default recomendado).** Sidebar de 218px `--surface` con borde derecho: marca, grupo "Cliente" (lista de clientes, sólo ALUAR activo, el resto `opacity:.38` y `cursor:not-allowed` con pill "pronto"), grupo "Secciones" con badges de conteo, y al pie el usuario con su rol. Ítem activo: fondo `--accent-soft`, texto `--accent-text`, 600. La más obvia para un equipo no técnico.
- **B · Cliente primero.** Sin sidebar: topbar con marca y usuario, fila de tabs de cliente (radio `7px 7px 0 0`, la activa con fondo `--bg` y borde sin base), y debajo tabs de sección con subrayado `2px solid var(--accent)`. Escala mejor cuando entren las otras pestañas del Sheet.
- **C · Bandeja única.** Rail de iconos de 52px `--chrome` (cuadrados 32px, activo `--accent`/`--accent-ink`) + panel de 256px con "Vistas guardadas" (Todas / En curso / Esperando OK / Para facturar / Necesitan revisión, con conteo) y facetas clickeables de Estado y Facturación (el chip activo gana `border-color: var(--accent)`). En esta variante **la barra de filtros de arriba se oculta**: el filtrado vive en el panel. Es lo más rápido para quien carga todo el día.

## Interactions & Behavior

- **Colapsar grupo OT**: click en la fila de grupo. El caret rota 90° (`transition:transform .12s`). Por defecto todos los grupos vienen abiertos.
- **Abrir detalle**: click en cualquier fila de tarea. `stopPropagation` en los botones internos ("Ver OT") para que no abran el panel.
- **Cerrar detalle**: ✕, backdrop, Guardar o Cancelar. Falta y hay que agregar: cerrar con `Esc`, foco atrapado en el drawer, y `aria-modal`.
- **Filtros**: se aplican en AND. El buscador matchea case-insensitive sobre detalle + OT + responsables + pidió + tipo. El filtro de responsable parte el campo por `/`.
- **"Necesitan revisión"**: marca una tarea cuando la OT es ambigua, cuando no tiene fecha de pedido, o cuando no tiene tipo de tarea. Esa regla es del prototipo — validarla contra las reglas de migración del spec y extenderla si hace falta.
- **Densidad**: compacta (`6px 14px`) / cómoda (`11px 14px`). Persistir por usuario.
- **Tema**: dark/light. Persistir por usuario y respetar `prefers-color-scheme` como valor inicial.
- **Rol**: Miembro no ve la sección Facturación; si estaba ahí, se lo saca a Tareas. En producción esto se resuelve en el servidor además de en la UI.
- **Selección para facturar / agrupar**: checkboxes con estado local; la fila seleccionada se tinta con `--sel`; los botones de acción se deshabilitan visualmente (`opacity:.45`, `cursor:not-allowed`) sin selección.
- **Hover de fila**: `--hover`. Sin transiciones de color en filas (la tabla tiene que sentirse instantánea).
- Sin animaciones más allá de la rotación del caret. Es una herramienta de trabajo, no una landing.

## State Management

Estado de UI (cliente):
`screen` · `q` · `fEst` · `fFac` · `fResp` · `revision` (bool) · `agrupado` (bool) · `densa` (bool) · `tema` · `rol` · `vistaGuardada` · `selTarea` (tarea abierta en el drawer) · `selOt` (OT abierta) · `gruposColapsados` (Set de nº OT) · `seleccionAgrupar` (Set) · `seleccionCola` (Set).

Persistir en localStorage o preferencias de usuario: `tema`, `densa`, `agrupado`, navegación elegida, y última vista guardada. `rol` viene del backend.

Datos (servidor): tareas, OT internas, clientes, catálogos de estado / facturación / tipo de tarea / personas, y el audit log del historial. Los conteos de badges, KPIs y facetas se derivan del set filtrado — no guardarlos aparte. Con ~30 filas alcanza calcular en cliente; el modelo real (10 clientes, años de historia) pide filtrado y paginado server-side.

## Notas de implementación

- **La tabla es el producto.** Recomiendo TanStack Table (headless) + virtualización de filas, con las columnas definidas como datos para poder mostrar/ocultar y persistir el orden. El CSS grid del prototipo se puede mantener tal cual: las anchuras de columna son fijas salvo Detalle, que es `1fr`.
- **Scroll horizontal**: el contenedor scrollea, la card lleva `min-width`. Si se le pone `overflow:hidden` a la card (por el radio) se clipean Estado y Facturación y no hay forma de llegar a ellas. Ya se cometió ese error una vez.
- El header de columnas es `position:sticky; top:0` dentro del scroller vertical.
- Los `<select>` nativos necesitan `option { background: var(--surface); color: var(--text) }` para no romperse en dark.
- Accesibilidad pendiente: las filas clickeables tienen que ser accesibles por teclado (`role="row"` + `tabIndex` o un botón real), los checkboxes tienen que ser `<input type="checkbox">` reales con label, y el drawer necesita foco atrapado + `Esc`.
- Contraste: los chips en dark rondan 4.5:1; los `--faint` sobre `--surface` quedan justos para texto chico. Verificar con la implementación real y subir un paso de la rampa si hace falta.

## Assets

Ninguna imagen. Los iconos del prototipo son glifos de texto (`↳ ↗ ▸ ✓ ✕ ⚠`) — reemplazar por un set real (Lucide encaja con la tipografía) manteniendo tamaño y color. Fuentes: IBM Plex Sans e IBM Plex Mono desde Google Fonts (o self-hosted).

## Files

- `design/Seguimiento de OTs.dc.html` — **el prototipo principal**. Todas las pantallas, las tres navegaciones, dark/light, densidad, roles, y los datos reales de ALUAR. Abrir en el navegador para recorrerlo.
- `design/Opciones de formato.dc.html` — las tres direcciones visuales que se exploraron (Planilla / Consola / Papel). Se eligió **Consola**, que es la que está aplicada en el prototipo principal. Sirve como contexto de por qué el diseño es así.
- `design/support.js` — runtime de la herramienta de diseño, necesario sólo para que los `.dc.html` abran localmente. **No portar.**
- `PRODUCT_SPEC.md` — el spec funcional completo del producto (modelo de datos, fases, Advertys, roles, migración del Sheet).
