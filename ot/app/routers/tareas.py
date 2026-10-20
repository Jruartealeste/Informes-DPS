import datetime as dt
import re

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app import cache
from app.cliente_ctx import cliente_activo
from app.db import get_db
from app.labels import ESTADO_LABELS, FACTURACION_LABELS, TIPO_TAREA_LABELS
from app.models import (
    TITULO_OT_MAX,
    Cliente,
    EstadoFacturacion,
    EstadoTarea,
    OtInterna,
    Tarea,
    TareaResponsable,
    TareaTipoTarea,
    TipoTarea,
)
from app.routers.responsables import combo_ctx, parse_ids
from app.templating import templates
from app.viewmodels import (
    construir_grupos,
    estado_vencimiento,
    motivo_no_anulable,
    parsear_estado,
    puede_anular,
    tarea_vm,
    unir_links,
    version_tarea,
)

router = APIRouter()


def _cargar_tareas(db: Session, cliente_id: int) -> list[Tarea]:
    stmt = (
        select(Tarea)
        .join(Tarea.ot_interna)
        .where(OtInterna.cliente_id == cliente_id)
        .options(
            joinedload(Tarea.ot_interna).joinedload(OtInterna.cliente),
            selectinload(Tarea.tipos).joinedload(TareaTipoTarea.tipo_tarea),
            selectinload(Tarea.responsables).joinedload(TareaResponsable.responsable),
            selectinload(Tarea.mails),
        )
        .order_by(Tarea.id)
    )
    return list(db.scalars(stmt).unique())


def _filtrar(
    tareas: list[Tarea],
    q: str,
    f_est: str,
    f_fac: str,
    f_resp: str,
    revision: bool,
    vencidas: bool = False,
) -> list[Tarea]:
    ql = q.strip().lower()

    def pasa(t: Tarea) -> bool:
        if ql:
            responsables = " / ".join(r.responsable.nombre for r in t.responsables)
            tipos = ", ".join(tt.tipo_tarea.nombre for tt in t.tipos)
            haystack = " ".join(
                [
                    t.detalle or "",
                    (t.ot_interna.numero_interno if t.ot_interna else t.ot_ambigua or ""),
                    responsables,
                    t.pedido_por or "",
                    tipos,
                ]
            ).lower()
            if ql not in haystack:
                return False
        if f_est and (t.estado_tarea is None or t.estado_tarea.name != f_est):
            return False
        if f_fac and t.estado_facturacion.name != f_fac:
            return False
        if f_resp and f_resp not in [r.responsable.nombre for r in t.responsables]:
            return False
        if revision:
            tiene_tipos = len(t.tipos) > 0
            es_revision = bool(t.ot_ambigua) or t.fecha_pedido is None or not tiene_tipos
            if not es_revision:
                return False
        if vencidas and estado_vencimiento(t) is None:
            return False
        return True

    return [t for t in tareas if pasa(t)]


def _opciones_responsables(tareas: list[Tarea]) -> list[str]:
    nombres = {r.responsable.nombre for t in tareas for r in t.responsables}
    return sorted(nombres)


def _contador_revision(tareas: list[Tarea]) -> int:
    n = 0
    for t in tareas:
        if bool(t.ot_ambigua) or t.fecha_pedido is None or not t.tipos:
            n += 1
    return n


def _contador_vencidas(tareas: list[Tarea]) -> tuple[int, int]:
    """(vencidas, por vencer) para el botón de filtro."""
    estados = [estado_vencimiento(t) for t in tareas]
    return estados.count("vencida"), estados.count("por_vencer")


