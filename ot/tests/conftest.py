import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Cliente, TipoTarea

TIPOS_TAREA = [
    "diseño", "redaccion", "produccion", "estrategia",
    "campania", "gestion", "mant_web", "pautas_medios", "otro",
]


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    session = TestingSessionLocal()
    session.add(Cliente(nombre="ALUAR", anunciante_advertys="ALUAR ALUMINIO ARG."))
    for nombre in TIPOS_TAREA:
        session.add(TipoTarea(nombre=nombre))
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


@pytest.fixture
def client(db_session):
    from fastapi.testclient import TestClient

    return TestClient(app)
