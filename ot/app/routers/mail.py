from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.gmail_client import GmailError, GmailNoConfigurado, enviar_mail
from app.models import EstadoMail, TareaMail
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
    return {
        "det": det,
        "con_mail": con_mail,
        "sin_mail": sin_mail,
        "seleccionados": seleccionados if seleccionados is not None else {r["id"] for r in con_mail},
        "asunto": asunto if asunto is not None else _asunto_sugerido(det),
        "cuerpo": cuerpo if cuerpo is not None else _cuerpo_sugerido(det),
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
):
    tarea = cargar_tarea_con_relaciones(db, tarea_id)
    ids_sel = {int(x) for x in destinatario_ids if x.isdigit()}
    mails = sorted(
        {r.responsable.mail for r in tarea.responsables if r.responsable_id in ids_sel and r.responsable.mail}
    )

    if not mails:
        ctx = _sheet_ctx(
            db, tarea_id, asunto=asunto, cuerpo=cuerpo, seleccionados=ids_sel,
            error="Elegí al menos un destinatario con mail cargado.",
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
