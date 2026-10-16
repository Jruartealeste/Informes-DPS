"""Recibe el sync server-a-server de datos ya cargados en Informes/
advertys.db (roadmap ítem 5, ver "Relación con Informes/ y con Advertys"
en CLAUDE.md). Autenticado con un bearer token fijo (SYNC_TOKEN) en vez de
OAuth de usuario -- no hay una persona logueada en este flujo, es
Informes/modules/sync_tareas_app/push.py hablando directo con esta app.
Por eso /api/sync/* está exento de AuthMiddleware (ver app/auth.py) y
valida el token acá adentro."""

from datetime import date, timezone
from datetime import datetime as dt

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.db import get_db
from app.models import (
    EstadoSolicitudAltaOt,
    OrdenTrabajoEspejo,
    OtInterna,
    ProductoAdvertys,
    SolicitudAltaOt,
    SyncLog,
)
from app.routers.ordenes_trabajo import resolver_solicitud

router = APIRouter(prefix="/api/sync", tags=["sync"])


class OrdenTrabajoIn(BaseModel):
    # Largos = columnas de OrdenTrabajoEspejo: un valor más largo da 422 acá, no 500 en la base.
    numero_ot: str = Field(max_length=20)
    id_advertys: str | None = Field(default=None, max_length=20)
    negocio: str | None = Field(default=None, max_length=80)
    anunciante: str | None = Field(default=None, max_length=300)
    marca: str | None = Field(default=None, max_length=200)
    producto: str | None = Field(default=None, max_length=300)
    resumen: str | None = None
    fecha_abierta: date | None = None
    fecha_cerrada: date | None = None
    responsable: str | None = Field(default=None, max_length=200)
    equipo: str | None = Field(default=None, max_length=200)
    estado: str | None = Field(default=None, max_length=40)
    renta_teorica: float | None = None
    renta_real: float | None = None

    @field_validator("numero_ot")
    @classmethod
    def _numero_ot_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("numero_ot no puede estar vacío")
        return v


def _verificar_token(authorization: str | None = Header(default=None)) -> None:
    if authorization != f"Bearer {settings.sync_token}":
        raise HTTPException(401, "Token de sync invalido o ausente")


@router.post("/ordenes-trabajo", dependencies=[Depends(_verificar_token)])
def sync_ordenes_trabajo(registros: list[OrdenTrabajoIn], db: Session = Depends(get_db)) -> dict:
    """Upsert por numero_ot contra ordenes_trabajo_espejo. Confía en los
    datos ya normalizados del lado de Informes (normalizar_fecha/
    normalizar_numero) -- solo valida lo que rompería la base (numero_ot
    vacío, largos de columna) y persiste.

    Upsert manual (get-then-set), no `ON CONFLICT` de Postgres: así el
    mismo código corre igual contra el sqlite descartable de
    `tools/qa_server.py` (ver skill `qa-ot`) que contra Neon en dev/prod --
    el volumen (cientos de OT) no justifica la sintaxis específica de
    dialecto."""
    # Si un numero_ot viene repetido en el lote, vale el último (un INSERT doble
    # rompería la clave primaria y tiraría abajo todo el lote).
    unicos = {r.numero_ot: r for r in registros}
    try:
        for r in unicos.values():
            valores = r.model_dump()
            fila = db.get(OrdenTrabajoEspejo, valores["numero_ot"])
            if fila is None:
                fila = OrdenTrabajoEspejo(**valores)
                db.add(fila)
            else:
                for campo, valor in valores.items():
                    setattr(fila, campo, valor)
            fila.sincronizado_en = dt.now(timezone.utc)
        db.add(SyncLog(origen="ordenes_trabajo", cantidad=len(registros), ok=True))
        db.commit()
    except Exception as e:
        db.rollback()
        db.add(SyncLog(origen="ordenes_trabajo", cantidad=len(registros), ok=False, detalle=str(e)[:2000]))
        db.commit()
        raise HTTPException(500, f"Error al sincronizar ordenes_trabajo: {e}") from e

    return {"ok": True, "cantidad": len(registros)}


class ProductoIn(BaseModel):
    # Largos = columnas de ProductoAdvertys (ver OrdenTrabajoIn).
    id_advertys: str = Field(max_length=20)
    nombre: str = Field(max_length=300)
    anunciante: str = Field(max_length=300)
    categoria: str | None = Field(default=None, max_length=200)
    marca: str | None = Field(default=None, max_length=200)

    @field_validator("id_advertys", "nombre", "anunciante")
    @classmethod
    def _no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("no puede estar vacío")
        return v