def _contexto_tabla(db: Session, request: Request) -> dict:
    qp = request.query_params
    q = qp.get("q", "")
    f_est = qp.get("f_est", "")
    f_fac = qp.get("f_fac", "")
    f_resp = qp.get("f_resp", "")
    revision = qp.get("revision") == "1"
    vencidas = qp.get("vencidas") == "1"
    agrupado = qp.get("agrupado", "0") == "1"

    cliente = cliente_activo(request, db)
    todas = _cargar_tareas(db, cliente.id) if cliente else []
    filtradas = _filtrar(todas, q, f_est, f_fac, f_resp, revision, vencidas)
    n_vencidas, n_por_vencer = _contador_vencidas(todas)

    grupos_todos = construir_grupos(todas)
    grupos_filtrados = construir_grupos(filtradas)

    return {
        "cliente_nombre": cliente.nombre if cliente else "",
        "q": q,
        "f_est": f_est,
        "f_fac": f_fac,
        "f_resp": f_resp,
        "revision": revision,
        "agrupado": agrupado,
        "opt_estado": [(e.name, ESTADO_LABELS[e]) for e in EstadoTarea],
        "opt_fac": [(f.name, FACTURACION_LABELS[f]) for f in EstadoFacturacion],
        "opt_resp": _opciones_responsables(todas),
        "n_revision": _contador_revision(todas),
        "vencidas": vencidas,
        "n_vencidas": n_vencidas,
        "n_por_vencer": n_por_vencer,
        "hay_filtros": bool(q or f_est or f_fac or f_resp or revision or vencidas),
        "grupos": grupos_filtrados,
        "filas": [tarea_vm(t) for t in filtradas],
        "resumen_filtro": f"{len(filtradas)} de {len(todas)} tareas · {len(grupos_filtrados)} OT",
        "vacio": len(filtradas) == 0,
        "total_tareas": len(todas),
        "total_ots": len(grupos_todos),
        "agrupado_next": "0" if agrupado else "1",
        "revision_next": "0" if revision else "1",
        "vencidas_next": "0" if vencidas else "1",
    }


def _tabla_y_cerrar_drawer(db: Session, request: Request, drawer_html: str = "") -> HTMLResponse:
    """Re-renderiza la tabla y reemplaza el drawer: vacío lo cierra; con
    `drawer_html` lo deja abierto mostrando ese contenido."""
    ctx = _contexto_tabla(db, request)
    tabla_html = templates.env.get_template("tareas/_tabla_swap.html").render(ctx)
    return HTMLResponse(tabla_html + f'<div id="drawer-root" hx-swap-oob="true">{drawer_html}</div>')


@router.get("/")
def raiz(request: Request, db: Session = Depends(get_db)):
    return tareas_home(request, db)


@router.get("/tareas")
def tareas_home(request: Request, db: Session = Depends(get_db)):
    ctx = _contexto_tabla(db, request)
    ctx["tema"] = request.cookies.get("tema", "dark")
    ctx["densidad"] = request.cookies.get("densidad", "1") != "0"
    ctx["seccion_activa"] = "tareas"
    return templates.TemplateResponse(request, "tareas/list.html", ctx)


@router.get("/tareas/partial")
def tareas_partial(request: Request, db: Session = Depends(get_db)):
    ctx = _contexto_tabla(db, request)
    return templates.TemplateResponse(request, "tareas/_tabla_swap.html", ctx)


def cargar_tarea_con_relaciones(db: Session, tarea_id: int) -> Tarea:
    # joinedload en las 3 colecciones (no selectinload): para UNA tarea el
    # "cartesiano" es de un puñado de filas (pocos tipos/responsables/mails),
    # trivial para Postgres — pero baja de 4 round-trips secuenciales a 1
    # sola, que es lo que realmente pesa con Neon remoto (ver CLAUDE.md,
    # notas de performance). _cargar_tareas (la tabla completa) sigue con
    # selectinload a propósito: ahí selectinload ya hace 1 query por
    # relación para TODAS las tareas del batch, así que no hay round-trips
    # de más que ahorrar y el joinedload sí multiplicaría el tráfico.
    return db.get(
        Tarea,
        tarea_id,
        options=[
            joinedload(Tarea.ot_interna).joinedload(OtInterna.cliente),
            joinedload(Tarea.tipos).joinedload(TareaTipoTarea.tipo_tarea),
            joinedload(Tarea.responsables).joinedload(TareaResponsable.responsable),
            joinedload(Tarea.mails),
        ],
    )


