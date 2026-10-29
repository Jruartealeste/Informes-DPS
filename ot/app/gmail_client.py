"""Envío de mail vía Gmail API desde la cuenta del usuario logueado (ver
"Mail a responsables" en CLAUDE.md). Cada usuario conecta su Gmail una vez
("Conectar Gmail", flujo OAuth en auth_routes.py, scope gmail.send) y su
refresh token queda cifrado en `usuarios.gmail_refresh_token_enc` con
MAIL_TOKEN_ENC_KEY. El OAuth client es el mismo del login, que es el que
emitió el token y por lo tanto el único que lo puede renovar.
"""

import base64
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid
from typing import NamedTuple

import httpx
from cryptography.fernet import Fernet, InvalidToken
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from app.config import settings
from app.models import Usuario

GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.send"


class GmailNoConfigurado(Exception):
    """Falta MAIL_TOKEN_ENC_KEY en el .env del server."""


class GmailNoConectado(Exception):
    """El usuario logueado todavía no conectó su cuenta de Gmail."""


class GmailError(Exception):
    """El envío se intentó pero Google lo rechazó (destinatario inválido,
    cuota, etc.)."""


class GmailTokenRevocado(GmailError):
    """El refresh token ya no sirve (se revocó el acceso desde la cuenta de
    Google): hay que volver a conectar."""


def _fernet() -> Fernet:
    if not settings.mail_token_enc_key:
        raise GmailNoConfigurado(
            "Falta configurar MAIL_TOKEN_ENC_KEY en el .env del server para poder mandar mails."
        )
    return Fernet(settings.mail_token_enc_key)


def cifrar_token(refresh_token: str) -> str:
    return _fernet().encrypt(refresh_token.encode()).decode("ascii")


def _descifrar_token(token_enc: str) -> str:
    try:
        return _fernet().decrypt(token_enc.encode()).decode()
    except InvalidToken as e:
        # cambió MAIL_TOKEN_ENC_KEY: el token guardado ya no se puede leer
        raise GmailTokenRevocado("No se pudo leer tu conexión con Gmail — volvé a conectarla.") from e


def desconectar(usuario: Usuario) -> None:
    """Borra el token del usuario (el llamador hace commit) y, de paso, le
    pide a Google que revoque el permiso para que la app deje de figurar en
    la cuenta. Si eso falla (ya revocado, sin red) se borra igual."""
    if usuario.gmail_refresh_token_enc:
        try:
            httpx.post(
                "https://oauth2.googleapis.com/revoke",
                data={"token": _descifrar_token(usuario.gmail_refresh_token_enc)},
                timeout=10,
            )
        except (httpx.HTTPError, GmailNoConfigurado, GmailError):
            pass
    usuario.gmail_refresh_token_enc = None
    usuario.gmail_conectado_en = None


def _credenciales(usuario: Usuario) -> Credentials:
    if not usuario.gmail_refresh_token_enc:
        raise GmailNoConectado("Conectá tu cuenta de Gmail para poder mandar mails.")
    refresh_token = _descifrar_token(usuario.gmail_refresh_token_enc)

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=settings.auth_google_client_id,
        client_secret=settings.auth_google_client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=[GMAIL_SCOPE],
    )
    try:
        creds.refresh(Request())
    except RefreshError as e:
        raise GmailTokenRevocado(f"Se perdió el acceso a tu Gmail, volvé a conectarlo ({e}).") from e
    return creds


class MailEnviado(NamedTuple):
    gmail_message_id: str
    gmail_thread_id: str | None
    rfc_message_id: str


def enviar_mail(
    usuario: Usuario,
    destinatarios: list[str],
    asunto: str,
    cuerpo: str,
    en_cadena: tuple[str | None, str] | None = None,
    adjuntos: list[tuple[str, str, bytes]] | None = None,
) -> MailEnviado:
    """Manda el mail desde la cuenta de `usuario`. `en_cadena` = (threadId
    de Gmail o None, Message-ID RFC del mail anterior) para colgarlo de la
    misma conversación: el threadId solo existe en la casilla de quien mandó
    el anterior, así que si fue otro usuario va None y la cadena queda
    armada solo por In-Reply-To/References (que es lo que ven los
    destinatarios). Gmail además exige que el asunto coincida con el de la
    cadena. Levanta GmailNoConfigurado, GmailNoConectado o GmailError si
    algo falla — el llamador decide cómo guardar el resultado (ver
    TareaMail.estado)."""
    creds = _credenciales(usuario)

    rfc_id = make_msgid(domain=usuario.email.split("@")[-1])
    if adjuntos:
        msg = MIMEMultipart()
        msg.attach(MIMEText(cuerpo))
        for nombre, tipo, datos in adjuntos:
            principal, _, sub = tipo.partition("/")
            parte = MIMEBase(principal or "application", sub or "octet-stream")
            parte.set_payload(datos)
            encoders.encode_base64(parte)
            parte.add_header("Content-Disposition", "attachment", filename=("utf-8", "", nombre))
            msg.attach(parte)
    else:
        msg = MIMEText(cuerpo)
    msg["To"] = ", ".join(destinatarios)
    msg["From"] = formataddr((usuario.nombre, usuario.email))
    msg["Subject"] = asunto
    msg["Message-ID"] = rfc_id
    payload: dict = {}
    if en_cadena:
        thread_id, rfc_anterior = en_cadena
        msg["In-Reply-To"] = rfc_anterior
        msg["References"] = rfc_anterior
        if thread_id:
            payload["threadId"] = thread_id
    payload["raw"] = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

    resp = httpx.post(
        GMAIL_SEND_URL,
        headers={"Authorization": f"Bearer {creds.token}"},
        json=payload,
        timeout=15,
    )
    if resp.status_code >= 400:
        raise GmailError(f"Gmail devolvió {resp.status_code}: {resp.text}")

    data = resp.json()
    return MailEnviado(data["id"], data.get("threadId"), rfc_id)
