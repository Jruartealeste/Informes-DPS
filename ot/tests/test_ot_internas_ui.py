def test_barra_de_asignacion_arranca_oculta_y_hay_tildar_todas(client):
    html = client.get("/ordenes-trabajo").text
    assert 'id="form-asignar-lote"' in html
    # oculta hasta que haya filas tildadas (la muestra el JS)
    assert 'class="card card--asignar-lote" hidden' in html
    assert 'id="chk-todas"' in html
    # va después de la tabla, no arriba: tildar una fila no empuja la lista
    assert html.index('class="table-card') < html.index('id="form-asignar-lote"')


def test_botones_del_encabezado_usan_la_semantica_de_alerta(client):
    html = client.get("/ordenes-trabajo").text
    assert "filters__revision" in html
    assert "is-empty" in html or "has-items" in html
