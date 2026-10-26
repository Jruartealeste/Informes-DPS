import time
from datetime import datetime, timedelta, timezone

from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import DominioNoAutorizado, UsuarioInactivo, oauth, procesar_login
from app.config import settings
from app.db import get_db
from app.gmail_client import GMAIL_SCOPE, cifrar_token
from app.models import Usuario
from app.templating import templates

router = APIRouter(prefix="/auth")


@router.get("/login")
def login(request: Request):
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "error_dominio": request.query_params.get("error") == "dominio",
            "error_inactivo": request.query_params.get("error") == "inactivo",
        },
    )


# Neon (plan Free) suspende el cómputo a los 5 min sin uso y el primer query
# después de eso tarda varios segundos. La página de login llama acá apenas
# carga: mientras la persona hace el login con Google (varios segundos), la
# base se despierta, y el primer request ya autenticado la encuentra lista.
# Es público (vive bajo /auth/) y solo hace SELECT 1; se limita a una query
# cada 20 s por instancia para que no sirva de amplificador.
_ULTIMO_DESPERTAR = 0.0
_DESPERTAR_CADA_S = 20


def _consultar_base_con_limite(db: Session) -> None:
    global _ULTIMO_DESPERTAR
    ahora = time.monotonic()
    if ahora - _ULTIMO_DESPERTAR >= _DESPERTAR_CADA_S:
        _ULTIMO_DESPERTAR = ahora
        db.execute(text("select 1"))


@router.get("/despertar", status_code=204)
def despertar(db: Session = Depends(get_db)):
    _consultar_base_con_limite(db)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


# Ping periódico para que Neon Free no se suspenda mientras el equipo trabaja
# (lo llama un cron externo cada ~4 min, ver "Rendimiento y backups" en
# CLAUDE.md). Solo toca la base de lunes a viernes en horario laboral
# (hora de Argentina): el plan Free incluye 100 CU-horas por mes y mantener la
# base despierta las 24 h gastaría ~180, así que un pinger mal configurado
# (24/7) no tiene que poder agotar el cupo. Fuera de horario responde igual
# 204 pero sin consultar. Argentina no tiene horario de verano: UTC-3 fijo
# (evita depender de tzdata en el runtime).
_AR = timezone(timedelta(hours=-3))
_HORARIO_DESDE = (7, 30)  # un poco antes de las 8:00, para que la base ya esté despierta
_HORARIO_HASTA = (19, 30)


def _ahora() -> datetime:
    return datetime.now(_AR)


def en_horario_laboral(ahora: datetime) -> bool:
    ahora = ahora.astimezone(_AR)
    if ahora.weekday() >= 5:  # sábado / domingo
        return False
    return _HORARIO_DESDE <= (ahora.hour, ahora.minute) < _HORARIO_HASTA


@router.get("/mantener", status_code=204)
def mantener(db: Session = Depends(get_db)):
    if not en_horario_laboral(_ahora()):
        return Response(status_code=204, headers={"Cache-Control": "no-store", "X-Mantener": "fuera-de-horario"})
    _consultar_base_con_limite(db)
    return Response(status_code=204, headers={"Cache-Control": "no-store", "X-Mantener": "ok"})


@router.get("/login/google")
async def login_google(request: Request, next: str = "/tareas"):
    request.session["next"] = next
    # un "Conectar Gmail" abandonado a mitad no tiene que desviar este login
    request.session.pop("gmail_next", None)
    redirect_uri = request.url_for("auth_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback", name="auth_callback")
async def callback(request: Request, db: Session = Depends(get_db)):
    if "gmail_next" in request.session:
        return await _callback_gmail(request, db)

    token = await oauth.google.authorize_access_token(request)
    claims = token["userinfo"]

    try:
        usuario = procesar_login(db, claims)
    except DominioNoAutorizado:
        return RedirectResponse("/auth/login?error=dominio")
    except UsuarioInactivo:
        return RedirectResponse("/auth/login?error=inactivo")

    request.session["user_id"] = usuario.id
    request.session["email"] = usuario.email
    request.session["nombre"] = usuario.nombre
    request.session["rol"] = usuario.rol.value
    destino = request.session.pop("next", "/tareas")
    return RedirectResponse(destino)


def _destino_local(next: str) -> str:
    # solo rutas de la propia app (evita usar esto de open redirect)
    return next if next.startswith("/") and not next.startswith("//") else "/tareas"


def _con_aviso(destino: str, valor: str) -> str:
    return f"{destino}{'&' if '?' in destino else '?'}gmail={valor}"


@router.get("/gmail/conectar")
async def gmail_conectar(request: Request, next: str = "/tareas", db: Session = Depends(get_db)):
    """Conectar Gmail: pide a Google el permiso gmail.send sobre la
    cuenta del usuario logueado, con acceso offline para guardar el refresh
    token. Reusa el OAuth client y el redirect URI del login (/auth/callback,
    que distingue este flujo por `gmail_next` en la sesión) para no tener que
    registrar otra URI en Google Cloud."""
    usuario = db.get(Usuario, request.session.get("user_id") or 0)
    if not usuario or not usuario.activo:
        return RedirectResponse("/auth/login")
    if not settings.mail_token_enc_key:
        raise HTTPException(503, "Falta configurar MAIL_TOKEN_ENC_KEY en el server para poder conectar Gmail.")
    request.session["gmail_next"] = _destino_local(next)
    return await oauth.google.authorize_redirect(
        request,
        request.url_for("auth_callback"),
        scope=f"openid email {GMAIL_SCOPE}",
        access_type="offline",
        # sin prompt=consent Google no vuelve a mandar refresh token si el
        # usuario ya había autorizado antes
        prompt="consent",
        include_granted_scopes="true",
        login_hint=usuario.email,
    )


async def _callback_gmail(request: Request, db: Session) -> RedirectResponse:
    destino = request.session.pop("gmail_next")
    usuario = db.get(Usuario, request.session.get("user_id") or 0)
    if not usuario:
        return RedirectResponse("/auth/login")
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError:
        # canceló en la pantalla de Google (error=access_denied) o el state no cerró
        return RedirectResponse(_con_aviso(destino, "cancelado"))

    email = (token.get("userinfo") or {}).get("email", "")
    if email.lower() != usuario.email.lower():
        # eligió otra cuenta en el selector de Google: los mails tienen que
        # salir de la cuenta con la que está logueado en la app
        return RedirectResponse(_con_aviso(destino, "otra_cuenta"))
    if GMAIL_SCOPE not in token.get("scope", "").split() or not token.get("refresh_token"):
        # destildó el permiso de enviar mail en la pantalla de consentimiento
        return RedirectResponse(_con_aviso(destino, "sin_permiso"))

    usuario.gmail_refresh_token_enc = cifrar_token(token["refresh_token"])
    usuario.gmail_conectado_en = datetime.now(timezone.utc)
    db.commit()
    return RedirectResponse(_con_aviso(destino, "conectado"))


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/auth/login")
