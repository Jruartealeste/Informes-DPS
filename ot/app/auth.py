"""Login con Google OAuth restringido a @aleste.ar (ver "Auth" en
CLAUDE.md). Sesión en cookie httponly firmada (Starlette SessionMiddleware,
montada en main.py) — nunca se guarda un token de Google en la sesión, solo
los datos mínimos del usuario ya logueado."""

from datetime import datetime, timezone

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import settings
from app.db import get_db
from app.models import RolUsuario, Usuario

DOMINIO_PERMITIDO = "aleste.ar"

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.auth_google_client_id,
    client_secret=settings.auth_google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


class DominioNoAutorizado(Exception):
    """El login con Google funcionó pero la cuenta no es @aleste.ar."""


class UsuarioInactivo(Exception):
    """La cuenta es @aleste.ar pero un ADMIN la desactivó (pantalla Usuarios)."""


def procesar_login(db: Session, claims: dict) -> Usuario:
    """Valida el dominio del claim `hd` y hace upsert del Usuario por
    email. No crea nada si el dominio no matchea — levanta
    DominioNoAutorizado, el router la traduce a un mensaje claro sin
    tocar la tabla `usuarios`. Un usuario desactivado no entra
    (UsuarioInactivo) y no se le actualiza `ultimo_login`."""
    if claims.get("hd") != DOMINIO_PERMITIDO or not claims.get("email_verified"):
        raise DominioNoAutorizado(claims.get("email", "(sin email)"))

    email = claims["email"]
    usuario = db.scalar(select(Usuario).where(Usuario.email == email))
    if usuario is None:
        usuario = Usuario(email=email, nombre=claims.get("name", email))
        db.add(usuario)
    elif not usuario.activo:
        raise UsuarioInactivo(email)
    usuario.ultimo_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(usuario)
    return usuario


_PREFIJOS_PUBLICOS = ("/auth/", "/static/", "/api/sync/")


def _rol_si_activo(scope: Scope, user_id: int) -> RolUsuario | None:
    """Rol del usuario de la sesión leído de la base, o None si ya no existe
    o está desactivado. Resuelve `get_db` respetando dependency_overrides
    (igual que templating.py y SoloLecturaMiddleware) para que los tests lo
    vean con su propia base."""
    dep = scope["app"].dependency_overrides.get(get_db, get_db)
    gen = dep()
    db = next(gen)
    try:
        fila = db.execute(select(Usuario.rol, Usuario.activo).where(Usuario.id == user_id)).first()
    finally:
        next(gen, None)
    if fila is None or not fila.activo:
        return None
    return fila.rol


def requiere_admin(request: Request, db: Session = Depends(get_db)) -> Usuario:
    """El rol se lee de la base en cada request (no de la sesión), para que
    dar o quitar ADMIN rija sin esperar al próximo login."""
    usuario = db.get(Usuario, request.session.get("user_id") or 0)
    if not usuario or not usuario.activo or usuario.rol != RolUsuario.ADMIN:
        raise HTTPException(403, "Solo un ADMIN puede entrar acá.")
    return usuario


class AuthMiddleware:
    """Exige sesión iniciada para toda la app salvo /auth/*, /static/* y
    /api/sync/*. Este último no queda "abierto" -- es server-a-server
    (Informes/modules/sync_tareas_app/push.py) y valida su propio bearer
    token adentro de app/routers/sync.py, no una sesión de usuario. Va
    montada después de SessionMiddleware (necesita request.session).

    Con sesión, igual valida contra la base en cada request que el usuario
    siga existiendo y esté activo (2026-10-14): desactivarlo desde la
    pantalla Usuarios lo saca en el próximo click, sin esperar a que venza la
    cookie. El rol leído queda en `request.state.rol_usuario` para que
    templating.py no repita la query."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"].startswith(_PREFIJOS_PUBLICOS):
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        user_id = request.session.get("user_id")
        if user_id:
            rol = _rol_si_activo(scope, user_id)
            if rol is not None:
                scope.setdefault("state", {})["rol_usuario"] = rol
                await self.app(scope, receive, send)
                return
            # Desactivado (o borrado) con la sesión todavía abierta: se la
            # cierra y vuelve al login con el aviso.
            request.session.clear()
            login = hx_login = "/auth/login?error=inactivo"
        else:
            login, hx_login = f"/auth/login?next={request.url.path}", "/auth/login"

        if request.headers.get("hx-request") == "true":
            response: Response = Response(status_code=401, headers={"HX-Redirect": hx_login})
        else:
            response = RedirectResponse(login)
        await response(scope, receive, send)
