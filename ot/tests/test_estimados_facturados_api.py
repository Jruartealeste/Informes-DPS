"""API para Informes/modules/sync_tareas_app/marcar_facturados.py: pasa a
FACTURADO las tareas de Estimados ya facturados en Advertys."""

from app.config import settings
from app.models import EstadoFacturacion, EstadoTarea, Estimado, Tarea
from tests.test_estimados import _armar, _crear

LISTA = "/api/sync/estimados-a-facturar"
MARCAR = "/api/sync/estimados-facturados"


def _h():
    return {"Authorization": f"Bearer {settings.sync_token}"}


def _estimado_con_numero(client, db_session, numero="590"):
    est_id = _crear(client, _armar(db_session), titulo="Catálogo")
    est = db_session.get(Estimado, est_id)
    est.numero_estimado = numero
    db_session.commit()
    return est_id


def test_exige_token(client_anonimo):
    assert client_anonimo.get(LISTA).status_code == 401
    assert client_anonimo.post(MARCAR, json={"numeros_estimado": ["1"]}).status_code == 401


def test_lista_estimados_con_tareas_sin_facturar(client, client_anonimo, db_session):
    _estimado_con_numero(client, db_session)
    [item] = client_anonimo.get(LISTA, headers=_h()).json()
    assert item["numero_estimado"] == "590" and len(item["tareas_pendientes"]) == 2


def test_marca_facturado_e_ignora_anuladas_y_no_corresponde(client, client_anonimo, db_session):
    est_id = _estimado_con_numero(client, db_session)
    tareas = db_session.get(Estimado, est_id).tareas
    tareas[0].estado_tarea = EstadoTarea.ANULADA
    db_session.commit()
    r = client_anonimo.post(MARCAR, json={"numeros_estimado": ["590", "999"]}, headers=_h())
    assert r.status_code == 200
    assert r.json()["tareas_marcadas"] == 1 and r.json()["estimados_no_encontrados"] == ["999"]
    db_session.expire_all()
    estados = {t.id: t.estado_facturacion for t in db_session.query(Tarea)}
    assert estados[tareas[1].id] == EstadoFacturacion.FACTURADO
    assert estados[tareas[0].id] != EstadoFacturacion.FACTURADO
    # idempotente: ya no hay nada pendiente
    assert client_anonimo.get(LISTA, headers=_h()).json() == []
    assert client_anonimo.post(MARCAR, json={"numeros_estimado": ["590"]}, headers=_h()).json()["tareas_marcadas"] == 0