def ot_catalogo_ctx(db: Session, cliente_id: int | None) -> dict:
    """Buscador de OT de la sheet de tarea: solo las OT del cliente (el número
    se repite entre anunciantes), y para el aviso de número repetido, en qué
    otros anunciantes existe cada número. `cliente_id` None = todas (tareas
    legado sin OT)."""
    propias, otros = [], {}
    for numero, titulo, cid, cliente, dps in cache.ot_numeros(db):
        if cliente_id is None or cid == cliente_id:
            propias.append((numero, titulo, dps))
        else:
            otros.setdefault(numero, []).append(cliente)
    return {"todos_ot_numeros": propias, "ot_numeros_otros": otros}


def contexto_detalle(db: Session, tarea_id: int, cliente_id: int | None = None) -> dict:
    """Contexto de tareas/_detalle.html — compartido con app/routers/mail.py
    para poder refrescar el drawer después de mandar un mail sin duplicar
    este armado."""
    t = cargar_tarea_con_relaciones(db, tarea_id)
    det = tarea_vm(t)
    if cliente_id is None and t.ot_interna:
        cliente_id = t.ot_interna.cliente_id
    return {
        "det": det,
        "estados": [(e.name, ESTADO_LABELS[e]) for e in EstadoTarea],
        "facturaciones": [(f.name, FACTURACION_LABELS[f]) for f in EstadoFacturacion],
        **ot_catalogo_ctx(db, cliente_id),
        **combo_ctx(db, set(det["responsable_ids"])),
        **tipos_combo_ctx(set(det["tipos"])),
    }


@router.get("/tareas/{tarea_id}/duplicar")
def duplicar_sheet(tarea_id: int, request: Request, db: Session = Depends(get_db)):
    """Sheet apilada que pregunta si la tarea duplicada usa la misma OT interna
    o una nueva."""
    t = cargar_tarea_con_relaciones(db, tarea_id)
    return templates.TemplateResponse(request, "tareas/_duplicar_sheet.html", {"det": tarea_vm(t)})


@router.get("/tareas/{tarea_id}/duplicar/form")
def duplicar_form(tarea_id: int, request: Request, ot: str = "misma", db: Session = Depends(get_db)):
    """Form de tarea nueva con los datos de la original precargados. No guarda
    nada: la fecha de pedido, el estado y la facturación arrancan de cero."""
    from app.routers.ordenes_trabajo import es_primera_ot, siguiente_numero_interno

    t = cargar_tarea_con_relaciones(db, tarea_id)
    det = tarea_vm(t)
    cliente = t.ot_interna.cliente if t.ot_interna else cliente_activo(request, db)
    ot_numero = siguiente_numero_interno(db, cliente) if ot == "nueva" else det["ot_numero_form"]
    ot_primera = ot == "nueva" and es_primera_ot(db, cliente)
    html = templates.env.get_template("tareas/_detalle.html").render(
        {
            "det": None,
            "pre": {
                "origen": det["detalle"],
                "ot_numero": ot_numero,
                # Número reservado solo "de palabra": se reasigna al guardar si
                # mientras tanto otra tarea se lo llevó (ver crear_tarea).
                "ot_generada": ot_numero if ot == "nueva" else "",
                "ot_primera": ot_primera,
                "detalle": t.detalle,
                "pedido_por": t.pedido_por or "",
                "link_drive": t.link_drive or "",
                "presupuestado": bool(t.presupuestado),
            },
            "estados": [(e.name, ESTADO_LABELS[e]) for e in EstadoTarea],
            "facturaciones": [(f.name, FACTURACION_LABELS[f]) for f in EstadoFacturacion],
            **ot_catalogo_ctx(db, cliente.id),
            **combo_ctx(db, set(det["responsable_ids"])),
            **tipos_combo_ctx(set(det["tipos"])),
        }
    )
    # La sheet de elección se cierra junto con el reemplazo del drawer.
    return HTMLResponse(html + '<div id="sheet-2-root" hx-swap-oob="true"></div>')


