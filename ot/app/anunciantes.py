"""Relación Cliente de la app ↔ Anunciantes reales de Advertys.

Un Cliente de acá puede ser varios Anunciantes en Advertys (FATE son 6) y los
nombres no coinciden letra por letra ("ALUAR" vs "ALUAR ALUMINIO ARGENTINO
SOCIEDAD ANONIM"), así que la relación se infiere del nombre, además de los
Anunciantes cargados a mano en `cliente_anunciantes`:

- por palabras: cada palabra del nombre del cliente es prefijo de la palabra
  en la misma posición del Anunciante ("FATE" → los 6 "FATE ...", "Nordelta"
  → "NORDELTA S.A." pero no "Asociación Vecinal Nordelta");
- por siglas: un cliente de una sola palabra que coincide con las iniciales
  del Anunciante — FAA es "FUNDACIÓN AURORA AUSTRAL" (confirmado por Javier,
  2026-10-14).
"""
import re
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Cliente, ProductoAdvertys


def _palabras(texto: str) -> list[str]:
    sin_tildes = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", sin_tildes.lower())


def corresponde(cliente: str, anunciante: str) -> bool:
    del_cliente, del_anunciante = _palabras(cliente), _palabras(anunciante)
    if not del_cliente or not del_anunciante:
        return False
    if len(del_cliente) <= len(del_anunciante) and all(
        a.startswith(c) for c, a in zip(del_cliente, del_anunciante)
    ):
        return True
    return (
        len(del_cliente) == 1
        and len(del_anunciante) > 1
        and del_cliente[0] == "".join(p[0] for p in del_anunciante)
    )


def productos_del_cliente(db: Session, cliente: Cliente | None) -> dict[str, list[str]]:
    """{anunciante de Advertys: [producto, ...]} de los Anunciantes del cliente."""
    if cliente is None:
        return {}
    cargados = {a.anunciante for a in cliente.anunciantes}
    catalogo: dict[str, list[str]] = {}
    for anunciante, nombre in db.execute(
        select(ProductoAdvertys.anunciante, ProductoAdvertys.nombre).order_by(
            ProductoAdvertys.anunciante, func.lower(ProductoAdvertys.nombre)
        )
    ):
        if anunciante in cargados or corresponde(cliente.nombre, anunciante):
            catalogo.setdefault(anunciante, []).append(nombre)
    return catalogo
