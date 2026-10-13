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
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import OrdenTrabajoEspejo, ProductoAdvertys, SyncLog

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
