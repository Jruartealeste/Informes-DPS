import os
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.cliente_ctx import CLIENTE_DEFAULT, COOKIE_CLIENTE
from app.db import get_db
from app.models import Cliente, OtInterna, RolUsuario, Tarea, Usuario
from app.viewmodels import links_de

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
        # Una sola query (clientes LEFT JOIN conteo) en vez de tres seriales:
        # cada una es una ida y vuelta a Neon por request. El cliente activo
        # se resuelve en Python sobre esa misma lista (cookie, o ALUAR por
        # default — misma regla que cliente_ctx.cliente_activo).
        filas = db.execute(
            select(Cliente.id, Cliente.nombre, Cliente.activo, func.count(Tarea.id))
            .outerjoin(OtInterna, OtInterna.cliente_id == Cliente.id)
            .outerjoin(Tarea, Tarea.ot_interna_id == OtInterna.id)
            .group_by(Cliente.id, Cliente.nombre, Cliente.activo)
            .order_by(Cliente.id)
        ).all()
        todos = [{"id": i, "nombre": n, "activo": a, "total_tareas": t} for i, n, a, t in filas]
        crudo = request.cookies.get(COOKIE_CLIENTE)
        activo_id = None
        if crudo and crudo.isdigit():
            activo_id = next((c["id"] for c in todos if c["id"] == int(crudo)), None)
        if activo_id is None:
            activo_id = next((c["id"] for c in todos if c["nombre"] == CLIENTE_DEFAULT), None)
        # Los desactivados no se ofrecen en el selector; si se está mirando uno
        # (solo lectura, desde la pantalla Anunciantes), aparece marcado.
        clientes_sidebar = [c for c in todos if c["activo"] or c["id"] == activo_id]
        actual = next((c for c in todos if c["id"] == activo_id), None)
        # AuthMiddleware ya leyó el rol de la base en este request.
        rol = getattr(request.state, "rol_usuario", None)
        if rol is None:
            rol = db.scalar(select(Usuario.rol).where(Usuario.id == (request.session.get("user_id") or 0)))
        return {
            "clientes_sidebar": clientes_sidebar,
            "cliente_activo_id": activo_id,
            "cliente_solo_lectura": bool(actual and not actual["activo"]),
            "es_admin": rol == RolUsuario.ADMIN,
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


def href_externo(valor: str | None) -> str | None:
    """URL apta para un <a href> a partir de un campo de texto libre (ej.
    link_drive), o None si no hay link usable. Solo http/https: un esquema
    raro (javascript:, data:) no se linkea. Sin esquema ("drive.google.com/…")
    se asume https."""
    v = (valor or "").strip()
    if not v or any(c.isspace() for c in v):
        return None
    esquema, sep, _ = v.partition(":")
    if sep and esquema.lower() in ("http", "https"):
        return v
    if sep and "/" not in esquema and "." not in esquema:
        return None  # otro esquema (javascript:, mailto:, data:…)
    return "https://" + v


templates.env.filters["href_externo"] = href_externo
templates.env.filters["links_de"] = links_de
