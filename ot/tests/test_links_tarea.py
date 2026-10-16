"""Links de la tarea: varios vínculos por tarea y celda de la tabla como
hipervínculo (2026-10-16)."""
from app.models import Responsable, Tarea
from app.templating import href_externo


def _tarea(db_session, links):
    fer = db_session.query(Responsable).filter_by(nombre="fer").one()
    return {"ot_numero": "4200", "ot_titulo": "Con links", "detalle": "Tarea con links", "fecha_pedido": "2026-10-16",
            "tipos": "diseño", "responsable_ids": str(fer.id), "link_drive": links}


def test_guarda_varios_links_sin_vacios_ni_repetidos(client, db_session):
    links = ["https://drive.google.com/a", "", "drive.google.com/b", "https://drive.google.com/a"]
    assert client.post("/tareas", data=_tarea(db_session, links)).status_code == 200
    t = db_session.query(Tarea).filter_by(detalle="Tarea con links").one()
    assert t.link_drive == "https://drive.google.com/a\ndrive.google.com/b"

    html = client.get("/tareas").text
    assert "cell-drive--varios" in html
    assert 'href="https://drive.google.com/b"' in html  # sin esquema: se asume https

    # el drawer muestra un input por link
    assert client.get(f"/tareas/{t.id}").text.count('name="link_drive"') == 2


def test_un_solo_link_es_hipervinculo_directo(client, db_session):
    assert client.post("/tareas", data=_tarea(db_session, ["https://drive.google.com/x"])).status_code == 200
    html = client.get("/tareas").text
    assert '<a class="cell-drive is-linked" href="https://drive.google.com/x" target="_blank"' in html


def test_sin_links_queda_null(client, db_session):
    assert client.post("/tareas", data=_tarea(db_session, [""])).status_code == 200
    assert db_session.query(Tarea).filter_by(detalle="Tarea con links").one().link_drive is None


def test_href_externo_no_linkea_esquemas_raros():
    assert href_externo("javascript:alert(1)") is None
    assert href_externo("data:text/html,x") is None
    assert href_externo("con espacios.com/x y") is None
    assert href_externo("HTTPS://drive.google.com/x") == "HTTPS://drive.google.com/x"
