"""Login con Google OAuth restringido a @aleste.ar (ver "Auth" en
CLAUDE.md). Sesión en cookie httponly firmada (Starlette SessionMiddleware,
montada en main.py) — nunca se guarda un token de Google en la sesión, solo
los datos mínimos del usuario ya logueado."""

from datetime import datetime, timezone

from authlib.integrations.starlette_client import OAuth
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import settings
from app.models import Usuario

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


def procesar_login(db: Session, claims: dict) -> Usuario:
    """Valida el dominio del claim `hd` y hace upsert del Usuario por
    email. No crea nada si el dominio no matchea — levanta
    DominioNoAutorizado, el router la traduce a un mensaje claro sin
    tocar la tabla `usuarios`."""
    if claims.get("hd") != DOMINIO_PERMITIDO or not claims.get("email_verified"):
        raise DominioNoAutorizado(claims.get("email", "(sin email)"))

    email = claims["email"]
    usuario = db.scalar(select(Usuario).where(Usuario.email == email))
    if usuario is None:
        usuario = Usuario(email=email, nombre=claims.get("name", email))
        db.add(usuario)
    usuario.ultimo_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(usuario)
    return usuario


_PREFIJOS_PUBLICOS = ("/auth/", "/static/")


class AuthMiddleware:
    """Exige sesión iniciada para toda la app salvo /auth/* y /static/*.
    Va montada después de SessionMiddleware (necesita request.session)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"].startswith(_PREFIJOS_PUBLICOS):
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        if request.session.get("user_id"):
            await self.app(scope, receive, send)
            return

        if request.headers.get("hx-request") == "true":
            response: Response = Response(status_code=401, headers={"HX-Redirect": "/auth/login"})
        else:
            destino = f"/auth/login?next={request.url.path}"
            response = RedirectResponse(destino)
        await response(scope, receive, send)
