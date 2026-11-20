import datetime as dt

from app.models import Cliente, EstadoTarea, OtInterna, Tarea
from app.viewmodels import hoy_ar


def _tarea(db, cliente, numero, detalle, dias, estado=None, activo=True):
    """Tarea que vence `dias` días desde hoy (negativo = ya vencida)."""
    ot = db.query(OtInterna).filter_by(numero_interno=numero, cliente_id=cliente.id).first()
    if not ot:
        ot = OtInterna(numero_interno=numero, cliente_id=cliente.id, titulo=f"OT {numero}")
        db.add(ot)
        db.flush()
    t = Tarea(ot_interna_id=ot.id, detalle=detalle, fecha_vencimiento=hoy_ar() + dt.timedelta(days=dias), estado_tarea=estado)
    db.add(t)
    db.commit()
    return t


def test_aviso_de_vencidas_de_otro_anunciante(client, db_session):
    aluar = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    otro = Cliente(nombre="OTRO")
    db_session.add(otro)
    db_session.commit()
    _tarea(db_session, otro, "100", "Vencida en otro", -5)

    # Sin cookie el anunciante activo es ALUAR: la vencida de OTRO se avisa igual.
    html = client.get("/tareas").text
    assert "1 tarea vencida" in html
    assert "OTRO (1)" in html
    assert 'aria-label="1 tarea vencida"' in html  # marca del sidebar

    # Parado en OTRO ya no es "otro anunciante": sin banner, sí la marca del sidebar.
    client.cookies.set("cliente_id", str(otro.id))
    html = client.get("/tareas").text
    assert "aviso-vencidas" not in html.split("<main", 1)[1]
    assert 'aria-label="1 tarea vencida"' in html
    assert aluar.id != otro.id


def test_no_cuentan_cerradas_ni_lejanas_ni_inactivas(client, db_session):
    activo = Cliente(nombre="ACTIVO")
    baja = Cliente(nombre="BAJA", activo=False)
    db_session.add_all([activo, baja])
    db_session.commit()
    _tarea(db_session, activo, "1", "finalizada", -3, EstadoTarea.FINALIZADO)
    _tarea(db_session, activo, "1", "anulada", -3, EstadoTarea.ANULADA)
    _tarea(db_session, activo, "1", "lejana", 30)
    _tarea(db_session, baja, "2", "de anunciante dado de baja", -3)
    html = client.get("/vencimientos").text
    assert "No hay tareas vencidas" in html


def test_pagina_vencimientos_agrupa_por_anunciante(client, db_session):
    a = Cliente(nombre="AAA")
    b = Cliente(nombre="BBB")
    db_session.add_all([a, b])
    db_session.commit()
    _tarea(db_session, a, "1", "una vencida", -2)
    _tarea(db_session, b, "1", "vence hoy", 0)
    _tarea(db_session, b, "2", "otra vencida", -10)
    html = client.get("/vencimientos").text
    assert "2 vencidas · 1 por vencer" in html
    assert "hace 10 días" in html and "vence hoy" in html
    # BBB tiene 1 vencida + 1 hoy; AAA 1 vencida: empatan en vencidas -> orden alfabético
    assert html.index("AAA") < html.index("BBB")


def test_activar_con_next_solo_rutas_locales(client, db_session):
    c = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    r = client.get(f"/clientes/{c.id}/activar?next=/tareas?vencidas=1", follow_redirects=False)
    assert r.headers["location"] == "/tareas?vencidas=1"
    for malo in ("https://evil.com", "//evil.com", "/\\evil.com"):
        r = client.get(f"/clientes/{c.id}/activar", params={"next": malo}, follow_redirects=False)
        assert r.headers["location"] == "/tareas"
