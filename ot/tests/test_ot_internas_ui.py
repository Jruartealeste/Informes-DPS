from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "public" / "static" / "css" / "app.css"


def test_panel_de_asignacion_fijo_arriba_de_la_tabla(client):
    html = client.get("/ordenes-trabajo").text
    # siempre visible (sin atributo hidden) y ANTES de la tabla, no abajo
    assert 'class="card card--asignar-lote">' in html
    assert html.index('id="form-asignar-lote"') < html.index('class="table-card')
    assert "OT de sistema para las OT internas tildadas" in html
    assert 'id="chk-todas"' in html


def test_tiene_buscador_y_filtros_como_tareas(client):
    html = client.get("/ordenes-trabajo").text
    assert 'id="filtro-q"' in html
    assert 'id="btn-filtros"' in html
    panel = html.split('id="filtros-panel"')[1].split("filtros__foot")[0]
    for id_ in ("filtro-estado", "filtro-dps", "filtro-fac"):
        assert f'id="{id_}"' in panel
    # el toolbar va antes del panel de asignación y de la tabla
    assert html.index('id="filtros-ot"') < html.index('id="form-asignar-lote"')


def test_botones_del_encabezado_usan_la_semantica_de_alerta(client):
    html = client.get("/ordenes-trabajo").text
    assert "filters__revision" in html
    assert "is-empty" in html or "has-items" in html


def test_tabla_de_ot_internas_ocupa_todo_el_ancho():
    css = CSS.read_text(encoding="utf-8")
    bloque = css.split(".table-card--ot-list {")[1].split("}")[0]
    assert "max-width" not in bloque
