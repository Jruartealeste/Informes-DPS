"""Mails programados: se guardan PROGRAMADO y los manda /auth/mantener cuando
llega la hora (ver "Mails programados" en CLAUDE.md)."""

from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet

from app import gmail_client
from app.config import settings
from app.gmail_client import GmailError, MailEnviado
from app.models import Cliente, EstadoMail, OtInterna, Responsable, Tarea, TareaMail, TareaResponsable, Usuario
from app.routers import auth_routes
from app.routers import mail as mail_router

AR = timezone(timedelta(hours=-3))


@pytest.fixture(autouse=True)
def clave(monkeypatch):
    monkeypatch.setattr(settings, "mail_token_enc_key", Fernet.generate_key().decode())


@pytest.fixture
def enviados(monkeypatch):
    lista = []

    def falso(usuario, destinatarios, asunto, cuerpo, en_cadena=None, adjuntos=None):
        lista.append({"de": usuario.email, "para": destinatarios, "asunto": asunto, "en_cadena": en_cadena})
        return MailEnviado(f"g{len(lista)}", "th1", f"<m{len(lista)}@aleste.ar>")

    monkeypatch.setattr(mail_router, "enviar_mail", falso)
    return lista


def _tarea(db_session):
    ot = OtInterna(numero_interno="6100", cliente_id=db_session.query(Cliente).first().id)
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


def _conectar(db_session):
    u = db_session.query(Usuario).filter_by(email="test@aleste.ar").one()
    u.gmail_refresh_token_enc = gmail_client.cifrar_token("rt")
    db_session.commit()
    return u


def _local(dt: datetime) -> str:
    return dt.astimezone(AR).strftime("%Y-%m-%dT%H:%M")


def _programar(client, tarea, fer, cuando: str, **extra):
    data = {"asunto": "Aviso", "cuerpo": "Hola", "destinatario_ids": [str(fer.id)],
            "accion": "programar", "programado_para": cuando, **extra}
    return client.post(f"/tareas/{tarea.id}/mail", data=data)


def _mails(db_session, tarea):
    db_session.expire_all()
    return db_session.query(TareaMail).filter_by(tarea_id=tarea.id).all()


def test_programar_guarda_en_utc_sin_mandar(client, db_session, enviados):
    tarea, fer = _tarea(db_session)
    _conectar(db_session)
    r = _programar(client, tarea, fer, "2099-03-02T09:30")
    assert r.status_code == 200 and "drawer-root" in r.text
    [m] = _mails(db_session, tarea)
    assert m.estado == EstadoMail.PROGRAMADO
    assert m.destinatarios == "fer@aleste.ar" and m.remitente == "test@aleste.ar"
    # 09:30 de Argentina = 12:30 UTC
    assert m.programado_para.replace(tzinfo=None) == datetime(2099, 3, 2, 12, 30)
    assert enviados == []
    assert "Programado" in r.text and "02/03 09:30" in r.text


@pytest.mark.parametrize("cuando,error", [
    ("", "Elegí la fecha y hora"),
    ("2001-01-01T10:00", "ya pasó"),
])
def test_programar_valida_fecha(client, db_session, enviados, cuando, error):
    tarea, fer = _tarea(db_session)
    _conectar(db_session)
    r = _programar(client, tarea, fer, cuando)
    assert error in r.text
    assert _mails(db_session, tarea) == []


def test_programar_sin_gmail_conectado(client, db_session, enviados):
    tarea, fer = _tarea(db_session)
    r = _programar(client, tarea, fer, "2099-03-02T09:30")
    assert "primero conectá tu Gmail" in r.text
    assert _mails(db_session, tarea) == []


def test_programar_no_acepta_adjuntos(client, db_session, enviados):
    tarea, fer = _tarea(db_session)
    _conectar(db_session)
    r = client.post(
        f"/tareas/{tarea.id}/mail",
        data={"asunto": "a", "cuerpo": "b", "destinatario_ids": [str(fer.id)],
              "accion": "programar", "programado_para": "2099-03-02T09:30"},
        files={"archivos": ("x.txt", b"hola", "text/plain")},
    )
    assert "adjuntos no se pueden programar" in r.text
    assert _mails(db_session, tarea) == []


def test_despachar_manda_solo_los_vencidos(client, db_session, enviados):
    tarea, fer = _tarea(db_session)
    _conectar(db_session)
    _programar(client, tarea, fer, "2099-03-02T09:30")
    ahora = datetime.now(timezone.utc)
    db_session.add(TareaMail(
        tarea_id=tarea.id, destinatarios="fer@aleste.ar", asunto="Ya", cuerpo="c",
        estado=EstadoMail.PROGRAMADO, remitente="test@aleste.ar",
        programado_para=ahora - timedelta(minutes=1),
    ))
    db_session.commit()

    assert mail_router.despachar_programados(db_session, ahora) == 1
    assert [e["asunto"] for e in enviados] == ["Ya"]
    estados = {m.asunto: m.estado for m in _mails(db_session, tarea)}
    assert estados == {"Ya": EstadoMail.ENVIADO, "Aviso": EstadoMail.PROGRAMADO}
    # una segunda pasada no lo reenvía
    assert mail_router.despachar_programados(db_session, ahora) == 0


