---
name: captura-visual
description: Use when Javier pide una captura de pantalla puntual para ver o iterar un diseño en desarrollo — una vista de la app ot/, un informe HTML, o cualquier página local — sin que haga falta el checklist completo de regresión CSS. Ej: "sacame una captura de la vista de tareas", "quiero ver cómo queda esto antes de seguir", "screenshotea localhost:8000/tareas".
argument-hint: [path-o-url] [label] [--mode light|dark|print|all]
---

## Qué hace

Usa la misma tool que ya existe para QA de informes —
[informes/tools/screenshot.py](../../../informes/tools/screenshot.py)
(Playwright headless) — pero para el caso más amplio de "ayudame a ver esto
mientras diseño", sin requerir que haya un cambio de CSS ya terminado ni el
checklist completo de `verificar-visual`. El script ya soporta tanto los
HTML autocontenidos de `informes/` (`file://`) como cualquier URL de un
servidor local en desarrollo — por ejemplo una vista de la app `ot/`
corriendo en `http://localhost:8000/...`.

## Cuándo usar esto vs. `verificar-visual`

- **`verificar-visual`**: checklist completo (claro/oscuro/print) después de
  tocar CSS/layout compartido de un informe — el objetivo es confirmar que
  no se rompió nada.
- **Este skill**: captura rápida y puntual para ver cómo se ve algo mientras
  se está diseñando o iterando — no implica un checklist de regresión, sirve
  también para diseño en curso de `ot/` (Jinja2+HTMX).

## Pasos

1. Si el target es una vista de `ot/`, confirmar que el server de desarrollo
   esté corriendo (`uvicorn app.main:app --reload` desde `ot/`) antes de
   capturar — el script no lo levanta por vos.
2. Parado en `informes/` (la tool vive ahí, ver nota abajo):
   `python tools/screenshot.py <path-o-url> [label] --mode light`
   (`--mode all` si además interesa ver claro/oscuro/print).
3. Leer el PNG resultante con la tool Read.

## Notas

- La tool vive en `informes/tools/screenshot.py` aunque el target sea una
  vista de `ot/` — es una utilidad de captura genérica (Playwright headless
  contra cualquier URL), no específica de un módulo de datos. No se duplica
  en `ot/`: correr un proceso Python con Playwright ya instalado desde
  `informes/` contra una URL servida por otro proceso (el server de `ot/`)
  no requiere que `ot/` tenga Playwright como dependencia propia.
- Capturas en `informes/exploracion/screenshots/`, mismo patrón numerado que
  el resto del proyecto (nunca pisan capturas anteriores).
- Si en algún momento esta captura puntual revela un problema de diseño que
  hay que perseguir con más profundidad (varias vistas, comparación
  claro/oscuro sistemática), pasarse a `verificar-visual` en vez de repetir
  capturas sueltas.
