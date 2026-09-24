import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("AUTH_GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("AUTH_GOOGLE_CLIENT_SECRET", "test-client-secret")

import base64
import json

import itsdangerous
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import cache
from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import Cliente, ClienteAnunciante, Responsable, TipoTarea, Usuario

TIPOS_TAREA = [
    "diseño", "redaccion", "produccion", "estrategia",
    "campania", "gestion", "mant_web", "pautas_medios", "otro",
]

RESPONSABLES = ["fer", "juli"]


@pytest.fixture
def db_session():
    cache.reset()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    session = TestingSessionLocal()
    cliente_aluar = Cliente(nombre="ALUAR")
    session.add(cliente_aluar)
    session.flush()
    session.add(ClienteAnunciante(cliente_id=cliente_aluar.id, anunciante="ALUAR ALUMINIO ARGENTINO SOCIEDAD ANONIM"))
    for nombre in TIPOS_TAREA:
        session.add(TipoTarea(nombre=nombre))
    for nombre in RESPONSABLES:
        session.add(Responsable(nombre=nombre, activo=True))
    session.commit()

    def override_get_db():
        s = TestingSessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()
    app.dependency_overrides.clear()


def cookie_sesion(data: dict) -> str:
    """Firma una cookie de sesión con el mismo formato que
    starlette.middleware.sessions.SessionMiddleware — para simular en tests
    un login ya hecho sin pasar por el flujo real de Google."""
    signer = itsdangerous.TimestampSigner(str(settings.session_secret))
    payload = base64.b64encode(json.dumps(data).encode("utf-8"))
    return signer.sign(payload).decode("utf-8")


@pytest.fixture
def client(db_session):
    """Cliente logueado por defecto — la app entera queda detrás de
    AuthMiddleware, así que los tests de tareas/OT/responsables (que no
    prueban auth en sí) necesitan una sesión válida para no chocar con el
    redirect a /auth/login."""
    from fastapi.testclient import TestClient

    usuario = Usuario(email="test@aleste.ar", nombre="Test User")
    db_session.add(usuario)
    db_session.commit()

    c = TestClient(app)
    c.cookies.set(
        "session",
        cookie_sesion({"user_id": usuario.id, "email": usuario.email, "nombre": usuario.nombre, "rol": "MIEMBRO"}),
    )
    return c


@pytest.fixture
def client_anonimo(db_session):
    """Sin sesión — para probar que AuthMiddleware efectivamente bloquea."""
    from fastapi.testclient import TestClient

    return TestClient(app)
