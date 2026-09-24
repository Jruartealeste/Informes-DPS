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
- **Captura visual puntual:** no hace falta sumar Playwright como
  dependencia propia de `ot/` para una captura rápida — `informes/tools/
  screenshot.py` (Playwright headless, ya usado para QA de informes)
  también funciona contra una URL local en desarrollo
  (`http://localhost:8000/...`). Ver skill `captura-visual`
  (`.claude/skills/captura-visual/SKILL.md`).
- **QA interactivo (clicks, forms, drawers) — no solo capturas:** skill
  `qa-ot` (`.claude/skills/qa-ot/SKILL.md`) + subagent `ot-qa`
  (`.claude/agents/ot-qa.md`). Corre contra `ot/tools/qa_server.py`, un
  server descartable propio en `:8123` con sqlite + datos ficticios de
  `scripts/seed.py` y login simulado — nunca contra `.env` real ni Neon.
  Detalle completo en `informes/workflows/arquitectura_claude_code.md`
  (sección "QA interactivo de `ot/`").

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
- Las credenciales de Advertys (`.env` de `Informes/`) no se copian ni se
  usan en este proyecto.
- **Sync `ordenes_trabajo` → `ordenes_trabajo_espejo`: construido y
  probado (2026-09-22, roadmap ítem 5).**
  - `Informes/modules/sync_tareas_app/push.py`: lee `ordenes_trabajo` con
    `db.get_connection()` y hace `POST` de la lista completa a
    `/api/sync/ordenes-trabajo` acá, autenticado con bearer token fijo
    (`OT_SYNC_TOKEN` del lado de `Informes/`, tiene que matchear
    `SYNC_TOKEN` acá — ambos viven en `.env`, no en `.env.example`). No es
    un script de escritura contra Advertys (la salvaguarda de solo
    lectura no aplica) — Advertys ni se toca, es Informes hablando con
    otra app propia. Se corre a mano después de un `ingest.py` de
    `ordenes_trabajo`, igual de manual que el resto del pipeline hoy; no
    está sumado a `tools/actualizar_todo.py` todavía.
  - `app/routers/sync.py`: valida el bearer token y hace upsert manual
    (get-then-set, no `ON CONFLICT` de Postgres) por `numero_ot` contra
    `ordenes_trabajo_espejo`, más un registro en `sync_log` por corrida
    (éxito o error). El upsert manual es a propósito dialect-agnostic:
    corre igual contra el sqlite descartable de `tools/qa_server.py`
    (skill `qa-ot`) que contra Neon — nunca hizo falta la sintaxis
    específica de Postgres para el volumen real (~300 OT).
    `/api/sync/*` está exento de `AuthMiddleware` (no hay usuario
    logueado en este flujo) y valida su propio token adentro.
  - **Probado end-to-end**: `push.py` contra el server de QA (297 OT
    reales sincronizadas), upsert confirmado corriendo dos veces sobre el
    mismo `numero_ot` (actualiza, no duplica), y rechazo 401 sin token.
    Falta correr `push.py` una vez contra el `ot/` de dev real (Neon) —
    la migración (`c4e8a1f5d2b7_agrega_ordenes_trabajo_espejo_y_sync_log`)
    ya está aplicada ahí.
  - Nadie lee `ordenes_trabajo_espejo` todavía del lado de la UI (ni
    autocompletado de `numero_ot_advertys`, ni nada) — esta vuelta solo
    deja el espejo poblado y sincronizable a demanda. Consumirlo queda
    para cuando haga falta (ej. roadmap ítem 7, autocompletado de OT).

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

## Decisiones confirmadas con Javier (2026-08-06)

- **`numero_interno` de `ot_interna` es siempre puramente numérico** (sin
  prefijo/sufijo) — confirmado, aunque la columna sigue siendo
  `String(20)` (no `Integer`) porque el resto del código la trata como
  texto (comparaciones, `ot_ambigua`, etc.).
- **Numeración de OT interna nueva: autogenerada, no tipeada a mano.**
  Antes, el campo "OT interna" del form de tarea creaba una OT nueva con
  cualquier número que la persona tipeara ahí (necesario para preservar
  los números históricos del Sheet en la migración). Eso ya no es el
  flujo para altas nuevas: el campo pasa a ser buscador (con datalist
  sobre los `numero_interno` existentes) y al lado hay un botón "+ Nueva"
  que pide el próximo número al backend (`GET
  /api/ordenes-trabajo/nuevo-numero`, `MAX(numero_interno::int) + 1`) y
  lo precarga en el campo — la fila en `ot_interna` recién se crea cuando
  se guarda la tarea (mismo `_resolver_ot_interna` de siempre, sin
  cambios), no al tocar el botón. Implementado en
  `app/routers/ordenes_trabajo.py` + `app/templates/tareas/_campo_ot.html`.
  - Conocido y aceptado: es un MAX+1 sin lock explícito, así que dos
    personas apretando "+ Nueva" casi al mismo tiempo podrían llevarse el
    mismo número sugerido; si ambas guardan, la segunda choca con el
    `unique=True` de `numero_interno` (no manejado todavía — hoy da error
    genérico). Con el volumen de uso actual (un puñado de personas
    cargando tareas, no en ráfaga) no se consideró prioritario resolverlo
    con una sequence de Postgres o un lock; revisar si empieza a doler.
