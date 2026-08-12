from app.models import Responsable


def test_crear_responsable_nuevo_queda_tildado(client, db_session):
    r = client.post("/api/responsables", data={"nombre": "pili", "responsable_ids": ""})
    assert r.status_code == 200

    pili = db_session.query(Responsable).filter_by(nombre="pili").one()
    assert pili.activo is True
    assert f'value="{pili.id}"' in r.text
    assert f'value="{pili.id}" checked' in r.text.replace("\n", " ")


def test_crear_responsable_repetido_reusa_existente(client, db_session):
    fer = db_session.query(Responsable).filter_by(nombre="fer").one()

    r = client.post("/api/responsables", data={"nombre": "FER", "responsable_ids": ""})
    assert r.status_code == 200

    assert db_session.query(Responsable).filter_by(nombre="fer").count() == 1
    assert f'value="{fer.id}"' in r.text


def test_toggle_desactiva_y_reactiva(client, db_session):
    fer = db_session.query(Responsable).filter_by(nombre="fer").one()
    fer_id = fer.id

    r = client.post(f"/responsables/{fer_id}/toggle")
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.get(Responsable, fer_id).activo is False

    r = client.post(f"/responsables/{fer_id}/toggle")
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.get(Responsable, fer_id).activo is True


def test_renombrar_responsable(client, db_session):
    fer = db_session.query(Responsable).filter_by(nombre="fer").one()

    r = client.post(f"/responsables/{fer.id}/renombrar", data={"nombre": "fernanda"})
    assert r.status_code == 200

    db_session.expire_all()
    assert db_session.get(Responsable, fer.id).nombre == "fernanda"


def test_responsable_desactivado_no_aparece_para_tareas_nuevas(client, db_session):
    fer = db_session.query(Responsable).filter_by(nombre="fer").one()
    client.post(f"/responsables/{fer.id}/toggle")

    r = client.get("/tareas-nuevo")
    assert r.status_code == 200
    assert "fer" not in r.text
