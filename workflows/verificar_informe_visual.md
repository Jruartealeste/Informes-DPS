# Verificación visual de un informe (Screenshot Workflow)

**Objetivo:** confirmar que un informe HTML se ve bien —claro, oscuro e
impreso— antes de darlo por terminado, sin depender de que Javier lo abra
manualmente para detectar un problema de layout.

**Cuándo usar:** después de cualquier cambio a `html_report.py` (shell,
CSS, gráficos compartidos) o al `generate_html_report.py` de un módulo
específico. No hace falta para un simple refresh de datos sobre un
informe que ya se verificó visualmente y no cambió de estructura.

**Un informe vs. varios en la misma pasada:** para un solo informe, seguir
este workflow inline (el overhead de arrancar un subagent nuevo no se
justifica para 3 capturas). Para 2+ informes en la misma pasada
(típicamente un cambio a `html_report.py` compartido que dispara
`refresh-dashboard`), delegar al subagent `informe-visual-qa`
(`.claude/agents/informe-visual-qa.md`, solo lectura) en vez de repetir
estos pasos módulo por módulo en el hilo principal — ver
`workflows/arquitectura_claude_code.md` para el criterio de cuándo usar un
subagent en este proyecto.

**Tool:** `tools/screenshot.py` (Playwright, Chromium headless — el mismo
motor que ya usan los `explore.py` de cada módulo, así que no suma
dependencias nuevas al proyecto).

**Pasos:**

1. Generar/actualizar el informe:
   `python -m modules.<modulo>.generate_html_report`
2. Capturar las 3 variantes de una sola vez:
   `python tools/screenshot.py informes/informe_<modulo>.html <modulo> --mode all`
   Esto guarda `exploracion/screenshots/screenshot-N-<modulo>-light.png`,
   `-dark.png` y `-print.png` (numerados, sin pisar capturas anteriores).
3. Leer los 3 PNG con la tool Read y revisar puntualmente:
   - Spacing/padding de stat tiles y tablas
   - Que ningún texto se corte contra el borde del contenedor (ver el bug
     real que apareció en `hbar_chart_svg`: labels largos —razones
     sociales— necesitan ancho de columna dinámico + truncado con "…", un
     ancho fijo los corta)
   - Contraste de colores en modo oscuro (paleta del skill `dataviz`)
   - En `print`: que la barra de filtro (controles interactivos,
     `.no-print`) esté oculta pero el texto de cobertura ("Datos
     disponibles: X a Y · Mostrando: X a Y") siga visible — el PDF
     impreso siempre tiene que dejar constancia de qué período cubre
4. Si algo se ve mal, corregir en `html_report.py` o en el
   `generate_html_report.py` del módulo, regenerar y repetir los pasos
   2-3 hasta que quede bien.

**Nota técnica:** los informes de este proyecto no tienen toggle de tema
en la UI — el modo oscuro sale puro de `@media (prefers-color-scheme:
dark)`. Por eso `screenshot.py` no clickea nada: emula `color_scheme`
directamente vía Playwright (`page.emulate_media`), y para `print` emula
`media="print"`. Si en algún momento se agrega un toggle de tema manual
en el HTML, este workflow y la tool van a necesitar un ajuste (clickear
el toggle en vez de solo emular el media feature).

**Salida esperada:** 3 capturas en `exploracion/screenshots/` que
confirman visualmente que el informe está listo, o una lista concreta de
ajustes de CSS pendientes para el siguiente paso.
