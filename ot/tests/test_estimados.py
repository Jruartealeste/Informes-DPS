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


def test_titulo_de_mas_de_300_caracteres_da_422(client, db_session):
    ids = _armar(db_session)
    datos = {"numero_ot_advertys": "260", "tarea_ids": str(ids[0])}
    assert client.post("/estimados", data={**datos, "titulo": "a" * 301}).status_code == 422
    assert client.post("/estimados", data={**datos, "titulo": "a" * 300}, follow_redirects=False).status_code == 303


def test_facturacion_solo_acepta_tareas_de_la_cola(client, db_session):
    ids = _armar(db_session)
    _crear(client, ids[:1])
    en_cola, fuera = ids[0], ids[1]  # `fuera` no está en ningún Estimado

    assert client.post(f"/facturacion/tareas/{en_cola}/estado", data={"estado_facturacion": "BASURA"}).status_code == 422
    assert client.post(f"/facturacion/tareas/{en_cola}/estado", data={"estado_facturacion": "FACTURADO"}).status_code == 200
    assert client.post(f"/facturacion/tareas/{fuera}/estado", data={"estado_facturacion": "FACTURADO"}).status_code == 404
    assert client.post("/facturacion/tareas/99999/estado", data={"estado_facturacion": "FACTURADO"}).status_code == 404
    db_session.expire_all()
    assert db_session.get(Tarea, en_cola).estado_facturacion.name == "FACTURADO"
    assert db_session.get(Tarea, fuera).estado_facturacion.name == "SIN_FACTURAR"


def test_desdoblar_tarea_crea_copia_libre_para_otro_estimado(client, db_session):
    ids = _armar(db_session, n_tareas=1)
    e1 = _crear(client, ids, titulo="Etapa 1")
    r = client.post(
        f"/estimados/tareas/{ids[0]}/desdoblar?volver=/estimados/{e1}", follow_redirects=False
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/estimados/{e1}"
    db_session.expire_all()
    original = db_session.get(Tarea, ids[0])
    assert original.estimado_id == e1
    copia = db_session.query(Tarea).filter(Tarea.id != ids[0]).one()
    assert copia.estimado_id is None
    assert copia.ot_interna_id == original.ot_interna_id
    assert copia.detalle == "t0 (desdoblada)"
    # la copia es candidata y entra en un segundo Estimado de la misma OT de sistema
    e2 = _crear(client, [copia.id], titulo="Etapa 2")
    assert e2 != e1


def test_desdoblar_no_redirige_a_destinos_externos(client, db_session):
    ids = _armar(db_session, n_tareas=1)
    r = client.post(f"/estimados/tareas/{ids[0]}/desdoblar?volver=//evil.com", follow_redirects=False)
    assert r.headers["location"] == "/estimados"


def _armar_dos_ots_misma_sistema(db_session):
    """Dos OT internas (4086 y 999) compartiendo la OT de sistema 260, más una
    tercera (5000) con otra OT de sistema."""
    cliente = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    ots = {
        n: OtInterna(numero_interno=n, cliente_id=cliente.id, numero_ot_advertys=s)
        for n, s in (("4086", "260"), ("999", "260"), ("5000", "300"))
    }
    db_session.add_all(ots.values())
    db_session.flush()
    tareas = {
        n: Tarea(ot_interna_id=ots[n].id, detalle=f"tarea de {n}", fecha_pedido=date(2026, 10, 1))
        for n in ots
    }
    db_session.add_all(tareas.values())
    db_session.commit()
    return {n: t.id for n, t in tareas.items()}


def test_nuevo_agrupa_candidatas_por_ot_interna_y_excluye_otra_ot_sistema(client, db_session):
    ids = _armar_dos_ots_misma_sistema(db_session)
    r = client.get("/estimados/nuevo?ot_advertys=260")
    assert r.status_code == 200
    assert f'class="chk-tarea" value="{ids["4086"]}"' in r.text
    assert f'class="chk-tarea" value="{ids["999"]}"' in r.text
    assert f'class="chk-tarea" value="{ids["5000"]}"' not in r.text
    # orden natural de los grupos: 999 antes que 4086
    assert r.text.index("OT interna 999") < r.text.index("OT interna 4086")


def test_estimado_con_tareas_de_dos_ots_internas_y_rechazo_de_otra_ot_sistema(client, db_session):
    ids = _armar_dos_ots_misma_sistema(db_session)
    est_id = _crear(client, [ids["4086"], ids["999"]])
    r = client.get(f"/estimados/{est_id}")
    assert "OT interna 999 · 1 tarea" in r.text
    assert "OT interna 4086 · 1 tarea" in r.text
    r = client.post(f"/estimados/{est_id}/agregar", data={"tarea_ids": str(ids["5000"])})
    assert r.status_code == 422


def test_listado_ofrece_nuevo_estimado_por_ot_sistema(client, db_session):
    _armar_dos_ots_misma_sistema(db_session)
    r = client.get("/estimados")
    assert r.status_code == 200
    assert '<option value="260">260 · OT int. 999, 4086</option>' in r.text
    assert '<option value="300">' in r.text


def test_selector_omite_ot_sistema_sin_tareas_libres(client, db_session):
    ids = _armar_dos_ots_misma_sistema(db_session)
    _crear(client, [ids["4086"], ids["999"]])  # agota la 260
    r = client.get("/estimados")
    assert '<option value="260">' not in r.text
    assert '<option value="300">' in r.text


def test_desenlazar_vuelve_a_borrador_y_permite_nuevo_alta(client, db_session):
    ids = _armar(db_session)
    est_id = _crear(client, ids)
    r = client.post(f"/estimados/{est_id}/generar-en-advertys", follow_redirects=False)
    assert r.status_code == 303
    sol = db_session.query(SolicitudAltaEstimado).one()
    client.post(f"/estimados/solicitudes/{sol.id}/resolver", data={"numero_estimado": "601"})
    db_session.expire_all()
    assert db_session.get(Estimado, est_id).estado == EstadoEstimado.GENERADO

    r = client.post(f"/estimados/{est_id}/desenlazar", follow_redirects=False)
    assert r.status_code == 303
    db_session.expire_all()
    e = db_session.get(Estimado, est_id)
    assert e.estado == EstadoEstimado.BORRADOR
    assert e.numero_estimado is None and e.solicitud_alta_id is None
    assert len(e.tareas) == 2
    assert db_session.query(SolicitudAltaEstimado).count() == 0
    # se puede cargar otro número
    r = client.post(f"/estimados/{est_id}/cargar-numero", data={"numero_estimado": "602"}, follow_redirects=False)
    assert r.status_code == 303


def test_desenlazar_un_borrador_es_idempotente(client, db_session):
    est_id = _crear(client, _armar(db_session))
    r = client.post(f"/estimados/{est_id}/desenlazar", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/estimados/{est_id}"
    db_session.expire_all()
    assert db_session.get(Estimado, est_id).estado == EstadoEstimado.BORRADOR
