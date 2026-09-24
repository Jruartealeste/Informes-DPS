from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db import get_db
from app.labels import TIPO_TAREA_LABELS
from app.models import (
    EstadoEstimado,
    EstadoSolicitudAltaEstimado,
    Estimado,
    OtInterna,
    SolicitudAltaEstimado,
    Tarea,
    TareaTipoTarea,
)
from app.templating import templates
from app.viewmodels import solicitud_alta_estimado_vm

router = APIRouter()


def _ctx_base(request: Request, db: Session) -> dict:
    return {
        "seccion_activa": "estimados",
        "tema": request.cookies.get("tema", "dark"),
        "densidad": request.cookies.get("densidad", "1") != "0",
        "total_tareas": db.scalar(select(func.count()).select_from(Tarea)) or 0,
        "total_ots": db.scalar(select(func.count()).select_from(OtInterna)) or 0,
    }


def _tareas_candidatas(db: Session, numero_ot_advertys: str) -> list[Tarea]:
    """Tareas de cualquier OT interna que comparta este numero_ot_advertys
    ("hermanas", ver ordenes_trabajo.py) y que todavía no estén en ningún
    Estimado -- confirmado con Javier (2026-09-18) que un Estimado puede
    agrupar tareas de más de una OT interna cuando comparten OT de
    sistema."""
    stmt = (
        select(Tarea)
        .join(Tarea.ot_interna)
        .where(OtInterna.numero_ot_advertys == numero_ot_advertys, Tarea.estimado_id.is_(None))
        .options(
            joinedload(Tarea.ot_interna),
            selectinload(Tarea.tipos).joinedload(TareaTipoTarea.tipo_tarea),
        )
        .order_by(Tarea.id)
    )
    return list(db.scalars(stmt).unique())


def _cargar_tareas_validadas(db: Session, ids: list[int], numero_ot_advertys: str) -> list[Tarea]:
    """Carga las tareas pedidas y corta con 422 si alguna no está libre
    (ya tiene estimado_id) o pertenece a una ot_interna con otra OT de
    sistema -- un Estimado no puede mezclar dos OT de sistema distintas
    (confirmado con Javier, 2026-09-21). No se filtra en silencio: si algo
    no matchea es señal de un bug de UI o de alguien pegando directo
    contra el endpoint, y conviene que falle explícito."""
    tareas = list(
        db.scalars(
            select(Tarea).where(Tarea.id.in_(ids)).options(joinedload(Tarea.ot_interna))
        ).unique()
    )
    encontrados = {t.id for t in tareas}
    faltantes = set(ids) - encontrados
    if faltantes:
        raise HTTPException(422, f"Tarea(s) inexistente(s): {sorted(faltantes)}")
    for t in tareas:
        if t.estimado_id is not None:
            raise HTTPException(422, f"La tarea {t.id} ya pertenece a otro Estimado.")
        if not t.ot_interna or t.ot_interna.numero_ot_advertys != numero_ot_advertys:
            raise HTTPException(
                422,
                f"La tarea {t.id} no pertenece a la OT de sistema {numero_ot_advertys}.",
            )
    return tareas


def _tarea_resumen_vm(t: Tarea) -> dict:
    return {
        "id": t.id,
        "detalle": t.detalle,
        "tipos_label": ", ".join(TIPO_TAREA_LABELS.get(tt.tipo_tarea.nombre, tt.tipo_tarea.nombre) for tt in t.tipos) or "—",
        "ot_numero": t.ot_interna.numero_interno if t.ot_interna else "—",
    }


def _estimado_vm(e: Estimado) -> dict:
    return {
        "id": e.id,
        "titulo": e.titulo,
        "numero_ot_advertys": e.numero_ot_advertys,
        "numero_estimado": e.numero_estimado,
        "estado": e.estado.name,
        "es_borrador": e.estado == EstadoEstimado.BORRADOR,
        "solicitud_pendiente": bool(
            e.solicitud_alta and e.solicitud_alta.estado == EstadoSolicitudAltaEstimado.PENDIENTE
        ),
        "creado_en": e.creado_en.strftime("%d/%m/%Y"),
        "tareas": [_tarea_resumen_vm(t) for t in e.tareas],
    }


def _cargar_estimado(db: Session, estimado_id: int) -> Estimado:
    estimado = db.get(
        Estimado,
        estimado_id,
        options=[
            selectinload(Estimado.tareas).selectinload(Tarea.tipos).joinedload(TareaTipoTarea.tipo_tarea),
            selectinload(Estimado.tareas).joinedload(Tarea.ot_interna),
            joinedload(Estimado.solicitud_alta),
        ],
    )
    if not estimado:
        raise HTTPException(404, "Estimado no encontrado")
    return estimado


