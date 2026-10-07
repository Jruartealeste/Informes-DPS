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
    assert "4200" in r.text

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


def _tarea_con_facturacion(db_session, numero, facturacion, estado=EstadoTarea.APROBADO):
    cliente = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    ot = OtInterna(numero_interno=numero, cliente_id=cliente.id)
    db_session.add(ot)
    db_session.flush()
    tarea = Tarea(ot_interna_id=ot.id, detalle="Tarea " + numero, estado_tarea=estado, estado_facturacion=facturacion)
    db_session.add(tarea)
    db_session.commit()
    return tarea.id


def test_no_se_puede_anular_tarea_facturada_ni_para_facturar(client, db_session):
    for numero, fact in (("4260", EstadoFacturacion.FACTURADO), ("4261", EstadoFacturacion.PARA_FACTURAR)):
        tarea_id = _tarea_con_facturacion(db_session, numero, fact)
        assert client.post(f"/tareas/{tarea_id}/anular").status_code == 409
        db_session.expire_all()
        assert db_session.get(Tarea, tarea_id).estado_tarea == EstadoTarea.APROBADO
        r = client.get(f"/tareas/{tarea_id}")
        assert "no se puede anular" in r.text and "disabled" in r.text


def test_se_puede_anular_tarea_finalizada_con_advertencia(client, db_session):
    tarea_id = _tarea_con_facturacion(
        db_session, "4262", EstadoFacturacion.SIN_FACTURAR, estado=EstadoTarea.FINALIZADO
    )
    assert "FINALIZADA" in client.get(f"/tareas/{tarea_id}").text
    assert client.post(f"/tareas/{tarea_id}/anular").status_code == 200
    db_session.expire_all()
    assert db_session.get(Tarea, tarea_id).estado_tarea == EstadoTarea.ANULADA


def test_necesitan_revision(client, db_session):
    cliente = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    ot = OtInterna(numero_interno="4230", cliente_id=cliente.id)
    db_session.add(ot)
    db_session.flush()
    db_session.add(Tarea(ot_interna_id=ot.id, detalle="Sin tipo ni fecha"))
    db_session.commit()

    r = client.get("/tareas/partial", params={"revision": "1"})
    assert "Sin tipo ni fecha" in r.text


def test_guardar_tipos_responsables_conserva_existentes_sin_chocar(db_session):
    """Regresión: editar una tarea manteniendo un responsable/tipo ya asignado
    daba 500 (IntegrityError por reinsertar antes de borrar el orphan)."""
    from app.models import Responsable, Tarea, TipoTarea
    from app.routers.tareas import _guardar_tipos_responsables

    resp_id = db_session.query(Responsable).first().id
    tipo = db_session.query(TipoTarea).first()
    tarea = Tarea(detalle="x")
    db_session.add(tarea)
    db_session.flush()

    _guardar_tipos_responsables(db_session, tarea, [], {resp_id})
    db_session.commit()
    _guardar_tipos_responsables(db_session, tarea, [tipo.nombre], {resp_id})
    db_session.commit()

    assert [t.tipo_tarea_id for t in tarea.tipos] == [tipo.id]
    assert [r.responsable_id for r in tarea.responsables] == [resp_id]


def test_guardar_tipos_crea_tipo_faltante_del_catalogo(db_session):
    """Regresión: con el catálogo tipos_tarea vacío (prod) el tipo elegido se
    descartaba en silencio y la tarea quedaba 'Necesita revisión'."""
    import pytest
    from fastapi import HTTPException
    from app.models import Responsable, Tarea, TipoTarea
    from app.routers.tareas import _guardar_tipos_responsables

    db_session.query(TipoTarea).delete()
    db_session.commit()
    resp_id = db_session.query(Responsable).first().id
    tarea = Tarea(detalle="x")
    db_session.add(tarea)
    db_session.flush()

    _guardar_tipos_responsables(db_session, tarea, ["diseño"], {resp_id})
    db_session.commit()
    assert [t.tipo_tarea.nombre for t in tarea.tipos] == ["diseño"]

    with pytest.raises(HTTPException):
        _guardar_tipos_responsables(db_session, tarea, ["inventado"], {resp_id})


