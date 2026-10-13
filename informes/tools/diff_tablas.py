"""Compara una tabla de advertys.db contra la misma tabla en otra base (p.ej. el
baseline de una corrida --legacy), fila a fila y sin la columna fecha_crawl.
Uso: python -m tools.diff_tablas <base_referencia.db> <tabla> [<tabla> ...]"""
import sqlite3
import sys


def filas(path, tabla):
    c = sqlite3.connect(path)
    cols = [r[1] for r in c.execute(f"PRAGMA table_info({tabla})") if r[1] != "fecha_crawl"]
    rows = c.execute(f"SELECT {', '.join(cols)} FROM {tabla}").fetchall()
    return cols, sorted(tuple("" if v is None else v for v in r) for r in rows)


def main():
    ref, tablas = sys.argv[1], sys.argv[2:]
    todo_ok = True
    for t in tablas:
        _, a = filas(ref, t)
        _, b = filas("advertys.db", t)
        solo_ref = [r for r in a if r not in b]
        solo_nuevo = [r for r in b if r not in a]
        ok = not solo_ref and not solo_nuevo
        todo_ok &= ok
        print(f"{'IGUAL' if ok else 'DIFIERE'} {t}: referencia={len(a)} filas, actual={len(b)} filas")
        for r in solo_ref[:5]:
            print("   solo en referencia:", r)
        for r in solo_nuevo[:5]:
            print("   solo en actual:    ", r)
    sys.exit(0 if todo_ok else 1)


if __name__ == "__main__":
    main()
