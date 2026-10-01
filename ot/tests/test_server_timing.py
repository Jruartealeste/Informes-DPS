import re


def test_responde_con_server_timing(client):
    resp = client.get("/tareas")
    assert resp.status_code == 200
    valor = resp.headers["server-timing"]
    assert re.search(r"total;dur=\d+", valor)
    # /tareas toca la base: tiene que haber contado al menos una query
    m = re.search(r'db;dur=\d+;desc="(\d+) queries', valor)
    assert m and int(m.group(1)) >= 1


def test_server_timing_tambien_en_rutas_sin_base(client_anonimo):
    resp = client_anonimo.get("/auth/login")
    assert "total;dur=" in resp.headers["server-timing"]