@router.post("/productos", dependencies=[Depends(_verificar_token)])
def sync_productos(registros: list[ProductoIn], db: Session = Depends(get_db)) -> dict:
    """Reemplazo total del catálogo de Productos: upsert por `id_advertys` y
    borra los que ya no vienen (un producto deshabilitado o borrado en
    Advertys tiene que dejar de ofrecerse en el alta de OT). Una lista vacía
    se rechaza: sería borrar todo el catálogo por un sync mal armado."""
    if not registros:
        raise HTTPException(422, "El sync de productos vino vacío: no se pisa el catálogo.")
    unicos = {r.id_advertys: r for r in registros}
    try:
        existentes = {p.id_advertys: p for p in db.query(ProductoAdvertys)}
        for id_, r in unicos.items():
            fila = existentes.get(id_)
            if fila is None:
                fila = ProductoAdvertys(**r.model_dump())
                db.add(fila)
            else:
                for campo, valor in r.model_dump().items():
                    setattr(fila, campo, valor)
            fila.sincronizado_en = dt.now(timezone.utc)
        for id_, fila in existentes.items():
            if id_ not in unicos:
                db.delete(fila)
        db.add(SyncLog(origen="productos", cantidad=len(unicos), ok=True))
        db.commit()
    except Exception as e:
        db.rollback()
        db.add(SyncLog(origen="productos", cantidad=len(registros), ok=False, detalle=str(e)[:2000]))
        db.commit()
        raise HTTPException(500, f"Error al sincronizar productos: {e}") from e

    return {"ok": True, "cantidad": len(unicos)}


# --- Solicitudes de alta de OT (skill `procesar-solicitudes-ot`) ---
# Informes/modules/ordenes_trabajo/procesar_solicitudes.py lee los pedidos
# PENDIENTES, corre crear_ot.py con el OK de Javier y resuelve acá con el
# número que devolvió Advertys. La app sigue sin correr nada ella misma.


def _solicitud_api(s: SolicitudAltaOt) -> dict:
    clientes = sorted({ot.cliente.nombre for ot in s.ots if ot.cliente})
    return {
        "id": s.id,
        "anunciante": s.anunciante,
        "resumen": s.resumen,
        "producto": s.producto,
        "centro_costo": s.centro_costo,
        "equipo": s.equipo,
        "estado": s.estado.name,
        "numero_ot_advertys": s.numero_ot_advertys,
        "cliente": ", ".join(clientes),
        "creado_por": s.creado_por.nombre if s.creado_por else None,
        "creado_en": s.creado_en.isoformat() if s.creado_en else None,
        "ots": [{"numero_interno": ot.numero_interno, "titulo": ot.titulo} for ot in s.ots],
    }


@router.get("/solicitudes-alta-ot", dependencies=[Depends(_verificar_token)])
def listar_solicitudes_alta_ot(estado: str = "PENDIENTE", db: Session = Depends(get_db)) -> list[dict]:
    try:
        estado_enum = EstadoSolicitudAltaOt[estado]
    except KeyError:
        raise HTTPException(422, f"Estado inválido: {estado}") from None
    solicitudes = db.scalars(
        select(SolicitudAltaOt)
        .where(SolicitudAltaOt.estado == estado_enum)
        .options(
            selectinload(SolicitudAltaOt.ots).selectinload(OtInterna.cliente),
            selectinload(SolicitudAltaOt.creado_por),
        )
        .order_by(SolicitudAltaOt.creado_en)
    )
    return [_solicitud_api(s) for s in solicitudes]


class ResolverIn(BaseModel):
    numero_ot_advertys: str = Field(min_length=1, max_length=20)


@router.post("/solicitudes-alta-ot/{solicitud_id}/resolver", dependencies=[Depends(_verificar_token)])
def resolver_solicitud_alta_ot(solicitud_id: int, body: ResolverIn, db: Session = Depends(get_db)) -> dict:
    """Idempotente para el reintento del script: si ya está RESUELTA con el
    mismo número responde 200 sin tocar nada; con otro número, 409 (alguien
    la resolvió a mano con un número distinto y hay que mirarlo)."""
    solicitud = db.get(SolicitudAltaOt, solicitud_id, options=[selectinload(SolicitudAltaOt.ots)])
    if not solicitud:
        raise HTTPException(404, "Solicitud no encontrada: puede que la hayan cancelado")
    valor = body.numero_ot_advertys.strip()
    if solicitud.estado == EstadoSolicitudAltaOt.RESUELTA:
        if solicitud.numero_ot_advertys == valor:
            return {"ok": True, "ya_estaba_resuelta": True, "id": solicitud.id}
        raise HTTPException(
            409, f"La solicitud ya está resuelta con la OT {solicitud.numero_ot_advertys}, no con {valor}."
        )
    resolver_solicitud(solicitud, valor)
    db.commit()
    return {"ok": True, "ya_estaba_resuelta": False, "id": solicitud.id}
