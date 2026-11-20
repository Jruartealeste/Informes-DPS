"""Vencimientos de tareas de TODOS los anunciantes activos (no solo el que se
está mirando): alimenta el aviso global de base.html y la página /vencimientos.

Misma regla que viewmodels.estado_vencimiento: una tarea cerrada (finalizada,
aprobada, anulada) no se sigue; "por vencer" = vence en los próximos
DIAS_POR_VENCER días."""

from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Cliente, OtInterna, Tarea
from app.viewmodels import _ESTADOS_SIN_SEGUIMIENTO, DIAS_POR_VENCER, hoy_ar


def consultar(db: Session, hoy: date | None = None) -> list[dict]:
    """Tareas vencidas o por vencer de anunciantes activos, la más atrasada
    primero. `dias` > 0 = días de atraso, 0 = vence hoy, < 0 = faltan."""
    hoy = hoy or hoy_ar()
    filas = db.execute(
        select(
            Tarea.id,
            Tarea.detalle,
            Tarea.fecha_vencimiento,
            OtInterna.numero_interno,
            Cliente.id,
            Cliente.nombre,
        )
        .join(OtInterna, Tarea.ot_interna_id == OtInterna.id)
        .join(Cliente, OtInterna.cliente_id == Cliente.id)
        .where(
            Cliente.activo.is_(True),
            Tarea.fecha_vencimiento.is_not(None),
            Tarea.fecha_vencimiento <= hoy + timedelta(days=DIAS_POR_VENCER),
            or_(Tarea.estado_tarea.is_(None), Tarea.estado_tarea.not_in(_ESTADOS_SIN_SEGUIMIENTO)),
        )
        .order_by(Tarea.fecha_vencimiento, Tarea.id)
    ).all()
    return [
        {
            "id": tid,
            "detalle": detalle,
            "fecha": fecha,
            "dias": (hoy - fecha).days,
            "vencida": fecha < hoy,
            "ot": ot,
            "cliente_id": cid,
            "cliente": cnombre,
        }
        for tid, detalle, fecha, ot, cid, cnombre in filas
    ]


def resumen(items: list[dict]) -> dict:
    """Conteos para el aviso: totales y vencidas por anunciante (orden de
    más a menos atrasadas)."""
    por_cliente: dict[int, dict] = {}
    for it in items:
        if not it["vencida"]:
            continue
        c = por_cliente.setdefault(it["cliente_id"], {"id": it["cliente_id"], "nombre": it["cliente"], "n": 0})
        c["n"] += 1
    return {
        "n_vencidas": sum(1 for it in items if it["vencida"]),
        "n_por_vencer": sum(1 for it in items if not it["vencida"]),
        "vencidas_por_cliente": sorted(por_cliente.values(), key=lambda c: (-c["n"], c["nombre"])),
    }
