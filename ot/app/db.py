import re

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# QueuePool (default de SQLAlchemy) con un puñado de conexiones vivas entre
# requests, no NullPool. Medido: conectar contra Neon desde acá paga
# ~1.1-1.5s de TCP+TLS+SCRAM cada vez (~200ms de RTT Argentina-Ohio x 6-7
# idas y vueltas del protocolo) — sin pool, ese costo se repetía en CADA
# click. En Vercel serverless el pool solo vive mientras viva la instancia
# (las instancias frías arrancan con el pool vacío), por eso además se usa el
# host pooled de Neon (ver _url_con_pooler).
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


def _url_con_pooler(url: str) -> str:
    """Neon expone dos hosts por endpoint: el directo (`ep-xxx.region...`) y el
    pooled (`ep-xxx-pooler.region...`, PgBouncer en modo transacción). En
    serverless cada instancia fría abre conexiones nuevas; contra el directo
    cada una paga el handshake completo y puede agotar max_connections, el
    pooler las multiplexa. Se deriva acá (no en la env var) para que
    `settings.database_url` siga siendo el directo, que es el que necesitan
    las migraciones de Alembic. Solo toca hosts de neon.tech."""
    m = re.search(r"@(ep-[a-z0-9-]+)\.[a-z0-9.-]*neon\.tech", url)
    if not m or m.group(1).endswith("-pooler"):
        return url
    return url.replace(f"@{m.group(1)}.", f"@{m.group(1)}-pooler.", 1)


_es_sqlite = settings.database_url.startswith("sqlite")
_pool_kwargs = {} if _es_sqlite else {
    "pool_size": 3,
    "max_overflow": 2,
    # PgBouncer en modo transacción: sin prepared statements de lado servidor
    # persistentes (psycopg3 los auto-prepara tras 5 usos de la misma query).
    "connect_args": {"prepare_threshold": None},
}
engine = create_engine(
    settings.database_url if _es_sqlite else _url_con_pooler(settings.database_url),
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
