import datetime as dt

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app import cache
from app.db import get_db
from app.labels import ESTADO_LABELS, FACTURACION_LABELS, TIPO_TAREA_LABELS
from app.models import (
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
from app.viewmodels import construir_grupos, puede_anular, tarea_vm

router = APIRouter()


def _cargar_tareas(db: Session) -> list[Tarea]:
    stmt = (
        select(Tarea)
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


def _contexto_tabla(db: Session, request: Request) -> dict:
    qp = request.query_params
    q = qp.get("q", "")
    f_est = qp.get("f_est", "")
    f_fac = qp.get("f_fac", "")
    f_resp = qp.get("f_resp", "")
    revision = qp.get("revision") == "1"
    agrupado = qp.get("agrupado", "0") == "1"

    todas = _cargar_tareas(db)
    filtradas = _filtrar(todas, q, f_est, f_fac, f_resp, revision)

    grupos_todos = construir_grupos(todas)
    grupos_filtrados = construir_grupos(filtradas)

    return {
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
        "hay_filtros": bool(q or f_est or f_fac or f_resp or revision),
        "grupos": grupos_filtrados,
        "filas": [tarea_vm(t) for t in filtradas],
        "resumen_filtro": f"{len(filtradas)} de {len(todas)} tareas · {len(grupos_filtrados)} OT",
        "vacio": len(filtradas) == 0,
        "total_tareas": len(todas),
        "total_ots": len(grupos_todos),
        "agrupado_next": "0" if agrupado else "1",
        "revision_next": "0" if revision else "1",
    }


def _tabla_y_cerrar_drawer(db: Session, request: Request) -> HTMLResponse:
    ctx = _contexto_tabla(db, request)
    tabla_html = templates.env.get_template("tareas/_tabla_swap.html").render(ctx)
    return HTMLResponse(tabla_html + '<div id="drawer-root" hx-swap-oob="true"></div>')


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


def contexto_detalle(db: Session, tarea_id: int) -> dict:
    """Contexto de tareas/_detalle.html — compartido con app/routers/mail.py
    para poder refrescar el drawer después de mandar un mail sin duplicar
    este armado."""
    t = cargar_tarea_con_relaciones(db, tarea_id)
    det = tarea_vm(t)
    return {
        "det": det,
        "estados": [(e.name, ESTADO_LABELS[e]) for e in EstadoTarea],
        "facturaciones": [(f.name, FACTURACION_LABELS[f]) for f in EstadoFacturacion],
        "todos_ot_numeros": cache.ot_numeros(db),
        **combo_ctx(db, set(det["responsable_ids"])),
        **tipos_combo_ctx(set(det["tipos"])),
    }


@router.get("/tareas/{tarea_id}")
def tarea_detalle(tarea_id: int, request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "tareas/_detalle.html", contexto_detalle(db, tarea_id))


def _resolver_ot_interna(db: Session, numero: str) -> tuple[int | None, str | None]:
    """Devuelve (ot_interna_id, ot_ambigua). Crea la OT interna si el número es
    limpio y todavía no existe (numeración interna, no toca Advertys)."""
    numero = (numero or "").strip()
    if not numero:
        return None, None
    existente = db.scalar(select(OtInterna).where(OtInterna.numero_interno == numero))
    if existente:
        return existente.id, None
    if "/" in numero or " " in numero or "-" in numero:
        return None, numero
    cliente = db.scalar(select(Cliente).where(Cliente.nombre == "ALUAR"))
    nueva = OtInterna(
        numero_interno=numero,
        cliente_id=cliente.id,
        fecha_apertura=dt.date.today(),
    )
    db.add(nueva)
    db.flush()
    cache.invalidar_ot_numeros()
    return nueva.id, None


def _validar_campos_obligatorios(
    ot_editable: bool,
    ot_numero: str,
    fecha_pedido: str,
    tipos: list[str],
    responsable_ids: set[int],
):
    """Respaldo server-side de los obligatorios de la sheet de tarea (ver
    ot/CLAUDE.md) — la sheet ya bloquea el guardado del lado del cliente,
    esto es solo para no dejar la puerta abierta a quien pegue directo
    contra el endpoint. `ot_editable` es False cuando la tarea ya tiene una
    OT interna asignada (el campo queda de solo lectura en la sheet, así
    que no viaja en el POST/PATCH y no corresponde exigirlo de nuevo)."""
    faltantes = []
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
    tarea.tipos.clear()
    for nombre in tipos:
        nombre = nombre.strip()
        if not nombre:
            continue
        tipo = db.scalar(select(TipoTarea).where(TipoTarea.nombre == nombre))
        if tipo:
            tarea.tipos.append(TareaTipoTarea(tipo_tarea_id=tipo.id))

    tarea.responsables.clear()
    for responsable_id in responsable_ids:
        tarea.responsables.append(TareaResponsable(responsable_id=responsable_id))


@router.post("/tareas")
def crear_tarea(
    request: Request,
    db: Session = Depends(get_db),
    ot_numero: str = Form(""),
    detalle: str = Form(...),
    fecha_pedido: str = Form(""),
    pedido_por: str = Form(""),
    link_drive: str = Form(""),
    presupuestado: str = Form(""),
    estado_tarea: str = Form(""),
    estado_facturacion: str = Form(EstadoFacturacion.SIN_FACTURAR.name),
    tipos: str = Form(""),
    responsable_ids: str = Form(""),
):
    tipos_lista = [x.strip() for x in tipos.split(",") if x.strip()]
    responsables = parse_ids(responsable_ids)
    _validar_campos_obligatorios(True, ot_numero, fecha_pedido, tipos_lista, responsables)

    ot_interna_id, ot_ambigua = _resolver_ot_interna(db, ot_numero)
    tarea = Tarea(
        ot_interna_id=ot_interna_id,
        ot_ambigua=ot_ambigua,
        detalle=detalle,
        fecha_pedido=dt.date.fromisoformat(fecha_pedido) if fecha_pedido else None,
        pedido_por=pedido_por or None,
        link_drive=link_drive or None,
        presupuestado={"si": True, "no": False}.get(presupuestado.lower()),
        estado_tarea=EstadoTarea[estado_tarea] if estado_tarea else None,
        estado_facturacion=EstadoFacturacion[estado_facturacion],
    )
    db.add(tarea)
    db.flush()
    _guardar_tipos_responsables(db, tarea, tipos_lista, responsables)
    db.commit()

    return _tabla_y_cerrar_drawer(db, request)


@router.patch("/tareas/{tarea_id}")
def editar_tarea(
    tarea_id: int,
    request: Request,
    db: Session = Depends(get_db),
    ot_numero: str = Form(""),
    detalle: str = Form(...),
    fecha_pedido: str = Form(""),
    pedido_por: str = Form(""),
    link_drive: str = Form(""),
    presupuestado: str = Form(""),
    estado_tarea: str = Form(""),
    estado_facturacion: str = Form(EstadoFacturacion.SIN_FACTURAR.name),
    tipos: str = Form(""),
    responsable_ids: str = Form(""),
):
    tarea = db.get(Tarea, tarea_id)
    tipos_lista = [x.strip() for x in tipos.split(",") if x.strip()]
    responsables = parse_ids(responsable_ids)
    _validar_campos_obligatorios(tarea.ot_interna_id is None, ot_numero, fecha_pedido, tipos_lista, responsables)

    if tarea.ot_interna_id is None:
        ot_interna_id, ot_ambigua = _resolver_ot_interna(db, ot_numero)
        tarea.ot_interna_id = ot_interna_id
        tarea.ot_ambigua = ot_ambigua
    tarea.detalle = detalle
    tarea.fecha_pedido = dt.date.fromisoformat(fecha_pedido) if fecha_pedido else None
    tarea.pedido_por = pedido_por or None
    tarea.link_drive = link_drive or None
    tarea.presupuestado = {"si": True, "no": False}.get(presupuestado.lower())
    tarea.estado_tarea = EstadoTarea[estado_tarea] if estado_tarea else None
    tarea.estado_facturacion = EstadoFacturacion[estado_facturacion]
    _guardar_tipos_responsables(db, tarea, tipos_lista, responsables)
    db.commit()

    return _tabla_y_cerrar_drawer(db, request)


@router.post("/tareas/{tarea_id}/anular")
def anular_tarea(tarea_id: int, request: Request, db: Session = Depends(get_db)):
    tarea = db.get(Tarea, tarea_id)
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
    tarea = db.get(Tarea, tarea_id)
    tarea.estado_tarea = EstadoTarea[estado_tarea] if estado_tarea else None
    db.commit()

    return _tabla_y_cerrar_drawer(db, request)


@router.post("/tareas/{tarea_id}/facturacion")
def actualizar_facturacion(
    tarea_id: int,
    request: Request,
    db: Session = Depends(get_db),
    estado_facturacion: str = Form(...),
):
    tarea = db.get(Tarea, tarea_id)
    tarea.estado_facturacion = EstadoFacturacion[estado_facturacion]
    db.commit()

    return _tabla_y_cerrar_drawer(db, request)


@router.get("/tareas-nuevo")
def form_nueva_tarea(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "tareas/_detalle.html",
        {
            "det": None,
            "estados": [(e.name, ESTADO_LABELS[e]) for e in EstadoTarea],
            "facturaciones": [(f.name, FACTURACION_LABELS[f]) for f in EstadoFacturacion],
            "todos_ot_numeros": cache.ot_numeros(db),
            **combo_ctx(db, set()),
            **tipos_combo_ctx(set()),
        },
    )