@router.get("/tareas/{tarea_id}")
def tarea_detalle(tarea_id: int, request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, "tareas/_detalle.html", contexto_detalle(db, tarea_id, cliente_activo(request, db).id)
    )


def _tarea_o_404(db: Session, tarea_id: int) -> Tarea:
    tarea = db.get(Tarea, tarea_id)
    if tarea is None:
        raise HTTPException(404, "Tarea no encontrada.")
    return tarea


def _resolver_ot_interna(
    db: Session, numero: str, cliente_id: int, titulo: str = ""
) -> tuple[int | None, str | None]:
    """Devuelve (ot_interna_id, ot_ambigua). Crea la OT interna si el número es
    limpio y todavía no existe en ese cliente (numeración interna, no toca
    Advertys). Cada anunciante numera por su cuenta (2026-10-14), así que el
    mismo número puede existir en otro cliente: es otra OT. Una OT nueva
    necesita título (2026-10-14); para una existente se ignora."""
    numero = (numero or "").strip()
    if not numero:
        return None, None
    existente = db.scalar(
        select(OtInterna).where(OtInterna.numero_interno == numero, OtInterna.cliente_id == cliente_id)
    )
    if existente:
        return existente.id, None
    if "/" in numero or " " in numero or "-" in numero:
        return None, numero
    titulo = " ".join(titulo.split())
    if not titulo:
        raise HTTPException(422, f"La OT interna {numero} es nueva: falta el título.")
    if len(titulo) > TITULO_OT_MAX:
        raise HTTPException(422, f"El título de la OT puede tener hasta {TITULO_OT_MAX} caracteres.")
    # Primera OT del anunciante: el número elegido fija dónde arranca su
    # secuencia (siguiente_numero_interno sigue desde acá).
    if numero.isdigit() and not db.scalar(select(OtInterna.id).where(OtInterna.cliente_id == cliente_id).limit(1)):
        db.get(Cliente, cliente_id).numero_ot_inicial = int(numero)
    nueva = OtInterna(
        numero_interno=numero,
        titulo=titulo,
        cliente_id=cliente_id,
        fecha_apertura=dt.date.today(),
    )
    db.add(nueva)
    db.flush()
    cache.invalidar_ot_numeros()
    return nueva.id, None


_FECHA_DMA = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def _parsear_fecha(valor: str, nombre: str = "Fecha de pedido") -> dt.date | None:
    """La sheet manda dd/mm/aaaa (formato argentino, 2026-10-15); también se
    acepta AAAA-MM-DD, que era lo que mandaba el input type="date"."""
    valor = (valor or "").strip()
    if not valor:
        return None
    try:
        m = _FECHA_DMA.fullmatch(valor)
        if m:
            return dt.date(int(m[3]), int(m[2]), int(m[1]))
        return dt.date.fromisoformat(valor)
    except ValueError:
        raise HTTPException(422, f"{nombre} inválida: {valor} (formato dd/mm/aaaa).")


