---
name: verificar-visual
description: Use after changing html_report.py or a module's generate_html_report.py (CSS, layout, shared charts) to visually confirm the report renders correctly in light, dark, and print modes before calling it done. Ej: "verificá visualmente el informe de Compras", "sacá capturas del dashboard", "chequeá que se vea bien en oscuro".
argument-hint: [informe.html] [modulo/label]
---

## Qué hace

Confirma visualmente (claro/oscuro/print) que un informe HTML quedó bien
después de tocar CSS o layout, sin depender de que Javier lo detecte
manualmente. Fuente de verdad completa:
[workflows/verificar_informe_visual.md](../../../workflows/verificar_informe_visual.md).

## Cuándo NO hace falta

Un simple refresh de datos sobre un informe que ya se verificó
visualmente y no cambió de estructura no necesita repetir este paso.

## Pasos

1. Si el HTML no está regenerado con los últimos cambios:
   `python -m modules.<modulo>.generate_html_report`
2. Capturar las 3 variantes de una sola vez:
   `python tools/screenshot.py $0 $1 --mode all`
   Guarda `exploracion/screenshots/screenshot-N-$1-light.png`, `-dark.png`
   y `-print.png` (numeradas, nunca pisan capturas anteriores).
3. Leer las 3 capturas con la tool Read y revisar puntualmente:
   - Spacing/padding de stat tiles y tablas
   - Que ningún texto se corte contra el borde del contenedor (labels
     largos —razones sociales, por ejemplo— necesitan ancho de columna
     dinámico + truncado con "…"; ver el bug real que apareció en
     `hbar_chart_svg` por ancho fijo)
   - Contraste de colores en modo oscuro (paleta del skill `dataviz`)
   - En `print`: que los controles interactivos (`.no-print`) estén
     ocultos pero el texto de cobertura de período ("Datos disponibles: X
     a Y · Mostrando: X a Y") siga visible
4. Si algo se ve mal, corregir en `html_report.py` o el
   `generate_html_report.py` del módulo correspondiente, regenerar y
   repetir los pasos 2-3 hasta que quede bien.

## Notas

- Los informes no tienen toggle de tema en la UI — el modo oscuro sale
  puro de `@media (prefers-color-scheme: dark)`. Por eso `screenshot.py`
  no clickea nada, emula media features directo vía Playwright. Si en
  algún momento se agrega un toggle manual, este skill y la tool
  necesitan ajuste.
- `exploracion/` es descartable/regenerable, no es un entregable.
- Salida esperada: 3 capturas que confirman que el informe está listo, o
  una lista concreta de ajustes de CSS pendientes.
