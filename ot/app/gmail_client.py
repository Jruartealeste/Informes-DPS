"""Envío de mail vía Gmail API, usando el refresh token de un único
remitente fijo (ver "Mail a responsables" en CLAUDE.md — Fase 1: solo vos,
no hay noción de usuario de la app todavía). El refresh token se obtiene
una vez con scripts/gmail_authorize.py y se guarda en el .env del server.
"""

import base64
from email.mime.text import MIMEText

import httpx
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from app.config import settings

GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class GmailNoConfigurado(Exception):
    """Faltan credenciales en el .env — ver scripts/gmail_authorize.py."""


class GmailError(Exception):
    """El envío se intentó pero Google lo rechazó (token revocado,
    destinatario inválido, cuota, etc.)."""


def _credenciales() -> Credentials:
    faltantes = [
        nombre
        for nombre, valor in [
            ("GOOGLE_CLIENT_ID", settings.google_client_id),
            ("GOOGLE_CLIENT_SECRET", settings.google_client_secret),
            ("GMAIL_REFRESH_TOKEN", settings.gmail_refresh_token),
            ("GMAIL_SENDER_EMAIL", settings.gmail_sender_email),
        ]
        if not valor
    ]
    if faltantes:
        raise GmailNoConfigurado(
            "Falta configurar en .env: " + ", ".join(faltantes) + ". Correr scripts/gmail_authorize.py."
        )

    creds = Credentials(
        token=None,
        refresh_token=settings.gmail_refresh_token,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=GMAIL_SCOPES,
    )
    try:
        creds.refresh(Request())
    except RefreshError as e:
        raise GmailError(f"No se pudo renovar el acceso a Gmail: {e}") from e
    return creds


def enviar_mail(destinatarios: list[str], asunto: str, cuerpo: str) -> str:
    """Manda el mail y devuelve el message id de Gmail. Levanta
    GmailNoConfigurado o GmailError si algo falla — el llamador decide
    cómo guardar el resultado (ver TareaMail.estado)."""
    creds = _credenciales()

    msg = MIMEText(cuerpo)
    msg["To"] = ", ".join(destinatarios)
    msg["From"] = f"{settings.gmail_sender_nombre} <{settings.gmail_sender_email}>"
    msg["Subject"] = asunto
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

    resp = httpx.post(
        GMAIL_SEND_URL,
        headers={"Authorization": f"Bearer {creds.token}"},
        json={"raw": raw},
        timeout=15,
    )
    if resp.status_code >= 400:
        raise GmailError(f"Gmail devolvió {resp.status_code}: {resp.text}")

    return resp.json()["id"]
