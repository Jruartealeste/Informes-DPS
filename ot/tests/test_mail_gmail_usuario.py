"""Mail de tareas desde la cuenta de Gmail del usuario logueado (ver
"Mail a responsables" en CLAUDE.md)."""

import email
import base64

import pytest
from cryptography.fernet import Fernet

from app import gmail_client
from app.config import settings
from app.models import Cliente, EstadoMail, OtInterna, Responsable, Tarea, TareaMail, TareaResponsable, Usuario


@pytest.fixture(autouse=True)
def clave(monkeypatch):
    monkeypatch.setattr(settings, "mail_token_enc_key", Fernet.generate_key().decode())


def _tarea(db_session):
    ot = OtInterna(numero_interno="6000", cliente_id=db_session.query(Cliente).first().id)
    db_session.add(ot)
    db_session.flush()
    fer = db_session.query(Responsable).filter_by(nombre="fer").one()
    fer.mail = "fer@aleste.ar"
    tarea = Tarea(ot_interna_id=ot.id, detalle="Banner")
    db_session.add(tarea)
    db_session.flush()
    db_session.add(TareaResponsable(tarea_id=tarea.id, responsable_id=fer.id))
    db_session.commit()
    return tarea, fer


def _usuario(db_session):
    return db_session.query(Usuario).filter_by(email="test@aleste.ar").one()


def _conectar(db_session, token="rt-1"):
    u = _usuario(db_session)
    u.gmail_refresh_token_enc = gmail_client.cifrar_token(token)
    db_session.commit()


def test_sin_conectar_ofrece_conectar_y_deshabilita_enviar(client, db_session):
    tarea, _ = _tarea(db_session)
    r = client.get(f"/tareas/{tarea.id}/mail")
    assert "Conectar Gmail" in r.text
    assert 'disabled title="Conectá tu Gmail primero"' in r.text
    # la firma sugerida es la del usuario, no un remitente fijo
    assert "Saludos,\nTest User" in r.text


def test_conectado_muestra_remitente_y_habilita_enviar(client, db_session):
    tarea, _ = _tarea(db_session)
    _conectar(db_session)
    r = client.get(f"/tareas/{tarea.id}/mail")
    assert "test@aleste.ar" in r.text and "Desconectar" in r.text
    assert "Conectá tu Gmail primero" not in r.text


def test_envio_sale_desde_el_usuario_logueado(client, db_session, monkeypatch):
    tarea, fer = _tarea(db_session)
    _conectar(db_session, token="rt-propio")
    enviados = []

    class Creds:
        token = "access"

        def __init__(self, **kw):
            enviados.append(("refresh_token", kw["refresh_token"]))

        def refresh(self, _req):
            pass

    class Resp:
        status_code = 200

        @staticmethod
        def json():
            return {"id": "g1", "threadId": "th1"}

    def post(url, headers, json, timeout):
        msg = email.message_from_bytes(base64.urlsafe_b64decode(json["raw"]))
        enviados.append(("from", msg["From"]))
        return Resp()

    monkeypatch.setattr(gmail_client, "Credentials", Creds)
    monkeypatch.setattr(gmail_client.httpx, "post", post)
    client.post(f"/tareas/{tarea.id}/mail", data={"asunto": "a", "cuerpo": "b", "destinatario_ids": [str(fer.id)]})

    assert ("refresh_token", "rt-propio") in enviados
    assert ("from", "Test User <test@aleste.ar>") in enviados
    m = db_session.query(TareaMail).filter_by(gmail_message_id="g1").one()
    assert m.estado == EstadoMail.ENVIADO and m.remitente == "test@aleste.ar"


