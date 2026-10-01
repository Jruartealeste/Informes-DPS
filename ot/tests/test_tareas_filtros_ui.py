def test_pagina_tiene_boton_filtros_y_alerta_de_revision_visible(client):
    html = client.get("/tareas").text
    assert 'id="btn-filtros"' in html
    # los selects viven dentro del panel de filtros, no sueltos en la barra
    panel = html.split('id="filtros-panel"')[1].split("</form>")[0]
    for nombre in ("f_est", "f_fac", "f_resp"):
        assert f'name="{nombre}"' in panel
    # la alerta queda fuera del panel, siempre visible
    assert 'id="btn-revision"' in html.split('id="filtros-panel"')[1].split("</div>\n  </div>")[1]


def test_partial_actualiza_alerta_y_resumen_por_oob(client):
    html = client.get("/tareas/partial?revision=1").text
    assert 'id="btn-revision"' in html and 'hx-swap-oob="true"' in html
    assert 'id="filtros-resumen"' in html
    assert "is-active" in html  # revision=1 => la alerta queda activa
