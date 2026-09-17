from app.models import Cliente, EstadoFacturacion, OtInterna, Responsable, Tarea


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
    fer = db_session.query(Responsable).filter_by(nombre="fer").one()
    cliente = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    db_session.add(OtInterna(numero_interno="500", cliente_id=cliente.id))
    db_session.commit()

    numero = client.get("/api/ordenes-trabajo/nuevo-numero")
    assert 'value="501"' in numero.text

    r = client.post(
        "/tareas",
        data={
            "ot_numero": "501",
            "detalle": "Tarea con OT autogenerada",
            "fecha_pedido": "2026-08-01",
            "tipos": "diseño",
            "responsable_ids": str(fer.id),
        },
    )
    assert r.status_code == 200

    ot = db_session.query(OtInterna).filter_by(numero_interno="501").one()
    assert ot.cliente.nombre == "ALUAR"


def test_listado_ordenes_trabajo(client, db_session):
    cliente = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    ot = OtInterna(numero_interno="700", cliente_id=cliente.id)
    db_session.add(ot)
    db_session.flush()
    db_session.add(Tarea(ot_interna_id=ot.id, detalle="Tarea de prueba"))
    db_session.commit()

    r = client.get("/ordenes-trabajo")
    assert r.status_code == 200
    assert "OT 700" in r.text


def test_detalle_orden_trabajo(client, db_session):
    cliente = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    ot = OtInterna(numero_interno="701", cliente_id=cliente.id)
    db_session.add(ot)
    db_session.flush()
    db_session.add(
        Tarea(
            ot_interna_id=ot.id,
            detalle="Diseño de pieza",
            estado_facturacion=EstadoFacturacion.FACTURADO,
        )
    )
    db_session.commit()

    r = client.get("/ordenes-trabajo/701")
    assert r.status_code == 200
    assert "Diseño de pieza" in r.text
    assert "Todavía no tiene OT de sistema" in r.text
    assert "1/1" in r.text


def test_detalle_orden_trabajo_inexistente(client):
    r = client.get("/ordenes-trabajo/99999")
    assert r.status_code == 404


def test_reasignar_ot_sistema(client, db_session):
    cliente = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    ot = OtInterna(numero_interno="702", cliente_id=cliente.id)
    db_session.add(ot)
    db_session.flush()
    db_session.add(Tarea(ot_interna_id=ot.id, detalle="Tarea de prueba"))
    db_session.commit()

    r = client.post(
        "/ordenes-trabajo/702/reasignar",
        data={"numero_ot_advertys": "260"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    db_session.refresh(ot)
    assert ot.numero_ot_advertys == "260"
