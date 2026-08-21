from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.gmail_client import GmailError, GmailNoConfigurado, enviar_mail
from app.models import EstadoMail, Tarea, TareaMail
from app.routers.tareas import cargar_tarea_con_relaciones, contexto_detalle
from app.templating import templates
from app.viewmodels import tarea_vm

router = APIRouter()


def _asunto_sugerido(det: dict) -> str:
    partes = [p for p in [det["otN"], det["ot_cliente"], det["tipos_label"] if det["tipos"] else None] if p]
    return " · ".join(partes) if partes else det["detalle"][:80]


def _cuerpo_sugerido(det: dict) -> str:
    lineas = [
        f"OT: {det['otN']} — {det['ot_cliente']}",
        f"Fecha de pedido: {det['fecha_pedido']}",
        "",
        det["detalle"],
    ]
    if det["link_drive"]:
        lineas += ["", f"Link Drive: {det['link_drive']}"]
    lineas += ["", "Saludos,", settings.gmail_sender_nombre]
    return "\n".join(lineas)


def _ultimo_borrador(tarea: Tarea) -> TareaMail | None:
    """El primer BORRADOR en tarea.mails — la relación ya viene ordenada
    por enviado_en desc, así que es el más reciente."""
    return next((m for m in tarea.mails if m.estado == EstadoMail.BORRADOR), None)


def _destinatarios(tarea: Tarea, ids_sel: set[int]) -> tuple[list[str], str]:
    """(mails, etiqueta) de los responsables tildados. La etiqueta incluye
    también a los que todavía no tienen mail cargado — sirve para dejar
    registrado a quién estaba dirigido un borrador, aunque hoy no se les
    pueda mandar nada."""
    con_mail: list[str] = []
    sin_mail: list[str] = []
    for r in tarea.responsables:
        if r.responsable_id not in ids_sel:
            continue
        if r.responsable.mail:
            con_mail.append(r.responsable.mail)
        else:
            sin_mail.append(r.responsable.nombre)
    con_mail = sorted(set(con_mail))
    partes = list(con_mail)
    if sin_mail:
        partes.append(f"{', '.join(sorted(sin_mail))} (sin mail cargado)")
    return con_mail, "; ".join(partes) if partes else "(sin destinatarios elegidos)"


def _sheet_ctx(
    db: Session,
    tarea_id: int,
    asunto: str | None = None,
    cuerpo: str | None = None,
    seleccionados: set[int] | None = None,
    error: str | None = None,
) -> dict:
    tarea = cargar_tarea_con_relaciones(db, tarea_id)
    det = tarea_vm(tarea)
    con_mail = [r for r in det["responsables_con_mail"] if r["mail"]]
    sin_mail = [r for r in det["responsables_con_mail"] if not r["mail"]]

    # al abrir el composer de cero (sin nada tipeado todavía), si ya había
    # un borrador guardado se retoma ese texto en vez de regenerar el
    # template — así no se pierde lo redactado a mano.
    borrador = _ultimo_borrador(tarea) if asunto is None and cuerpo is None else None

    return {
        "det": det,
        "con_mail": con_mail,
        "sin_mail": sin_mail,
        "seleccionados": (
            seleccionados if seleccionados is not None else {r["id"] for r in con_mail + sin_mail}
        ),
        "asunto": asunto if asunto is not None else (borrador.asunto if borrador else _asunto_sugerido(det)),
        "cuerpo": cuerpo if cuerpo is not None else (borrador.cuerpo if borrador else _cuerpo_sugerido(det)),
        "error": error,
    }


@router.get("/tareas/{tarea_id}/mail")
def form_mail(tarea_id: int, request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "tareas/_mail_sheet.html", _sheet_ctx(db, tarea_id))


@router.post("/tareas/{tarea_id}/mail")
def enviar_mail_tarea(
    tarea_id: int,
    request: Request,
    db: Session = Depends(get_db),
    asunto: str = Form(...),
    cuerpo: str = Form(...),
    destinatario_ids: list[str] = Form([]),
    accion: str = Form("enviar"),
):
    tarea = cargar_tarea_con_relaciones(db, tarea_id)
    ids_sel = {int(x) for x in destinatario_ids if x.isdigit()}
    mails, etiqueta = _destinatarios(tarea, ids_sel)

    if accion == "borrador":
        registro = TareaMail(
            tarea_id=tarea_id, destinatarios=etiqueta, asunto=asunto, cuerpo=cuerpo, estado=EstadoMail.BORRADOR
        )
        db.add(registro)
        db.commit()
        drawer_html = templates.env.get_template("tareas/_detalle.html").render(contexto_detalle(db, tarea_id))
        return HTMLResponse(f'<div id="drawer-root" hx-swap-oob="true">{drawer_html}</div>')

    if not mails:
        ctx = _sheet_ctx(
            db, tarea_id, asunto=asunto, cuerpo=cuerpo, seleccionados=ids_sel,
            error="Elegí al menos un destinatario con mail cargado para enviar — mientras tanto podés guardar como borrador.",
        )
        return templates.TemplateResponse(request, "tareas/_mail_sheet.html", ctx)

    registro = TareaMail(tarea_id=tarea_id, destinatarios=", ".join(mails), asunto=asunto, cuerpo=cuerpo)
    try:
        registro.gmail_message_id = enviar_mail(mails, asunto, cuerpo)
        registro.estado = EstadoMail.ENVIADO
    except (GmailNoConfigurado, GmailError) as e:
        registro.estado = EstadoMail.ERROR
        registro.error_detalle = str(e)
        db.add(registro)
        db.commit()
        ctx = _sheet_ctx(db, tarea_id, asunto=asunto, cuerpo=cuerpo, seleccionados=ids_sel, error=str(e))
        return templates.TemplateResponse(request, "tareas/_mail_sheet.html", ctx)

    db.add(registro)
    db.commit()

    # se mandó bien: el contenido principal (vacío) cierra la sheet del
    # composer al swappear en #sheet-2-root (mismo patrón que
    # _tabla_y_cerrar_drawer en tareas.py); el OOB refresca el drawer de
    # abajo para que se vea el mail nuevo en el historial.
    drawer_html = templates.env.get_template("tareas/_detalle.html").render(contexto_detalle(db, tarea_id))
    return HTMLResponse(f'<div id="drawer-root" hx-swap-oob="true">{drawer_html}</div>')
