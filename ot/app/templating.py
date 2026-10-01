import os
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.cliente_ctx import cliente_activo
from app.db import get_db
from app.models import Cliente, OtInterna, Tarea

# public/ (no app/): en Vercel el CDN sirve public/** sin pasar por la función
# Python. Ver vercel.json (headers de cache) y app/main.py (mount local).
STATIC_DIR = Path(__file__).parent.parent / "public" / "static"


def _contexto_clientes(request: Request) -> dict:
    """Sidebar de clientes: se arma acá (context processor, no por-route)
    porque el sidebar vive en base.html y lo incluyen todas las páginas —
    repetir esto en cada router sería puro copy-paste. Un context processor
    solo recibe el Request, no la dependencia `db` ya resuelta de la route,
    así que se resuelve `get_db` a mano acá — respetando
    `app.dependency_overrides` (clave de por qué no se usa `SessionLocal`
    directo: los tests overridean `get_db` con su propio engine de sqlite
    en memoria, y esto tiene que verlo igual)."""
    dep = request.app.dependency_overrides.get(get_db, get_db)
    gen = dep()
    db = next(gen)
    try:
        activo = cliente_activo(request, db)
        conteos = dict(
            db.execute(
                select(OtInterna.cliente_id, func.count(Tarea.id))
                .join(Tarea, Tarea.ot_interna_id == OtInterna.id)
                .group_by(OtInterna.cliente_id)
            ).all()
        )
        clientes = list(db.scalars(select(Cliente).order_by(Cliente.id)))
        return {
            "clientes_sidebar": [
                {"id": c.id, "nombre": c.nombre, "total_tareas": conteos.get(c.id, 0)}
                for c in clientes
            ],
            "cliente_activo_id": activo.id if activo else None,
        }
    finally:
        next(gen, None)


templates = Jinja2Templates(
    directory=Path(__file__).parent / "templates",
    context_processors=[_contexto_clientes],
)


def static_version(rel_path: str) -> str:
    """Versión para el ?v= de los estáticos. Como /static/* se sirve con
    `immutable` (cache de un año), la versión TIENE que cambiar en cada deploy:
    en Vercel el mtime de los archivos es fijo, así que se usa el id del
    deploy. En local/Docker, el mtime del archivo (invalida al editar)."""
    deploy = os.environ.get("VERCEL_DEPLOYMENT_ID") or os.environ.get("VERCEL_GIT_COMMIT_SHA")
    if deploy:
        return deploy[-12:]
    try:
        return str(int((STATIC_DIR / rel_path).stat().st_mtime))
    except FileNotFoundError:
        return "0"


templates.env.globals["static_version"] = static_version
