from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text as sa_text

from app.routers import auth_routes

AR = timezone(timedelta(hours=-3))


@pytest.mark.parametrize(
    "dia,hora,minuto,esperado",
    [
        (7, 7, 29, False),   # lunes 7:29: todavía no
        (7, 7, 30, True),    # lunes 7:30: arranca
        (7, 13, 0, True),    # lunes mediodía
        (11, 19, 29, True),  # viernes 19:29
        (11, 19, 30, False), # viernes 19:30: ya no
        (12, 12, 0, False),  # sábado
        (13, 12, 0, False),  # domingo
    ],
)
def test_horario_laboral_lunes_a_viernes(dia, hora, minuto, esperado):
    # 2026-09-07 es lunes
    assert auth_routes.en_horario_laboral(datetime(2026, 9, dia, hora, minuto, tzinfo=AR)) is esperado


def test_horario_se_evalua_en_hora_argentina_aunque_llegue_en_utc():
    # 10:30 UTC = 7:30 en Argentina (lunes)
    assert auth_routes.en_horario_laboral(datetime(2026, 9, 7, 10, 30, tzinfo=timezone.utc)) is True
    # 22:30 UTC = 19:30 en Argentina
    assert auth_routes.en_horario_laboral(datetime(2026, 9, 7, 22, 30, tzinfo=timezone.utc)) is False


def _contar_consultas(monkeypatch):
    consultas = []

    def contando(sql):
        consultas.append(sql)
        return sa_text(sql)

    monkeypatch.setattr(auth_routes, "text", contando)
    auth_routes._ULTIMO_DESPERTAR = 0.0
    return consultas


def test_mantener_en_horario_consulta_la_base(client_anonimo, monkeypatch):
    consultas = _contar_consultas(monkeypatch)
    monkeypatch.setattr(auth_routes, "_ahora", lambda: datetime(2026, 9, 7, 12, 0, tzinfo=AR))
    resp = client_anonimo.get("/auth/mantener")
    assert resp.status_code == 204
    assert resp.headers["x-mantener"] == "ok"
    assert len(consultas) == 1


def test_mantener_fuera_de_horario_no_toca_la_base(client_anonimo, monkeypatch):
    consultas = _contar_consultas(monkeypatch)
    monkeypatch.setattr(auth_routes, "_ahora", lambda: datetime(2026, 9, 12, 12, 0, tzinfo=AR))  # sábado
    resp = client_anonimo.get("/auth/mantener")
    assert resp.status_code == 204
    assert resp.headers["x-mantener"] == "fuera-de-horario"
    assert consultas == []
