from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db import get_db
from app.models import EstadoEstimado, Estimado, OtInterna, Tarea, TareaTipoTarea
from app.templating import templates

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


def _tarea_resumen_vm(t: Tarea) -> dict:
    return {
        "id": t.id,
        "detalle": t.detalle,
        "tipos_label": ", ".join(tt.tipo_tarea.nombre for tt in t.tipos) or "—",
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
        ],
    )
    if not estimado:
        raise HTTPException(404, "Estimado no encontrado")
    return estimado


@router.get("/estimados")
def listado_estimados(request: Request, db: Session = Depends(get_db)):
    estimados = list(
        db.scalars(
            select(Estimado).options(selectinload(Estimado.tareas)).order_by(Estimado.creado_en.desc())
        )
    )
    return templates.TemplateResponse(
        request,
        "estimados/list.html",
        {"estimados": [_estimado_vm(e) for e in estimados], **_ctx_base(request, db)},
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

    estimado = Estimado(
        titulo=titulo.strip(),
        numero_ot_advertys=numero_ot_advertys.strip(),
        creado_por_id=request.session.get("user_id"),
    )
    db.add(estimado)
    db.flush()

    tareas = list(db.scalars(select(Tarea).where(Tarea.id.in_(ids), Tarea.estimado_id.is_(None))))
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
    tareas = list(db.scalars(select(Tarea).where(Tarea.id.in_(ids), Tarea.estimado_id.is_(None))))
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
