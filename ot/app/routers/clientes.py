from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.cliente_ctx import COOKIE_CLIENTE
from app.db import get_db
from app.models import Cliente

router = APIRouter()


@router.get("/clientes/{cliente_id}/activar")
def activar_cliente(cliente_id: int, request: Request, db: Session = Depends(get_db)):
    if not db.get(Cliente, cliente_id):
        raise HTTPException(404, "Cliente no encontrado")
    destino = request.headers.get("referer") or "/tareas"
    resp = RedirectResponse(destino, status_code=303)
    resp.set_cookie(COOKIE_CLIENTE, str(cliente_id), max_age=31536000, path="/")
    return resp
