import re

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import cache
from app.db import get_db
from app.models import Responsable
from app.templating import templates

router = APIRouter()

_MAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MSG_MAIL = "Cargá un mail válido (ej. nombre@aleste.ar): no puede haber responsables sin mail."


def mail_valido(mail: str) -> bool:
    return bool(_MAIL_RE.match(mail))


def parse_ids(csv: str) -> set[int]:
    ids: set[int] = set()
    for chunk in csv.split(","):
        chunk = chunk.strip()
        if chunk.isdigit():
            ids.add(int(chunk))
    return ids


def combo_ctx(
    db: Session, seleccionados: set[int], abierto: bool = False,
    error: str | None = None, nombre_nuevo: str = "", mail_nuevo: str = "",
) -> dict:
    """Contexto para tareas/_campo_responsables.html: catálogo de responsables
    activos + cualquier inactivo ya seleccionado (para no perderlo de vista en
    una tarea vieja que lo tenía asignado)."""
    todos = list(cache.responsables_activos(db))
    faltantes = seleccionados - {r.id for r in todos}
    if faltantes:
        todos += list(
            db.scalars(select(Responsable).where(Responsable.id.in_(faltantes)).order_by(Responsable.nombre))
        )
    nombres_sel = [r.nombre for r in todos if r.id in seleccionados]
    return {
        "responsables_todos": todos,
        "resp_sel": seleccionados,
        "resp_sel_csv": ",".join(str(i) for i in sorted(seleccionados)),
        "resp_resumen": " / ".join(nombres_sel) if nombres_sel else "Sin responsables",
        "abierto": abierto,
        "error": error,
        "nombre_nuevo": nombre_nuevo,
        "mail_nuevo": mail_nuevo,
    }


@router.post("/api/responsables")
def crear_responsable(
    request: Request,
    db: Session = Depends(get_db),
    nombre: str = Form(""),
    mail: str = Form(""),
    responsable_ids: str = Form(""),
):
    seleccionados = parse_ids(responsable_ids)
    nombre = nombre.strip()
    mail = mail.strip()
    error = None
    if nombre:
        existente = db.scalar(select(Responsable).where(func.lower(Responsable.nombre) == nombre.lower()))
        if existente and existente.mail:
            existente.activo = True
            seleccionados.add(existente.id)
        elif not mail_valido(mail):
            # nuevo, o existente sin mail (legado): el mail es obligatorio
            error = MSG_MAIL
        elif existente:
            existente.activo = True
            existente.mail = mail
            seleccionados.add(existente.id)
        else:
            nuevo = Responsable(nombre=nombre, mail=mail, activo=True)
            db.add(nuevo)
            db.flush()
            seleccionados.add(nuevo.id)
        if error:
            db.rollback()
        else:
            db.commit()
            cache.invalidar_responsables()

    ctx = combo_ctx(
        db, seleccionados, abierto=True,
        error=error, nombre_nuevo=nombre if error else "", mail_nuevo=mail if error else "",
    )
    return templates.TemplateResponse(request, "tareas/_campo_responsables.html", ctx)


def _listar_todos(db: Session) -> list[Responsable]:
    return list(db.scalars(select(Responsable).order_by(Responsable.activo.desc(), Responsable.nombre)))


def _panel(request: Request, db: Session, error: str | None = None, nombre_nuevo: str = "", mail_nuevo: str = ""):
    return templates.TemplateResponse(
        request, "responsables/_panel.html",
        {"responsables": _listar_todos(db), "error": error, "nombre_nuevo": nombre_nuevo, "mail_nuevo": mail_nuevo},
    )


@router.get("/responsables")
def listar_responsables(request: Request, db: Session = Depends(get_db)):
    ctx = {"responsables": _listar_todos(db)}
    if request.headers.get("HX-Request"):
        # abierto como sheet apilada sobre otra sheet (ver "Gestionar
        # responsables" en tareas/_campo_responsables.html) — solo el
        # fragmento, no la pagina completa con su propio <html>/sidebar.
        return templates.TemplateResponse(request, "responsables/_sheet.html", ctx)
    return templates.TemplateResponse(request, "responsables/list.html", ctx)


@router.post("/responsables")
def crear_responsable_admin(
    request: Request, db: Session = Depends(get_db), nombre: str = Form(""), mail: str = Form("")
):
    nombre, mail = nombre.strip(), mail.strip()
    if not nombre:
        return _panel(request, db)
    if db.scalar(select(Responsable).where(func.lower(Responsable.nombre) == nombre.lower())):
        return _panel(request, db, f"Ya existe un responsable llamado «{nombre}».", nombre, mail)
    if not mail_valido(mail):
        return _panel(request, db, MSG_MAIL, nombre, mail)
    db.add(Responsable(nombre=nombre, mail=mail, activo=True))
    db.commit()
    cache.invalidar_responsables()
    return _panel(request, db)


@router.post("/responsables/{responsable_id}/renombrar")
def renombrar_responsable(
    responsable_id: int, request: Request, db: Session = Depends(get_db), nombre: str = Form("")
):
    r = db.get(Responsable, responsable_id)
    nombre = nombre.strip()
    if r and nombre:
        r.nombre = nombre
        db.commit()
        cache.invalidar_responsables()
    return _panel(request, db)


@router.post("/responsables/{responsable_id}/mail")
def editar_mail_responsable(
    responsable_id: int, request: Request, db: Session = Depends(get_db), mail: str = Form("")
):
    r = db.get(Responsable, responsable_id)
    mail = mail.strip()
    if r and not mail_valido(mail):
        return _panel(request, db, f"{r.nombre}: {MSG_MAIL}")
    if r:
        r.mail = mail
        db.commit()
        cache.invalidar_responsables()
    return _panel(request, db)


@router.post("/responsables/{responsable_id}/toggle")
def toggle_responsable(responsable_id: int, request: Request, db: Session = Depends(get_db)):
    r = db.get(Responsable, responsable_id)
    if r:
        r.activo = not r.activo
        db.commit()
        cache.invalidar_responsables()
    return _panel(request, db)
