from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db import get_db
from app.models import OtInterna, Tarea, TareaResponsable, TareaTipoTarea
from app.templating import templates
from app.viewmodels import desglose_facturacion_vm, ot_interna_vm

router = APIRouter(prefix="/api/ordenes-trabajo")
router_paginas = APIRouter()


def siguiente_numero_interno(db: Session) -> str:
    """Próximo número de OT interna: el mayor numero_interno existente + 1."""
    maximo = db.scalar(select(func.max(cast(OtInterna.numero_interno, Integer))))
    return str((maximo or 0) + 1)


@router.get("/nuevo-numero")
def nuevo_numero(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, "tareas/_campo_ot.html", {"ot_numero": siguiente_numero_interno(db)}
    )


def _total_tareas(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Tarea)) or 0


def _cargar_ot(db: Session, numero_interno: str) -> OtInterna:
    ot = db.scalar(
        select(OtInterna)
        .where(OtInterna.numero_interno == numero_interno)
        .options(
            joinedload(OtInterna.cliente),
            selectinload(OtInterna.tareas).joinedload(Tarea.ot_interna),
            selectinload(OtInterna.tareas)
            .selectinload(Tarea.tipos)
            .joinedload(TareaTipoTarea.tipo_tarea),
            selectinload(OtInterna.tareas)
            .selectinload(Tarea.responsables)
            .joinedload(TareaResponsable.responsable),
            selectinload(OtInterna.tareas).selectinload(Tarea.mails),
        )
    )
    if not ot:
        raise HTTPException(404, "OT interna no encontrada")
    return ot


def _dps_existentes(db: Session) -> list[dict]:
    """OT de sistema ya cargadas en alguna OT interna, con cuántas la
    comparten -- para el picker de "asignar a OT de sistema existente" del
    alta en lote."""
    filas = db.execute(
        select(OtInterna.numero_ot_advertys, func.count())
        .where(OtInterna.numero_ot_advertys.isnot(None))
        .group_by(OtInterna.numero_ot_advertys)
        .order_by(OtInterna.numero_ot_advertys)
    ).all()
    return [{"valor": valor, "n_ots": n} for valor, n in filas]


@router_paginas.get("/ordenes-trabajo")
def listado_ordenes_trabajo(request: Request, db: Session = Depends(get_db)):
    ots = list(
        db.scalars(
            select(OtInterna)
            .options(joinedload(OtInterna.cliente), selectinload(OtInterna.tareas))
            .order_by(cast(OtInterna.numero_interno, Integer).desc())
        ).unique()
    )
    return templates.TemplateResponse(
        request,
        "ordenes_trabajo/list.html",
        {
            "ots": [ot_interna_vm(ot) for ot in ots],
            "total_ots": len(ots),
            "total_tareas": _total_tareas(db),
            "dps_existentes": _dps_existentes(db),
            "seccion_activa": "ordenes_trabajo",
            "tema": request.cookies.get("tema", "dark"),
            "densidad": request.cookies.get("densidad", "1") != "0",
        },
    )


@router_paginas.get("/ordenes-trabajo/{numero_interno}")
def detalle_orden_trabajo(numero_interno: str, request: Request, db: Session = Depends(get_db)):
    ot = _cargar_ot(db, numero_interno)
    hermanas = []
    if ot.numero_ot_advertys:
        hermanas = list(
            db.scalars(
                select(OtInterna.numero_interno).where(
                    OtInterna.numero_ot_advertys == ot.numero_ot_advertys,
                    OtInterna.id != ot.id,
                )
            )
        )
    vm = ot_interna_vm(ot)
    vm["hermanas"] = hermanas

    total_ots = db.scalar(select(func.count()).select_from(OtInterna)) or 0

    return templates.TemplateResponse(
        request,
        "ordenes_trabajo/detalle.html",
        {
            "ot": vm,
            "cliente": ot.cliente.nombre,
            "anunciante": ot.cliente.anunciante_advertys,
            "desglose": desglose_facturacion_vm(ot.tareas),
            "total_ots": total_ots,
            "total_tareas": _total_tareas(db),
            "seccion_activa": "ordenes_trabajo",
            "tema": request.cookies.get("tema", "dark"),
            "densidad": request.cookies.get("densidad", "1") != "0",
        },
    )


@router_paginas.post("/ordenes-trabajo/asignar-lote")
def asignar_lote_ot_sistema(
    db: Session = Depends(get_db),
    ot_ids: str = Form(""),
    numero_ot_advertys: str = Form(""),
):
    numeros = [n.strip() for n in ot_ids.split(",") if n.strip()]
    valor = numero_ot_advertys.strip()
    if not numeros:
        raise HTTPException(422, "Seleccioná al menos una OT interna.")
    if not valor:
        raise HTTPException(422, "Falta el número de OT de sistema.")
    ots = list(db.scalars(select(OtInterna).where(OtInterna.numero_interno.in_(numeros))))
    for ot in ots:
        ot.numero_ot_advertys = valor
    db.commit()
    return RedirectResponse("/ordenes-trabajo", status_code=303)


@router_paginas.post("/ordenes-trabajo/{numero_interno}/reasignar")
def reasignar_ot_sistema(
    numero_interno: str,
    db: Session = Depends(get_db),
    numero_ot_advertys: str = Form(""),
):
    ot = _cargar_ot(db, numero_interno)
    ot.numero_ot_advertys = numero_ot_advertys.strip() or None
    db.commit()
    return RedirectResponse(f"/ordenes-trabajo/{numero_interno}", status_code=303)