- **La OT interna de una tarea, una vez asignada, es definitiva — y nace
  el concepto de tarea "borrador".** Antes, el campo "OT interna" del
  drawer de tarea quedaba siempre editable como buscador de texto, incluso
  en una tarea ya guardada: reescribirlo reasignaba la tarea a otra OT (o
  creaba una nueva) por error. Ahora:
  - ~~Se puede crear una tarea con solo el nombre (`detalle`, ya era el
    único campo obligatorio), sin OT — sirve de ayuda-memoria.~~ Revertido
    2026-09-17: ver "Decisiones confirmadas con Javier (2026-09-17)" abajo
    — OT interna pasó a ser obligatoria siempre, ya no existe la tarea
    "borrador" sin OT.
  - Mientras la tarea no tenga OT asignada (`ot_interna_id` y `ot_ambigua`
    ambos vacíos) — solo alcanzable hoy en datos legado de la migración del
    Sheet, ya no se puede llegar a este estado creando desde la sheet —,
    los selects de Estado y Facturación se ocultan en el drawer (no tiene
    sentido fijarlos todavía).
  - En cuanto se le asigna una OT real (existente o generando un número
    nuevo con "+ Nueva") y se guarda, el campo pasa a mostrarse como caja
    de solo lectura — ya no se puede volver a tocar. Excepción: si quedó
    con `ot_ambigua` sin resolver (caso legado de la migración del Sheet,
    ej. "4086/4110"), el campo sigue editable para poder terminar de
    resolverlo a mano.
  - Nuevo estado `EstadoTarea.ANULADA` + botón "Anular" en el drawer (con
    confirmación). Se deshabilita si la tarea ya está `FINALIZADO` o su
    facturación ya es `FACTURADO`/`PARA_FACTURAR` — no se puede anular
    algo que ya se cerró o ya se está facturando.
  - No toca `ot_interna.numero_ot_advertys` (la reasignación de OT de
    sistema post-alta) — ese campo sigue siendo editable siempre, es una
    decisión distinta y ya tomada (ver más arriba, "Clave de negocio
    confirmada con Javier (2026-07-31)").
  - Implementado en `app/models.py`, `app/labels.py`, `app/viewmodels.py`
    (`puede_anular`, `ot_bloqueada`, `ot_asignada`),
    `app/routers/tareas.py` (`POST /tareas/{id}/anular`),
    `app/templates/tareas/_campo_ot.html` y `_detalle.html`.

## Decisiones confirmadas con Javier (2026-08-20)

- **Mail a responsables desde el drawer de tarea — implementado (Fase 1,
  remitente único).** Botón "Enviar mail" en el footer del drawer de
  tarea (deshabilitado solo si la tarea no tiene ningún responsable
  asignado — no hace falta que tengan mail cargado, ver "borradores"
  abajo) abre una sheet apilada (`app/templates/tareas/_mail_sheet.html`)
  con destinatarios (checkboxes de todos los responsables de la tarea,
  con o sin mail; los sin mail se pueden tildar igual pero quedan
  marcados "sin mail" y no reciben nada al mandar), asunto y cuerpo
  prellenados desde los datos de la tarea (OT, cliente, detalle, link
  Drive) y completamente editables — ahí se redacta el detalle más largo.
  Al mandar, queda guardado en `tarea_mails` (asunto + cuerpo +
  destinatarios + estado + `gmail_message_id`) y se ve en una sección
  "Mails" colapsable dentro del drawer. Envío por tarea individual (no
  agrupado por OT, según lo decidido).
  - **Borradores (sumado 2026-08-20):** aunque ningún responsable tenga
    mail cargado todavía, se puede redactar y "Guardar borrador"
    (`EstadoMail.BORRADOR`, tercer estado además de ENVIADO/ERROR — el
    enum de Postgres no soporta sacar valores, ver downgrade no-op en la
    migración `d3f8a1b4e6c9`) para no perder el trabajo de redacción. La
    próxima vez que se abre "Enviar mail" para esa tarea, si hay un
    borrador guardado se precarga ESE texto (no se regenera el template
    genérico) — así, apenas alguien carga el mail del responsable, el
    texto ya está listo para mandar tal cual quedó redactado.
  - Mecanismo: **Gmail API con OAuth** (no SMTP), remitente único = vos.
    `app/gmail_client.py` refresca el access token a partir de un refresh
    token fijo (`GMAIL_REFRESH_TOKEN` en el `.env` del server, obtenido
    una vez corriendo `python -m scripts.gmail_authorize` a mano — pide
    `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` de una credencial OAuth tipo
    Desktop app en un proyecto de Google Cloud con la Gmail API
    habilitada y consent screen tipo Interno) y postea directo contra
    `users.messages.send` de la API REST (sin sumar
    `google-api-python-client`, alcanza con `google-auth` + `httpx`).
    Settings opcionales en `app/config.py` — si faltan, el envío falla
    con mensaje claro ("Falta configurar…") en vez de romper el arranque
    de la app; probado así en dev (sin credenciales todavía) y el error
    queda igual guardado en el historial.
  - **Pendiente, no empezar sin decisión explícita:** que cada usuario de
    la app conecte su propia cuenta Gmail y mande en su nombre (en vez de
    todo saliendo como vos). No se puede construir todavía porque depende
    de que exista login (roadmap ítem 4 abajo, sin implementar) — sin
    usuarios de la app no hay a quién atarle un refresh token propio.
    `app/gmail_client.py` ya expone `enviar_mail(destinatarios, asunto,
    cuerpo)` como función de nivel de módulo (no una clase atada a "el
    remitente"), para que agregar el parámetro de remitente después sea
    un cambio chico. Diseño pensado para cuando se retome: botón
    self-service "Conectar Gmail" (flujo OAuth por navegador, scope
    `gmail.send` incremental sobre la cuenta `@aleste.ar` de quien está
    logueado), refresh token por usuario cifrado en la base
    (`MAIL_TOKEN_ENC_KEY`), botón "Enviar mail" deshabilitado si el
    usuario todavía no conectó su cuenta.
  - **Falta para que funcione en la práctica (a hacer vos):** crear el
    proyecto de Google Cloud + credencial OAuth y correr `python -m
    scripts.gmail_authorize` una vez para obtener el refresh token — sin
    eso el botón manda pero guarda el intento como error (probado en
    dev). Ver también migración `c07737c98c23_agrega_tarea_mails.py`
    (aplicada ya en la base de dev de Neon).

## Decisiones confirmadas con Javier (2026-08-21)

- **Auth con Google OAuth — implementado (roadmap ítem 4).** Toda la app
  queda detrás de login salvo `/auth/*` y `/static/*`
  (`app/auth.py::AuthMiddleware`, montada en `main.py` después de
  `SessionMiddleware` de Starlette — sesión en cookie httponly firmada,
  nunca se guarda un token de Google, solo `user_id`/`email`/`nombre`/`rol`).
  Sin sesión: una request normal redirige a `/auth/login?next=...`; una
  request HTMX (`HX-Request: true`) devuelve `401` + header
  `HX-Redirect: /auth/login` en vez de un redirect plano, porque HTMX solo
  swapea el fragmento target con un redirect normal — no navega la
  página.
  - `app/auth.py::procesar_login(db, claims)` valida `claims["hd"] ==
    "aleste.ar"` y `email_verified` (si no, `DominioNoAutorizado`, no
    crea nada) y hace upsert de `Usuario` por email, actualizando
    `ultimo_login` en cada login. Primera vez que alguien de `@aleste.ar`
    entra, se crea solo con eso — no hay paso de invitación separado
    (el dominio restringido de Google Workspace ya es el gate).
  - `rol_usuario` (`MIEMBRO`/`APROBADOR_FACTURACION`/`ADMIN`) está
    modelado y se guarda en la sesión, pero **nada lo usa todavía para
    gatear rutas** — no hay ninguna feature hoy que lo necesite. Un
    cambio de rol o `activo=False` tarda hasta el próximo login en
    reflejarse (se lee de la sesión, no de la DB en cada request) —
    aceptado para un equipo de ~10 personas, revisar si llega a doler.
  - **Credencial OAuth separada de la de Gmail**, a propósito:
    `AUTH_GOOGLE_CLIENT_ID`/`AUTH_GOOGLE_CLIENT_SECRET` (nuevos, en vez
    de reusar `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` de Gmail) porque
    un login por navegador necesita una credencial tipo **"Web
    application"** con redirect URI registrada — la de Gmail es tipo
    "Desktop app" (pensada para el flujo de `gmail_authorize.py`, sin
    redirect URI real) y no sirve para esto.
  - **Falta para que funcione en la práctica (a hacer vos):** crear ese
    segundo OAuth client en el mismo proyecto de Google Cloud que ya
    usás para Gmail, con `http://localhost:8000/auth/callback` como
    redirect URI en dev (sumar la URL de Vercel cuando se despliegue), y
    cargar `SESSION_SECRET` (random, ver `.env.example`),
    `AUTH_GOOGLE_CLIENT_ID` y `AUTH_GOOGLE_CLIENT_SECRET` en `ot/.env` —
    son settings requeridos, la app no arranca sin ellos (a propósito:
    mejor que falle a que arranque con todo abierto por falta de
    config).

## Decisiones confirmadas con Javier (2026-09-17)

- **OT interna, fecha de pedido, tipo de tarea y responsables pasan a ser
  obligatorios siempre en la sheet de tarea** (detalle ya lo era). Revierte
  la decisión de 2026-08-06 que permitía crear una tarea "borrador" con
  solo el detalle, sin OT, como ayuda-memoria — ya no se puede crear ni
  editar una tarea sin completar los 5 campos.
  - Doble capa, no solo cosmética: la sheet bloquea el guardado del lado
    del cliente (`required` nativo en OT interna/fecha/tipo de tarea/
    detalle; el combo de responsables usa un hidden `type="hidden"` que
    queda "barred from constraint validation" por spec HTML, así que ahí
    hace falta un listener de `submit` propio en `app/templates/base.html`
    que lo valida a mano antes de dejar pasar el request de htmx) **y**
    `app/routers/tareas.py::_validar_campos_obligatorios` repite la
    validación server-side (422 si falta algo) para no dejar la puerta
    abierta a quien pegue directo contra `POST/PATCH /tareas` sin pasar
    por la UI.
  - OT interna solo se exige cuando el campo está editable en la sheet —
    si la tarea ya tiene `ot_interna_id` (campo bloqueado, de solo
    lectura) no se vuelve a pedir en el POST/PATCH porque directamente no
    viaja en el form.
  - **Presupuestado pasó de combo Si/No/— a checkbox** (destildado = No,
    tildado = Si) — se pierde el tercer estado "sin dato" (`presupuestado
    IS NULL` en la DB) para carga nueva desde la sheet; datos legado con
    `NULL` siguen existiendo y se muestran como "—" donde ya se leían así
    (ej. tabla de tareas), pero en cuanto se vuelve a guardar esa tarea
    desde el drawer, el checkbox resuelve a un booleano explícito.
  - Implementado en `app/templates/tareas/_detalle.html`,
    `_campo_ot.html`, `_campo_responsables.html`, `app/templates/base.html`
    (validación de submit + sync del checkbox), `app/static/css/app.css` y
    `app/routers/tareas.py`.

## Decisiones confirmadas con Javier (2026-09-21) — Estimados de Costo

- **Alcance confirmado: "una vez creada la OT en Advertys, adentro se hacen
  los Estimados de Costo, y cada Estimado puede incluir una o más
  tareas."** Esto amplía el límite que hasta ahora dejaba `tareas` 100%
  interna a la app (ver "Clave de negocio confirmada con Javier
  (2026-07-31)" más arriba, sección "Alcance inicial de la escritura en
  Advertys") — pero **acotado**: la carga de items (líneas con costo,
  proveedor) dentro de un Estimado **sigue siendo 100% manual en
  Advertys**, igual que ya lo es el encabezado de una Orden de Compra. La
  app no automatiza esa parte ni la releva a fondo (se evaluó relevarla
  creando un Estimado de prueba y descartando el paso, pero Javier lo
  frenó: "esa parte sigue siendo manual", 2026-09-21).
  - Lo que sí aporta la app: un **resumen de Estimado** — una vista propia
    en `ot/` (no un export, no texto para copiar) donde se seleccionan las
    tareas que van a formar parte de un Estimado y se ve una tabla con
    detalle + tipo de tarea de cada una, para tener abierta al lado de
    Advertys mientras se carga el Estimado (encabezado y items) a mano.
    Explícitamente fuera de este resumen por ahora: responsables, link
    Drive, fecha de pedido (se puede sumar después si hace falta, no se
    descartó por diseño sino por alcance inicial).
  - Lo que sí se automatiza: el **alta del encabezado** del Estimado en
    Advertys (no los items) — un botón "Generar Estimado en Advertys" en
    `ot/`, mismo patrón que "Generar OT en Advertys" (acción explícita del
    usuario, nunca disparada por un cambio de estado silencioso).
- **Relevamiento ya hecho (2026-09-18), en modo lectura, contra Advertys
  real** (`Informes/modules/estimados_costos/explore_nuevo_estimado.py`,
  corrido sobre la OT 289 — abrió el formulario y lo cerró sin guardar,
  confirmado que la grilla de Estimados de esa OT no cambió):
  - **El alta es CONTEXTUAL, no suelta**: no hay un botón "Nuevo" en el
    listado global de Estimado Costos (`ViewID=EstimadoCostos_ListView`) —
    ese listado solo tiene Editar/Facturar/Importar/Clonar
    Estimado/Exportar. El único camino real es entrar al detalle de una OT
    (existente o recién creada) y usar el botón **"Nuevo Estimado"** que
    está en la barra "Acciones:" del detalle de la OT (junto a "Lista
    OT"), no dentro de la pestaña "Estimados Costo" en sí.
  - El popup de alta ("Agregar Estimado (ALESTE ADS S.A.)") tiene
    **solo 3 campos**: `Fecha Solicitada` (date, default hoy),
    `Fecha Analisis` (date, default hoy — es el "periodo" AAAAMM que ya
    usa el pipeline de lectura de `estimados_costos`) y `Titulo` (texto
    libre, vacío). Nada de Cliente/Anunciante/Producto/Moneda ahí —
    Advertys los hereda automáticamente de la OT al aceptar. Son 3 inputs
    HTML normales dentro de un iframe propio del popup (ojo si se
    automatiza: hay que ubicar el frame por texto antes de tocar los
    inputs, `document.querySelectorAll` sobre la página principal no los
    encuentra).
  - Pregunta que quedó respondida por este relevamiento: no hace falta
    entrar primero a una pantalla separada de "Estimados" — el flujo
    completo (abrir OT → Nuevo Estimado → completar 3 campos → Aceptar)
    encaja con un único script de escritura, mismo nivel que `crear_ot.py`.
- **Un Estimado puede agrupar tareas de más de una `ot_interna`**, siempre
  que compartan el mismo `numero_ot_advertys` — coherente con la regla ya
  confirmada de que varias OT internas comparten una OT de sistema para no
  duplicar altas (ver 2026-07-31 más arriba). El agrupamiento para armar un
  Estimado se arma **por lote, a criterio manual de quien gestiona**
  (selecciona qué tareas ya cerradas/listas entran en ese Estimado), no un
  Estimado automático por tarea individual — mismo criterio que ya se usa
  para "Generar OT en Advertys".
- **Modelo de datos (implementado 2026-09-21):** tabla `estimados` — id,
  `titulo`, `numero_ot_advertys` (a qué OT de sistema pertenece — no FK a
  una tabla espejo real todavía, ver nota abajo), `numero_estimado`
  (nullable hasta generarse en Advertys), `estado` (`EstadoEstimado`:
  BORRADOR/GENERADO), `creado_por_id`, timestamps. Sin campos de
  costo/monto: eso vive únicamente en Advertys.
  - **FK directo en `tareas.estimado_id`, no tabla puente N:M** (se pensó
    N:M al principio, se descartó al implementar): una tarea se factura
    como un todo (`estado_facturacion` es un único valor por tarea, sin
    facturación parcial modelada) así que no hay caso real de que una
    tarea pertenezca a dos Estimados a la vez — mismo patrón ya usado para
    `tareas.ot_interna_id`.
  - Nota de estado real del código (chequeado 2026-09-21): `ordenes_trabajo_espejo`
    todavía NO existe en `app/models.py` — sigue siendo un campo de texto
    suelto (`OtInterna.numero_ot_advertys: str | None`), no una FK. El sync
    real (roadmap ítem 5) y `crear_ot.py` (ítem 6) siguen sin construirse
    todavía. Esto no bloquea Estimados: las OT ya existen hoy en Advertys
    (creadas a mano por el equipo), así que `crear_estimado.py` puede
    apuntar a un `numero_ot_advertys` ya cargado sin depender de que
    `crear_ot.py` exista primero.
  - Script nuevo en `Informes/`: `modules/estimados_costos/crear_estimado.py`
    (mismo nivel de cuidado que `crear_ot.py`/`cerrar_ot.py` — ver
    salvaguarda en `CLAUDE.md` raíz). Solo el alta de encabezado (3
    campos), nunca items.

## Decisiones confirmadas con Javier (2026-09-22) — Generar OT en Advertys

- **Relevamiento de solo lectura del formulario "Nueva OT" hecho**
  (`Informes/modules/ordenes_trabajo/explore_nueva_ot.py`, corrido contra
  Advertys real: abre el formulario, releva campos y opciones de combo,
  abre el popup de Anunciante y cierra todo sin guardar — confirmado que
  no quedó ninguna OT nueva). Volcado en
  `Informes/exploracion/ot_nuevo_campos.json` y
  `Informes/exploracion/ot_nuevo_opciones_combos.json`. Hallazgos clave:
  - **Autogenerado por Advertys, no se toca:** Nro OT, Estado ("Abierta"),
    F.Abierta (hoy), Abierta por (usuario logueado).
  - **Negocio:** combo con una sola opción real ("PRODUCCION"), ya viene
    preseleccionado.
  - **Resumen:** texto libre.
  - **Anunciante NO es un combo simple** — es un lookup con botón de
    búsqueda que abre un popup en un iframe propio (`Dialog=true` en la
    URL) con un buscador de texto y una grilla de resultados (Id
    Anunciante / Nombre). Hay que buscar y elegir una fila, no alcanza con
    tipear el nombre en el campo. **Gatea por cascada** a Producto y
    Contacto Anunciante (quedan vacíos hasta elegir un Anunciante).
  - **Centro Costo** es un combo fijo de 4 valores: `ADMINISTRACION`,
    `AGENCIA - ESTRUCTURA`, `CREATIVIDAD - PRODUCCION`, `MEDIOS` — no
    dependen del cliente elegido.
  - **Equipo** es otro combo fijo: `ALUAR-LA RESPUESTA`, `Area Beta`,
    `Equipo Grafica`, `Riádigos`.
  - **Tag** es un combo fijo pero de valores que parecen libres/por
    campaña (ej. "Campaña Donación de sangre", "DENARI") — no hay un
    conjunto cerrado de tags "correctos" por cliente.
  - **Contacto Anunciante** es un contacto del lado del **cliente**
    (cascada de Anunciante), no un responsable interno de la agencia — el
    plan original ("cliente/anunciante, marca, producto, resumen,
    responsable, equipo", ver "Decisiones confirmadas con Javier
    (2026-07-31)" arriba) asumía un campo "responsable" que en la práctica
    no existe tal cual en el formulario real; lo más parecido es este
    contacto externo, no un usuario interno.
- **Decisión: qué completa `crear_ot.py` y qué no.**
  - **Centro Costo es obligatorio siempre** — no hay un default seguro
    por cliente, lo elige quien genera la OT en el momento (parámetro
    obligatorio del script, y futuro campo obligatorio en el botón
    "Generar OT en Advertys" de `ot/`).
  - **Equipo es opcional** — si no se pasa, queda en N / D.
  - **Producto, Tag y Contacto Anunciante quedan siempre sin completar**
    — se cargan a mano en Advertys después si hace falta, mismo criterio
    que ya se usa para los items de Estimados.
- **Script `Informes/modules/ordenes_trabajo/crear_ot.py` escrito**
  (2026-09-22, mismo nivel de cuidado que `crear_estimado.py`/
  `cerrar_ot.py`): busca y selecciona el Anunciante por el popup (corta
  con error si la búsqueda no resuelve a exactamente una fila, nunca
  asume), completa Resumen + Centro Costo + Equipo (opcional), clickea
  "Guardar" y lee el número de OT nuevo directo del campo Nro OT (a
  diferencia de `crear_estimado.py`, ese campo está en la misma página
  así que no hace falta comparar grillas antes/después).
  `python -m modules.ordenes_trabajo.crear_ot "<anunciante>" "<resumen>" "<centro_costo>" [--equipo "<equipo>"]`.
  **Todavía no se corrió contra Advertys real** — falta tu confirmación
  explícita (con un Anunciante/Resumen/Centro Costo reales para la
  primera prueba) antes del primer alta real, no hay ambiente de prueba
  separado.
- ~~Pendiente, mismo problema abierto que con Estimados: cómo dispara el
  botón "Generar OT en Advertys" de esta app la ejecución de
  `crear_ot.py`~~ — **resuelto para OT (2026-09-23), ver sección siguiente**
  ("solicitud + corrida manual": la app arma el pedido, nunca corre el
  script). El mismo trade-off para Estimados (botón "Generar Estimado en
  Advertys") sigue sin resolverse — se decidió enfocar primero en OT
  porque `crear_ot.py` ya estaba escrito y probado.

## Decisiones confirmadas con Javier (2026-09-23) — Producto pasa a obligatorio

- **Primera corrida real de `crear_ot.py` (Anunciante ALUAR, Resumen
  "Prueba 123", Centro Costo CREATIVIDAD - PRODUCCION) reveló dos bugs
  contra el relevamiento original de `explore_nueva_ot.py`:**
  1. El popup de búsqueda de Anunciante no siempre espera un click en
     "Aceptar" — a veces el click en la fila ya dispara el postback y
     cierra el iframe solo (el relevamiento original nunca probó el flujo
     completo de selección, solo abría y cerraba el popup con Escape).
     Corregido en `seleccionar_anunciante`: tolera que el frame quede
     detached y valida releyendo el campo del formulario principal.
  2. **Advertys exige completar Producto para poder Guardar** ("Falta
     Producto") — contradice la decisión original (2026-09-22) de dejarlo
     siempre sin completar. Ninguna OT llegó a crearse en ninguno de los
     dos intentos (el segundo cortó antes de Guardar, con el error de
     validación, sin persistir nada).
- **Decisión: Producto pasa a ser obligatorio**, tanto en `crear_ot.py`
  como (a futuro) en el formulario de "Generar OT en Advertys" de esta
  app — el conjunto obligatorio queda **Anunciante, Resumen, Producto y
  Centro Costo** (Equipo sigue opcional).
- **Producto es un catálogo propio de cada Anunciante** (combo en
  cascada, no una lista fija global como Centro Costo) — hay que
  relevarlo cliente por cliente a mano, no se puede asumir ni adivinar.
  Nuevo script de solo lectura
  `Informes/modules/ordenes_trabajo/explore_producto_por_anunciante.py`
  (abre el form "Nuevo", selecciona el Anunciante, lee las opciones del
  combo Producto, cierra sin Guardar) vuelca el resultado en
  `Informes/modules/ordenes_trabajo/productos_por_anunciante.json`, que
  `crear_ot.py` usa para validar el parámetro `producto` cuando el
  Anunciante ya está relevado ahí (si no está, no bloquea — deja que
  Advertys sea la última palabra, para no trabar altas de clientes
  nuevos por falta de relevamiento previo).
  - **Relevado hasta ahora: ALUAR** (9 productos, ver el JSON). Falta
    relevar el resto de los clientes — se suma uno por uno a medida que
    haga falta generar una OT para ellos (mismo criterio incremental que
    "Alcance de datos: solo ALUAR primero" de la migración del Sheet).
- **Probado contra Advertys real (2026-09-23, con tu OK explícito):**
  `python -m modules.ordenes_trabajo.crear_ot "ALUAR" "Prueba 123"
  "INSTITUCIONAL" "CREATIVIDAD - PRODUCCION"` creó la **OT 298**
  correctamente de punta a punta (Anunciante resuelto por el popup,
  Producto y Centro Costo seleccionados, Guardar, número leído del
  campo). Los dos intentos previos (sin Producto) habían fallado antes de
  Guardar sin dejar nada creado. Pendiente: que vos anules/borres la OT
  298 de prueba en Advertys cuando quieras (no lo hace este agente, mismo
  criterio que el Estimado 558 de prueba).

## Decisiones confirmadas con Javier (2026-09-23) — Solicitud de alta en Advertys (UI)

- **Resuelto el "cómo dispara el botón" para OT: "solicitud + corrida
  manual"** (opción elegida sobre "subprocess local como MVP" -- ver
  discusión en la sección "Decisiones confirmadas con Javier (2026-09-22)
  — Generar OT en Advertys" arriba). Motivo: `ot/` va a Cloud Run (roadmap
  ítem 8) y las credenciales de Advertys nunca se copian acá (ver
  "Relación con `Informes/` y con Advertys"), así que un subprocess local
  sería trabajo tirado apenas se despliegue. La app nunca corre
  `crear_ot.py` ni va a correrlo.
- **Modelo nuevo: `SolicitudAltaOt`** (`app/models.py`, migración
  `a5c9e2f4b8d1_agrega_solicitudes_alta_ot`) — `anunciante`, `resumen`,
  `producto`, `centro_costo`, `equipo` (nullable), `estado`
  (`PENDIENTE`/`RESUELTA`), `numero_ot_advertys` (nullable hasta
  resolverse), `creado_por_id`, timestamps. `OtInterna.solicitud_alta_id`
  (FK nullable) agrupa qué OT internas quedan bajo un mismo pedido --
  mismo patrón que `Tarea.estimado_id` → `Estimado`.
- **Flujo implementado** (`app/routers/ordenes_trabajo.py`,
  `app/templates/ordenes_trabajo/list.html` +
  `app/templates/ordenes_trabajo/solicitudes.html`):
  1. En el listado de OT internas, el panel de selección en lote suma un
     tercer modo "Generar OT en Advertys" (junto a "Cargar número" y
     "Asignar a una ya usada") -- pide Resumen, Producto (texto libre,
     catálogo por Anunciante todavía no vive acá) y Centro Costo
     (obligatorio, combo fijo de 4 valores), Equipo opcional (combo fijo
     de 4 valores). El Anunciante NO se tipea: se toma de
     `cliente.anunciante_advertys` de las OT internas tildadas, que tienen
     que ser todas del mismo cliente (`POST /ordenes-trabajo/generar-ot`
     corta con 422 si no).
  2. Eso crea una `SolicitudAltaOt` PENDIENTE y redirige a
     `/ordenes-trabajo/solicitudes` -- un listado de pedidos con los datos
     confirmados, un botón "Copiar" con la línea exacta de
     `crear_ot.py` lista para pegar en la terminal de `informes/`, y un
     campo para cargar el número de OT resultante
     (`POST /ordenes-trabajo/solicitudes/{id}/resolver`) que propaga
     `numero_ot_advertys` a todas las OT internas del pedido de una. Hay
     también "Cancelar pedido" (`.../cancelar`) para pedidos tipeados mal,
     que libera las OT internas para armar otro.
  3. El listado de OT internas suma un link "Solicitudes de alta
     pendientes" con contador (junto al filtro "Sin OT de sistema" ya
     existente) para no perder de vista pedidos sin resolver.
- **Validado con el server descartable de QA** (`tools/qa_server.py
  --reset`, no contra Neon real): armar solicitud con 2 OT internas
  ALUAR, ver el comando generado, resolver con un número de prueba y
  confirmar que se propagó a ambas OT internas (`compartida con 1 OT
  interna más`) -- flujo completo probado por navegador, no solo capturas.
  Suite de tests (`pytest`, 30 casos) sigue en verde.
- **Mismo patrón queda disponible para Estimados** (la decisión pendiente
  de "Generar Estimado en Advertys" que seguía abierta) pero no se tocó
  todavía -- explícitamente fuera de esta vuelta, Javier pidió enfocar en
  OT primero.

## Roadmap inmediato

1. ~~Relevamiento de solo lectura del formulario "Nueva OT" en Advertys~~
   — hecho (2026-09-22, ver "Decisiones confirmadas con Javier
   (2026-09-22) — Generar OT en Advertys" abajo).
2. ~~Modelo de datos (`models.py` + primera migración de Alembic) y CRUD
   básico de tareas~~ — hecho, y bastante más allá de lo mínimo (mail a
   responsables con borradores, anular tarea).
3. `scripts/migrar_sheet.py` en modo dry-run contra la pestaña ALUAR del
   Sheet real, revisar el CSV de filas flaggeadas con Javier antes de
   `--commit` (casos reales ya vistos: OT compuesta "4086/4110",
   "9119 - 1602", filas sin número de OT).
4. ~~Auth con Google OAuth restringido a `@aleste.ar`~~ — implementado
   2026-08-21 (ver "Decisiones confirmadas con Javier (2026-08-21)"
   arriba); falta que vos cargues las credenciales reales en `.env` para
   que funcione en la práctica.
5. ~~Sync `ordenes_trabajo` ↔ `ordenes_trabajo_espejo` (script en
   `Informes/` + endpoint acá)~~ — hecho y probado (2026-09-22, ver
   "Relación con `Informes/` y con Advertys" arriba). Falta correr
   `push.py` una vez contra Neon real (solo probado contra QA hasta
   ahora) y, más adelante, consumir el espejo desde algún lado de la UI.
6. ~~`crear_ot.py`~~ — escrito (2026-09-22) y **probado con éxito contra
   Advertys real** (2026-09-23, OT 298 de prueba, ver "Decisiones
   confirmadas con Javier (2026-09-23) — Producto pasa a obligatorio"
   arriba). Producto resultó ser un campo obligatorio no previsto en el
   relevamiento original — ya está sumado como parámetro, validado contra
   un catálogo por-cliente relevado a mano (`productos_por_anunciante.json`,
   solo ALUAR por ahora). ~~Sigue sin resolverse cómo el botón "Generar OT
   en Advertys" de la UI dispara este script~~ — resuelto (2026-09-23,
   patrón "solicitud + corrida manual", ver "Decisiones confirmadas con
   Javier (2026-09-23) — Solicitud de alta en Advertys (UI)" arriba): el
   botón arma el pedido, vos corrés `crear_ot.py` a mano y pegás el
   número. Mismo trade-off sigue abierto para el botón de Estimados.
7. UI: vista unificada filtrable, vista por cliente, alta/edición de tarea
   con autocompletado de OT + botón "Generar OT en Advertys", vista
   `/facturacion/listas`.
8. Deploy en Cloud Run + Neon — con OK explícito de Javier antes de
   desplegar.
9. **Estimados de Costo** (agregado 2026-09-21, ver decisiones arriba) —
   no depende de (5)/(6), puede avanzar en paralelo apuntando a OT ya
   existentes en Advertys:
   - ~~Modelo de datos: tabla `estimados` + FK `tareas.estimado_id`~~ —
     hecho (`app/models.py` + migración `agrega_estimados`).
   - ~~UI: selección de tareas (de una o varias `ot_interna` que compartan
     `numero_ot_advertys`) → vista de "resumen de Estimado" (detalle + tipo
     de tarea) para tener al lado de Advertys~~ — hecho (`app/routers/
     estimados.py` + `app/templates/estimados/`, botón "Armar Estimado" en
     `ordenes_trabajo/detalle.html` cuando la OT ya tiene OT de sistema,
     ítem de sidebar propio). QA funcional + visual contra el server
     descartable de `ot/tools/qa_server.py` (2026-09-21): alta, agregar,
     quitar tareas, listado — todo probado, sin errores de servidor ni de
     layout. Falta agregar validación de campos obligatorios espejo del
     lado del cliente (hoy solo hay un `alert()` de JS, no bloqueo nativo
     como en la sheet de tarea) si llega a hacer falta más adelante.
   - ~~Script de escritura `Informes/modules/estimados_costos/
     crear_estimado.py`~~ — hecho (2026-09-22): alta de encabezado
     únicamente (Fecha Solicitada, Fecha Analisis, Titulo), mismo nivel de
     cuidado que `crear_ot.py`/`cerrar_ot.py` (solo clickea "Nuevo
     Estimado" y "Aceptar", nunca toca un estimado existente). Recupera el
     número de Estimado que asigna Advertys comparando la grilla antes/
     después del alta (el popup no lo muestra).
     **Probado contra Advertys real (2026-09-22, con tu OK explícito):**
     `python -m modules.estimados_costos.crear_estimado 258 "PRUEBA -
     Claude Code"` sobre la OT 258 (la reabriste vos para la prueba —
     estaba Anulada) creó el **Estimado N° 558** correctamente. El alta en
     sí funcionó a la primera; lo que falló fue la lectura posterior del
     script (la grilla se repinta async tras el postback, un solo
     `wait_for_timeout` fijo no le daba tiempo) — se reemplazó por un
     polling de hasta 10s, sin volver a correr todavía contra Advertys
     para no dejar un tercer estimado de prueba en la OT 258. Pendiente:
     que vos anules/borres el Estimado 558 de prueba en Advertys cuando
     quieras (no lo hace este agente).
   - **Decisión pendiente (2026-09-22): cómo dispara el botón "Generar
     Estimado en Advertys" de esta app la ejecución de ese script.**
     Explícitamente no definida todavía — `ot/` corre local hoy pero está
     pensada para Cloud Run (roadmap ítem 8) y las credenciales de
     Advertys nunca se copian a este proyecto (ver "Relación con
     `Informes/` y con Advertys" arriba), así que un simple `subprocess`
     desde acá no sobrevive el deploy. Opciones evaluadas sin resolver:
     (a) subprocess local como MVP, revisar al desplegar; (b) el botón
     solo prepara/marca el Estimado y `crear_estimado.py` se sigue
     corriendo a mano como hoy con `cerrar_ot.py`, cargando después el
     número resultante en `ot/`. Por ahora el flujo real es manual: correr
     el script desde `Informes/` y cargar el `numero_estimado` a mano en
     el Estimado correspondiente de `ot/`. El botón de la UI queda para
     cuando se resuelva esto.
