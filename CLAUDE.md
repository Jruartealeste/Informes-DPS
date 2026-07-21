# Agent Instructions — Pipeline Advertys → Informes dinámicos

Trabajás dentro del **framework WAT** (Workflows, Agents, Tools) aplicado
a este proyecto puntual: pasar exports manuales de Advertys (ERP de
ALESTE ADS S.A.) a informes HTML dinámicos, un módulo por vez. La
separación WAT existe para que la parte probabilística (vos, razonando)
no toque directamente los pasos deterministas (scripts Python) que ya
están escritos, probados y documentados.

## La arquitectura WAT en este proyecto

**Capa 1 — Workflows (`workflows/*.md`):** SOPs en texto plano que
describen un objetivo, qué tools usar y en qué orden, y los errores
conocidos con su causa. Antes de hacer un pedido de rutina (cargar un
export, armar un módulo nuevo, verificar un informe visualmente), leé el
workflow correspondiente:

- `workflows/actualizar_informe.md` — cargar un export nuevo en un módulo
  existente y regenerar su informe.
- `workflows/relevar_modulo_nuevo.md` — la receta completa (ya validada
  3/3 veces) para sumar un módulo de Advertys que todavía no existe.
- `workflows/verificar_informe_visual.md` — el Screenshot Workflow:
  capturar claro/oscuro/print de un informe con Playwright antes de
  darlo por terminado.

**Capa 2 — Vos (el agente):** coordinás. Leés el workflow que aplica,
corrés las tools en el orden correcto, manejás errores (muchos ya están
documentados con su causa real en los propios workflows y en el README),
y preguntás cuando hay ambigüedad de negocio/contable que no te
corresponde resolver sola/o (ver ejemplo real: dos columnas "Importe
s/IVA" con distinto signo en Compras — eso se confirmó con Javier, no se
asumió).

**Capa 3 — Tools (ejecución determinista):**
- Por módulo (`modules/<modulo>/`): `config.py` (mapeo de columnas),
  `ingest.py` (Excel → SQLite), `generate_html_report.py` (SQLite →
  `informe_<modulo>.html`), `explore.py` (Playwright, relevamiento en
  vivo contra Advertys).
- Compartidas (raíz): `db.py` (conexión SQLite), `common.py`
  (`normalizar_fecha`/`normalizar_numero`), `html_report.py` (page shell,
  CSS claro/oscuro/print, charts SVG, motor JS del dashboard dinámico,
  `dashboard_shell()` para el sidebar+iframe), `generate_dashboard.py`
  (genera `informes/dashboard.html`, el entrypoint que agrupa todos los
  `informes/informe_*.html`), `api.py` (API local de solo lectura).
- Genéricas (`tools/`): utilidades que no son de un módulo puntual.
  Hoy: `tools/screenshot.py` (captura con Playwright para verificación
  visual — ver Screenshot Workflow más abajo).
- Credenciales de Advertys en `.env` (nunca en otro lado — ver
  `.env.example`).

**Por qué importa la separación:** si cada paso de este pipeline lo
hicieras "a mano" razonando en cada corrida (parsear el Excel, decidir
la clave única, armar el HTML) en vez de correr un script determinista ya
probado, un 90% de precisión por paso se convierte en ~59% de éxito a los
cinco pasos. Los scripts en `modules/` y `tools/` ya están verificados
contra Advertys real — tu trabajo es orquestarlos, no reimplementarlos.

## Cómo operar

**1. Buscá la tool que ya existe antes de escribir una nueva.** Si el
pedido es sobre un módulo ya armado (ver tabla en el README), usá su
`ingest.py`/`generate_html_report.py`. Si es sobre relevar algo nuevo,
`workflows/relevar_modulo_nuevo.md` te dice cómo partir de un `explore.py`
existente en vez de empezar de cero.

**2. Aprendé de los errores y dejalo escrito.** Cuando algo falla contra
Advertys real (un `KeyError` de columna, un filtro que trae menos filas
de las esperadas, un nodo de menú ambiguo): identificá la causa real
(no un parche genérico), arreglá el script, volvé a correrlo para
confirmar, y documentá el hallazgo en el workflow o en la sección de
notas del módulo en el README — para que el próximo módulo (o la próxima
corrida) no repita la misma exploración a ciegas. Los gotchas de Compras
y Facturas en el README son ejemplos reales de esto.

**3. Los workflows son instrucciones, no se pisan solas.** Podés
actualizar un `workflows/*.md` cuando aprendés algo nuevo que lo vuelve
más preciso. No crees ni sobrescribas un workflow sin avisar, salvo que
Javier te lo pida explícitamente — son la referencia que se va afinando
con el tiempo, no un archivo descartable.

Repetido, esto es el loop de mejora continua del proyecto: cada vuelta
(fallo real → causa arreglada → verificado → documentado) deja el
sistema un poco más robusto que la anterior.

## Screenshot Workflow

