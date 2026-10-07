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


def _dos_ots(db_session, a="810", b="811"):
    cliente = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    ots = [OtInterna(numero_interno=n, cliente_id=cliente.id) for n in (a, b)]
    db_session.add_all(ots)
    db_session.commit()
    return ots


_PEDIDO = {"anunciante": "ALUAR", "resumen": "Resumen", "producto": "Producto", "centro_costo": "Gráfica"}


def _centro_costo_valido():
    from app.labels import CENTRO_COSTO_OPCIONES

    return sorted(CENTRO_COSTO_OPCIONES)[0]


def _generar(client, numeros, **extra):
    return client.post(
        "/ordenes-trabajo/generar-ot",
        data={**_PEDIDO, "centro_costo": _centro_costo_valido(), "ot_ids": ",".join(numeros), **extra},
        follow_redirects=False,
    )


def test_no_se_asigna_ot_de_sistema_a_ot_con_pedido_pendiente(client, db_session):
    a, b = _dos_ots(db_session)
    assert _generar(client, ["810"]).status_code == 303

    r = client.post("/ordenes-trabajo/asignar-lote", data={"ot_ids": "810,811", "numero_ot_advertys": "9300"})
    assert r.status_code == 409 and "810" in r.text
    r = client.post("/ordenes-trabajo/810/reasignar", data={"numero_ot_advertys": "9300"})
    assert r.status_code == 409
    db_session.expire_all()
    assert a.numero_ot_advertys is None and b.numero_ot_advertys is None


def test_reasignar_ot_de_pedido_resuelto_la_desvincula_y_permite_volver_a_pedir(client, db_session):
    a, b = _dos_ots(db_session)
    _generar(client, ["810", "811"])
    solicitud_id = a.solicitud_alta_id or db_session.query(OtInterna).filter_by(numero_interno="810").one().solicitud_alta_id
    assert client.post(
        f"/ordenes-trabajo/solicitudes/{solicitud_id}/resolver",
        data={"numero_ot_advertys": "9100"},
        follow_redirects=False,
    ).status_code == 303

    # Mismo número: sigue vinculada. Otro número: se desvincula solo esa OT.
    client.post("/ordenes-trabajo/811/reasignar", data={"numero_ot_advertys": "9100"}, follow_redirects=False)
    client.post("/ordenes-trabajo/810/reasignar", data={"numero_ot_advertys": ""}, follow_redirects=False)
    db_session.expire_all()
    assert a.solicitud_alta_id is None and a.numero_ot_advertys is None
    assert b.solicitud_alta_id == solicitud_id

    # La OT vaciada se puede volver a pedir (antes daba "ya tiene un pedido pendiente").
    assert _generar(client, ["810"]).status_code == 303


def test_comando_crear_ot_escapa_texto_libre(db_session):
    from app.models import SolicitudAltaOt
    from app.viewmodels import _comando_crear_ot

    s = SolicitudAltaOt(
        anunciante="O'Brien & Co", resumen='Resumen con "comillas" y $var `x` $(whoami)\nlinea 2',
        producto="P", centro_costo="C", equipo="Eq",
    )
    cmd = _comando_crear_ot(s)
    assert "\n" not in cmd
    assert "'O''Brien & Co'" in cmd
    assert "'Resumen con \"comillas\" y $var `x` $(whoami) linea 2'" in cmd
    assert cmd.endswith("--equipo 'Eq'")
