from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db import get_db
from app.labels import ESTADOS_FACTURADOS, FACTURACION_LABELS, TIPO_TAREA_LABELS
from app.models import EstadoFacturacion, OtInterna, Tarea, TareaTipoTarea
from app.templating import templates

router = APIRouter()

OPT_FAC = [(f.name, FACTURACION_LABELS[f]) for f in EstadoFacturacion]


def _ctx_base(request: Request, db: Session) -> dict:
    return {
        "seccion_activa": "facturacion",
        "tema": request.cookies.get("tema", "dark"),
        "densidad": request.cookies.get("densidad", "1") != "0",
        "total_tareas": db.scalar(select(func.count()).select_from(Tarea)) or 0,
        "total_ots": db.scalar(select(func.count()).select_from(OtInterna)) or 0,
    }


def _tareas_facturables(db: Session) -> list[Tarea]:
    """Tareas listas para entrar en la cola de facturación: OT de sistema
    asignada + Estimado relacionado (condición confirmada con Javier,
    2026-09-24) -- Advertys va a facturar automáticamente por Estimado una
    vez que exista el script de alta, así que agrupamos por ahí."""
    stmt = (
        select(Tarea)
        .join(Tarea.ot_interna)
        .where(Tarea.estimado_id.is_not(None), OtInterna.numero_ot_advertys.is_not(None))
        .options(
            joinedload(Tarea.ot_interna).joinedload(OtInterna.cliente),
            joinedload(Tarea.estimado),
            selectinload(Tarea.tipos).joinedload(TareaTipoTarea.tipo_tarea),
        )
        .order_by(Tarea.estimado_id, Tarea.id)
    )
    return list(db.scalars(stmt).unique())


def _tarea_fila_vm(t: Tarea) -> dict:
    return {
        "id": t.id,
        "detalle": t.detalle,
        "tipos_label": ", ".join(
            TIPO_TAREA_LABELS.get(tt.tipo_tarea.nombre, tt.tipo_tarea.nombre) for tt in t.tipos
        )
        or "—",
        "ot_numero": t.ot_interna.numero_interno,
        "estado_facturacion": t.estado_facturacion.name,
    }


def _grupo_vm(tareas: list[Tarea]) -> dict:
    estimado = tareas[0].estimado
    total = len(tareas)
    facturadas = sum(1 for t in tareas if t.estado_facturacion in ESTADOS_FACTURADOS)
    return {
        "estimado_id": estimado.id,
        "titulo": estimado.titulo,
        "numero_estimado": estimado.numero_estimado,
        "numero_ot_advertys": estimado.numero_ot_advertys,
        "cliente": tareas[0].ot_interna.cliente.nombre,
        "tareas": [_tarea_fila_vm(t) for t in tareas],
        "total": total,
        "facturadas": facturadas,
        "pendientes": total - facturadas,
    }


def _grupos_facturables(db: Session) -> list[dict]:
    tareas = _tareas_facturables(db)
    por_estimado: dict[int, list[Tarea]] = {}
    orden: list[int] = []
    for t in tareas:
        if t.estimado_id not in por_estimado:
            por_estimado[t.estimado_id] = []
            orden.append(t.estimado_id)
        por_estimado[t.estimado_id].append(t)
    grupos = [_grupo_vm(por_estimado[eid]) for eid in orden]
    grupos.sort(key=lambda g: (-g["pendientes"], g["titulo"]))
    return grupos


def _kicker(grupos: list[dict]) -> str:
    n = len(grupos)
    texto = f"ALUAR · {n} Estimado{'s' if n != 1 else ''} en cola"
    pendientes = sum(g["pendientes"] for g in grupos)
    if pendientes:
        texto += f" · {pendientes} tarea{'s' if pendientes != 1 else ''} pendiente{'s' if pendientes != 1 else ''}"
    return texto


@router.get("/facturacion")
def listado_facturacion(request: Request, db: Session = Depends(get_db)):
    grupos = _grupos_facturables(db)
    return templates.TemplateResponse(
        request,
        "facturacion/list.html",
        {
            "grupos": grupos,
            "opt_fac": OPT_FAC,
            "kicker": _kicker(grupos),
            **_ctx_base(request, db),
        },
    )


@router.post("/facturacion/tareas/{tarea_id}/estado")
def actualizar_estado_facturacion(
    tarea_id: int,
    request: Request,
    db: Session = Depends(get_db),
    estado_facturacion: str = Form(...),
):
    tarea = db.get(Tarea, tarea_id)
    if tarea:
        tarea.estado_facturacion = EstadoFacturacion[estado_facturacion]
        db.commit()
    grupos = _grupos_facturables(db)
    lista_html = templates.env.get_template("facturacion/_grupos.html").render(
        {"grupos": grupos, "opt_fac": OPT_FAC}
    )
    kicker_html = f'<div id="fact-kicker" hx-swap-oob="true">{_kicker(grupos)}</div>'
    return HTMLResponse(lista_html + kicker_html)