def test_token_revocado_desconecta_y_registra_error(client, db_session, monkeypatch):
    tarea, fer = _tarea(db_session)
    _conectar(db_session)

    def revocado(usuario):
        raise gmail_client.GmailTokenRevocado("revocado")

    monkeypatch.setattr(gmail_client, "_credenciales", revocado)
    monkeypatch.setattr(gmail_client.httpx, "post", lambda *a, **k: None)
    r = client.post(f"/tareas/{tarea.id}/mail", data={"asunto": "a", "cuerpo": "b", "destinatario_ids": [str(fer.id)]})

    assert "Conectar Gmail" in r.text
    db_session.expire_all()
    assert _usuario(db_session).gmail_refresh_token_enc is None
    assert db_session.query(TareaMail).one().estado == EstadoMail.ERROR


def test_desconectar_desde_el_composer(client, db_session, monkeypatch):
    tarea, _ = _tarea(db_session)
    _conectar(db_session)
    revocados = []
    monkeypatch.setattr(gmail_client.httpx, "post", lambda url, data, timeout: revocados.append(data["token"]))
    r = client.post(f"/tareas/{tarea.id}/mail/desconectar-gmail", data={"asunto": "mío", "cuerpo": "texto mío"})

    assert revocados == ["rt-1"]
    assert "Conectar Gmail" in r.text and "texto mío" in r.text
    db_session.expire_all()
    assert _usuario(db_session).gmail_refresh_token_enc is None


def test_conectar_sin_sesion_va_al_login(client_anonimo):
    r = client_anonimo.get("/auth/gmail/conectar", follow_redirects=False)
    assert r.headers["location"] == "/auth/login"


def test_conectar_pide_gmail_send_offline(client):
    r = client.get("/auth/gmail/conectar?next=/tareas", follow_redirects=False)
    loc = r.headers["location"]
    assert "gmail.send" in loc and "access_type=offline" in loc and "prompt=consent" in loc
    assert "login_hint=test%40aleste.ar" in loc
    assert "redirect_uri=http%3A%2F%2Ftestserver%2Fauth%2Fcallback" in loc


@pytest.mark.parametrize("next_, esperado", [("/tareas?x=1", "/tareas?x=1"), ("//evil.com", "/tareas"), ("https://evil.com", "/tareas")])
def test_destino_local(next_, esperado):
    from app.routers.auth_routes import _destino_local

    assert _destino_local(next_) == esperado


def _callback(client, monkeypatch, token):
    from app.auth import oauth

    async def falso(request):
        return token

    monkeypatch.setattr(oauth.google, "authorize_access_token", falso)
    client.get("/auth/gmail/conectar?next=/tareas", follow_redirects=False)  # deja gmail_next en la sesión
    return client.get("/auth/callback", follow_redirects=False).headers["location"]


def test_callback_guarda_token_cifrado(client, db_session, monkeypatch):
    loc = _callback(client, monkeypatch, {
        "userinfo": {"email": "test@aleste.ar"}, "refresh_token": "rt-nuevo",
        "scope": f"openid email {gmail_client.GMAIL_SCOPE}",
    })
    assert loc == "/tareas?gmail=conectado"
    db_session.expire_all()
    u = _usuario(db_session)
    assert u.gmail_refresh_token_enc and "rt-nuevo" not in u.gmail_refresh_token_enc
    assert gmail_client._descifrar_token(u.gmail_refresh_token_enc) == "rt-nuevo"


def test_callback_con_otra_cuenta_no_guarda(client, db_session, monkeypatch):
    loc = _callback(client, monkeypatch, {
        "userinfo": {"email": "otra@aleste.ar"}, "refresh_token": "rt",
        "scope": gmail_client.GMAIL_SCOPE,
    })
    assert loc == "/tareas?gmail=otra_cuenta"
    db_session.expire_all()
    assert _usuario(db_session).gmail_refresh_token_enc is None


def test_callback_sin_permiso_de_envio_no_guarda(client, db_session, monkeypatch):
    loc = _callback(client, monkeypatch, {"userinfo": {"email": "test@aleste.ar"}, "refresh_token": "rt", "scope": "openid email"})
    assert loc == "/tareas?gmail=sin_permiso"
