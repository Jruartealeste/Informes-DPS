import pytest

from app.auth import DominioNoAutorizado, procesar_login
from app.models import Usuario


def _claims(email="fer@aleste.ar", hd="aleste.ar", verified=True, nombre="Fer"):
    return {"email": email, "hd": hd, "email_verified": verified, "name": nombre}


def test_procesar_login_crea_usuario_nuevo(db_session):
    usuario = procesar_login(db_session, _claims())

    assert usuario.id is not None
    assert usuario.email == "fer@aleste.ar"
    assert usuario.nombre == "Fer"
    assert usuario.ultimo_login is not None


def test_procesar_login_actualiza_ultimo_login_en_usuario_existente(db_session):
    primero = procesar_login(db_session, _claims())
    primer_login = primero.ultimo_login

    segundo = procesar_login(db_session, _claims())

    assert segundo.id == primero.id
    assert db_session.query(Usuario).count() == 1
    assert segundo.ultimo_login >= primer_login


def test_procesar_login_rechaza_dominio_distinto(db_session):
    with pytest.raises(DominioNoAutorizado):
        procesar_login(db_session, _claims(email="alguien@gmail.com", hd="gmail.com"))

    assert db_session.query(Usuario).count() == 0


def test_procesar_login_rechaza_email_no_verificado(db_session):
    with pytest.raises(DominioNoAutorizado):
        procesar_login(db_session, _claims(verified=False))

    assert db_session.query(Usuario).count() == 0


def test_ruta_protegida_sin_sesion_redirige_a_login(client_anonimo):
    resp = client_anonimo.get("/tareas", follow_redirects=False)

    assert resp.status_code in (302, 307)
    assert resp.headers["location"].startswith("/auth/login")


def test_ruta_protegida_sin_sesion_via_htmx_devuelve_hx_redirect(client_anonimo):
    resp = client_anonimo.get("/tareas", headers={"HX-Request": "true"})

    assert resp.status_code == 401
    assert resp.headers["HX-Redirect"] == "/auth/login"


def test_login_y_static_accesibles_sin_sesion(client_anonimo):
    resp = client_anonimo.get("/auth/login")
    assert resp.status_code == 200

    resp = client_anonimo.get("/static/css/app.css")
    assert resp.status_code == 200


def test_ruta_protegida_con_sesion_valida_pasa(client):
    resp = client.get("/tareas")
    assert resp.status_code == 200
