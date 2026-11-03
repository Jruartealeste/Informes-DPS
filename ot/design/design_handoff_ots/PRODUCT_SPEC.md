# OTs — app de tareas del equipo + vínculo a facturación

Reemplaza el Google Sheet compartido donde ~10 personas del equipo (diseño,
producción, redacción, estrategia) cargan tareas por cliente. Hoy ese Sheet
no tiene ningún vínculo real a las Órdenes de Trabajo de Advertys ni a las
facturas emitidas — el estado de facturación es texto libre
("FACTURADO"/"PARA FACTURAR"/etc.) sin número de factura asociado. Esta app
cierra ese gap: cada tarea se vincula a una OT real, y más adelante
(Fase 2) al número de factura que la cubre.

Proyecto hermano de `Informes/` (mismo repo, misma agencia — ALESTE ADS
S.A.), pero de otra categoría de sistema: `Informes/` es scripts +
HTML estático corridos a demanda por un solo operador; esto es una
**aplicación web multiusuario** con servidor persistente, base de datos y
login. Por eso vive en su propia carpeta con su propio `CLAUDE.md`, en vez
de sumarse al pipeline de informes.

## Estado actual

Todavía no hay código — este documento es el punto de partida. El primer
trabajo real es el modelo de datos + CRUD de tareas (ver "Roadmap" abajo).

## Alcance: dos fases

**Fase 1 (la que se construye ahora):** app donde el equipo carga y edita
tareas. Cada tarea se vincula a una OT real de Advertys (nunca texto libre
suelto — se valida contra datos ya sincronizados, no contra Advertys en
vivo). Estados de tarea y de facturación normalizados. Login con Google
OAuth restringido a `@aleste.ar` (la agencia ya tiene Google Workspace
pago).

**Fase 2 (fuera de alcance por ahora, no empezar sin decisión explícita):**
facturación semi-automática — seleccionar tareas/OT terminadas → aprobación
humana → Advertys crea la factura en BORRADOR → revisión humana → recién
ahí se solicita el CAE (paso fiscal sin retorno) → se captura el número de
factura resultante y se vincula a la(s) tarea(s) que la originaron. Esto
implica escribir en Advertys (hoy de solo lectura en todo el proyecto
`Informes/`, salvo la excepción puntual y muy acotada de
`modules/ordenes_trabajo/cerrar_ot.py`, aprobada explícitamente por
Javier). Antes de tocar una sola línea de esto hace falta: (a) relevar en
modo lectura el formulario "Nueva Factura" de Advertys (todavía no se hizo
nunca) y (b) aprobación explícita de Javier antes de cualquier click que
cree o edite algo ahí.

## Stack

- **Backend:** FastAPI.
- **Base de datos:** PostgreSQL, vía SQLAlchemy 2.x + Alembic para
  migraciones.
- **Frontend:** Jinja2 + HTMX, sin build de JS (HTMX vendorizado local, sin
  CDN). El caso de uso es CRUD + filtros + formularios con autocompletado —
  no justifica el costo de mantenimiento de una SPA para un equipo no
  técnico.
- **Auth:** Google OAuth (Authlib), validando el claim `hd` del id_token
  contra `aleste.ar` del lado del servidor (no alcanza con mirar el sufijo
  del email). Sesión en cookie httponly firmada — no se exponen tokens al
  cliente.

## Arquitectura / estructura de carpetas (a crear)

```
app/
├── main.py            # instancia FastAPI, monta routers y SessionMiddleware
├── config.py           # settings vía env: DATABASE_URL, GOOGLE_CLIENT_ID/SECRET, SYNC_TOKEN, SESSION_SECRET
├── db.py                # engine/session de SQLAlchemy
├── models.py             # ORM: ver "Modelo de datos" abajo
├── schemas.py             # Pydantic
├── auth.py                # OAuth Google + validación de dominio + dependencias require_user/require_role
├── routers/
│   ├── tareas.py           # /, /tareas, /tareas/{id}, /tareas/partial
│   ├── clientes.py          # /clientes/{cliente_id}
│   ├── facturacion.py        # /facturacion/listas (cola de "listas para facturar", semilla de Fase 2)
│   ├── ordenes_trabajo.py     # /api/ordenes-trabajo/buscar (autocompletar OT)
│   ├── sync.py                 # /api/sync/ordenes-trabajo, /api/sync/facturas
│   └── auth_routes.py           # /auth/login, /auth/callback, /auth/logout
├── templates/                    # Jinja2
└── static/                        # HTMX vendorizado, CSS propio
migrations/                         # Alembic
scripts/
└── migrar_sheet.py                 # migración one-off del Google Sheet real
tests/
```

