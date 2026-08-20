from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
