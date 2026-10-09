from datetime import date

from app.models import (
    Cliente,
    EstadoEstimado,
    EstadoTarea,
    Estimado,
    OtInterna,
    SolicitudAltaEstimado,
    Tarea,
)
from app.viewmodels import _comando_crear_estimado


def _armar(db_session, n_tareas=2):
    cliente = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    ot = OtInterna(numero_interno="4000", cliente_id=cliente.id, numero_ot_advertys="260")
    db_session.add(ot)
    db_session.flush()
    tareas = [
        Tarea(ot_interna_id=ot.id, detalle=f"t{i}", fecha_pedido=date(2026, 10, 1))
        for i in range(n_tareas)
    ]
    db_session.add_all(tareas)
    db_session.commit()
    return [t.id for t in tareas]


def _crear(client, ids, titulo="E1"):
    r = client.post(
        "/estimados",
        data={"numero_ot_advertys": "260", "titulo": titulo, "tarea_ids": ",".join(map(str, ids))},
        follow_redirects=False,
    )
    assert r.status_code == 303
    return int(r.headers["location"].rsplit("/", 1)[1])


def test_tarea_ids_no_numerico_da_422(client, db_session):
    ids = _armar(db_session)
    r = client.post("/estimados", data={"numero_ot_advertys": "260", "titulo": "x", "tarea_ids": "abc"})
    assert r.status_code == 422
    est_id = _crear(client, ids[:1])
    r = client.post(f"/estimados/{est_id}/agregar", data={"tarea_ids": "abc"})
    assert r.status_code == 422


def test_anulada_no_es_candidata(client, db_session):
    ids = _armar(db_session)
    db_session.get(Tarea, ids[0]).estado_tarea = EstadoTarea.ANULADA
    db_session.commit()
    r = client.get("/estimados/nuevo?ot_advertys=260")
    assert f'class="chk-tarea" value="{ids[0]}"' not in r.text
    assert f'class="chk-tarea" value="{ids[1]}"' in r.text


def test_anulada_no_entra_en_facturacion(client, db_session):
    ids = _armar(db_session)
    est_id = _crear(client, ids)
    db_session.get(Tarea, ids[0]).estado_tarea = EstadoTarea.ANULADA
    db_session.commit()
    r = client.get("/facturacion")
    assert r.status_code == 200
    assert "tarea-anulada" not in r.text
    assert f"/facturacion/tareas/{ids[0]}/estado" not in r.text
    assert f"/facturacion/tareas/{ids[1]}/estado" in r.text
    assert est_id


def test_cargar_numero_con_pedido_pendiente_da_409(client, db_session):
    ids = _armar(db_session)
    est_id = _crear(client, ids)
    assert client.post(f"/estimados/{est_id}/generar-en-advertys", data={}, follow_redirects=False).status_code == 303
    r = client.post(f"/estimados/{est_id}/cargar-numero", data={"numero_estimado": "777"})
    assert r.status_code == 409
    db_session.expire_all()
    assert db_session.get(Estimado, est_id).estado == EstadoEstimado.BORRADOR
    # con pedido pendiente tampoco se editan las tareas
    assert client.post(f"/estimados/{est_id}/tareas/{ids[0]}/quitar").status_code == 409


def test_fechas_invalidas_dan_422_y_no_crean_pedido(client, db_session):
    ids = _armar(db_session)
    est_id = _crear(client, ids)
    for malo in ["$HOME", "a" * 40, "2026-10-01"]:
        r = client.post(f"/estimados/{est_id}/generar-en-advertys", data={"fecha_solicitada": malo})
        assert r.status_code == 422
    assert db_session.query(SolicitudAltaEstimado).count() == 0
    r = client.post(
        f"/estimados/{est_id}/generar-en-advertys",
        data={"fecha_solicitada": "5/10/2026", "fecha_analisis": "1/10/2026"},
        follow_redirects=False,
    )
    assert r.status_code == 303


def test_estimado_sin_tareas_no_genera_pedido(client, db_session):
    ids = _armar(db_session, n_tareas=1)
    est_id = _crear(client, ids)
    client.post(f"/estimados/{est_id}/tareas/{ids[0]}/quitar")
    r = client.post(f"/estimados/{est_id}/generar-en-advertys", data={})
    assert r.status_code == 422
    assert db_session.query(SolicitudAltaEstimado).count() == 0


def test_comando_escapa_titulo_y_fechas():
    est = Estimado(titulo='Camp "X" $(calc) it\'s', numero_ot_advertys="260")
    sol = SolicitudAltaEstimado(fecha_solicitada="$HOME", fecha_analisis="1/10/2026")
    cmd = _comando_crear_estimado(sol, est)
    assert "'Camp \"X\" $(calc) it''s'" in cmd
    assert "--fecha-solicitada '$HOME'" in cmd
    assert '"' not in cmd.replace("\"X\"", "")


def test_tarea_en_estimado_no_se_anula_hasta_quitarla(client, db_session):
    ids = _armar(db_session)
    est_id = _crear(client, ids)
    r = client.post(f"/tareas/{ids[0]}/anular")
    assert r.status_code == 409
    db_session.expire_all()
    assert db_session.get(Tarea, ids[0]).estado_tarea != EstadoTarea.ANULADA

    client.post(f"/estimados/{est_id}/tareas/{ids[0]}/quitar")
    assert client.post(f"/tareas/{ids[0]}/anular").status_code == 200
    db_session.expire_all()
    assert db_session.get(Tarea, ids[0]).estado_tarea == EstadoTarea.ANULADA