## Modelo de datos

**Clave de negocio confirmada con Javier (2026-07-31):** la OT interna NO
es 1 a 1 con la OT de sistema (Advertys). Son trabajos chicos que a
veces conviene agrupar: **varias OT internas pueden compartir una misma
OT de sistema** (para no generar de más en Advertys). Por eso `ot_interna`
es una entidad propia, no un número suelto en `tareas`:

- El flujo principal es agrupar **antes** de generar la OT de sistema
  (varias `ot_interna` sin `numero_ot_advertys` todavía, se juntan y se
  dispara un único alta). Pero tiene que poder corregirse después
  (reasignar a qué OT de sistema apunta una `ot_interna` ya creada) —
  no es un campo que se setea una vez y listo.
- Una OT (interna) puede durar meses: las tareas de adentro se van
  facturando de a partes a medida que se van cerrando, y se pueden sumar
  tareas nuevas más adelante. Por eso `estado_facturacion` sigue viviendo
  en `tareas`, no en `ot_interna` ni en la OT de sistema — compartir OT de
  sistema con otra OT interna es una decisión administrativa/de
  numeración en Advertys, no ata la facturación de las tareas entre sí.
- **Alcance inicial de la escritura en Advertys: solo el alta de la OT**
  (el "encabezado" — cliente/anunciante, marca, producto, resumen,
  responsable, equipo). Crear una tarea NO crea nada en Advertys todavía:
  en Advertys eso equivaldría a crear Estimados de Costo (y
  potencialmente disparar Órdenes de Compra), que implica un
  entrenamiento del equipo que no se va a encarar ahora. Las `tareas` son
  100% internas a esta app en Fase 1.

Enums (normalizan los valores reales del Sheet, typos incluidos):

- `estado_tarea`: PARA_INICIAR, EN_PROCESO, PAUSADO, PENDIENTE_OK (normaliza
  el typo real "PENDIETE OK" además de "PENDIENTE OK"), FINALIZADO,
  APROBADO.
- `estado_facturacion`: SIN_FACTURAR (default), PARA_FACTURAR,
  FALTA_OK_CLIENTE, FACTURADO, NO_CORRESPONDE.
- `estado_ot_interna`: ABIERTA, CERRADA (agregado 2026-07-31 — una OT
  interna puede durar meses con tareas abriéndose y cerrándose adentro).
- `rol_usuario`: MIEMBRO, APROBADOR_FACTURACION (modelado ya, sin uso hasta
  Fase 2), ADMIN.

Tablas:

- `usuarios` — id, email (único), nombre, rol, activo, ultimo_login.
- `clientes` — id, nombre, `anunciante_advertys` (alias hacia
  `ordenes_trabajo_espejo.anunciante`; el nombre de cuenta interno no
  siempre coincide 1:1 con el de Advertys).
- `ot_interna` (agregada 2026-07-31, reemplaza el campo suelto
  `tareas.numero_ot` del diseño original) — id, `numero_interno` (el
  número que hoy es la columna "OT" del Sheet, único), cliente_id,
  fecha_apertura, estado (`estado_ot_interna`), `numero_ot_advertys`
  (nullable, **no único** — varias `ot_interna` pueden compartir el mismo
  valor cuando se agrupan bajo una sola OT de sistema; se puede reasignar
  después de creada, con auditoría en `tareas_historial` o un historial
  propio de `ot_interna`).
- `tipos_tarea` — catálogo (diseño, redaccion, produccion, estrategia,
  campania, gestion, mant_web, pautas_medios, otro) — en el Sheet
  "TIPO DE TAREA" es multivalor separado por coma.
- `tareas` — id, `ot_interna_id` (FK a `ot_interna`; nullable solo durante
  la migración para casos que no resuelven), `ot_ambigua` (texto crudo
  cuando no resuelve a una `ot_interna` real, ej. "4086/4110" — puede
  terminar siendo dos `ot_interna` reales agrupadas, a revisar caso a caso
  en la migración, no asumir que es solo ruido de tipeo), fecha_pedido,
  detalle, pedido_por, link_drive, presupuestado, estado_tarea,
  estado_facturacion, `numero_factura`/`cae` (nullable, placeholders de
  Fase 2), `fila_sheet_original` (trazabilidad de la migración),
  creado_por_id, timestamps.
