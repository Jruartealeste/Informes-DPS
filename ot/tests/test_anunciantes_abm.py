"""Numeración de OT interna por anunciante y ABM de anunciantes (2026-10-14)."""
from app.models import Cliente, ClienteAnunciante, OtInterna, ProductoAdvertys, Responsable, RolUsuario, Usuario


def _hacer_admin(db_session):
    usuario = db_session.query(Usuario).filter_by(email="test@aleste.ar").one()
    usuario.rol = RolUsuario.ADMIN
    db_session.commit()


def _cliente(db_session, nombre, **kw):
    c = Cliente(nombre=nombre, **kw)
    db_session.add(c)
    db_session.commit()
    return c


def _usar(client, cliente):
    client.cookies.set("cliente_id", str(cliente.id))


def _tarea(db_session, numero, titulo="Título"):
    fer = db_session.query(Responsable).filter_by(nombre="fer").one()
    return {"ot_numero": numero, "ot_titulo": titulo, "detalle": "Tarea", "fecha_pedido": "2026-10-14",
            "tipos": "diseño", "responsable_ids": str(fer.id)}


def test_cada_anunciante_numera_por_su_cuenta(client, db_session):
    aluar = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    db_session.add(OtInterna(numero_interno="4120", cliente_id=aluar.id))
    faa = _cliente(db_session, "FAA", numero_ot_inicial=2033)

    assert 'value="4121"' in client.get("/api/ordenes-trabajo/nuevo-numero").text  # sin cookie: ALUAR
    _usar(client, faa)
    assert 'value="2033"' in client.get("/api/ordenes-trabajo/nuevo-numero").text
    assert client.post("/tareas", data=_tarea(db_session, "2033")).status_code == 200
    assert 'value="2034"' in client.get("/api/ordenes-trabajo/nuevo-numero").text


def test_primera_ot_del_anunciante_elige_numero_de_partida(client, db_session):
    faa = _cliente(db_session, "FAA")
    _usar(client, faa)

    html = client.get("/api/ordenes-trabajo/nuevo-numero").text
    assert 'value="1"' in html and "Primera OT de este anunciante" in html and "data-ot-primera" in html
    assert client.post("/tareas", data=_tarea(db_session, "500")).status_code == 200
    db_session.refresh(faa)
    assert faa.numero_ot_inicial == 500

    html = client.get("/api/ordenes-trabajo/nuevo-numero").text
    assert 'value="501"' in html and "Primera OT de este anunciante" not in html


def test_panel_nueva_tarea_abre_con_la_primera_ot_sugerida(client, db_session):
    faa = _cliente(db_session, "FAA", numero_ot_inicial=2033)
    _usar(client, faa)

    html = client.get("/tareas-nuevo").text
    assert 'value="2033"' in html and "Primera OT de este anunciante" in html
    assert "duplicada de" not in html
    aluar = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    db_session.add(OtInterna(numero_interno="4120", cliente_id=aluar.id))
    db_session.commit()
    client.cookies.delete("cliente_id")  # ALUAR ya tiene OT: panel vacío como siempre
    assert "Primera OT de este anunciante" not in client.get("/tareas-nuevo").text


def test_el_mismo_numero_en_otro_anunciante_es_otra_ot_con_aviso(client, db_session):
    aluar = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    db_session.add(OtInterna(numero_interno="2033", cliente_id=aluar.id, titulo="De ALUAR"))
    faa = _cliente(db_session, "FAA", numero_ot_inicial=2033)
    _usar(client, faa)

    html = client.get("/api/ordenes-trabajo/nuevo-numero").text
    assert "ya existe en ALUAR" in html
    assert client.post("/tareas", data=_tarea(db_session, "2033", "De FAA")).status_code == 200
    ots = {o.cliente_id: o.titulo for o in db_session.query(OtInterna).filter_by(numero_interno="2033")}
    assert ots == {aluar.id: "De ALUAR", faa.id: "De FAA"}

    # el detalle muestra la del anunciante elegido
    assert "De FAA" in client.get("/ordenes-trabajo/2033").text
    client.cookies.delete("cliente_id")
    assert "De ALUAR" in client.get("/ordenes-trabajo/2033").text