def _validar_campos_obligatorios(
    ot_editable: bool,
    ot_numero: str,
    fecha_pedido: str,
    tipos: list[str],
    responsable_ids: set[int],
    detalle: str,
):
    """Respaldo server-side de los obligatorios de la sheet de tarea (ver
    ot/CLAUDE.md) — la sheet ya bloquea el guardado del lado del cliente,
    esto es solo para no dejar la puerta abierta a quien pegue directo
    contra el endpoint. `ot_editable` es False cuando la tarea ya tiene una
    OT interna asignada (el campo queda de solo lectura en la sheet, así
    que no viaja en el POST/PATCH y no corresponde exigirlo de nuevo)."""
    faltantes = []
    if not detalle.strip():
        faltantes.append("detalle")
    if ot_editable and not ot_numero.strip():
        faltantes.append("OT interna")
    if not fecha_pedido:
        faltantes.append("fecha de pedido")
    if not tipos:
        faltantes.append("tipo de tarea")
    if not responsable_ids:
        faltantes.append("responsables")
    if faltantes:
        raise HTTPException(422, f"Faltan campos obligatorios: {', '.join(faltantes)}.")


def tipos_combo_ctx(seleccionados: set[str]) -> dict:
    """Contexto para tareas/_campo_tipos.html: a diferencia de
    combo_ctx (responsables), el catálogo es fijo (TIPO_TAREA_LABELS) y no
    crece desde la UI, así que no hace falta tocar la DB acá."""
    labels_sel = [label for nombre, label in TIPO_TAREA_LABELS.items() if nombre in seleccionados]
    return {
        "tipos_catalogo": list(TIPO_TAREA_LABELS.items()),
        "tipos_sel": seleccionados,
        "tipos_sel_csv": ",".join(sorted(seleccionados)),
        "tipos_resumen": " / ".join(labels_sel) if labels_sel else "Sin tipo de tarea",
    }


def _guardar_tipos_responsables(db: Session, tarea: Tarea, tipos: list[str], responsable_ids: set[int]):
    # Sincroniza por diferencia (no clear() + re-append): SQLAlchemy hace los
    # INSERT antes que los DELETE del orphan, así que reinsertar un
    # responsable/tipo que ya estaba choca con su UNIQUE/PK y la edición da 500.
    tipo_ids = set()
    for nombre in tipos:
        nombre = nombre.strip()
        if not nombre:
            continue
        tipo = db.scalar(select(TipoTarea).where(TipoTarea.nombre == nombre))
        if not tipo:
            # El catálogo no lo carga ninguna migración (solo seed/tests): si
            # falta un tipo válido se crea acá en vez de descartarlo en silencio.
            if nombre not in TIPO_TAREA_LABELS:
                raise HTTPException(422, f"Tipo de tarea desconocido: {nombre}.")
            tipo = TipoTarea(nombre=nombre)
            db.add(tipo)
            db.flush()
        tipo_ids.add(tipo.id)

    for tt in list(tarea.tipos):
        if tt.tipo_tarea_id not in tipo_ids:
            tarea.tipos.remove(tt)
    ya_tipos = {tt.tipo_tarea_id for tt in tarea.tipos}
    for tipo_id in tipo_ids - ya_tipos:
        tarea.tipos.append(TareaTipoTarea(tipo_tarea_id=tipo_id))

    for r in list(tarea.responsables):
        if r.responsable_id not in responsable_ids:
            tarea.responsables.remove(r)
    ya_resp = {r.responsable_id for r in tarea.responsables}
    for responsable_id in responsable_ids - ya_resp:
        tarea.responsables.append(TareaResponsable(responsable_id=responsable_id))


