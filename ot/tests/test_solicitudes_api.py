"""API de solicitudes de alta de OT para el skill `procesar-solicitudes-ot`
(Informes/modules/ordenes_trabajo/procesar_solicitudes.py)."""

from app.config import settings
from app.models import EstadoSolicitudAltaOt, OtInterna, SolicitudAltaOt
from tests.test_ordenes_trabajo import _dos_ots, _generar

URL = "/api/sync/solicitudes-alta-ot"


def _h():
    return {"Authorization": f"Bearer {settings.sync_token}"}


def _pedido(client, db_session):
    _dos_ots(db_session)
    r = _generar(client, ["810", "811"])
    assert r.status_code == 303
    return db_session.query(SolicitudAltaOt).one()


def test_api_solicitudes_exige_token(client_anonimo):
    assert client_anonimo.get(URL).status_code == 401
    assert client_anonimo.post(f"{URL}/1/resolver", json={"numero_ot_advertys": "1"}).status_code == 401


def test_api_lista_pendientes_con_ots_y_cliente(client, client_anonimo, db_session):
    s = _pedido(client, db_session)
    r = client_anonimo.get(URL, headers=_h())
    assert r.status_code == 200
    [item] = r.json()
    assert item["id"] == s.id and item["estado"] == "PENDIENTE"
    assert item["cliente"] == "ALUAR"
    assert sorted(o["numero_interno"] for o in item["ots"]) == ["810", "811"]
    assert client_anonimo.get(URL, params={"estado": "RESUELTA"}, headers=_h()).json() == []
    assert client_anonimo.get(URL, params={"estado": "X"}, headers=_h()).status_code == 422


def test_api_resolver_propaga_y_es_idempotente(client, client_anonimo, db_session):
    s = _pedido(client, db_session)
    r = client_anonimo.post(f"{URL}/{s.id}/resolver", json={"numero_ot_advertys": " 9500 "}, headers=_h())
    assert r.status_code == 200 and r.json()["ya_estaba_resuelta"] is False
    db_session.expire_all()
    assert s.estado == EstadoSolicitudAltaOt.RESUELTA and s.numero_ot_advertys == "9500"
    assert {o.numero_ot_advertys for o in db_session.query(OtInterna)} == {"9500"}

    # Reintento con el mismo número: OK sin cambios. Con otro: 409.
    r = client_anonimo.post(f"{URL}/{s.id}/resolver", json={"numero_ot_advertys": "9500"}, headers=_h())
    assert r.status_code == 200 and r.json()["ya_estaba_resuelta"] is True
    r = client_anonimo.post(f"{URL}/{s.id}/resolver", json={"numero_ot_advertys": "9501"}, headers=_h())
    assert r.status_code == 409
    assert client_anonimo.get(URL, headers=_h()).json() == []


def test_api_resolver_solicitud_cancelada_da_404(client, client_anonimo, db_session):
    s = _pedido(client, db_session)
    sid = s.id
    client.post(f"/ordenes-trabajo/solicitudes/{sid}/cancelar", follow_redirects=False)
    r = client_anonimo.post(f"{URL}/{sid}/resolver", json={"numero_ot_advertys": "9500"}, headers=_h())
    assert r.status_code == 404


def test_pedido_nuevo_avisa_que_hay_que_correr_el_alta_con_claude(client, db_session):
    _dos_ots(db_session)
    r = _generar(client, ["810"])
    assert r.headers["location"].startswith("/ordenes-trabajo/solicitudes?nueva=")
    html = client.get(r.headers["location"]).text
    assert "todavía no está en Advertys" in html
    assert "procesá las solicitudes de OT pendientes" in html
    assert "is-nueva" in html


def test_sin_pendientes_no_hay_aviso(client, db_session):
    s = _pedido(client, db_session)
    client.post(f"/ordenes-trabajo/solicitudes/{s.id}/resolver", data={"numero_ot_advertys": "9500"})
    html = client.get("/ordenes-trabajo/solicitudes").text
    assert "aviso-pendiente-claude" not in html


def test_ot_internas_y_sidebar_marcan_altas_pendientes(client, db_session):
    html = client.get("/ordenes-trabajo").text
    assert "sidebar__alerta" not in html and "filters__revision has-items" not in html

    s = _pedido(client, db_session)
    html = client.get("/ordenes-trabajo").text
    # La OT del pedido lleva la marca en la tabla; la que no, no.
    assert html.count('class="marca-alta-pendiente"') == 2  # 810 y 811
    # Alcanza con el botón "Solicitudes de alta N" resaltado (sin cartel aparte).
    assert "filters__revision has-items" in html and "espera crearse en Advertys" not in html
    # La marca del sidebar se ve desde cualquier pantalla.
    assert 'class="sidebar__alerta"' in client.get("/tareas").text

    client.post(f"/ordenes-trabajo/solicitudes/{s.id}/resolver", data={"numero_ot_advertys": "9500"})
    html = client.get("/ordenes-trabajo").text
    assert "filters__revision has-items" not in html and "sidebar__alerta" not in html
    assert "marca-alta-pendiente\"" not in html