- `tarea_tipos_tarea` / `tarea_responsables` — N:M ("RESPONSABLES" en el
  Sheet también es multivalor, separado por "/"; `tarea_responsables`
  incluye `nombre_libre` como fallback cuando no matchea a un usuario real).
- `tareas_historial` — auditoría de cambios de campo (10 personas editando
  lo mismo).
- `ordenes_trabajo_espejo` — espejo de solo lectura de la tabla
  `ordenes_trabajo` de `Informes/advertys.db`, poblado únicamente por sync
  (upsert por `numero_ot`). `ot_interna.numero_ot_advertys` referencia acá
  cuando ya se generó el alta real.
- `facturas_espejo` — opcional en Fase 1, deja el terreno listo para
  Fase 2.
- `sync_log` — auditoría de cada sync recibido.

## Relación con `Informes/` y con Advertys

- Esta app nunca habla directo con Advertys. Todo lo que sabe de OT viene
  de `ordenes_trabajo_espejo`, sincronizada desde `Informes/advertys.db`.
- El único cambio que este proyecto le suma al pipeline padre es un script
  chico ahí (`Informes/modules/sync_tareas_app/push.py`, a construir): lee
  `ordenes_trabajo` con `db.get_connection()` y hace `POST` autenticado
  (bearer token separado en `SYNC_TOKEN`, no OAuth de usuario) a
  `/api/sync/ordenes-trabajo` acá. Se corre a mano después de un
  `ingest.py`, igual de manual que el resto del pipeline hoy.
- Las credenciales de Advertys (`.env` de `Informes/`) no se copian ni se
  usan en este proyecto.

## Quirks conocidos del Google Sheet real (relevado 2026-07-23)

- **Typos reales en "ESTADO"**: aparece "PENDIETE OK" (sic) además de
  "PENDIENTE OK" — reconocer ambos en la migración.
- **"OT" no siempre es un número limpio**: valores como "4086/4110" (dos OT
  en una tarea) o vacío. Si no resuelve a una `ot_interna` real, guardar el
  texto crudo en `ot_ambigua` y flaggear para revisión manual — **ojo,
  esto puede no ser solo ruido de tipeo**: confirmado con Javier
  (2026-07-31) que agrupar varias OT chicas bajo una misma OT de sistema
  es una operación real y querida, así que un caso "4086/4110" puede
  representar dos `ot_interna` reales que ya se pensaban juntas — revisar
  con Javier caso a caso en la migración, nunca descartar ni adivinar.
- **"TIPO DE TAREA" y "RESPONSABLES" son multivalor** en una sola celda
  (coma y "/" respectivamente).
- **Columna "OT DPS"**: la nota original (2026-07-23) decía "casi siempre
  vacía, propósito legacy no claro". Revisado de nuevo el 2026-07-31: en
  las filas más recientes de ALUAR (numero interno 4129 en adelante) ya
  aparece completa con una numeración propia (255, 256, 257...) — es
  exactamente el número de OT de sistema que hoy se empezó a cargar a
  mano, no un campo legacy muerto. Al migrar, este valor (cuando está) es
  el `numero_ot_advertys` inicial de esa `ot_interna` — no se descarta.
- **"FACTURACION" es texto libre sin número de factura** — es exactamente
  el gap que esta app viene a cerrar; no asumir que "FACTURADO" implica que
  existe un número recuperable en algún lado del Sheet (no existe).

## Decisiones confirmadas con Javier (2026-07-31)

- **Hosting: costo cero inicialmente.** Se descarta Render/Railway (mínimo
  ~USD 5-20/mes) y Cloud SQL (sin tier gratis real). Se usa **Cloud Run**
  para la app (escala a cero, sin tráfico no hay costo — mismo ecosistema
  que el Google Workspace del login OAuth) + **Neon.tech** para Postgres
  (tier gratis serverless, no se "duerme" por completo como el free de
  Supabase). Revisar esta decisión cuando el uso crezca o los límites del
  free tier empiecen a doler (cold starts de Cloud Run, tope de storage de
  Neon) — no es una decisión para siempre, es la de arranque.