@router.get("/estimados")
def listado_estimados(request: Request, db: Session = Depends(get_db)):
    estimados = list(
        db.scalars(
            select(Estimado)
            .options(selectinload(Estimado.tareas), joinedload(Estimado.solicitud_alta))
            .order_by(Estimado.creado_en.desc())
        )
    )
    n_solicitudes_pendientes = (
        db.scalar(
            select(func.count())
            .select_from(SolicitudAltaEstimado)
            .where(SolicitudAltaEstimado.estado == EstadoSolicitudAltaEstimado.PENDIENTE)
        )
        or 0
    )
    return templates.TemplateResponse(
        request,
        "estimados/list.html",
        {
            "estimados": [_estimado_vm(e) for e in estimados],
            "n_solicitudes_pendientes": n_solicitudes_pendientes,
            **_ctx_base(request, db),
        },
    )


@router.get("/estimados/solicitudes")
def listado_solicitudes_estimado(request: Request, db: Session = Depends(get_db)):
    solicitudes = list(
        db.scalars(
            select(SolicitudAltaEstimado)
            .options(selectinload(SolicitudAltaEstimado.estimados))
            .order_by(SolicitudAltaEstimado.creado_en.desc())
        )
    )
    return templates.TemplateResponse(
        request,
        "estimados/solicitudes.html",
        {"solicitudes": [solicitud_alta_estimado_vm(s) for s in solicitudes], **_ctx_base(request, db)},
    )


@router.get("/estimados/nuevo")
def form_nuevo_estimado(request: Request, db: Session = Depends(get_db)):
    numero_ot_advertys = request.query_params.get("ot_advertys", "").strip()
    if not numero_ot_advertys:
        raise HTTPException(400, "Falta el número de OT de sistema (ot_advertys)")
    candidatas = _tareas_candidatas(db, numero_ot_advertys)
    return templates.TemplateResponse(
        request,
        "estimados/nuevo.html",
        {
            "numero_ot_advertys": numero_ot_advertys,
            "candidatas": [_tarea_resumen_vm(t) for t in candidatas],
            **_ctx_base(request, db),
        },
    )


@router.post("/estimados")
def crear_estimado(
    request: Request,
    db: Session = Depends(get_db),
    numero_ot_advertys: str = Form(...),
    titulo: str = Form(...),
    tarea_ids: str = Form(""),
):
    ids = [int(x) for x in tarea_ids.split(",") if x.strip()]
    if not ids:
        raise HTTPException(422, "Seleccioná al menos una tarea para el Estimado.")
    if not titulo.strip():
        raise HTTPException(422, "El título es obligatorio.")

    numero_ot_advertys = numero_ot_advertys.strip()
    tareas = _cargar_tareas_validadas(db, ids, numero_ot_advertys)

    estimado = Estimado(
        titulo=titulo.strip(),
        numero_ot_advertys=numero_ot_advertys,
        creado_por_id=request.session.get("user_id"),
    )
    db.add(estimado)
    db.flush()

    for t in tareas:
        t.estimado_id = estimado.id
    db.commit()

    return RedirectResponse(f"/estimados/{estimado.id}", status_code=303)


@router.get("/estimados/{estimado_id}")
def detalle_estimado(estimado_id: int, request: Request, db: Session = Depends(get_db)):
    estimado = _cargar_estimado(db, estimado_id)
    disponibles = []
    if estimado.estado == EstadoEstimado.BORRADOR:
        disponibles = [_tarea_resumen_vm(t) for t in _tareas_candidatas(db, estimado.numero_ot_advertys)]

    return templates.TemplateResponse(
        request,
        "estimados/detalle.html",
        {"est": _estimado_vm(estimado), "disponibles": disponibles, **_ctx_base(request, db)},
    )


@router.post("/estimados/{estimado_id}/agregar")
def agregar_tareas(estimado_id: int, db: Session = Depends(get_db), tarea_ids: str = Form("")):
    estimado = _cargar_estimado(db, estimado_id)
    if estimado.estado != EstadoEstimado.BORRADOR:
        raise HTTPException(409, "Este Estimado ya fue generado en Advertys, no se puede editar.")
    ids = [int(x) for x in tarea_ids.split(",") if x.strip()]
    if not ids:
        return RedirectResponse(f"/estimados/{estimado_id}", status_code=303)
    tareas = _cargar_tareas_validadas(db, ids, estimado.numero_ot_advertys)
    for t in tareas:
        t.estimado_id = estimado.id
    db.commit()
    return RedirectResponse(f"/estimados/{estimado_id}", status_code=303)


