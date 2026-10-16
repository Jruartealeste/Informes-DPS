from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.anunciantes import corresponde
from app.auth import requiere_admin
from app.cliente_ctx import COOKIE_CLIENTE
from app.db import get_db
from app.models import Cliente, ClienteAnunciante, OrdenTrabajoEspejo, OtInterna, ProductoAdvertys, Usuario
from app.templating import templates

router = APIRouter()


@router.get("/clientes/{cliente_id}/activar")
def activar_cliente(cliente_id: int, request: Request, db: Session = Depends(get_db)):
    if not db.get(Cliente, cliente_id):
        raise HTTPException(404, "Cliente no encontrado")
    destino = request.headers.get("referer") or "/tareas"
    resp = RedirectResponse(destino, status_code=303)
    resp.set_cookie(COOKIE_CLIENTE, str(cliente_id), max_age=31536000, path="/")
    return resp


# ---- Pantalla "Anunciantes" (ABM de clientes, solo ADMIN, 2026-10-14) ----
# En la UI se llaman "anunciantes" (como el selector del sidebar); en el código
# son `Cliente`, que se relaciona con uno o varios Anunciantes reales de
# Advertys (`ClienteAnunciante`).


def _anunciantes_advertys(db: Session) -> list[str]:
    """Nombres de Anunciante que existen en Advertys según lo sincronizado
    (catálogo de Productos y espejo de OT), más los ya relacionados a mano."""
    nombres = set(db.scalars(select(ProductoAdvertys.anunciante).distinct()))
    nombres |= {n for n in db.scalars(select(OrdenTrabajoEspejo.anunciante).distinct()) if n}
    nombres |= set(db.scalars(select(ClienteAnunciante.anunciante).distinct()))
    return sorted(nombres, key=str.lower)


def _parsear_numero_inicial(valor: str) -> int | None:
    valor = valor.strip()
    if not valor:
        return None
    if not valor.isdigit() or int(valor) < 1:
        raise HTTPException(422, "El número inicial de OT tiene que ser un entero positivo.")
    return int(valor)


def _guardar(db: Session, cliente: Cliente, nombre: str, numero_ot_inicial: str, anunciantes: list[str]) -> None:
    nombre = " ".join(nombre.split())
    if not nombre:
        raise HTTPException(422, "Falta el nombre del anunciante.")
    if len(nombre) > 80:
        raise HTTPException(422, "El nombre puede tener hasta 80 caracteres.")
    duplicado = db.scalar(
        select(Cliente.id).where(func.lower(Cliente.nombre) == nombre.lower(), Cliente.id != (cliente.id or 0))
    )
    if duplicado:
        raise HTTPException(422, f"Ya existe un anunciante llamado «{nombre}».")
    cliente.nombre = nombre
    cliente.numero_ot_inicial = _parsear_numero_inicial(numero_ot_inicial)
    elegidos = {a.strip() for a in anunciantes if a.strip()}
    for rel in list(cliente.anunciantes):
        if rel.anunciante not in elegidos:
            db.delete(rel)
    actuales = {rel.anunciante for rel in cliente.anunciantes}
    for a in sorted(elegidos - actuales):
        cliente.anunciantes.append(ClienteAnunciante(anunciante=a))


def _contadores_sidebar(request: Request, db: Session) -> dict:
    """Los badges de Tareas / OT internas del sidebar (las demás páginas los
    pasan igual: total de tareas, OT internas del anunciante elegido)."""
    from app.cliente_ctx import cliente_activo
    from app.routers.ordenes_trabajo import _total_tareas

    actual = cliente_activo(request, db)
    total_ots = db.scalar(
        select(func.count()).select_from(OtInterna).where(OtInterna.cliente_id == (actual.id if actual else None))
    )
    return {"total_tareas": _total_tareas(db), "total_ots": total_ots or 0}


def _contexto_form(request: Request, db: Session, cliente: Cliente | None) -> dict:
    from app.routers.ordenes_trabajo import siguiente_numero_interno

    return {
        **_contadores_sidebar(request, db),
        "c": cliente,
        "relacionados": {a.anunciante for a in cliente.anunciantes} if cliente else set(),
        "anunciantes_advertys": _anunciantes_advertys(db),
        "proximo_numero": siguiente_numero_interno(db, cliente) if cliente and cliente.id else None,
        "seccion_activa": "anunciantes",
        "tema": request.cookies.get("tema", "dark"),
        "densidad": request.cookies.get("densidad", "1") != "0",
    }


