from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings

# NullPool: en serverless (Vercel) cada invocación puede correr en un proceso
# nuevo, así que mantener un pool de conexiones entre invocaciones no sirve y
# solo acumula conexiones muertas contra el endpoint pooled de Neon.
engine = create_engine(settings.database_url, poolclass=NullPool)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
