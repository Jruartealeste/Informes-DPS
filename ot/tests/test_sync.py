import json
import re

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


PRODUCTOS_URL = "/api/sync/productos"


def _prod(id_, nombre, anunciante="ALUAR ALUMINIO ARGENTINO SOCIEDAD ANONIM"):
    return {"id_advertys": id_, "nombre": nombre, "anunciante": anunciante}


def test_sync_productos_exige_token(client_anonimo):
    assert client_anonimo.post(PRODUCTOS_URL, json=[_prod("1", "A")]).status_code == 401


def test_sync_productos_es_reemplazo_total(client_anonimo, db_session):
    from app.models import ProductoAdvertys

    r = client_anonimo.post(PRODUCTOS_URL, json=[_prod("1", "Hosting"), _prod("2", "Viejo")], headers=_h())
    assert r.status_code == 200 and r.json()["cantidad"] == 2
    # segundo sync: 1 cambia de nombre, 2 desaparece (deshabilitado en Advertys), 3 es nuevo
    r = client_anonimo.post(PRODUCTOS_URL, json=[_prod("1", "Hosting web"), _prod("3", "Nuevo")], headers=_h())
    assert r.status_code == 200
    db_session.expire_all()
    assert {p.id_advertys: p.nombre for p in db_session.query(ProductoAdvertys)} == {"1": "Hosting web", "3": "Nuevo"}


def test_sync_productos_vacio_o_invalido_no_toca_el_catalogo(client_anonimo, db_session):
    from app.models import ProductoAdvertys

    client_anonimo.post(PRODUCTOS_URL, json=[_prod("1", "Hosting")], headers=_h())
    assert client_anonimo.post(PRODUCTOS_URL, json=[], headers=_h()).status_code == 422
    for malo in ({"id_advertys": "2", "nombre": "  ", "anunciante": "X"}, _prod("3", "n" * 301), _prod("4", "ok", "a" * 301)):
        assert client_anonimo.post(PRODUCTOS_URL, json=[_prod("9", "Otro"), malo], headers=_h()).status_code == 422
    assert [p.id_advertys for p in db_session.query(ProductoAdvertys)] == ["1"]


def test_combo_producto_lista_solo_el_catalogo_del_cliente_del_sidebar(client, db_session):
    from app.models import ProductoAdvertys

    db_session.add_all([
        ProductoAdvertys(id_advertys="1", nombre="Hosting", anunciante="ALUAR ALUMINIO ARGENTINO SOCIEDAD ANONIM"),
        ProductoAdvertys(id_advertys="2", nombre="Diseño de piezas", anunciante="ALUAR ALUMINIO ARGENTINO SOCIEDAD ANONIM"),
        ProductoAdvertys(id_advertys="3", nombre="Brochures", anunciante="GIHON - LABORATORIOS QUIMICOS SRL"),
    ])
    db_session.commit()
    html = client.get("/ordenes-trabajo").text  # sin cookie: ALUAR
    assert 'id="select-producto"' in html
    assert 'data-anunciante="ALUAR ALUMINIO ARGENTINO SOCIEDAD ANONIM">Hosting<' in html
    assert "Brochures" not in html
