# Relevar un módulo nuevo de Advertys

**Objetivo:** armar el pipeline completo (`config.py`, `ingest.py`,
`generate_html_report.py`, `explore.py`) para una sección de Advertys que
todavía no tiene informe.

**Cuándo usar:** Javier pide un informe de una sección de Advertys que no
está en la tabla de "Módulos armados hasta ahora" del README.

**Receta validada (3/3 módulos hasta ahora: Órdenes de Trabajo, Compras,
Facturas):**

1. **Relevar en vivo con Playwright.** Adaptar el `explore.py` de un
   módulo existente como punto de partida: loguearse con `.env`, navegar
   hasta la vista real y probar el export a Excel. Si hay nombres
   repetidos en el menú (pasó con "Facturacion"/"Facturas" — Administración
   tiene su propio nodo aparte del de Consultas), navegar por **ID exacto
   del nodo del árbol**, no por texto — confirmar con `page.screenshot()`
   que el click llegó a la vista correcta antes de seguir.
2. **Revisar el filtro de la vista.** Cada vista de Advertys puede tener
   su propio widget de filtro, con nombres y opciones distintas — no
   asumir que todas usan "Abierta/Todas" (Facturas usa un combo "Filtro"
   con Año Actual/Todos/Mes Actual/Año Anterior/Mes Anterior, y el default
   "Mes Actual" trae casi nada). Ponerlo en la opción más amplia antes de
   exportar.
3. **Inspeccionar el Excel real:** columnas, nulos, duplicados de nombre,
   candidata a clave única. A veces no alcanza una sola columna — Compras
   y Facturas necesitaron clave compuesta. Ojo con "N°" vs "Nº": Advertys
   no es consistente entre módulos, revisar bytes UTF-8 exactos si un
   mapeo nuevo tira `KeyError`.
4. **Confirmar con Javier** cualquier ambigüedad de negocio/contable antes
   de mapear columnas (ejemplo real: Compras tiene dos columnas literales
   "Importe s/IVA", una siempre positiva y otra con signo contable).
5. **Armar el módulo:** `modules/<modulo>/{config.py, ingest.py,
   generate_html_report.py}`, reusando `common.normalizar_fecha` /
   `normalizar_numero` y `db.get_connection()` de la raíz. Tabla nueva en
   `advertys.db`, mismo patrón que los módulos existentes — no crear un
   framework genérico para esto (ver nota abajo).
6. **Generar el HTML y verificar visualmente** antes de dar el módulo por
   terminado — ver `workflows/verificar_informe_visual.md`.
7. **Registrar el módulo en el dashboard:** sumarlo a la lista `MODULOS` de
   `generate_dashboard.py` (raíz) — `(id, label,
   os.path.basename(config.REPORT_HTML_OUTPUT_PATH))`, usando el path desde
   el `config.py` del módulo nuevo en vez de escribir el nombre del archivo
   a mano — y correr `python generate_dashboard.py` para que aparezca en
   el sidebar de `informes/dashboard.html`. El `REPORT_HTML_OUTPUT_PATH`
   del módulo nuevo tiene que apuntar a `informes/informe_<modulo>.html`
   (misma carpeta que el dashboard) para que el iframe lo encuentre.
8. **Documentar** en el README (sumar el módulo a la tabla + una sección
   de notas propias si hubo gotchas) para que el próximo módulo no repita
   la misma exploración a ciegas.

**Por qué no hay un framework genérico multi-módulo:** con pocos módulos
previstos se prefirió duplicar el patrón simple (`config.py`/`ingest.py`/
`generate_html_report.py` por módulo) en vez de construir una abstracción
de "motor de módulos". Reevaluar solo si esto crece a 4-5 módulos — hasta
entonces, duplicar es más simple que mantener una abstracción prematura.