- **Alcance de datos: solo ALUAR primero.** El Sheet real tiene ~10
  pestañas con templates distintos entre sí (confirmado leyendo el Sheet:
  algunas de 8-9 columnas sin "OT DPS" ni LINK DRIVE, ALUAR con 12). Se
  migra y valida el modelo con ALUAR (el template más completo) antes de
  sumar el resto, uno por vez, mapeando cada template dispar al mismo
  esquema. Hay además una pestaña "Control de horas x cliente" que es un
  timesheet por empleado, no tracking de OT — fuera de alcance de esta
  migración.
- **Creación automática de OT en Advertys: SÍ está en alcance de Fase 1**
  (no queda para Fase 2 como se había asumido originalmente), pero
  **acotada solo al alta del encabezado de la OT** — cliente/anunciante,
  marca, producto, resumen, responsable, equipo. NO incluye crear nada
  a nivel tarea dentro de Advertys: eso equivaldría a dar de alta
  Estimados de Costo (y potencialmente disparar Órdenes de Compra), que
  requiere un entrenamiento del equipo que Javier decidió no encarar
  todavía (confirmado 2026-07-31). Las `tareas` de esta app siguen siendo
  100% internas.
  - El flujo principal es agrupar varias `ot_interna` **antes** de
    generar la OT de sistema (a criterio de quien gestiona) y disparar un
    único alta para el grupo. Tiene que existir también una vía de
    corrección posterior (reasignar el `numero_ot_advertys` de una
    `ot_interna` ya creada) para cuando cambian las cosas — no es
    "agrupás una vez y ya".
  - Esto es la primera escritura de "alta" en todo el proyecto
    `Informes/` (hasta ahora solo existía la transición de cierre en
    `cerrar_ot.py`, aprobada puntualmente) — se trata con el mismo nivel
    de cuidado: relevamiento de solo lectura primero, aprobación
    explícita de Javier antes de ejecutar el primer click real de alta.
  - **Trigger recomendado (default, revisar si Javier prefiere otro):**
    una acción explícita del usuario ("Generar OT en Advertys", un botón,
    no un cambio de estado silencioso) — crear una OT en Advertys implica
    numeración/contabilidad y no es trivial de deshacer, así que se prefirió
    no dispararlo automáticamente ante cualquier cambio de estado que
    alguien toque sin querer.
  - Script nuevo en `Informes/`: `modules/ordenes_trabajo/crear_ot.py` (el
    segundo script de escritura del proyecto, junto a `cerrar_ot.py`,
    mismas salvaguardas — ver `CLAUDE.md` raíz). Solo crea el encabezado
    de la OT, nunca Estimados ni OC. No se escribe una sola línea de este
    script hasta que el relevamiento de abajo esté hecho y aprobado.

## Roadmap inmediato

1. **Relevamiento de solo lectura del formulario "Nueva OT" en Advertys**
   (`Informes/modules/ordenes_trabajo/explore_nueva_ot.py`, en curso) — qué
   campos pide, cuáles autogenera el sistema (el número de OT), cuáles hay
   que mandar desde la app. Sin guardar nada.
2. Modelo de datos (`models.py` + primera migración de Alembic) y CRUD
   básico de tareas, sin auth todavía (para poder probar rápido) — carga
   inicial solo con ALUAR.
3. `scripts/migrar_sheet.py` en modo dry-run contra la pestaña ALUAR del
   Sheet real, revisar el CSV de filas flaggeadas con Javier antes de
   `--commit` (casos reales ya vistos: OT compuesta "4086/4110",
   "9119 - 1602", filas sin número de OT).
4. Auth con Google OAuth restringido a `@aleste.ar`.
5. Sync `ordenes_trabajo` ↔ `ordenes_trabajo_espejo` (script en
   `Informes/` + endpoint acá).
6. `crear_ot.py` — solo después de (1) confirmado y aprobado explícitamente
   por Javier.
7. UI: vista unificada filtrable, vista por cliente, alta/edición de tarea
   con autocompletado de OT + botón "Generar OT en Advertys", vista
   `/facturacion/listas`.
8. Deploy en Cloud Run + Neon — con OK explícito de Javier antes de
   desplegar.
