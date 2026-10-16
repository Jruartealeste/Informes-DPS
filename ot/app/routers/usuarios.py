"""Pantalla "Usuarios" (solo ADMIN, 2026-10-14): rol y alta/baja de quienes
entran a la app. No hay alta manual: el usuario se crea solo en su primer
login con una cuenta @aleste.ar (app/auth.py::procesar_login); acá se le
cambia el rol o se lo desactiva (baja = activo=False, nunca borrar, así
quedan sus referencias)."""

from datetime import timedelta, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import requiere_admin
from app.db import get_db
from app.models import RolUsuario, Usuario
from app.routers.clientes import _contadores_sidebar
from app.templating import templates

router = APIRouter()

ROLES = {
    RolUsuario.MIEMBRO: "Miembro",
    RolUsuario.APROBADOR_FACTURACION: "Aprobador de facturación",
    RolUsuario.ADMIN: "Admin",
}

_AR = timezone(timedelta(hours=-3))  # Argentina, UTC-3 fijo (sin horario de verano)


def _fecha(dt) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:  # sqlite (tests) devuelve naive; se guardó en UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_AR).strftime("%d/%m/%Y %H:%M")


def _usuario_o_404(db: Session, usuario_id: int) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(404, "Usuario no encontrado.")
    return usuario


@router.get("/usuarios")
def listado_usuarios(request: Request, db: Session = Depends(get_db), yo: Usuario = Depends(requiere_admin)):
    usuarios = list(db.scalars(select(Usuario).order_by(Usuario.activo.desc(), Usuario.nombre)))
    filas = [{"u": u, "ultimo_login": _fecha(u.ultimo_login), "soy_yo": u.id == yo.id} for u in usuarios]
    return templates.TemplateResponse(
        request,
        "usuarios/list.html",
        {
            "filas": filas,
            "roles": ROLES,
            **_contadores_sidebar(request, db),
            "seccion_activa": "usuarios",
            "tema": request.cookies.get("tema", "dark"),
            "densidad": request.cookies.get("densidad", "1") != "0",
        },
    )


@router.post("/usuarios/{usuario_id}/rol")
def cambiar_rol(
    usuario_id: int,
    db: Session = Depends(get_db),
    yo: Usuario = Depends(requiere_admin),
    rol: str = Form(""),
):
    try:
        nuevo = RolUsuario(rol)
    except ValueError:
        raise HTTPException(422, "Rol desconocido.")
    usuario = _usuario_o_404(db, usuario_id)
    # Un ADMIN no puede sacarse el rol a sí mismo: así siempre queda al menos
    # uno (quien hace el cambio) y nadie se deja afuera de esta pantalla.
    if usuario.id == yo.id and nuevo != RolUsuario.ADMIN:
        raise HTTPException(409, "No podés quitarte el rol de Admin a vos mismo; pedíselo a otro Admin.")
    usuario.rol = nuevo
    db.commit()
    return RedirectResponse("/usuarios", status_code=303)


@router.post("/usuarios/{usuario_id}/desactivar")
def desactivar_usuario(usuario_id: int, db: Session = Depends(get_db), yo: Usuario = Depends(requiere_admin)):
    """Rige en el próximo request de esa persona: AuthMiddleware valida
    `activo` contra la base en cada request y le cierra la sesión."""
    usuario = _usuario_o_404(db, usuario_id)
    if usuario.id == yo.id:
        raise HTTPException(409, "No podés desactivarte a vos mismo.")
    usuario.activo = False
    db.commit()
    return RedirectResponse("/usuarios", status_code=303)


@router.post("/usuarios/{usuario_id}/reactivar")
def reactivar_usuario(usuario_id: int, db: Session = Depends(get_db), _: Usuario = Depends(requiere_admin)):
    usuario = _usuario_o_404(db, usuario_id)
    usuario.activo = True
    db.commit()
    return RedirectResponse("/usuarios", status_code=303)