- Tool: `python tools/screenshot.py <path-o-url> [label] [--mode
  light|dark|print|all]` (Playwright Python — misma dependencia que ya
  usan los `explore.py`, no suma toolchain nuevo).
- Capturas en `exploracion/screenshots/screenshot-N[-label][-modo].png`
  (numeradas, nunca se pisan). `--mode all` es lo normal después de tocar
  CSS o el layout de un informe.
- Leé el PNG resultante con la tool Read antes de dar el cambio por
  terminado.
- Detalle completo del cuándo/por qué en
  `workflows/verificar_informe_visual.md`.
- **Criterio unificado (2026-07-21):** absolutamente todo screenshot
  temporal de este proyecto — el de `tools/screenshot.py`, el de cada
  `explore.py` de módulo, y el del flujo de cierre de OT
  (`cerrar_ot.py`/`explore_cerrar_ot.py`/`ver_imputaciones.py`) — se
  guarda en la misma carpeta `exploracion/screenshots/`, nunca suelto en
  la raíz de `exploracion/` ni en subcarpetas propias por script. Cada
  script prefija sus archivos con el nombre del módulo (`compras_...`,
  `facturas_...`, `ot_...`, `est_...`) para que no se pisen entre sí al
  compartir carpeta. Un `explore.py` nuevo debe seguir este mismo patrón
  (`SCREENSHOT_DIR = OUT_DIR / "screenshots"`, prefijo de módulo en el
  nombre de archivo) en vez de tirar PNGs sueltos en `exploracion/`.

## Estructura de carpetas

```
modules/<modulo>/       # config.py, ingest.py, generate_html_report.py, explore.py — por módulo
workflows/              # SOPs en markdown (qué hacer y cómo)
tools/                  # utilidades genéricas (hoy: screenshot.py)
db.py, common.py,       # compartido entre módulos
html_report.py, api.py
exploracion/            # capturas y HTML/Excel de relevamientos y verificaciones (gitignored)
advertys.db             # SQLite, una tabla por módulo (gitignored)
informes/               # dashboard.html + informe_*.html — entregable real, se sobrescribe en cada corrida
.env                    # credenciales de Advertys (NUNCA en otro lado, gitignored)
```

**Deliverable real:** los `informe_<modulo>.html` en `informes/` — son
autocontenidos (sin CDN), se abren con doble click y se imprimen a PDF
desde el navegador. `informes/dashboard.html` los agrupa con un `<iframe>`
que apunta a cada uno por nombre de archivo relativo, así que todos tienen
que vivir juntos en esa misma carpeta. Como el proyecto vive en OneDrive,
se sincronizan solos.

**Todo lo de `exploracion/` es descartable/regenerable** — capturas de
relevamiento, HTML crudo de Advertys, exports intermedios. No es un
entregable, es evidencia de proceso.

## Salvaguarda: Advertys es de solo lectura

Este pipeline **nunca** debe escribir, editar ni borrar datos dentro de
Advertys. Los `explore.py` y cualquier automatización con Playwright
contra Advertys real solo pueden hacer: login, navegación entre vistas,
cambio de filtros de visualización, y exportación/descarga (XLSX/Excel).

**Regla dura:** si un script (nuevo o existente) va a hacer click sobre
cualquier elemento cuyo texto, título o `id` sugiera una acción de alta,
edición o borrado — por ejemplo "Nuevo", "Agregar", "Editar", "Modificar",
"Eliminar", "Borrar", "Guardar" fuera de un simple filtro de vista — **hay
que parar y pedir aprobación explícita a Javier antes de ejecutar ese
click**, aunque sea en un script de exploración. No se asume, no se
ejecuta "para probar". Login, navegación y exportación sí están
permitidos sin pedir autorización caso por caso.

Esto aplica tanto a código nuevo que yo escriba como a los `explore.py`
ya existentes: si en algún momento agrego o modifico un flujo contra
Advertys real, reviso primero que ningún click apunte a un botón de
esa naturaleza antes de correrlo.

## Quirks conocidos del entorno

- **Windows / PATH de Python:** `python` y `py` en la terminal de este
  proyecto apuntan al alias de Microsoft Store, no sirven. Invocar con la
  ruta completa:
  `/c/Users/javie/AppData/Local/Programs/Python/Python312/python.exe`
- **Siempre parado en la raíz del proyecto:** los módulos se corren con
  `python -m modules.<modulo>.<script>`, nunca `python archivo.py` directo.
- **Advertys no es consistente con "N°" vs "Nº"** entre módulos — si un
  mapeo nuevo tira `KeyError` en una columna con ese símbolo, revisar el
  byte exacto.
- Varias vistas de Advertys son nodos de TreeView sin URL directa, y
  puede haber nombres de nodo repetidos en el menú — navegar por ID
  exacto del árbol cuando hay ambigüedad (ver `modules/facturas/explore.py`
  como referencia).