@router.post("/tareas")
def crear_tarea(
    request: Request,
    db: Session = Depends(get_db),
    ot_numero: str = Form(""),
    ot_generada: str = Form(""),
    ot_titulo: str = Form(""),
    detalle: str = Form(...),
    fecha_pedido: str = Form(""),
    fecha_vencimiento: str = Form(""),
    pedido_por: str = Form(""),
    link_drive: list[str] = Form([]),
    presupuestado: str = Form(""),
    estado_tarea: str = Form(""),
    estado_facturacion: str = Form(EstadoFacturacion.SIN_FACTURAR.name),
    tipos: str = Form(""),
    responsable_ids: str = Form(""),
):
    tipos_lista = [x.strip() for x in tipos.split(",") if x.strip()]
    responsables = parse_ids(responsable_ids)
    _validar_campos_obligatorios(True, ot_numero, fecha_pedido, tipos_lista, responsables, detalle)

    cliente = cliente_activo(request, db)
    # El número vino de "+ Nueva" / "Duplicar → OT nueva" (se calcula al abrir, sin
    # reservar). Si entretanto otra tarea lo ocupó, se asigna el siguiente libre en
    # vez de pegar esta tarea en silencio a la OT ajena.
    if ot_generada and ot_numero.strip() == ot_generada:
        from app.routers.ordenes_trabajo import siguiente_numero_interno

        if db.scalar(
            select(OtInterna.id).where(OtInterna.numero_interno == ot_generada, OtInterna.cliente_id == cliente.id)
        ):
            ot_numero = siguiente_numero_interno(db, cliente)
    ot_interna_id, ot_ambigua = _resolver_ot_interna(db, ot_numero, cliente.id, ot_titulo)
    tarea = Tarea(
        ot_interna_id=ot_interna_id,
        ot_ambigua=ot_ambigua,
        detalle=detalle,
        fecha_pedido=_parsear_fecha(fecha_pedido),
        fecha_vencimiento=_parsear_fecha(fecha_vencimiento, "Fecha de vencimiento"),
        pedido_por=pedido_por or None,
        link_drive=unir_links(link_drive),
        presupuestado={"si": True, "no": False}.get(presupuestado.lower()),
        estado_tarea=parsear_estado(EstadoTarea, estado_tarea, "Estado", vacio_es_none=True),
        estado_facturacion=parsear_estado(EstadoFacturacion, estado_facturacion, "Facturación"),
    )
    db.add(tarea)
    db.flush()
    _guardar_tipos_responsables(db, tarea, tipos_lista, responsables)
    db.commit()

    # Al crear, el drawer queda abierto en modo edición de la tarea nueva (con
    # Enviar mail / Anular habilitados) en vez de cerrarse.
    drawer_html = templates.env.get_template("tareas/_detalle.html").render(contexto_detalle(db, tarea.id))
    return _tabla_y_cerrar_drawer(db, request, drawer_html)


def _asignar_estado_tarea(tarea: Tarea, nuevo: EstadoTarea | None) -> None:
    """Pasar a ANULADA tiene las mismas reglas que /anular (facturada, para
    facturar o dentro de un Estimado no se anula), sea cual sea la ruta."""
    if nuevo == EstadoTarea.ANULADA and tarea.estado_tarea != EstadoTarea.ANULADA and not puede_anular(tarea):
        raise HTTPException(409, motivo_no_anulable(tarea))
    tarea.estado_tarea = nuevo


