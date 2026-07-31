# Arquitectura Claude Code de este proyecto (Skills / Subagents / Agent Teams)

**Objetivo:** mapear las 3 capas WAT ya documentadas en `CLAUDE.md`
(Workflows / Vos / Tools) a los mecanismos reales de Claude Code, para que
al sumar o ajustar automatización nueva se use la pieza correcta — sin
reinventar términos propios ni copiar un patrón que no aplica a este
proyecto. Fuente: documentación oficial de Anthropic
(`code.claude.com/docs/en/skills.md`, `sub-agents.md`, `agents.md`,
`memory.md`, `permissions.md`).

**Cuándo usar este workflow:** cuando el pedido es sobre la configuración
de Claude Code del proyecto mismo (agregar un skill, evaluar un subagent,
revisar cómo está organizado esto) — no para un módulo de datos nuevo de
Advertys (eso es `relevar_modulo_nuevo.md`).

## Skills = la capa 2 "bajo demanda"

Un Skill (`.claude/skills/<nombre>/SKILL.md`) es el mecanismo nativo de
Claude Code para que algo se "llame cuando haga falta" en vez de repasarse
en cada pedido: el campo `description` del frontmatter es lo único que
Claude mantiene siempre disponible en contexto; el cuerpo completo del
`SKILL.md` (y cualquier workflow que referencie) solo se carga cuando la
descripción matchea el pedido de Javier.

Los 4 skills existentes (`actualizar-informe`, `refresh-dashboard`,
`relevar-modulo`, `verificar-visual`) ya siguen el molde correcto:
frontmatter con `name`/`description`/`argument-hint`, cuerpo corto que
remite a un workflow en `workflows/` como fuente de verdad completa, sin
duplicar contenido. **Sumar un skill nuevo con este mismo molde** cuando
aparece un pedido recurrente de Javier con una receta ya estable — no
antes (un skill para un caso aislado es sobre-ingeniería).

## Subagents = aislamiento de contexto, no un patrón por defecto

Un subagent (`.claude/agents/<nombre>.md`) corre en su propia ventana de
contexto, con su propio set de tools permitidos, y devuelve solo un
resumen a la conversación principal. Sirve para absorber ruido (output
voluminoso que no hace falta ver en el hilo principal) o para restringir
qué puede tocar un paso puntual (por ejemplo, solo lectura).

**Regla de decisión antes de crear uno:**

1. ¿El paso genera output voluminoso que no aporta valor en la
   conversación principal (muchas capturas, logs largos, exploración
   repetitiva)? Si no, no hace falta un subagent.
2. ¿El paso puede correr sin `AskUserQuestion` ni confirmaciones en vivo
   con Javier a mitad de camino? Un subagent en background no puede
   preguntar — si el paso necesita ida y vuelta, tiene que quedarse en la
   conversación principal.
3. Cada subagent definido se suma a la lista que Claude Code mantiene
   siempre disponible como opción — no crear subagents "por las dudas",
   solo cuando (1) y (2) se cumplen los dos.

**Ejemplo que sí calza:** verificación visual multi-informe. Un solo
informe se sigue verificando inline (el overhead de arrancar un subagent
nuevo no se justifica para 3 capturas). Pero `refresh-dashboard` puede
tocar CSS/layout compartido y disparar la verificación sobre varios
informes en la misma pasada — ahí sí conviene delegar al subagent
`informe-visual-qa` (`.claude/agents/informe-visual-qa.md`, solo lectura:
`Bash` + `Read`) para no inflar el hilo principal con 3×N capturas. Ese
subagent solo diagnostica; si hay que corregir CSS, el fix se aplica en la
conversación principal (donde Javier puede opinar) y recién ahí se
re-invoca el subagent para re-verificar.

**Ejemplo que NO calza:** `relevar-modulo`. Necesita confirmaciones de
negocio en vivo con Javier (ambigüedades contables, revisar screenshots de
exploración juntos) — forzar ese flujo a un subagent rompería el patrón ya
validado 3/3 veces. Se queda en la conversación principal, como está.

## Agent Teams: descartado para este proyecto

Agent Teams (múltiples sesiones coordinadas con mensajería entre sí,
manejadas por un lead) es una función real de Claude Code, pero
**experimental y deshabilitada por default**, pensada para partir un
proyecto grande en piezas que corren en paralelo con varios
desarrolladores. No aplica acá: pipeline de un solo desarrollador
(Javier), mayormente secuencial, con pasos que dependen de confirmaciones
humanas puntuales (negocio/contable) — exactamente lo que Agent Teams no
está pensado para resolver bien.

**No re-evaluar esto** salvo que cambie algo estructural (por ejemplo, más
de una persona tocando el pipeline al mismo tiempo) — mismo espíritu que
la decisión ya documentada en `workflows/relevar_modulo_nuevo.md` de no
armar un framework genérico multi-módulo hasta que haga falta.

## CLAUDE.md vs. este workflow

Igual que con los otros 3 workflows, `CLAUDE.md` solo tiene un puntero
corto a este archivo (ver sección "La arquitectura WAT en este proyecto").
El contenido completo se lee bajo demanda cuando el pedido es sobre la
configuración de Claude Code del proyecto — no se repite en cada pedido de
rutina sobre un módulo de datos.

## Permisos / `settings.json`

No se tocó proactivamente (no hay fricción reportada hoy). Si en algún
momento las confirmaciones repetidas de tools molestan, está el skill
bundled `fewer-permission-prompts` (escanea transcripts recientes y arma
un allowlist en `.claude/settings.json`) — invocarlo cuando Javier lo pida,
no antes.
