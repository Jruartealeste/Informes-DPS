"""Punta a punta de informes/modules/ordenes_trabajo/procesar_solicitudes.py
(skill `procesar-solicitudes-ot`) contra la API real de esta app en proceso:
httpx se redirige al TestClient y crear_ot se simula, nunca toca Advertys."""
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "informes"))
from modules.ordenes_trabajo import procesar_solicitudes as ps  # noqa: E402

from app.config import settings
from app.models import OtInterna, SolicitudAltaOt
from tests.test_ordenes_trabajo import _dos_ots, _generar

URL = "http://localhost:8123"


@pytest.fixture
def entorno(client, client_anonimo, db_session, monkeypatch, tmp_path):
    monkeypatch.setenv("OT_SYNC_TOKEN", settings.sync_token)

    def fake_request(metodo, url, headers=None, timeout=None, **kw):
        return client_anonimo.request(metodo, urlparse(url).path, headers=headers, **kw)

    monkeypatch.setattr(ps.httpx, "request", fake_request)
    _dos_ots(db_session)
    _dos_ots(db_session, "812", "813")
    assert _generar(client, ["810", "811"]).status_code == 303
    assert _generar(client, ["812"]).status_code == 303
    ids = [s.id for s in db_session.query(SolicitudAltaOt).order_by(SolicitudAltaOt.id)]
    return tmp_path / "log.jsonl", ids


def test_flujo_completo(entorno, db_session, capsys, monkeypatch):
    log, (a, b) = entorno
    assert ps.cmd_listar(URL, log) == 0
    out = capsys.readouterr().out
    assert f"Solicitud #{a}" in out and f"Solicitud #{b}" in out and "810 , 811" not in out

    # Falla el resolver de la primera despues de crear: queda colgada, se frena la tanda.
    real = ps.resolver_api
    monkeypatch.setattr(ps, "resolver_api", lambda *x: (_ for _ in ()).throw(ps.ProcesarError("red caida")))
    assert ps.cmd_procesar(URL, [a, b], True, log) == 1
    out = capsys.readouterr().out
    assert "red caida" in out and f"no se procesaron #{b}" in out
    monkeypatch.setattr(ps, "resolver_api", real)

    assert ps.cmd_listar(URL, log) == 0
    out = capsys.readouterr().out
    assert f"YA CREADA en Advertys como OT SIM-{a}" in out

    # Reintento: no vuelve a crear la colgada.
    creadas = []
    orig = ps._crear
    monkeypatch.setattr(ps, "_crear", lambda s, sim: creadas.append(s["id"]) or orig(s, sim))
    assert ps.cmd_procesar(URL, [a, b, 9999], True, log) == 0
    out = capsys.readouterr().out
    assert creadas == [b]
    assert "SALTEADA" in out
    db_session.expire_all()
    nums = {o.numero_interno: o.numero_ot_advertys for o in db_session.query(OtInterna)}
    assert nums["810"] == nums["811"] == f"SIM-{a}" and nums["812"] == f"SIM-{b}" and nums["813"] is None
    assert ps.cmd_listar(URL, log) == 0
    assert "No hay solicitudes" in capsys.readouterr().out


def test_cancelada_despues_de_crear_queda_huerfana_y_se_descarta(entorno, client, capsys, monkeypatch):
    log, (a, b) = entorno
    real = ps.resolver_api
    monkeypatch.setattr(ps, "resolver_api", lambda *x: (_ for _ in ()).throw(ps.ProcesarError("timeout")))
    ps.cmd_procesar(URL, [a], True, log)
    monkeypatch.setattr(ps, "resolver_api", real)
    client.post(f"/ordenes-trabajo/solicitudes/{a}/cancelar", follow_redirects=False)
    capsys.readouterr()
    ps.cmd_listar(URL, log)
    out = capsys.readouterr().out
    assert "ATENCION" in out and f"SIM-{a}" in out
    # Procesar el id huerfano intenta vincular y da 404 explicito.
    assert ps.cmd_procesar(URL, [a], True, log) == 1
    out = capsys.readouterr().out
    assert "404" in out
    ps.cmd_descartar(URL, [a], log)
    ps.cmd_listar(URL, log)
    out = capsys.readouterr().out
    assert "ATENCION" not in out, out
