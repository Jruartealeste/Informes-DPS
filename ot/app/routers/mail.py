import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app import gmail_client
from app.db import get_db
from app.gmail_client import GmailError, GmailNoConectado, GmailNoConfigurado, GmailTokenRevocado, enviar_mail
from app.models import EstadoMail, Tarea, TareaMail, Usuario
from app.routers.tareas import cargar_tarea_con_relaciones, contexto_detalle
from app.templating import templates
from app.viewmodels import tarea_vm

router = APIRouter()


def _asunto_sugerido(det: dict) -> str:
    partes = [p for p in [det["otN"], det["ot_cliente"], det["tipos_label"] if det["tipos"] else None] if p]
    return " · ".join(partes) if partes else det["detalle"][:80]


def _usuario(request: Request, db: Session) -> Usuario:
    # AuthMiddleware ya garantizó sesión con un usuario activo
    return db.get(Usuario, request.session["user_id"])


def _cuerpo_sugerido(det: dict, firma: str) -> str:
    lineas = [
        f"OT: {det['otN']} — {det['ot_cliente']}",
        f"Fecha de pedido: {det['fecha_pedido']}",
        "",
        det["detalle"],
    ]
    links = det["links_drive"]
    if len(links) == 1:
        lineas += ["", f"Link Drive: {links[0]}"]
    elif links:
        lineas += ["", "Links:"] + [f"- {x}" for x in links]
    lineas += ["", "Saludos,", firma]
    return "\n".join(lineas)


def _ultimo_borrador(tarea: Tarea) -> TareaMail | None:
    """El primer BORRADOR en tarea.mails — la relación ya viene ordenada
    por enviado_en desc, así que es el más reciente."""
    return next((m for m in tarea.mails if m.estado == EstadoMail.BORRADOR), None)


def _mail_de_cadena(tarea: Tarea) -> TareaMail | None:
    """El último mail ENVIADO de la tarea que guardó threadId y Message-ID
    (tarea.mails viene ordenada por enviado_en desc). Los enviados antes de
    existir el encadenado no los tienen y no sirven para colgar un mail.
    Puede haberlo mandado otro usuario: ver _ancla_cadena."""
    return next(
        (m for m in tarea.mails
         if m.estado == EstadoMail.ENVIADO and m.gmail_thread_id and m.rfc_message_id),
        None,
    )


def _ancla_cadena(anterior: TareaMail, usuario: Usuario) -> tuple[str | None, str]:
    """(threadId, Message-ID) para enviar_mail. El threadId es de la casilla
    de quien mandó el anterior: si fue otro usuario no existe en la del que
    manda ahora, y la cadena se arma solo con In-Reply-To/References."""
    thread_id = anterior.gmail_thread_id if anterior.remitente == usuario.email else None
    return thread_id, anterior.rfc_message_id


def _asunto_en_cadena(anterior: TareaMail) -> str:
    base = re.sub(r"^(re:\s*)+", "", anterior.asunto, flags=re.IGNORECASE).strip()
    return f"Re: {base}"


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
    usuario: Usuario,
    tarea_id: int,
    asunto: str | None = None,
    cuerpo: str | None = None,
    seleccionados: set[int] | None = None,
    error: str | None = None,
    misma_cadena: bool | None = None,
) -> dict:
    tarea = cargar_tarea_con_relaciones(db, tarea_id)
    det = tarea_vm(tarea)
    con_mail = [r for r in det["responsables_con_mail"] if r["mail"]]
    sin_mail = [r for r in det["responsables_con_mail"] if not r["mail"]]

    # al abrir el composer de cero (sin nada tipeado todavía), si ya había
    # un borrador guardado se retoma ese texto en vez de regenerar el
    # template — así no se pierde lo redactado a mano.
    borrador = _ultimo_borrador(tarea) if asunto is None and cuerpo is None else None

    anterior = _mail_de_cadena(tarea)
    asunto_libre = asunto if asunto is not None else (borrador.asunto if borrador else _asunto_sugerido(det))
    # tildado por defecto al abrir; al re-renderizar por error se respeta lo que había elegido
    en_cadena = anterior is not None and (misma_cadena is None or misma_cadena)

    return {
        "det": det,
        "cadena": (
            {"asunto": _asunto_en_cadena(anterior)}
            if anterior else None
        ),
        "misma_cadena": en_cadena,
        "asunto_libre": asunto_libre,
        "con_mail": con_mail,
        "sin_mail": sin_mail,
        "seleccionados": (
            seleccionados if seleccionados is not None else {r["id"] for r in con_mail + sin_mail}
        ),
        "asunto": _asunto_en_cadena(anterior) if en_cadena else asunto_libre,
        "cuerpo": cuerpo if cuerpo is not None else (borrador.cuerpo if borrador else _cuerpo_sugerido(det, usuario.nombre)),
        "error": error,
        "remitente": usuario.email,
        "gmail_conectado": bool(usuario.gmail_refresh_token_enc),
    }