def test_crear_tarea_deja_drawer_abierto_en_modo_edicion(client, db_session):
    fer = db_session.query(Responsable).filter_by(nombre="fer").one()
    r = client.post(
        "/tareas",
        data={
            "ot_numero": "4300",
            "detalle": "Tarea que queda abierta",
            "fecha_pedido": "2026-08-01",
            "tipos": "diseño",
            "responsable_ids": str(fer.id),
        },
    )
    assert r.status_code == 200
    tarea = db_session.query(Tarea).filter_by(detalle="Tarea que queda abierta").one()
    # drawer OOB con el form en modo edición (PATCH) y los botones habilitados
    assert 'id="drawer-root" hx-swap-oob="true"' in r.text
    assert f'hx-patch="/tareas/{tarea.id}"' in r.text
    assert f'hx-get="/tareas/{tarea.id}/mail"' in r.text
    assert "Asigná un responsable primero" not in r.text


def _tarea_para_duplicar(db_session):
    fer = db_session.query(Responsable).filter_by(nombre="fer").one()
    cliente = db_session.query(Cliente).filter_by(nombre="ALUAR").one()
    ot = OtInterna(numero_interno="4400", cliente_id=cliente.id)
    db_session.add(ot)
    db_session.flush()
    tarea = Tarea(
        ot_interna_id=ot.id, detalle="Original a duplicar", pedido_por="marina",
        fecha_pedido=__import__("datetime").date(2026, 8, 1), estado_tarea=EstadoTarea.EN_PROCESO,
        estado_facturacion=EstadoFacturacion.PARA_FACTURAR,
    )
    db_session.add(tarea)
    db_session.commit()
    return tarea.id


def test_duplicar_pregunta_ot_y_no_guarda_nada(client, db_session):
    tid = _tarea_para_duplicar(db_session)
    r = client.get(f"/tareas/{tid}/duplicar")
    assert r.status_code == 200
    assert "Misma OT interna (4400)" in r.text and "OT interna nueva" in r.text
    assert db_session.query(Tarea).count() == 1


def test_duplicar_form_misma_ot_precarga_sin_fecha(client, db_session):
    tid = _tarea_para_duplicar(db_session)
    r = client.get(f"/tareas/{tid}/duplicar/form?ot=misma")
    assert r.status_code == 200
    assert 'hx-post="/tareas"' in r.text
    assert 'value="4400"' in r.text and "Original a duplicar" in r.text and 'value="marina"' in r.text
    assert 'name="fecha_pedido" required value=""' in r.text
    assert db_session.query(Tarea).count() == 1


def test_duplicar_form_ot_nueva_usa_proximo_numero(client, db_session):
    tid = _tarea_para_duplicar(db_session)
    r = client.get(f"/tareas/{tid}/duplicar/form?ot=nueva")
    assert 'value="4401"' in r.text


def test_duplicar_ot_nueva_dos_aperturas_no_comparten_ot(client, db_session):
    tid = _tarea_para_duplicar(db_session)
    forms = [client.get(f"/tareas/{tid}/duplicar/form?ot=nueva") for _ in range(2)]
    assert all('value="4401"' in f.text and 'name="ot_generada" value="4401"' in f.text for f in forms)
    base = {"detalle": "dup", "fecha_pedido": "2026-10-07", "tipos": "diseño",
            "ot_numero": "4401", "ot_generada": "4401"}
    from app.models import Responsable, TipoTarea
    db_session.add(TipoTarea(nombre="diseño")) if not db_session.query(TipoTarea).filter_by(nombre="diseño").first() else None
    r = db_session.query(Responsable).first()
    if r is None:
        r = Responsable(nombre="Resp"); db_session.add(r)
    db_session.commit()
    base["responsable_ids"] = str(r.id)
    assert client.post("/tareas", data=base).status_code == 200
    assert client.post("/tareas", data=base).status_code == 200
    numeros = sorted(o.numero_interno for o in db_session.query(OtInterna).all())
    assert numeros == ["4400", "4401", "4402"]


def test_anular_tarea_inexistente_es_404(client):
    assert client.post("/tareas/99999/anular").status_code == 404


def test_detalle_vacio_es_422_al_crear_y_editar(client, db_session):
    fer = db_session.query(Responsable).filter_by(nombre="fer").one()
    ot_numero = "4290"
    completo = {"ot_numero": ot_numero, "fecha_pedido": "2026-10-07", "tipos": "diseño",
                "responsable_ids": str(fer.id)}
    assert client.post("/tareas", data={**completo, "detalle": "   "}).status_code == 422
    assert db_session.query(Tarea).count() == 0

    assert client.post("/tareas", data={**completo, "detalle": "Original"}).status_code == 200
    tarea = db_session.query(Tarea).one()
    r = client.patch(f"/tareas/{tarea.id}", data={**completo, "detalle": ""})
    assert r.status_code == 422
    db_session.expire_all()
    assert db_session.get(Tarea, tarea.id).detalle == "Original"
