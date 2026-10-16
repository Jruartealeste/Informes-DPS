"""Pantalla Usuarios (solo ADMIN) y bloqueo real de usuarios inactivos (2026-10-14)."""
import pytest

from app.auth import UsuarioInactivo, procesar_login
from app.models import RolUsuario, Usuario


def _yo(db_session):
    return db_session.query(Usuario).filter_by(email="test@aleste.ar").one()


def _hacer_admin(db_session):
    yo = _yo(db_session)
    yo.rol = RolUsuario.ADMIN
    db_session.commit()
    return yo


def _usuario(db_session, email="fer@aleste.ar", nombre="Fer", **kw):
    u = Usuario(email=email, nombre=nombre, **kw)
    db_session.add(u)
    db_session.commit()
    return u


def _recargar(db_session, u):
    db_session.expire_all()
    return db_session.get(Usuario, u.id)


# ---- Acceso a la pantalla ----


def test_usuarios_solo_admin(client, db_session):
    assert client.get("/usuarios").status_code == 403
    otro = _usuario(db_session)
    assert client.post(f"/usuarios/{otro.id}/desactivar").status_code == 403
    assert client.post(f"/usuarios/{otro.id}/rol", data={"rol": "ADMIN"}).status_code == 403
    assert _recargar(db_session, otro).activo is True


def test_link_usuarios_en_sidebar_solo_para_admin(client, db_session):
    assert 'href="/usuarios"' not in client.get("/tareas").text
    _hacer_admin(db_session)
    assert 'href="/usuarios"' in client.get("/tareas").text


def test_listado_muestra_usuarios(client, db_session):
    _hacer_admin(db_session)
    _usuario(db_session, email="juli@aleste.ar", nombre="Juli", rol=RolUsuario.APROBADOR_FACTURACION)
    _usuario(db_session, email="ex@aleste.ar", nombre="Ex", activo=False)

    html = client.get("/usuarios").text

    assert "juli@aleste.ar" in html and "ex@aleste.ar" in html
    assert "2 activos · 3 en total" in html
    assert "DESACTIVADO" in html
    # La propia fila no ofrece cambiar rol ni desactivarse.
    assert f'action="/usuarios/{_yo(db_session).id}/rol"' not in html
    assert f'action="/usuarios/{_yo(db_session).id}/desactivar"' not in html


# ---- Cambiar rol ----


def test_cambiar_rol(client, db_session):
    _hacer_admin(db_session)
    otro = _usuario(db_session)

    resp = client.post(f"/usuarios/{otro.id}/rol", data={"rol": "APROBADOR_FACTURACION"}, follow_redirects=False)

    assert resp.status_code == 303
    assert _recargar(db_session, otro).rol == RolUsuario.APROBADOR_FACTURACION


def test_rol_desconocido_422(client, db_session):
    _hacer_admin(db_session)
    otro = _usuario(db_session)
    assert client.post(f"/usuarios/{otro.id}/rol", data={"rol": "SUPERUSUARIO"}).status_code == 422


def test_admin_no_puede_quitarse_el_rol(client, db_session):
    yo = _hacer_admin(db_session)

    resp = client.post(f"/usuarios/{yo.id}/rol", data={"rol": "MIEMBRO"})

    assert resp.status_code == 409
    assert _recargar(db_session, yo).rol == RolUsuario.ADMIN


def test_dar_admin_rige_sin_relogin(client, db_session):
    """El rol se lee de la base en cada request: la sesión (que dice MIEMBRO)
    no importa."""
    yo = _yo(db_session)
    assert client.get("/usuarios").status_code == 403
    yo.rol = RolUsuario.ADMIN
    db_session.commit()
    assert client.get("/usuarios").status_code == 200


def test_quitar_admin_rige_sin_relogin(client, db_session):
    yo = _hacer_admin(db_session)
    assert client.get("/anunciantes").status_code == 200
    yo.rol = RolUsuario.MIEMBRO
    db_session.commit()
    assert client.get("/anunciantes").status_code == 403


# ---- Activar / desactivar ----


def test_desactivar_y_reactivar(client, db_session):
    _hacer_admin(db_session)
    otro = _usuario(db_session)

    assert client.post(f"/usuarios/{otro.id}/desactivar", follow_redirects=False).status_code == 303
    assert _recargar(db_session, otro).activo is False

    assert client.post(f"/usuarios/{otro.id}/reactivar", follow_redirects=False).status_code == 303
    assert _recargar(db_session, otro).activo is True


def test_admin_no_puede_desactivarse(client, db_session):
    yo = _hacer_admin(db_session)

    assert client.post(f"/usuarios/{yo.id}/desactivar").status_code == 409
    assert _recargar(db_session, yo).activo is True


def test_usuario_inexistente_404(client, db_session):
    _hacer_admin(db_session)
    assert client.post("/usuarios/9999/desactivar").status_code == 404


def test_usuarios_no_lo_bloquea_anunciante_en_solo_lectura(client, db_session):
    """La gestión de usuarios no depende del anunciante del sidebar."""
    from app.models import Cliente

    _hacer_admin(db_session)
    baja = Cliente(nombre="BAJA", activo=False)
    db_session.add(baja)
    db_session.commit()
    client.cookies.set("cliente_id", str(baja.id))
    otro = _usuario(db_session)

    assert client.post(f"/usuarios/{otro.id}/desactivar", follow_redirects=False).status_code == 303


# ---- Bloqueo real del inactivo ----


def test_login_de_inactivo_se_rechaza(db_session):
    u = _usuario(db_session, activo=False)
    claims = {"email": u.email, "hd": "aleste.ar", "email_verified": True, "name": "Fer"}

    with pytest.raises(UsuarioInactivo):
        procesar_login(db_session, claims)

    assert _recargar(db_session, u).ultimo_login is None


def test_sesion_abierta_de_desactivado_se_corta_en_el_proximo_request(client, db_session):
    assert client.get("/tareas").status_code == 200
    yo = _yo(db_session)
    yo.activo = False
    db_session.commit()

    resp = client.get("/tareas", follow_redirects=False)

    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "/auth/login?error=inactivo"
    # Se le borra la cookie de sesión: aunque lo reactiven, vuelve a loguearse.
    # (Se mira el header: el cookie jar del TestClient no suelta una cookie
    # cargada a mano sin dominio, ver conftest.client.)
    assert resp.headers["set-cookie"].startswith("session=null;")
    assert "expires=Thu, 01 Jan 1970" in resp.headers["set-cookie"]


def test_desactivado_via_htmx_hx_redirect(client, db_session):
    yo = _yo(db_session)
    yo.activo = False
    db_session.commit()

    resp = client.get("/tareas", headers={"HX-Request": "true"})

    assert resp.status_code == 401
    assert resp.headers["HX-Redirect"] == "/auth/login?error=inactivo"


def test_desactivado_no_puede_escribir(client, db_session):
    yo = _yo(db_session)
    yo.activo = False
    db_session.commit()

    resp = client.post("/tareas", data={"detalle": "x"}, follow_redirects=False)

    assert resp.status_code in (302, 307)
    assert "error=inactivo" in resp.headers["location"]


def test_sesion_de_usuario_borrado_se_corta(client, db_session):
    db_session.delete(_yo(db_session))
    db_session.commit()

    resp = client.get("/tareas", follow_redirects=False)

    assert resp.headers["location"] == "/auth/login?error=inactivo"


def test_login_muestra_aviso_de_inactivo(client_anonimo):
    assert "desactivado" in client_anonimo.get("/auth/login?error=inactivo").text
    assert "desactivado" not in client_anonimo.get("/auth/login").text