@router.post("/estimados/{estimado_id}/tareas/{tarea_id}/quitar")
def quitar_tarea(estimado_id: int, tarea_id: int, db: Session = Depends(get_db)):
    estimado = _cargar_estimado(db, estimado_id)
    if estimado.estado != EstadoEstimado.BORRADOR:
        raise HTTPException(409, "Este Estimado ya fue generado en Advertys, no se puede editar.")
    tarea = db.get(Tarea, tarea_id)
    if tarea and tarea.estimado_id == estimado_id:
        tarea.estimado_id = None
        db.commit()
    return RedirectResponse(f"/estimados/{estimado_id}", status_code=303)


@router.post("/estimados/{estimado_id}/cargar-numero")
def cargar_numero_estimado(estimado_id: int, db: Session = Depends(get_db), numero_estimado: str = Form(...)):
    """Carga directa de un número de Estimado ya existente en Advertys (creado
    por otra vía, sin pasar por una solicitud acá) -- mismo criterio que
    "Cargar número" para OT internas."""
    estimado = _cargar_estimado(db, estimado_id)
    if estimado.estado != EstadoEstimado.BORRADOR:
        raise HTTPException(409, "Este Estimado ya tiene un número cargado.")
    valor = numero_estimado.strip()
    if not valor:
        raise HTTPException(422, "Falta el número de Estimado.")
    estimado.numero_estimado = valor
    estimado.estado = EstadoEstimado.GENERADO
    db.commit()
    return RedirectResponse(f"/estimados/{estimado_id}", status_code=303)


@router.post("/estimados/{estimado_id}/generar-en-advertys")
def generar_estimado_en_advertys(
    estimado_id: int,
    request: Request,
    db: Session = Depends(get_db),
    fecha_solicitada: str = Form(""),
    fecha_analisis: str = Form(""),
):
    """Junta los datos para correr `crear_estimado.py` a mano desde
    `informes/` (ver ot/CLAUDE.md, "solicitud + corrida manual" -- esta app
    nunca corre el script ella misma). Título y OT de sistema no se piden
    acá: ya viven en el Estimado local."""
    estimado = _cargar_estimado(db, estimado_id)
    if estimado.estado != EstadoEstimado.BORRADOR:
        raise HTTPException(409, "Este Estimado ya tiene un número cargado.")
    if estimado.solicitud_alta_id:
        raise HTTPException(422, "Este Estimado ya tiene un pedido de alta pendiente.")

    solicitud = SolicitudAltaEstimado(
        fecha_solicitada=fecha_solicitada.strip() or None,
        fecha_analisis=fecha_analisis.strip() or None,
        creado_por_id=request.session.get("user_id"),
    )
    db.add(solicitud)
    db.flush()
    estimado.solicitud_alta_id = solicitud.id
    db.commit()
    return RedirectResponse("/estimados/solicitudes", status_code=303)


@router.post("/estimados/solicitudes/{solicitud_id}/resolver")
def resolver_solicitud_estimado(
    solicitud_id: int, db: Session = Depends(get_db), numero_estimado: str = Form("")
):
    solicitud = db.get(
        SolicitudAltaEstimado, solicitud_id, options=[selectinload(SolicitudAltaEstimado.estimados)]
    )
    if not solicitud:
        raise HTTPException(404, "Solicitud no encontrada")
    if solicitud.estado != EstadoSolicitudAltaEstimado.PENDIENTE:
        raise HTTPException(409, "Esta solicitud ya fue resuelta.")
    valor = numero_estimado.strip()
    if not valor:
        raise HTTPException(422, "Falta el número de Estimado resultante.")
    solicitud.estado = EstadoSolicitudAltaEstimado.RESUELTA
    solicitud.resuelto_en = datetime.now(timezone.utc)
    for estimado in solicitud.estimados:
        estimado.numero_estimado = valor
        estimado.estado = EstadoEstimado.GENERADO
    db.commit()
    return RedirectResponse("/estimados/solicitudes", status_code=303)


@router.post("/estimados/solicitudes/{solicitud_id}/cancelar")
def cancelar_solicitud_estimado(solicitud_id: int, db: Session = Depends(get_db)):
    solicitud = db.get(
        SolicitudAltaEstimado, solicitud_id, options=[selectinload(SolicitudAltaEstimado.estimados)]
    )
    if not solicitud:
        raise HTTPException(404, "Solicitud no encontrada")
    if solicitud.estado != EstadoSolicitudAltaEstimado.PENDIENTE:
        raise HTTPException(409, "Esta solicitud ya fue resuelta.")
    for estimado in solicitud.estimados:
        estimado.solicitud_alta_id = None
    db.delete(solicitud)
    db.commit()
    return RedirectResponse("/estimados/solicitudes", status_code=303)
