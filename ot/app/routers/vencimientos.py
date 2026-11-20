from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app import vencimientos
from app.db import get_db
from app.templating import templates

router = APIRouter()


@router.get("/vencimientos")
def pagina_vencimientos(request: Request, db: Session = Depends(get_db)):
    """Todo lo vencido y por vencer, de todos los anunciantes, agrupado."""
    items = vencimientos.consultar(db)
    grupos: dict[int, dict] = {}
    for it in items:
        g = grupos.setdefault(it["cliente_id"], {"id": it["cliente_id"], "nombre": it["cliente"], "items": []})
        g["items"].append(it)
    # Anunciantes con más vencidas primero.
    ordenados = sorted(grupos.values(), key=lambda g: (-sum(1 for i in g["items"] if i["vencida"]), g["nombre"]))
    return templates.TemplateResponse(
        request,
        "vencimientos/list.html",
        {
            "seccion_activa": "vencimientos",
            "grupos": ordenados,
            "tema": request.cookies.get("tema", "dark"),
            "densidad": request.cookies.get("densidad", "1") != "0",
            **vencimientos.resumen(items),
        },
    )