def test_despachar_en_cadena_cuelga_del_ultimo_enviado(client, db_session, enviados):
    tarea, fer = _tarea(db_session)
    _conectar(db_session)
    db_session.add(TareaMail(
        tarea_id=tarea.id, destinatarios="fer@aleste.ar", asunto="Original", cuerpo="c",
        estado=EstadoMail.ENVIADO, remitente="test@aleste.ar",
        gmail_thread_id="th-orig", rfc_message_id="<orig@aleste.ar>",
    ))
    db_session.commit()
    _programar(client, tarea, fer, "2099-03-02T09:30", misma_cadena="1")
    [prog] = [m for m in _mails(db_session, tarea) if m.estado == EstadoMail.PROGRAMADO]
    assert prog.misma_cadena and prog.asunto == "Re: Original"

    mail_router.despachar_programados(db_session, datetime(2099, 3, 3, tzinfo=timezone.utc))
    assert enviados[0]["en_cadena"] == ("th-orig", "<orig@aleste.ar>")
    assert enviados[0]["asunto"] == "Re: Original"


def test_despachar_error_de_gmail_queda_en_error(client, db_session, monkeypatch):
    tarea, fer = _tarea(db_session)
    _conectar(db_session)
    _programar(client, tarea, fer, "2099-03-02T09:30")

    def falla(*a, **k):
        raise GmailError("cuota excedida")

    monkeypatch.setattr(mail_router, "enviar_mail", falla)
    mail_router.despachar_programados(db_session, datetime(2099, 3, 3, tzinfo=timezone.utc))
    [m] = _mails(db_session, tarea)
    assert m.estado == EstadoMail.ERROR and "cuota excedida" in m.error_detalle


def test_despachar_usuario_inactivo_no_manda(client, db_session, enviados):
    tarea, fer = _tarea(db_session)
    u = _conectar(db_session)
    _programar(client, tarea, fer, "2099-03-02T09:30")
    u.activo = False
    db_session.commit()
    mail_router.despachar_programados(db_session, datetime(2099, 3, 3, tzinfo=timezone.utc))
    [m] = _mails(db_session, tarea)
    assert m.estado == EstadoMail.ERROR and enviados == []


def test_cancelar_programado_lo_deja_como_borrador(client, db_session, enviados):
    tarea, fer = _tarea(db_session)
    _conectar(db_session)
    _programar(client, tarea, fer, "2099-03-02T09:30")
    [m] = _mails(db_session, tarea)
    r = client.post(f"/tareas/{tarea.id}/mail/{m.id}/cancelar-programado")
    assert r.status_code == 200
    [m] = _mails(db_session, tarea)
    assert m.estado == EstadoMail.BORRADOR and m.programado_para is None
    # el composer retoma ese texto
    assert "Hola" in client.get(f"/tareas/{tarea.id}/mail").text
    # ya no está programado: cancelar de nuevo da 409
    assert client.post(f"/tareas/{tarea.id}/mail/{m.id}/cancelar-programado").status_code == 409


def test_mantener_en_horario_despacha(client, client_anonimo, db_session, enviados, monkeypatch):
    tarea, fer = _tarea(db_session)
    _conectar(db_session)
    db_session.add(TareaMail(
        tarea_id=tarea.id, destinatarios="fer@aleste.ar", asunto="Ya", cuerpo="c",
        estado=EstadoMail.PROGRAMADO, remitente="test@aleste.ar",
        programado_para=datetime.now(timezone.utc) - timedelta(minutes=1),
    ))
    db_session.commit()
    monkeypatch.setattr(auth_routes, "_ahora", lambda: datetime(2026, 9, 7, 12, 0, tzinfo=AR))
    monkeypatch.setattr(auth_routes, "_ULTIMO_DESPACHO", 0.0)
    assert client_anonimo.get("/auth/mantener").status_code == 204
    assert [e["asunto"] for e in enviados] == ["Ya"]


def test_mantener_fuera_de_horario_no_despacha(client, client_anonimo, db_session, enviados, monkeypatch):
    tarea, fer = _tarea(db_session)
    _conectar(db_session)
    db_session.add(TareaMail(
        tarea_id=tarea.id, destinatarios="fer@aleste.ar", asunto="Ya", cuerpo="c",
        estado=EstadoMail.PROGRAMADO, remitente="test@aleste.ar",
        programado_para=datetime.now(timezone.utc) - timedelta(minutes=1),
    ))
    db_session.commit()
    monkeypatch.setattr(auth_routes, "_ahora", lambda: datetime(2026, 9, 12, 12, 0, tzinfo=AR))  # sábado
    monkeypatch.setattr(auth_routes, "_ULTIMO_DESPACHO", 0.0)
    client_anonimo.get("/auth/mantener")
    assert enviados == []
