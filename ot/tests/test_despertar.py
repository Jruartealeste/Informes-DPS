from sqlalchemy import text as sa_text

from app.routers import auth_routes


def test_despertar_no_pide_sesion_y_responde_204(client_anonimo):
    auth_routes._ULTIMO_DESPERTAR = 0.0
    resp = client_anonimo.get("/auth/despertar")
    assert resp.status_code == 204
    assert resp.headers["cache-control"] == "no-store"


def test_despertar_consulta_la_base_como_mucho_una_vez_por_ventana(client_anonimo, monkeypatch):
    consultas = []

    def contando(sql):
        consultas.append(sql)
        return sa_text(sql)

    monkeypatch.setattr(auth_routes, "text", contando)
    auth_routes._ULTIMO_DESPERTAR = 0.0
    for _ in range(5):
        assert client_anonimo.get("/auth/despertar").status_code == 204
    assert len(consultas) == 1


def test_login_llama_a_despertar(client_anonimo):
    assert "/auth/despertar" in client_anonimo.get("/auth/login").text
