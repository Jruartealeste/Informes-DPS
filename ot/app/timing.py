"""Cabecera `Server-Timing` en cada respuesta: tiempo total de la request,
tiempo acumulado en la base y cantidad de queries. Sirve para separar, desde
el navegador (DevTools > Network > Timing, o `response.headers` en un fetch
same-origin), cuánto de una página lenta es la base y cuánto es la función.
Solo expone duraciones, nada de datos."""

import time
from contextvars import ContextVar

from sqlalchemy import event
from sqlalchemy.engine import Engine

# Mutable compartida: las rutas sync corren en un threadpool con una COPIA del
# contexto, pero el dict es el mismo objeto, así que ven las mismas escrituras.
_acum: ContextVar[dict | None] = ContextVar("server_timing", default=None)


@event.listens_for(Engine, "before_cursor_execute")
def _antes(conn, cursor, statement, parameters, context, executemany):
    a = _acum.get()
    if a is not None:
        conn.info["_t0"] = time.perf_counter()


@event.listens_for(Engine, "after_cursor_execute")
def _despues(conn, cursor, statement, parameters, context, executemany):
    a = _acum.get()
    t0 = conn.info.pop("_t0", None)
    if a is not None and t0 is not None:
        dt = time.perf_counter() - t0
        a["db"] += dt
        a["n"] += 1
        a["max"] = max(a["max"], dt)


class ServerTimingMiddleware:
    """ASGI puro (no BaseHTTPMiddleware) para no sumar overhead propio."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        a = {"db": 0.0, "n": 0, "max": 0.0}
        token = _acum.set(a)
        t0 = time.perf_counter()

        async def send_con_timing(msg):
            if msg["type"] == "http.response.start":
                total = (time.perf_counter() - t0) * 1000
                valor = (
                    f"total;dur={total:.0f}, "
                    f'db;dur={a["db"] * 1000:.0f};desc="{a["n"]} queries, max {a["max"] * 1000:.0f}ms"'
                )
                msg.setdefault("headers", []).append((b"server-timing", valor.encode()))
            await send(msg)

        try:
            await self.app(scope, receive, send_con_timing)
        finally:
            _acum.reset(token)
