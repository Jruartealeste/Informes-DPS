"""API de solicitudes de alta de Estimado para
Informes/modules/estimados_costos/procesar_solicitudes.py."""

from app.config import settings
from app.models import EstadoEstimado, EstadoSolicitudAltaEstimado, Estimado, SolicitudAltaEstimado
from tests.test_estimados import _armar, _crear

URL = "/api/sync/solicitudes-alta-estimado"


def _h():
    return {"Authorization": f"Bearer {settings.sync_token}"}


def _pedido(client, db_session):
    est_id = _crear(client, _armar(db_session), titulo="Catálogo 2026")
    r = client.post(
        f"/estimados/{est_id}/generar-en-advertys", data={"fecha_analisis": "1/10/2026"}, follow_redirects=False
    )
    assert r.status_code == 303
    return db_session.query(SolicitudAltaEstimado).one(), est_id


def test_api_exige_token(client_anonimo):
    assert client_anonimo.get(URL).status_code == 401
    assert client_anonimo.post(f"{URL}/1/resolver", json={"numero_estimado": "1"}).status_code == 401


def test_api_lista_pendientes_con_ot_titulo_y_tareas(client, client_anonimo, db_session):
    s, est_id = _pedido(client, db_session)
    [item] = client_anonimo.get(URL, headers=_h()).json()
    assert item["id"] == s.id and item["estado"] == "PENDIENTE"
    assert item["estimado_id"] == est_id
    assert item["titulo"] == "Catálogo 2026" and item["numero_ot_advertys"] == "260"
    assert item["fecha_analisis"] == "1/10/2026" and item["fecha_solicitada"] is None
    assert sorted(item["tareas"]) == ["t0", "t1"]
    assert client_anonimo.get(URL, params={"estado": "RESUELTA"}, headers=_h()).json() == []
    assert client_anonimo.get(URL, params={"estado": "X"}, headers=_h()).status_code == 422


def test_api_resolver_propaga_y_es_idempotente(client, client_anonimo, db_session):
    s, est_id = _pedido(client, db_session)
    r = client_anonimo.post(f"{URL}/{s.id}/resolver", json={"numero_estimado": " 590 "}, headers=_h())
    assert r.status_code == 200 and r.json()["ya_estaba_resuelta"] is False
    db_session.expire_all()
    est = db_session.get(Estimado, est_id)
    assert s.estado == EstadoSolicitudAltaEstimado.RESUELTA
    assert est.numero_estimado == "590" and est.estado == EstadoEstimado.GENERADO

    r = client_anonimo.post(f"{URL}/{s.id}/resolver", json={"numero_estimado": "590"}, headers=_h())
    assert r.status_code == 200 and r.json()["ya_estaba_resuelta"] is True
    r = client_anonimo.post(f"{URL}/{s.id}/resolver", json={"numero_estimado": "591"}, headers=_h())
    assert r.status_code == 409
    assert client_anonimo.get(URL, headers=_h()).json() == []


def test_api_resolver_solicitud_cancelada_da_404(client, client_anonimo, db_session):
    s, _ = _pedido(client, db_session)
    sid = s.id
    client.post(f"/estimados/solicitudes/{sid}/cancelar", follow_redirects=False)
    r = client_anonimo.post(f"{URL}/{sid}/resolver", json={"numero_estimado": "590"}, headers=_h())
    assert r.status_code == 404
