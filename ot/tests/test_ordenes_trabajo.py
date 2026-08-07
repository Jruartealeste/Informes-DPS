from app.models import Cliente, OtInterna


def test_nuevo_numero_sin_ot_previas(client):
    r = client.get("/api/ordenes-trabajo/nuevo-numero")
    assert r.status_code == 200
    assert 'value="1"' in r.text


def test_nuevo_numero_toma_el_maximo_existente(client, db_session):
    cliente = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    db_session.add(OtInterna(numero_interno="4230", cliente_id=cliente.id))
    db_session.add(OtInterna(numero_interno="120", cliente_id=cliente.id))
    db_session.commit()

    r = client.get("/api/ordenes-trabajo/nuevo-numero")
    assert r.status_code == 200
    assert 'value="4231"' in r.text


def test_crear_tarea_con_numero_autogenerado(client, db_session):
    cliente = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    db_session.add(OtInterna(numero_interno="500", cliente_id=cliente.id))
    db_session.commit()

    numero = client.get("/api/ordenes-trabajo/nuevo-numero")
    assert 'value="501"' in numero.text

    r = client.post(
        "/tareas",
        data={"ot_numero": "501", "detalle": "Tarea con OT autogenerada"},
    )
    assert r.status_code == 200

    ot = db_session.query(OtInterna).filter_by(numero_interno="501").one()
    assert ot.cliente.nombre == "ALUAR"
