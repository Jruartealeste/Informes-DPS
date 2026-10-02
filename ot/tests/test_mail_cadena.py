from app import gmail_client
from app.models import Cliente, EstadoMail, OtInterna, Responsable, Tarea, TareaMail, TareaResponsable
from app.routers import mail as mail_router


def _tarea_con_mail_enviado(db_session, con_hilo=True):
    cliente = db_session.query(Cliente).first()
    ot = OtInterna(numero_interno="5000", cliente_id=cliente.id)
    db_session.add(ot)
    db_session.flush()
    fer = db_session.query(Responsable).filter_by(nombre="fer").one()
    fer.mail = "fer@aleste.ar"
    tarea = Tarea(ot_interna_id=ot.id, detalle="Flyer")
    db_session.add(tarea)
    db_session.flush()
    db_session.add(TareaResponsable(tarea_id=tarea.id, responsable_id=fer.id))
    db_session.add(TareaMail(
        tarea_id=tarea.id, destinatarios="fer@aleste.ar", asunto="5000 · Flyer", cuerpo="hola",
        estado=EstadoMail.ENVIADO, gmail_message_id="m1",
        gmail_thread_id="t1" if con_hilo else None,
        rfc_message_id="<a@aleste.ar>" if con_hilo else None,
    ))
    db_session.commit()
    return tarea, fer


def test_composer_ofrece_cadena_tildada(client, db_session):
    tarea, _ = _tarea_con_mail_enviado(db_session)
    r = client.get(f"/tareas/{tarea.id}/mail")
    assert 'id="chk-misma-cadena"' in r.text
    assert "checked" in r.text.split('id="chk-misma-cadena"')[1].split(">")[0] + r.text.split('id="chk-misma-cadena"')[1].split(">")[1]
    assert 'value="Re: 5000 · Flyer"' in r.text


def test_composer_sin_hilo_previo_no_ofrece_cadena(client, db_session):
    tarea, _ = _tarea_con_mail_enviado(db_session, con_hilo=False)
    r = client.get(f"/tareas/{tarea.id}/mail")
    assert "chk-misma-cadena" not in r.text


def test_envio_en_cadena_pasa_thread_y_asunto(client, db_session, monkeypatch):
    tarea, fer = _tarea_con_mail_enviado(db_session)
    llamadas = []

    def falso(dest, asunto, cuerpo, en_cadena=None):
        llamadas.append((asunto, en_cadena))
        return gmail_client.MailEnviado("m2", "t1", "<b@aleste.ar>")

    monkeypatch.setattr(mail_router, "enviar_mail", falso)
    client.post(f"/tareas/{tarea.id}/mail", data={
        "asunto": "otro", "cuerpo": "x", "destinatario_ids": [str(fer.id)], "misma_cadena": "1",
    })
    assert llamadas == [("Re: 5000 · Flyer", ("t1", "<a@aleste.ar>"))]
    nuevo = db_session.query(TareaMail).filter_by(gmail_message_id="m2").one()
    assert nuevo.rfc_message_id == "<b@aleste.ar>"


def test_envio_destildado_es_mail_nuevo(client, db_session, monkeypatch):
    tarea, fer = _tarea_con_mail_enviado(db_session)
    llamadas = []

    def falso(dest, asunto, cuerpo, en_cadena=None):
        llamadas.append((asunto, en_cadena))
        return gmail_client.MailEnviado("m3", "t9", "<c@aleste.ar>")

    monkeypatch.setattr(mail_router, "enviar_mail", falso)
    client.post(f"/tareas/{tarea.id}/mail", data={
        "asunto": "Asunto propio", "cuerpo": "x", "destinatario_ids": [str(fer.id)],
    })
    assert llamadas == [("Asunto propio", None)]
