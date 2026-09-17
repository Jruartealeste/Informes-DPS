from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# QueuePool (default de SQLAlchemy) con un puñado de conexiones vivas entre
# requests, no NullPool. Medido: conectar contra Neon desde acá paga
# ~1.1-1.5s de TCP+TLS+SCRAM cada vez (~200ms de RTT Argentina-Ohio x 6-7
# idas y vueltas del protocolo) — sin pool, ese costo se repetía en CADA
# click. Esto asume un proceso uvicorn persistente (dev, o un Cloud Run con
# contenedor "warm"); si el deploy real termina siendo Vercel serverless con
# instancias efímeras de vida muy corta, esta decisión hay que revisarla de
# nuevo (ver ot/CLAUDE.md — todavía no está resuelto Cloud Run vs. Vercel).
# pool_pre_ping=True (probado) suma ~290ms de ping a CADA checkout de
# conexión — con uso activo, esa plata se tira casi siempre para cubrir un
# caso raro (que Neon haya cerrado la conexión por autosuspend de
# inactividad). Se deja afuera a propósito: pool_recycle solo reduce la
# ventana en la que eso puede pasar. Si el equipo empieza a ver 500 al
# volver de un rato largo sin usar la app (conexión pooled que Neon ya
# tiró), ese es el síntoma esperado — se soluciona reintentando (recarga la
# página) y ahí sí valdría la pena reconsiderar pre_ping o manejar el
# reintento a mano en vez de pagar el ping siempre.
# pool_size/max_overflow no son opciones válidas para el SingletonThreadPool
# que SQLAlchemy usa por default con sqlite (los tests corren contra
# "sqlite:///:memory:", ver tests/conftest.py) — solo se pasan contra Postgres.
_pool_kwargs = {} if settings.database_url.startswith("sqlite") else {
    "pool_size": 3,
    "max_overflow": 2,
}
engine = create_engine(
    settings.database_url,
    pool_recycle=280,
    **_pool_kwargs,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
