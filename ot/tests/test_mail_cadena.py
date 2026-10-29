from app import gmail_client
from app.models import Cliente, EstadoMail, OtInterna, Responsable, Tarea, TareaMail, TareaResponsable, Usuario
from app.routers import mail as mail_router


def _tarea_con_mail_enviado(db_session, con_hilo=True, remitente="test@aleste.ar"):
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
        remitente=remitente,
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

    def falso(usuario, dest, asunto, cuerpo, en_cadena=None):
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

    def falso(usuario, dest, asunto, cuerpo, en_cadena=None):
        llamadas.append((asunto, en_cadena))
        return gmail_client.MailEnviado("m3", "t9", "<c@aleste.ar>")

    monkeypatch.setattr(mail_router, "enviar_mail", falso)
    client.post(f"/tareas/{tarea.id}/mail", data={
        "asunto": "Asunto propio", "cuerpo": "x", "destinatario_ids": [str(fer.id)],
    })
    assert llamadas == [("Asunto propio", None)]


def test_cadena_de_otro_remitente_va_sin_thread_id(client, db_session, monkeypatch):
    # el threadId es de la casilla de quien mandó el anterior: desde otra
    # cuenta se encadena solo por In-Reply-To/References
    tarea, fer = _tarea_con_mail_enviado(db_session, remitente="javier@aleste.ar")
    llamadas = []

    def falso(usuario, dest, asunto, cuerpo, en_cadena=None):
        llamadas.append((usuario.email, en_cadena))
        return gmail_client.MailEnviado("m4", "t7", "<d@aleste.ar>")

    monkeypatch.setattr(mail_router, "enviar_mail", falso)
    client.post(f"/tareas/{tarea.id}/mail", data={
        "asunto": "x", "cuerpo": "x", "destinatario_ids": [str(fer.id)], "misma_cadena": "1",
    })
    assert llamadas == [("test@aleste.ar", (None, "<a@aleste.ar>"))]
    assert db_session.query(TareaMail).filter_by(gmail_message_id="m4").one().remitente == "test@aleste.ar"


def test_asunto_sugerido_con_titulo_y_detalle_recortado():
    det = {"otN": "4163", "ot_titulo": "Catálogo en inglés",
           "detalle": "Armar las piezas del catálogo para la feria internacional de Dubai con nuevos precios"}
    asunto = mail_router._asunto_sugerido(det)
    assert asunto.startswith("4163 · Catálogo en inglés · Armar las piezas")
    assert asunto.endswith("…") and len(asunto) < 90
    assert mail_router._asunto_sugerido({"otN": "1", "ot_titulo": None, "detalle": "Flyer"}) == "1 · Flyer"


def test_envio_con_adjunto_pasa_archivos(client, db_session, monkeypatch):
    tarea, fer = _tarea_con_mail_enviado(db_session)
    llamadas = []

    def falso(usuario, dest, asunto, cuerpo, en_cadena=None, adjuntos=None):
        llamadas.append(adjuntos)
        return gmail_client.MailEnviado("m2", "t1", "<b@aleste.ar>")

    monkeypatch.setattr(mail_router, "enviar_mail", falso)
    usuario = db_session.query(Usuario).first()
    usuario.gmail_refresh_token_enc = "x"
    db_session.commit()
    client.post(
        f"/tareas/{tarea.id}/mail",
        data={"asunto": "a", "cuerpo": "b", "destinatario_ids": [str(fer.id)]},
        files={"archivos": ("brief.pdf", b"%PDF-1", "application/pdf")},
    )
    assert llamadas == [[("brief.pdf", "application/pdf", b"%PDF-1")]]
