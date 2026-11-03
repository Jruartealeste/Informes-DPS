"""Google Sheet con los items del Estimado: carga en la UI y lectura por la API de sync."""

from app.config import settings
from app.models import Estimado
from tests.test_estimados import _armar, _crear

URL = "/api/sync/estimados-con-sheet"
SHEET = "https://docs.google.com/spreadsheets/d/1fRv5MtmB0pDJ8YbKo5cY8JXRy2-Ffjg7Jc9TVBBMGP0/edit?gid=998284253#gid=998284253"


def _h():
    return {"Authorization": f"Bearer {settings.sync_token}"}


def test_guardar_sheet_y_mostrarlo_en_el_detalle(client, db_session):
    est_id = _crear(client, _armar(db_session))
    r = client.post(
        f"/estimados/{est_id}/sheet",
        data={"sheet_url": SHEET, "sheet_pestana": "Presentación", "sheet_fila_inicio": "15", "items_modo": "total"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    db_session.expire_all()
    est = db_session.get(Estimado, est_id)
    assert est.sheet_url == SHEET and est.sheet_fila_inicio == 15 and est.items_modo == "total"
    html = client.get(f"/estimados/{est_id}").text
    assert "Google Sheet con los items" in html and "Abrir el sheet" in html


def test_sheet_valida_link_modo_y_fila(client, db_session):
    est_id = _crear(client, _armar(db_session))
    url = f"/estimados/{est_id}/sheet"
    assert client.post(url, data={"sheet_url": "https://evil.example/x"}).status_code == 422
    assert client.post(url, data={"sheet_url": "javascript:alert(1)"}).status_code == 422
    assert client.post(url, data={"sheet_url": SHEET, "items_modo": "otro"}).status_code == 422
    assert client.post(url, data={"sheet_url": SHEET, "sheet_fila_inicio": "abc"}).status_code == 422
    assert client.post(url, data={"sheet_url": SHEET, "sheet_fila_inicio": "0"}).status_code == 422


def test_sheet_vacio_quita_el_vinculo(client, db_session):
    est_id = _crear(client, _armar(db_session))
    client.post(f"/estimados/{est_id}/sheet", data={"sheet_url": SHEET, "sheet_fila_inicio": "20"})
    client.post(f"/estimados/{est_id}/sheet", data={"sheet_url": ""})
    db_session.expire_all()
    est = db_session.get(Estimado, est_id)
    assert est.sheet_url is None and est.sheet_fila_inicio is None and est.items_modo is None


def test_api_lista_solo_estimados_con_sheet_y_numero(client, client_anonimo, db_session):
    assert client_anonimo.get(URL).status_code == 401
    est_id = _crear(client, _armar(db_session))
    client.post(f"/estimados/{est_id}/sheet", data={"sheet_url": SHEET})
    # Con sheet pero sin número en Advertys todavía: no aparece.
    assert client_anonimo.get(URL, headers=_h()).json() == []
    client.post(f"/estimados/{est_id}/cargar-numero", data={"numero_estimado": "599"})
    [item] = client_anonimo.get(URL, headers=_h()).json()
    assert item["numero_estimado"] == "599" and item["numero_ot_advertys"] == "260"
    assert item["sheet_url"] == SHEET
    assert item["sheet_pestana"] == "Presentación" and item["sheet_fila_inicio"] == 15 and item["items_modo"] == "cantidad"
