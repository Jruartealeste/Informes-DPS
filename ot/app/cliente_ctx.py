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


# Métodos que cambian datos. Un anunciante desactivado queda en solo lectura:
# ningún cambio (tareas, OT, estimados, mails...) mientras sea el del sidebar.
_METODOS_ESCRITURA = {"POST", "PUT", "PATCH", "DELETE"}
# /anunciantes y /clientes son la gestión de anunciantes (reactivar incluido);
# /auth, /api/sync y /usuarios no dependen del anunciante elegido.
_PREFIJOS_LIBRES = ("/auth", "/api/sync", "/anunciantes", "/clientes", "/usuarios", "/static")


class SoloLecturaMiddleware:
    """Rechaza (409) cualquier escritura si el anunciante del sidebar está
    desactivado (2026-10-14: baja = solo lectura, nunca borrar). Resuelve
    `get_db` respetando dependency_overrides, igual que templating.py, para
    que los tests lo vean con su propia base."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] not in _METODOS_ESCRITURA
            or scope["path"].startswith(_PREFIJOS_LIBRES)
        ):
            await self.app(scope, receive, send)
            return
        from starlette.responses import PlainTextResponse

        from app.db import get_db

        request = Request(scope, receive)
        crudo = request.cookies.get(COOKIE_CLIENTE)
        inactivo = None
        if crudo and crudo.isdigit():
            dep = scope["app"].dependency_overrides.get(get_db, get_db)
            gen = dep()
            db = next(gen)
            try:
                cliente = db.get(Cliente, int(crudo))
                if cliente and not cliente.activo:
                    inactivo = cliente.nombre
            finally:
                next(gen, None)
        if inactivo:
            resp = PlainTextResponse(
                f"El anunciante {inactivo} está desactivado: solo lectura, no admite cambios.", status_code=409
            )
            await resp(scope, receive, send)
            return
        await self.app(scope, receive, send)
