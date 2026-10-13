from app.config import settings
from app.models import OrdenTrabajoEspejo, SyncLog

URL = "/api/sync/ordenes-trabajo"


def _h():
    return {"Authorization": f"Bearer {settings.sync_token}"}


def test_sync_exige_token(client_anonimo):
    assert client_anonimo.post(URL, json=[{"numero_ot": "9001"}]).status_code == 401
    assert client_anonimo.post(URL, json=[{"numero_ot": "9001"}], headers={"Authorization": "Bearer x"}).status_code == 401


def test_sync_upsert_no_duplica(client_anonimo, db_session):
    client_anonimo.post(URL, json=[{"numero_ot": "9001", "estado": "Abierta"}], headers=_h())
    r = client_anonimo.post(URL, json=[{"numero_ot": "9001", "estado": "Cerrada"}], headers=_h())
    assert r.status_code == 200
    filas = db_session.query(OrdenTrabajoEspejo).all()
    assert [(f.numero_ot, f.estado) for f in filas] == [("9001", "Cerrada")]


def test_sync_numero_repetido_en_el_lote_vale_el_ultimo(client_anonimo, db_session):
    r = client_anonimo.post(
        URL, json=[{"numero_ot": "9002", "estado": "A"}, {"numero_ot": "9002", "estado": "B"}], headers=_h()
    )
    assert r.status_code == 200
    assert [f.estado for f in db_session.query(OrdenTrabajoEspejo).all()] == ["B"]
    assert db_session.query(SyncLog).filter_by(ok=True).count() == 1


def test_sync_registro_invalido_da_422_y_no_guarda_nada(client_anonimo, db_session):
    malos = [
        {"numero_ot": ""},
        {"numero_ot": "   "},
        {"numero_ot": "7" * 21},
        {"numero_ot": "9003", "estado": "e" * 41},
        {"numero_ot": "9003", "negocio": "n" * 81},
    ]
    for malo in malos:
        r = client_anonimo.post(URL, json=[{"numero_ot": "9004"}, malo], headers=_h())
        assert r.status_code == 422, malo
    assert db_session.query(OrdenTrabajoEspejo).count() == 0


def test_sync_limites_exactos_se_aceptan(client_anonimo, db_session):
    r = client_anonimo.post(URL, json=[{"numero_ot": "7" * 20, "estado": "e" * 40, "negocio": "n" * 80}], headers=_h())
    assert r.status_code == 200 and db_session.query(OrdenTrabajoEspejo).count() == 1
