from app.models import Cliente, EstadoFacturacion, EstadoOtInterna, EstadoTarea, OtInterna, Responsable, Tarea


def test_lista_vacia(client):
    r = client.get("/tareas")
    assert r.status_code == 200
    assert "Ninguna tarea coincide con los filtros." in r.text


def test_crear_tarea_nueva_ot(client, db_session):
    fer = db_session.query(Responsable).filter_by(nombre="fer").one()
    juli = db_session.query(Responsable).filter_by(nombre="juli").one()

    r = client.post(
        "/tareas",
        data={
            "ot_numero": "4200",
            "detalle": "Diseño de flyer institucional",
            "fecha_pedido": "2026-08-01",
            "pedido_por": "marina",
            "tipos": "diseño",
            "responsable_ids": f"{fer.id},{juli.id}",
            "estado_facturacion": "SIN_FACTURAR",
        },
    )
    assert r.status_code == 200
    assert "Diseño de flyer institucional" in r.text
    assert "OT 4200" in r.text

    ot = db_session.query(OtInterna).filter_by(numero_interno="4200").one()
    assert ot.estado == EstadoOtInterna.ABIERTA
    tarea = db_session.query(Tarea).filter_by(ot_interna_id=ot.id).one()
    assert sorted(r.responsable.nombre for r in tarea.responsables) == ["fer", "juli"]


def test_tarea_con_ot_ambigua_no_crea_ot_interna(client, db_session):
    fer = db_session.query(Responsable).filter_by(nombre="fer").one()

    client.post(
        "/tareas",
        data={
            "ot_numero": "4086/4110",
            "detalle": "Video institucional",
            "fecha_pedido": "2026-08-01",
            "tipos": "produccion",
            "responsable_ids": str(fer.id),
        },
    )
    tarea = db_session.query(Tarea).filter_by(detalle="Video institucional").one()
    assert tarea.ot_interna_id is None
    assert tarea.ot_ambigua == "4086/4110"
    assert db_session.query(OtInterna).count() == 0


def test_filtro_por_estado(client, db_session):
    cliente = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    ot = OtInterna(numero_interno="4210", cliente_id=cliente.id)
    db_session.add(ot)
    db_session.flush()
    db_session.add(Tarea(ot_interna_id=ot.id, detalle="Tarea finalizada", estado_tarea=EstadoTarea.FINALIZADO))
    db_session.add(Tarea(ot_interna_id=ot.id, detalle="Tarea en proceso", estado_tarea=EstadoTarea.EN_PROCESO))
    db_session.commit()

    r = client.get("/tareas/partial", params={"f_est": "FINALIZADO"})
    assert "Tarea finalizada" in r.text
    assert "Tarea en proceso" not in r.text


def test_editar_tarea(client, db_session):
    fer = db_session.query(Responsable).filter_by(nombre="fer").one()
    cliente = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    ot = OtInterna(numero_interno="4220", cliente_id=cliente.id)
    db_session.add(ot)
    db_session.flush()
    tarea = Tarea(ot_interna_id=ot.id, detalle="Tarea original")
    db_session.add(tarea)
    db_session.commit()
    tarea_id = tarea.id

    r = client.patch(
        f"/tareas/{tarea_id}",
        data={
            "ot_numero": "4220",
            "detalle": "Tarea editada",
            "fecha_pedido": "2026-08-01",
            "tipos": "diseño",
            "responsable_ids": str(fer.id),
            "estado_facturacion": "PARA_FACTURAR",
        },
    )
    assert r.status_code == 200
    assert "Tarea editada" in r.text

    db_session.expire_all()
    actualizada = db_session.get(Tarea, tarea_id)
    assert actualizada.detalle == "Tarea editada"
    assert actualizada.estado_facturacion.name == "PARA_FACTURAR"


def test_crear_tarea_sin_campos_obligatorios_falla(client, db_session):
    # Ver ot/CLAUDE.md: hasta 2026-09-17 se podía crear una tarea "borrador"
    # con solo el detalle, sin OT — decisión revertida, ahora OT interna,
    # fecha de pedido, tipo de tarea y responsables son obligatorios siempre
    # (la sheet ya lo bloquea del lado del cliente; esto prueba el respaldo
    # server-side para quien pegue directo contra el endpoint).
    r = client.post("/tareas", data={"detalle": "Recordar pedir presupuesto a imprenta"})
    assert r.status_code == 422

    assert db_session.query(Tarea).filter_by(detalle="Recordar pedir presupuesto a imprenta").count() == 0


def test_no_se_puede_cambiar_ot_ya_asignada(client, db_session):
    fer = db_session.query(Responsable).filter_by(nombre="fer").one()
    cliente = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    ot_original = OtInterna(numero_interno="4240", cliente_id=cliente.id)
    ot_otra = OtInterna(numero_interno="4241", cliente_id=cliente.id)
    db_session.add_all([ot_original, ot_otra])
    db_session.flush()
    tarea = Tarea(ot_interna_id=ot_original.id, detalle="Tarea con OT fija")
    db_session.add(tarea)
    db_session.commit()
    tarea_id = tarea.id

    r = client.patch(
        f"/tareas/{tarea_id}",
        data={
            "ot_numero": "4241",
            "detalle": "Tarea con OT fija",
            "fecha_pedido": "2026-08-01",
            "tipos": "diseño",
            "responsable_ids": str(fer.id),
        },
    )
    assert r.status_code == 200

    db_session.expire_all()
    actualizada = db_session.get(Tarea, tarea_id)
    assert actualizada.ot_interna_id == ot_original.id


def test_anular_tarea(client, db_session):
    cliente = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    ot = OtInterna(numero_interno="4250", cliente_id=cliente.id)
    db_session.add(ot)
    db_session.flush()
    tarea = Tarea(ot_interna_id=ot.id, detalle="Tarea a anular", estado_tarea=EstadoTarea.EN_PROCESO)
    db_session.add(tarea)
    db_session.commit()
    tarea_id = tarea.id

    r = client.post(f"/tareas/{tarea_id}/anular")
    assert r.status_code == 200

    db_session.expire_all()
    actualizada = db_session.get(Tarea, tarea_id)
    assert actualizada.estado_tarea == EstadoTarea.ANULADA


def test_no_se_puede_anular_tarea_facturada(client, db_session):
    cliente = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    ot = OtInterna(numero_interno="4260", cliente_id=cliente.id)
    db_session.add(ot)
    db_session.flush()
    tarea = Tarea(
        ot_interna_id=ot.id,
        detalle="Tarea ya facturada",
        estado_tarea=EstadoTarea.APROBADO,
        estado_facturacion=EstadoFacturacion.FACTURADO,
    )
    db_session.add(tarea)
    db_session.commit()
    tarea_id = tarea.id

    r = client.post(f"/tareas/{tarea_id}/anular")
    assert r.status_code == 200

    db_session.expire_all()
    actualizada = db_session.get(Tarea, tarea_id)
    assert actualizada.estado_tarea == EstadoTarea.APROBADO


def test_necesitan_revision(client, db_session):
    cliente = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    ot = OtInterna(numero_interno="4230", cliente_id=cliente.id)
    db_session.add(ot)
    db_session.flush()
    db_session.add(Tarea(ot_interna_id=ot.id, detalle="Sin tipo ni fecha"))
    db_session.commit()

    r = client.get("/tareas/partial", params={"revision": "1"})
    assert "Sin tipo ni fecha" in r.text
