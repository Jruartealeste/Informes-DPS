"""Cache en memoria de proceso para catálogos que se piden enteros en cada
apertura de la sheet de tarea (tipos de tarea, números de OT interna,
responsables activos) pero cambian poco. Evita repetir esas queries contra
Neon (remoto, sin pool — ver app/db.py) en cada click sobre una fila de la
tabla. Se invalida a mano en los puntos donde el catálogo correspondiente
cambia; en un deploy con múltiples procesos/instancias esto es un cache por
proceso, no compartido — aceptable para el volumen de uso actual."""

import threading
from types import SimpleNamespace

from sqlalchemy import Integer, cast, select
from sqlalchemy.orm import Session

from app.models import OtInterna, Responsable

_lock = threading.Lock()
_ot_numeros: list[str] | None = None
_responsables_activos: list[SimpleNamespace] | None = None


def ot_numeros(db: Session) -> list[str]:
    global _ot_numeros
    if _ot_numeros is None:
        with _lock:
            if _ot_numeros is None:
                stmt = select(OtInterna.numero_interno).order_by(cast(OtInterna.numero_interno, Integer).desc())
                _ot_numeros = list(db.scalars(stmt))
    return _ot_numeros


def invalidar_ot_numeros() -> None:
    global _ot_numeros
    _ot_numeros = None


def responsables_activos(db: Session) -> list[SimpleNamespace]:
    """Copias livianas (no instancias ORM atadas a la sesión) con los mismos
    atributos que usan las templates: id, nombre, activo, mail."""
    global _responsables_activos
    if _responsables_activos is None:
        with _lock:
            if _responsables_activos is None:
                filas = db.scalars(
                    select(Responsable).where(Responsable.activo.is_(True)).order_by(Responsable.nombre)
                )
                _responsables_activos = [
                    SimpleNamespace(id=r.id, nombre=r.nombre, activo=r.activo, mail=r.mail) for r in filas
                ]
    return _responsables_activos


def invalidar_responsables() -> None:
    global _responsables_activos
    _responsables_activos = None


def reset() -> None:
    """Solo para tests: cada test arma su propia base desde cero (ver
    tests/conftest.py::db_session), así que hay que limpiar este cache de
    proceso entre corridas para no arrastrar datos de una base a otra."""
    global _ot_numeros, _responsables_activos
    _ot_numeros = None
    _responsables_activos = None