@router.get("/anunciantes")
def listado_anunciantes(request: Request, db: Session = Depends(get_db), _: Usuario = Depends(requiere_admin)):
    from app.routers.ordenes_trabajo import siguiente_numero_interno

    clientes = list(db.scalars(select(Cliente).options(selectinload(Cliente.anunciantes)).order_by(Cliente.nombre)))
    n_ots = dict(db.execute(select(OtInterna.cliente_id, func.count()).group_by(OtInterna.cliente_id)).all())
    filas = [
        {
            "c": c,
            "n_ots": n_ots.get(c.id, 0),
            "proximo_numero": siguiente_numero_interno(db, c),
        }
        for c in clientes
    ]
    return templates.TemplateResponse(
        request,
        "clientes/list.html",
        {
            "filas": filas,
            **_contadores_sidebar(request, db),
            "seccion_activa": "anunciantes",
            "tema": request.cookies.get("tema", "dark"),
            "densidad": request.cookies.get("densidad", "1") != "0",
        },
    )


@router.get("/anunciantes/sugeridos")
def anunciantes_sugeridos(nombre: str = "", db: Session = Depends(get_db), _: Usuario = Depends(requiere_admin)):
    """Anunciantes de Advertys que corresponden a un nombre (misma inferencia
    que el combo Producto, app/anunciantes.py: palabras o siglas)."""
    return [a for a in _anunciantes_advertys(db) if corresponde(nombre, a)]


@router.get("/anunciantes/nuevo")
def form_nuevo_anunciante(request: Request, db: Session = Depends(get_db), _: Usuario = Depends(requiere_admin)):
    return templates.TemplateResponse(request, "clientes/form.html", _contexto_form(request, db, None))


@router.post("/anunciantes")
def crear_anunciante(
    db: Session = Depends(get_db),
    _: Usuario = Depends(requiere_admin),
    nombre: str = Form(""),
    numero_ot_inicial: str = Form(""),
    anunciantes: list[str] = Form([]),
):
    cliente = Cliente(nombre="", activo=True)
    _guardar(db, cliente, nombre, numero_ot_inicial, anunciantes)
    db.add(cliente)
    db.commit()
    return RedirectResponse("/anunciantes", status_code=303)


def _cliente_o_404(db: Session, cliente_id: int) -> Cliente:
    cliente = db.get(Cliente, cliente_id)
    if cliente is None:
        raise HTTPException(404, "Anunciante no encontrado.")
    return cliente


@router.get("/anunciantes/{cliente_id}")
def form_editar_anunciante(
    cliente_id: int, request: Request, db: Session = Depends(get_db), _: Usuario = Depends(requiere_admin)
):
    return templates.TemplateResponse(
        request, "clientes/form.html", _contexto_form(request, db, _cliente_o_404(db, cliente_id))
    )


@router.post("/anunciantes/{cliente_id}")
def editar_anunciante(
    cliente_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(requiere_admin),
    nombre: str = Form(""),
    numero_ot_inicial: str = Form(""),
    anunciantes: list[str] = Form([]),
):
    cliente = _cliente_o_404(db, cliente_id)
    _guardar(db, cliente, nombre, numero_ot_inicial, anunciantes)
    db.commit()
    return RedirectResponse("/anunciantes", status_code=303)


@router.post("/anunciantes/{cliente_id}/desactivar")
def desactivar_anunciante(cliente_id: int, db: Session = Depends(get_db), _: Usuario = Depends(requiere_admin)):
    """Baja = solo lectura (nunca se borra): sale del selector del sidebar y no
    admite cambios (app/cliente_ctx.SoloLecturaMiddleware); el historial
    queda consultable desde esta pantalla."""
    cliente = _cliente_o_404(db, cliente_id)
    activos = db.scalar(select(func.count()).select_from(Cliente).where(Cliente.activo.is_(True))) or 0
    if cliente.activo and activos <= 1:
        raise HTTPException(409, "No se puede desactivar el único anunciante activo.")
    cliente.activo = False
    db.commit()
    return RedirectResponse("/anunciantes", status_code=303)


@router.post("/anunciantes/{cliente_id}/reactivar")
def reactivar_anunciante(cliente_id: int, db: Session = Depends(get_db), _: Usuario = Depends(requiere_admin)):
    cliente = _cliente_o_404(db, cliente_id)
    cliente.activo = True
    db.commit()
    return RedirectResponse("/anunciantes", status_code=303)
