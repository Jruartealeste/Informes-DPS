from fastapi import APIRouter, Depends, Request
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import OtInterna
from app.templating import templates

router = APIRouter(prefix="/api/ordenes-trabajo")


def siguiente_numero_interno(db: Session) -> str:
    """Próximo número de OT interna: el mayor numero_interno existente + 1."""
    maximo = db.scalar(select(func.max(cast(OtInterna.numero_interno, Integer))))
    return str((maximo or 0) + 1)


@router.get("/nuevo-numero")
def nuevo_numero(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, "tareas/_campo_ot.html", {"ot_numero": siguiente_numero_interno(db)}
    )
