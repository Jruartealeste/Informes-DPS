"""
Capa de base de datos compartida por todos los modulos. Usa SQLite (un solo
archivo, sin instalar nada) para arrancar rapido. Si mas de una persona
necesita consultar al mismo tiempo, esto se migra a Postgres cambiando solo
este archivo.

Cada modulo (modules/<modulo>/ingest.py) define su propio esquema y sus
propias funciones de upsert, pero todos comparten la misma conexion/archivo
a traves de get_connection().
"""
import sqlite3
from contextlib import contextmanager

DB_PATH = "advertys.db"


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
