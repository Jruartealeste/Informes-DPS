from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.auth import AuthMiddleware
from app.config import settings
from app.routers import (
    auth_routes,
    clientes,
    estimados,
    facturacion,
    mail,
    ordenes_trabajo,
    responsables,
    sync,
    tareas,
)

app = FastAPI(title="Órdenes de trabajo")

class _StaticInmutable(StaticFiles):
    """Cache de un año: las URLs llevan ?v=<versión de deploy/mtime> (ver
    templating.static_version), así que un archivo nuevo siempre es otra URL."""

    def file_response(self, *args, **kwargs):
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp


# En Vercel esto casi no se usa: public/static lo sirve el CDN antes de llegar
# acá. Queda para dev local, Docker/Cloud Run y los tests.
app.mount(
    "/static",
    _StaticInmutable(directory=Path(__file__).parent.parent / "public" / "static"),
    name="static",
)

# Orden importa: AuthMiddleware necesita request.session, así que
# SessionMiddleware va montada después (Starlette ejecuta el middleware
# agregado último primero, "más afuera").
app.add_middleware(AuthMiddleware)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, same_site="lax")

app.include_router(auth_routes.router)
app.include_router(clientes.router)
app.include_router(tareas.router)
app.include_router(ordenes_trabajo.router)
app.include_router(ordenes_trabajo.router_paginas)
app.include_router(responsables.router)
app.include_router(mail.router)
app.include_router(estimados.router)
app.include_router(facturacion.router)
app.include_router(sync.router)