def test_link_a_ot_de_otro_anunciante_cambia_de_anunciante(client, db_session):
    faa = _cliente(db_session, "FAA")
    db_session.add(OtInterna(numero_interno="7001", cliente_id=faa.id))
    db_session.commit()
    r = client.get("/ordenes-trabajo/7001", follow_redirects=False)  # sin cookie: ALUAR
    assert r.status_code == 303 and r.cookies.get("cliente_id") == str(faa.id)


def test_solo_admin_gestiona_anunciantes(client, db_session):
    assert client.get("/anunciantes").status_code == 403
    assert client.post("/anunciantes", data={"nombre": "Nuevo"}).status_code == 403
    _hacer_admin(db_session)
    assert client.get("/anunciantes").status_code == 200


def test_alta_de_anunciante_con_anunciantes_de_advertys_y_numero_inicial(client, db_session):
    _hacer_admin(db_session)
    db_session.add(ProductoAdvertys(id_advertys="9", nombre="Campañas", anunciante="FUNDACIÓN AURORA AUSTRAL"))
    db_session.commit()
    assert client.get("/anunciantes/sugeridos", params={"nombre": "FAA"}).json() == ["FUNDACIÓN AURORA AUSTRAL"]

    r = client.post(
        "/anunciantes",
        data={"nombre": " FAA ", "numero_ot_inicial": "2033", "anunciantes": ["FUNDACIÓN AURORA AUSTRAL"]},
        follow_redirects=False,
    )
    assert r.status_code == 303
    faa = db_session.query(Cliente).filter_by(nombre="FAA").one()
    assert faa.activo and faa.numero_ot_inicial == 2033
    assert [a.anunciante for a in faa.anunciantes] == ["FUNDACIÓN AURORA AUSTRAL"]
    # nombre repetido
    assert client.post("/anunciantes", data={"nombre": "faa"}).status_code == 422


def test_editar_anunciante_cambia_relacion_con_advertys(client, db_session):
    _hacer_admin(db_session)
    fate = _cliente(db_session, "FATE")
    db_session.add(ClienteAnunciante(cliente_id=fate.id, anunciante="FATE - MARKETING"))
    db_session.commit()
    r = client.post(
        f"/anunciantes/{fate.id}",
        data={"nombre": "FATE", "numero_ot_inicial": "", "anunciantes": ["FATE S.A.I.C.I.", "FATE - AGRICOLA"]},
        follow_redirects=False,
    )
    assert r.status_code == 303
    db_session.expire_all()
    assert sorted(a.anunciante for a in db_session.get(Cliente, fate.id).anunciantes) == [
        "FATE - AGRICOLA", "FATE S.A.I.C.I.",
    ]


def test_anunciante_desactivado_queda_en_solo_lectura(client, db_session):
    _hacer_admin(db_session)
    faa = _cliente(db_session, "FAA")
    assert client.post(f"/anunciantes/{faa.id}/desactivar", follow_redirects=False).status_code == 303
    db_session.expire_all()
    assert db_session.get(Cliente, faa.id).activo is False

    # sale del selector del sidebar
    assert f'<option value="{faa.id}"' not in client.get("/tareas").text

    # mirándolo: se ve, avisa, y rechaza cambios
    _usar(client, faa)
    html = client.get("/tareas").text
    assert "está <strong>desactivado</strong>" in html and "Nueva OT/tarea" not in html
    assert client.post("/tareas", data=_tarea(db_session, "1")).status_code == 409

    # reactivar sí se puede (es gestión de anunciantes)
    assert client.post(f"/anunciantes/{faa.id}/reactivar", follow_redirects=False).status_code == 303
    assert client.post("/tareas", data=_tarea(db_session, "1")).status_code == 200


def test_no_se_desactiva_el_unico_anunciante_activo(client, db_session):
    _hacer_admin(db_session)
    aluar = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    assert client.post(f"/anunciantes/{aluar.id}/desactivar").status_code == 409