@router.get("/tareas/{tarea_id}/mail")
def form_mail(tarea_id: int, request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "tareas/_mail_sheet.html", _sheet_ctx(db, _usuario(request, db), tarea_id))


@router.post("/tareas/{tarea_id}/mail")
def enviar_mail_tarea(
    tarea_id: int,
    request: Request,
    db: Session = Depends(get_db),
    asunto: str = Form(...),
    cuerpo: str = Form(...),
    destinatario_ids: list[str] = Form([]),
    accion: str = Form("enviar"),
    misma_cadena: str = Form(""),
):
    usuario = _usuario(request, db)
    tarea = cargar_tarea_con_relaciones(db, tarea_id)
    ids_sel = {int(x) for x in destinatario_ids if x.isdigit()}
    mails, etiqueta = _destinatarios(tarea, ids_sel)
    anterior = _mail_de_cadena(tarea)
    en_cadena = bool(misma_cadena) and anterior is not None
    if en_cadena:
        asunto = _asunto_en_cadena(anterior)

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
            db, usuario, tarea_id, asunto=asunto, cuerpo=cuerpo, seleccionados=ids_sel,
            misma_cadena=en_cadena,
            error="Elegí al menos un destinatario con mail cargado para enviar — mientras tanto podés guardar como borrador.",
        )
        return templates.TemplateResponse(request, "tareas/_mail_sheet.html", ctx)

    registro = TareaMail(
        tarea_id=tarea_id, destinatarios=", ".join(mails), asunto=asunto, cuerpo=cuerpo, remitente=usuario.email
    )
    try:
        enviado = enviar_mail(
            usuario, mails, asunto, cuerpo,
            en_cadena=_ancla_cadena(anterior, usuario) if en_cadena else None,
        )
        registro.gmail_message_id = enviado.gmail_message_id
        registro.gmail_thread_id = enviado.gmail_thread_id
        registro.rfc_message_id = enviado.rfc_message_id
        registro.estado = EstadoMail.ENVIADO
    except GmailNoConectado as e:
        # el botón ya viene deshabilitado sin conexión; no se registra intento
        ctx = _sheet_ctx(db, usuario, tarea_id, asunto=asunto, cuerpo=cuerpo, seleccionados=ids_sel, misma_cadena=en_cadena, error=str(e))
        return templates.TemplateResponse(request, "tareas/_mail_sheet.html", ctx)
    except (GmailNoConfigurado, GmailError) as e:
        if isinstance(e, GmailTokenRevocado):
            # el token guardado ya no sirve: que el composer ofrezca reconectar
            gmail_client.desconectar(usuario)
        registro.estado = EstadoMail.ERROR
        registro.error_detalle = str(e)
        db.add(registro)
        db.commit()
        ctx = _sheet_ctx(db, usuario, tarea_id, asunto=asunto, cuerpo=cuerpo, seleccionados=ids_sel, misma_cadena=en_cadena, error=str(e))
        return templates.TemplateResponse(request, "tareas/_mail_sheet.html", ctx)

    db.add(registro)
    db.commit()

    # se mandó bien: el contenido principal (vacío) cierra la sheet del
    # composer al swappear en #sheet-2-root (mismo patrón que
    # _tabla_y_cerrar_drawer en tareas.py); el OOB refresca el drawer de
    # abajo para que se vea el mail nuevo en el historial.
    drawer_html = templates.env.get_template("tareas/_detalle.html").render(contexto_detalle(db, tarea_id))
    return HTMLResponse(f'<div id="drawer-root" hx-swap-oob="true">{drawer_html}</div>')


@router.post("/tareas/{tarea_id}/mail/desconectar-gmail")
def desconectar_gmail(
    tarea_id: int,
    request: Request,
    db: Session = Depends(get_db),
    asunto: str | None = Form(None),
    cuerpo: str | None = Form(None),
    destinatario_ids: list[str] = Form([]),
    misma_cadena: str = Form(""),
):
    """Desde el composer: borra la conexión de Gmail del usuario logueado y
    vuelve a mostrar el composer con lo que ya estaba escrito."""
    usuario = _usuario(request, db)
    gmail_client.desconectar(usuario)
    db.commit()
    ctx = _sheet_ctx(
        db, usuario, tarea_id, asunto=asunto, cuerpo=cuerpo,
        seleccionados={int(x) for x in destinatario_ids if x.isdigit()} if asunto is not None else None,
        misma_cadena=bool(misma_cadena) if asunto is not None else None,
    )
    return templates.TemplateResponse(request, "tareas/_mail_sheet.html", ctx)
