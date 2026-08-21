from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # Ruta absoluta (no ".env" relativo) — un ".env" relativo depende del
    # cwd del proceso que arranca la app, que no siempre es la raíz de
    # ot/ (systemd, un launcher externo, etc.).
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    database_url: str

    # Envío de mail a responsables (Gmail API, remitente único — ver
    # "Mail a responsables" en CLAUDE.md). Quedan opcionales para que el
    # resto de la app funcione sin configurar esto: el envío falla con un
    # error claro si faltan, en vez de romper el arranque.
    google_client_id: str | None = None
    google_client_secret: str | None = None
    gmail_refresh_token: str | None = None
    gmail_sender_email: str | None = None
    gmail_sender_nombre: str = "Aleste"


settings = Settings()
