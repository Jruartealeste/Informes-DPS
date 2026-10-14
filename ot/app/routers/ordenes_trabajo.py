from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.anunciantes import productos_del_cliente
from app.cliente_ctx import cliente_activo
from app.db import get_db
from app.labels import CENTRO_COSTO_OPCIONES, EQUIPO_OPCIONES
from app.models import (
    EstadoSolicitudAltaOt,
    OtInterna,
    SolicitudAltaOt,
    Tarea,
    TareaResponsable,
    TareaTipoTarea,
)
from app.templating import templates
from app.viewmodels import desglose_facturacion_vm, ot_interna_vm, solicitud_alta_vm


router = APIRouter(prefix="/api/ordenes-trabajo")
router_paginas = APIRouter()


def siguiente_numero_interno(db: Session) -> str:
    """Próximo número de OT interna: el mayor numero_interno existente + 1."""
    maximo = db.scalar(select(func.max(cast(OtInterna.numero_interno, Integer))))
    return str((maximo or 0) + 1)


@router.get("/nuevo-numero")
def nuevo_numero(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, "tareas/_campo_ot.html", {"ot_numero": (n := siguiente_numero_interno(db)), "ot_generada": n}
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


def _dps_existentes(db: Session, cliente_id: int | None = None) -> list[dict]:
    """OT de sistema ya cargadas en alguna OT interna, con cuántas la
    comparten -- para el picker de "asignar a OT de sistema existente" del
    alta en lote. Con `cliente_id`, solo las de ese cliente."""
    stmt = select(OtInterna.numero_ot_advertys, func.count()).where(OtInterna.numero_ot_advertys.isnot(None))
    if cliente_id is not None:
        stmt = stmt.where(OtInterna.cliente_id == cliente_id)
    filas = db.execute(
        stmt.group_by(OtInterna.numero_ot_advertys).order_by(OtInterna.numero_ot_advertys)
    ).all()
    return [{"valor": valor, "n_ots": n} for valor, n in filas]


@router_paginas.get("/ordenes-trabajo")
def listado_ordenes_trabajo(request: Request, db: Session = Depends(get_db)):
    # Solo las OT internas del cliente del sidebar: el panel de alta en lote
    # (Producto, Anunciante) depende de ese cliente.
    cliente = cliente_activo(request, db)
    del_cliente = OtInterna.cliente_id == (cliente.id if cliente else None)
    stmt = (
        select(OtInterna)
        .where(del_cliente)
        .options(joinedload(OtInterna.cliente), selectinload(OtInterna.tareas))
        .order_by(cast(OtInterna.numero_interno, Integer).desc())
    )
    total_ots = db.scalar(select(func.count()).select_from(OtInterna).where(del_cliente)) or 0
    n_sin_dps = (
        db.scalar(
            select(func.count())
            .select_from(OtInterna)
            .where(del_cliente, OtInterna.numero_ot_advertys.is_(None))
        )
        or 0
    )
    ots = list(db.scalars(stmt).unique())
    n_solicitudes_pendientes = (
        db.scalar(
            select(func.count())
            .select_from(SolicitudAltaOt)
            .where(SolicitudAltaOt.estado == EstadoSolicitudAltaOt.PENDIENTE)
        )
        or 0
    )
    return templates.TemplateResponse(
        request,
        "ordenes_trabajo/list.html",
        {
            "ots": [ot_interna_vm(ot) for ot in ots],
            "total_ots": total_ots,
            "n_sin_dps": n_sin_dps,
            "n_solicitudes_pendientes": n_solicitudes_pendientes,
            "total_tareas": _total_tareas(db),
            "dps_existentes": _dps_existentes(db, cliente.id if cliente else None),
            "centro_costo_opciones": CENTRO_COSTO_OPCIONES,
            "equipo_opciones": EQUIPO_OPCIONES,
            "cliente": cliente,
            "productos_cliente": productos_del_cliente(db, cliente),
            "seccion_activa": "ordenes_trabajo",
            "tema": request.cookies.get("tema", "dark"),
            "densidad": request.cookies.get("densidad", "1") != "0",
        },
    )


@router_paginas.get("/ordenes-trabajo/solicitudes")
def listado_solicitudes_alta(request: Request, db: Session = Depends(get_db)):
    solicitudes = list(
        db.scalars(
            select(SolicitudAltaOt)
            .options(selectinload(SolicitudAltaOt.ots))
            .order_by(SolicitudAltaOt.creado_en.desc())
        )
    )
    return templates.TemplateResponse(
        request,
        "ordenes_trabajo/solicitudes.html",
        {
            "solicitudes": [solicitud_alta_vm(s) for s in solicitudes],
            "total_ots": db.scalar(select(func.count()).select_from(OtInterna)) or 0,
            "total_tareas": _total_tareas(db),
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
            "anunciante": ", ".join(a.anunciante for a in ot.cliente.anunciantes) or None,
            "desglose": desglose_facturacion_vm(ot.tareas),
            "total_ots": total_ots,
            "total_tareas": _total_tareas(db),
            "seccion_activa": "ordenes_trabajo",
            "tema": request.cookies.get("tema", "dark"),
            "densidad": request.cookies.get("densidad", "1") != "0",
        },
    )


def _rechazar_con_solicitud_pendiente(ots: list[OtInterna]) -> None:
    """Una OT con un pedido de alta PENDIENTE espera el número que va a devolver
    crear_ot.py: asignarle uno a mano haría que `resolver` lo pise en silencio."""
    pendientes = [
        ot.numero_interno
        for ot in ots
        if ot.solicitud_alta and ot.solicitud_alta.estado == EstadoSolicitudAltaOt.PENDIENTE
    ]
    if pendientes:
        raise HTTPException(
            409,
            f"OT interna(s) {', '.join(pendientes)} tienen un pedido de alta pendiente: "
            "resolvelo o cancelalo en Solicitudes antes de asignarles una OT de sistema.",
        )


def _asignar_ot_sistema(ot: OtInterna, valor: str | None) -> None:
    """Asigna (o vacía) la OT de sistema. Si la OT venía de un pedido ya resuelto
    y el número cambia, se la desvincula: la solicitud resuelta ya no la describe
    y, además, impediría volver a pedir el alta."""
    solicitud = ot.solicitud_alta
    if solicitud and solicitud.estado == EstadoSolicitudAltaOt.RESUELTA and solicitud.numero_ot_advertys != valor:
        ot.solicitud_alta_id = None
    ot.numero_ot_advertys = valor


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
    ots = list(
        db.scalars(
            select(OtInterna)
            .where(OtInterna.numero_interno.in_(numeros))
            .options(joinedload(OtInterna.solicitud_alta))
        )
    )
    _rechazar_con_solicitud_pendiente(ots)
    for ot in ots:
        _asignar_ot_sistema(ot, valor)
    db.commit()
    return RedirectResponse("/ordenes-trabajo", status_code=303)


@router_paginas.post("/ordenes-trabajo/{numero_interno}/reasignar")
def reasignar_ot_sistema(
    numero_interno: str,
    db: Session = Depends(get_db),
    numero_ot_advertys: str = Form(""),
):
    ot = _cargar_ot(db, numero_interno)
    _rechazar_con_solicitud_pendiente([ot])
    _asignar_ot_sistema(ot, numero_ot_advertys.strip() or None)
    db.commit()
    return RedirectResponse(f"/ordenes-trabajo/{numero_interno}", status_code=303)


@router_paginas.post("/ordenes-trabajo/generar-ot")
def generar_ot(
    request: Request,
    db: Session = Depends(get_db),
    ot_ids: str = Form(""),
    anunciante: str = Form(...),
    resumen: str = Form(...),
    producto: str = Form(...),
    centro_costo: str = Form(...),
    equipo: str = Form(""),
):
    """Junta los datos de un alta de OT nueva en Advertys, ya confirmados
    con Javier, para que corra `crear_ot.py` a mano desde `informes/` (ver
    ot/CLAUDE.md, decisión 2026-09-23 "solicitud + corrida manual" -- esta
    app nunca tiene ni va a tener las credenciales de Advertys). No dispara
    ningún subprocess. El cliente es el activo del sidebar y el Anunciante
    sale del Producto elegido: el combo solo ofrece productos de los
    Anunciantes de Advertys de ese cliente (app/anunciantes.py) -- un Cliente
    de acá puede ser varios Anunciantes (FATE son 6)."""
    numeros = [n.strip() for n in ot_ids.split(",") if n.strip()]
    anunciante = anunciante.strip()
    centro_costo = centro_costo.strip()
    equipo = equipo.strip()
    if not numeros:
        raise HTTPException(422, "Seleccioná al menos una OT interna.")
    if not anunciante:
        raise HTTPException(422, "Falta el Anunciante.")
    if centro_costo not in CENTRO_COSTO_OPCIONES:
        raise HTTPException(422, "Centro Costo inválido.")
    if equipo and equipo not in EQUIPO_OPCIONES:
        raise HTTPException(422, "Equipo inválido.")
    if not resumen.strip() or not producto.strip():
        raise HTTPException(422, "Resumen y Producto son obligatorios.")

    ots = list(
        db.scalars(
            select(OtInterna)
            .where(OtInterna.numero_interno.in_(numeros))
            .options(joinedload(OtInterna.cliente), joinedload(OtInterna.solicitud_alta))
        )
    )
    if len(ots) != len(numeros):
        raise HTTPException(422, "Alguna OT interna seleccionada no existe.")
    ya_con_dps = [ot.numero_interno for ot in ots if ot.numero_ot_advertys]
    if ya_con_dps:
        raise HTTPException(
            422, f"OT interna(s) {', '.join(ya_con_dps)} ya tienen OT de sistema -- no se puede regenerar."
        )
    ya_en_solicitud = [
        ot.numero_interno
        for ot in ots
        if ot.solicitud_alta and ot.solicitud_alta.estado == EstadoSolicitudAltaOt.PENDIENTE
    ]
    if ya_en_solicitud:
        raise HTTPException(
            422, f"OT interna(s) {', '.join(ya_en_solicitud)} ya tienen un pedido de alta pendiente."
        )
    clientes_ids = {ot.cliente_id for ot in ots}
    if len(clientes_ids) > 1:
        raise HTTPException(
            422, "Las OT internas seleccionadas no son todas del mismo cliente."
        )
    cliente = cliente_activo(request, db)
    if cliente is None or clientes_ids != {cliente.id}:
        raise HTTPException(
            422, "Las OT internas seleccionadas no son del cliente elegido en el sidebar."
        )
    if producto.strip() not in productos_del_cliente(db, cliente).get(anunciante, []):
        raise HTTPException(
            422, f"«{producto.strip()}» no es un Producto de Advertys de {cliente.nombre} ({anunciante})."
        )

    solicitud = SolicitudAltaOt(
        anunciante=anunciante,
        resumen=resumen.strip(),
        producto=producto.strip(),
        centro_costo=centro_costo,
        equipo=equipo.strip() or None,
        creado_por_id=request.session.get("user_id"),
    )
    db.add(solicitud)
    db.flush()
    for ot in ots:
        ot.solicitud_alta_id = solicitud.id
    db.commit()
    return RedirectResponse("/ordenes-trabajo/solicitudes", status_code=303)


@router_paginas.post("/ordenes-trabajo/solicitudes/{solicitud_id}/resolver")
def resolver_solicitud_alta(
    solicitud_id: int,
    db: Session = Depends(get_db),
    numero_ot_advertys: str = Form(""),
):
    solicitud = db.get(SolicitudAltaOt, solicitud_id, options=[selectinload(SolicitudAltaOt.ots)])
    if not solicitud:
        raise HTTPException(404, "Solicitud no encontrada")
    if solicitud.estado != EstadoSolicitudAltaOt.PENDIENTE:
        raise HTTPException(409, "Esta solicitud ya fue resuelta.")
    valor = numero_ot_advertys.strip()
    if not valor:
        raise HTTPException(422, "Falta el número de OT resultante.")
    solicitud.numero_ot_advertys = valor
    solicitud.estado = EstadoSolicitudAltaOt.RESUELTA
    solicitud.resuelto_en = datetime.now(timezone.utc)
    for ot in solicitud.ots:
        ot.numero_ot_advertys = valor
    db.commit()
    return RedirectResponse("/ordenes-trabajo/solicitudes", status_code=303)


@router_paginas.post("/ordenes-trabajo/solicitudes/{solicitud_id}/cancelar")
def cancelar_solicitud_alta(solicitud_id: int, db: Session = Depends(get_db)):
    solicitud = db.get(SolicitudAltaOt, solicitud_id, options=[selectinload(SolicitudAltaOt.ots)])
    if not solicitud:
        raise HTTPException(404, "Solicitud no encontrada")
    if solicitud.estado != EstadoSolicitudAltaOt.PENDIENTE:
        raise HTTPException(409, "Esta solicitud ya fue resuelta.")
    for ot in solicitud.ots:
        ot.solicitud_alta_id = None
    db.delete(solicitud)
    db.commit()
    return RedirectResponse("/ordenes-trabajo/solicitudes", status_code=303)