@router.patch("/tareas/{tarea_id}")
def editar_tarea(
    tarea_id: int,
    request: Request,
    db: Session = Depends(get_db),
    ot_numero: str = Form(""),
    ot_titulo: str = Form(""),
    detalle: str = Form(...),
    fecha_pedido: str = Form(""),
    fecha_vencimiento: str = Form(""),
    pedido_por: str = Form(""),
    link_drive: list[str] = Form([]),
    presupuestado: str = Form(""),
    estado_tarea: str = Form(""),
    estado_facturacion: str = Form(EstadoFacturacion.SIN_FACTURAR.name),
    tipos: str = Form(""),
    responsable_ids: str = Form(""),
    version: str = Form(""),
):
    tarea = _tarea_o_404(db, tarea_id)
    if version and version != version_tarea(tarea):
        raise HTTPException(
            409, "Otra persona modificó esta tarea mientras la tenías abierta. Cerrá el panel y volvé a abrirla para ver los cambios."
        )
    tipos_lista = [x.strip() for x in tipos.split(",") if x.strip()]
    responsables = parse_ids(responsable_ids)
    _validar_campos_obligatorios(
        tarea.ot_interna_id is None, ot_numero, fecha_pedido, tipos_lista, responsables, detalle
    )

    if tarea.ot_interna_id is None:
        cliente = cliente_activo(request, db)
        ot_interna_id, ot_ambigua = _resolver_ot_interna(db, ot_numero, cliente.id, ot_titulo)
        tarea.ot_interna_id = ot_interna_id
        tarea.ot_ambigua = ot_ambigua
    tarea.detalle = detalle
    tarea.fecha_pedido = _parsear_fecha(fecha_pedido)
    tarea.fecha_vencimiento = _parsear_fecha(fecha_vencimiento, "Fecha de vencimiento")
    tarea.pedido_por = pedido_por or None
    tarea.link_drive = unir_links(link_drive)
    tarea.presupuestado = {"si": True, "no": False}.get(presupuestado.lower())
    _asignar_estado_tarea(tarea, parsear_estado(EstadoTarea, estado_tarea, "Estado", vacio_es_none=True))
    tarea.estado_facturacion = parsear_estado(EstadoFacturacion, estado_facturacion, "Facturación")
    _guardar_tipos_responsables(db, tarea, tipos_lista, responsables)
    db.commit()

    return _tabla_y_cerrar_drawer(db, request)


@router.post("/tareas/{tarea_id}/anular")
def anular_tarea(tarea_id: int, request: Request, db: Session = Depends(get_db)):
    tarea = _tarea_o_404(db, tarea_id)
    if tarea.estado_tarea != EstadoTarea.ANULADA and not puede_anular(tarea):
        raise HTTPException(409, motivo_no_anulable(tarea))
    if puede_anular(tarea):
        tarea.estado_tarea = EstadoTarea.ANULADA
        db.commit()

    return _tabla_y_cerrar_drawer(db, request)


@router.post("/tareas/{tarea_id}/estado")
def actualizar_estado(
    tarea_id: int,
    request: Request,
    db: Session = Depends(get_db),
    estado_tarea: str = Form(""),
):
    tarea = _tarea_o_404(db, tarea_id)
    _asignar_estado_tarea(tarea, parsear_estado(EstadoTarea, estado_tarea, "Estado", vacio_es_none=True))
    db.commit()

    return _tabla_y_cerrar_drawer(db, request)


@router.post("/tareas/{tarea_id}/facturacion")
def actualizar_facturacion(
    tarea_id: int,
    request: Request,
    db: Session = Depends(get_db),
    estado_facturacion: str = Form(...),
):
    tarea = _tarea_o_404(db, tarea_id)
    tarea.estado_facturacion = parsear_estado(EstadoFacturacion, estado_facturacion, "Facturación")
    db.commit()

    return _tabla_y_cerrar_drawer(db, request)


@router.get("/tareas-nuevo")
def form_nueva_tarea(request: Request, db: Session = Depends(get_db)):
    from app.routers.ordenes_trabajo import es_primera_ot, siguiente_numero_interno

    cliente = cliente_activo(request, db)
    # Anunciante sin OT internas: no hay nada que buscar, así que el panel abre
    # directo con la OT nueva (y el aviso de que se elige el número de partida)
    # en vez de esperar a que toquen "+ Nueva".
    pre = None
    if es_primera_ot(db, cliente):
        n = siguiente_numero_interno(db, cliente)
        pre = {"ot_numero": n, "ot_generada": n, "ot_primera": True}
    return templates.TemplateResponse(
        request,
        "tareas/_detalle.html",
        {
            "det": None,
            "pre": pre,
            "estados": [(e.name, ESTADO_LABELS[e]) for e in EstadoTarea],
            "facturaciones": [(f.name, FACTURACION_LABELS[f]) for f in EstadoFacturacion],
            **ot_catalogo_ctx(db, cliente.id),
            **combo_ctx(db, set()),
            **tipos_combo_ctx(set()),
        },
    )
