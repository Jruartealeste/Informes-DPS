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
  CSS claro/oscuro/print, charts SVG, motor JS del dashboard dinámico),
  `api.py` (API local de solo lectura).
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

## Screenshot Workflow

Para mejorar la calidad visual de los informes, este proyecto usa
**Playwright (Python)** en vez de Puppeteer/Node — ya es la dependencia
que usan los `explore.py` de cada módulo, así que no suma un toolchain
nuevo.

- Tool: `python tools/screenshot.py <path-o-url> [label] [--mode
  light|dark|print|all]`
- Capturas van a `exploracion/screenshots/screenshot-N[-label][-modo].png`
  (numeradas, nunca se pisan).
- `--mode all` saca las 3 variantes de una corrida — es lo normal después
  de tocar CSS o el layout de un informe.
- Después de capturar, leé el PNG con la tool Read — podés ver la imagen
  directamente y comparar spacing, tamaños de fuente, colores exactos,
  truncado de texto, alineación.
- Detalle completo del cuándo/por qué en
  `workflows/verificar_informe_visual.md`.

## El loop de mejora continua

1. Identificar qué falló (un error de Advertys real, un layout roto, un
   dato mal mapeado)
2. Arreglar el tool correspondiente
3. Verificar que el arreglo funciona (correrlo de nuevo; si es visual,
   con el Screenshot Workflow)
4. Actualizar el workflow o el README con el hallazgo
5. Seguir, con un sistema un poco más robusto que antes

## Estructura de carpetas

```
modules/<modulo>/       # config.py, ingest.py, generate_html_report.py, explore.py — por módulo
workflows/              # SOPs en markdown (qué hacer y cómo)
tools/                  # utilidades genéricas (hoy: screenshot.py)
db.py, common.py,       # compartido entre módulos
html_report.py, api.py
exploracion/            # capturas y HTML/Excel de relevamientos y verificaciones (gitignored)
advertys.db             # SQLite, una tabla por módulo (gitignored)
informe_*.html          # entregable real — se sobrescribe en cada corrida, no se acumula
.env                    # credenciales de Advertys (NUNCA en otro lado, gitignored)
```

**Deliverable real:** los `informe_<modulo>.html` en la raíz — son
autocontenidos (sin CDN), se abren con doble click y se imprimen a PDF
desde el navegador. Como el proyecto vive en OneDrive, se sincronizan
solos.

**Todo lo de `exploracion/` es descartable/regenerable** — capturas de
relevamiento, HTML crudo de Advertys, exports intermedios. No es un
entregable, es evidencia de proceso.

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
