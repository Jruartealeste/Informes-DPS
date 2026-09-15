from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
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
