from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Cliente

COOKIE_CLIENTE = "cliente_id"
CLIENTE_DEFAULT = "ALUAR"


def cliente_activo(request: Request, db: Session) -> Cliente | None:
    """Cliente elegido en el sidebar (cookie `cliente_id`, seteada por
    GET /clientes/{id}/activar). Sin cookie, o apuntando a un cliente ya
    borrado, cae a ALUAR (default histórico, el único con datos reales)."""
    crudo = request.cookies.get(COOKIE_CLIENTE)
    if crudo and crudo.isdigit():
        cliente = db.get(Cliente, int(crudo))
        if cliente:
            return cliente
    return db.scalar(select(Cliente).where(Cliente.nombre == CLIENTE_DEFAULT))
