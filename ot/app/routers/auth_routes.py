import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import DominioNoAutorizado, oauth, procesar_login
from app.db import get_db
from app.templating import templates

router = APIRouter(prefix="/auth")


@router.get("/login")
def login(request: Request):
    return templates.TemplateResponse(
        request, "auth/login.html", {"error_dominio": request.query_params.get("error") == "dominio"}
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
    redirect_uri = request.url_for("auth_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback", name="auth_callback")
async def callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    claims = token["userinfo"]

    try:
        usuario = procesar_login(db, claims)
    except DominioNoAutorizado:
        return RedirectResponse("/auth/login?error=dominio")

    request.session["user_id"] = usuario.id
    request.session["email"] = usuario.email
    request.session["nombre"] = usuario.nombre
    request.session["rol"] = usuario.rol.value
    destino = request.session.pop("next", "/tareas")
    return RedirectResponse(destino)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/auth/login")
