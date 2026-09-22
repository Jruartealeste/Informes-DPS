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
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import OrdenTrabajoEspejo, SyncLog

router = APIRouter(prefix="/api/sync", tags=["sync"])


class OrdenTrabajoIn(BaseModel):
    numero_ot: str
    id_advertys: str | None = None
    negocio: str | None = None
    anunciante: str | None = None
    marca: str | None = None
    producto: str | None = None
    resumen: str | None = None
    fecha_abierta: date | None = None
    fecha_cerrada: date | None = None
    responsable: str | None = None
    equipo: str | None = None
    estado: str | None = None
    renta_teorica: float | None = None
    renta_real: float | None = None


def _verificar_token(authorization: str | None = Header(default=None)) -> None:
    if authorization != f"Bearer {settings.sync_token}":
        raise HTTPException(401, "Token de sync invalido o ausente")


@router.post("/ordenes-trabajo", dependencies=[Depends(_verificar_token)])
def sync_ordenes_trabajo(registros: list[OrdenTrabajoIn], db: Session = Depends(get_db)) -> dict:
    """Upsert por numero_ot contra ordenes_trabajo_espejo. Confía en los
    datos ya normalizados del lado de Informes (normalizar_fecha/
    normalizar_numero) -- no revalida formato acá, solo persiste.

    Upsert manual (get-then-set), no `ON CONFLICT` de Postgres: así el
    mismo código corre igual contra el sqlite descartable de
    `tools/qa_server.py` (ver skill `qa-ot`) que contra Neon en dev/prod --
    el volumen (cientos de OT) no justifica la sintaxis específica de
    dialecto."""
    try:
        for r in registros:
            valores = r.model_dump()
            fila = db.get(OrdenTrabajoEspejo, valores["numero_ot"])
            if fila is None:
                fila = OrdenTrabajoEspejo(**valores)
                db.add(fila)
            else:
                for campo, valor in valores.items():
                    setattr(fila, campo, valor)
            fila.sincronizado_en = dt.now(timezone.utc)
    except Exception as e:
        db.rollback()
        db.add(SyncLog(origen="ordenes_trabajo", cantidad=len(registros), ok=False, detalle=str(e)[:2000]))
        db.commit()
        raise HTTPException(500, f"Error al sincronizar ordenes_trabajo: {e}") from e

    db.add(SyncLog(origen="ordenes_trabajo", cantidad=len(registros), ok=True))
    db.commit()
    return {"ok": True, "cantidad": len(registros)}
