"""Autorización one-time para que la app pueda mandar mail como vos.

Correr una sola vez, a mano, desde tu máquina (no en el server):

    python -m scripts.gmail_authorize

Pide GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET (los del proyecto de Google
Cloud, credencial tipo "Desktop app" con la Gmail API habilitada — ver
"Mail a responsables" en CLAUDE.md). Abre el navegador para que te loguees
con javier@aleste.ar y aceptes el permiso de mandar mail en tu nombre, y al
final imprime el refresh token para pegar en el .env del server
(GMAIL_REFRESH_TOKEN), junto con GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET /
GMAIL_SENDER_EMAIL.

No hace falta volver a correr esto salvo que revoques el acceso desde
https://myaccount.google.com/permissions.
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def main() -> None:
    client_id = input("GOOGLE_CLIENT_ID: ").strip()
    client_secret = input("GOOGLE_CLIENT_SECRET: ").strip()

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    # access_type=offline + prompt=consent: sin esto Google solo devuelve
    # refresh_token la primera vez que se autoriza el client_id entero, no
    # cada vez que se corre este script — forzarlo evita un token vacío
    # si ya habías autorizado antes y estás regenerando.
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    print("\nListo. Sumá esto al .env del server:\n")
    print(f"GOOGLE_CLIENT_ID={client_id}")
    print(f"GOOGLE_CLIENT_SECRET={client_secret}")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")
    print("GMAIL_SENDER_EMAIL=javier@aleste.ar")


if __name__ == "__main__":
    main()
