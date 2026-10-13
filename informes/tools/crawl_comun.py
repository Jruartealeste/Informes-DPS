"""
Piezas compartidas para hacer INCREMENTALES y PARALELOS los crawls de
Playwright contra Advertys (solo lectura, ver salvaguarda en CLAUDE.md).

Contexto (2026-10-13): `tools.actualizar_cobranza` tardaba ~70 min porque los
3 crawls borraban su tabla y volvian a visitar TODO en cada corrida (~214
visitas de ~20 s). Este modulo pone lo comun en un solo lugar:

  1. Cache (tabla `crawl_cache`): que claves ya se crawlearon, con que
     "firma" de cabecera y cuantas filas dieron. Guarda tambien las que dieron
     0 filas (si no, se recrawlean para siempre).
  2. Regla de que recrawlear (`decidir`): mes cerrado -> congelado; reciente
     -> siempre; firma cambiada -> si; sin resultado util -> reintentar.
  3. `correr_en_paralelo`: N hilos, cada uno con su propio navegador + login.
  4. Esperas por condicion (`esperar_grid`) y `volver_o_recargar` para no
     recargar el listado en cada item.

Regla de cierre de mes (Javier, 2026-10-13): el mes M se cierra alrededor del
dia 15-20 del mes siguiente y despues no se tocan asientos de M. Se usa el
dia 20 (el mas conservador). La fecha que se congela es la del REGISTRO cuyo
contenido es contable e inmutable al cerrar (recibo, factura). Para OC/OP la
fecha de la orden NO congela (una orden vieja puede recibir una factura de
compra nueva): ahi manda la firma de cabecera (estado/saldo/comprado/pagado).

Receta para convertir otro crawl: workflows / skill `acelerar-crawl`.
"""
from __future__ import annotations

import hashlib
import queue
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Iterable

import db

DIA_CIERRE = 20

SCHEMA_CACHE = """
CREATE TABLE IF NOT EXISTS crawl_cache (
    modulo TEXT NOT NULL,
    clave TEXT NOT NULL,
    firma TEXT,
    fecha_dato TEXT,
    fecha_crawl TEXT,
    n_filas INTEGER,
    n_ok INTEGER,
    PRIMARY KEY (modulo, clave)
);
"""


# --------------------------------------------------------------------------
# Regla de cierre de mes
# --------------------------------------------------------------------------
def _a_fecha(valor) -> date | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return datetime.fromisoformat(str(valor)[:10]).date()


def mes_cerrado(fecha, hoy: date | None = None, dia_cierre: int = DIA_CIERRE) -> bool:
    """True si el mes de `fecha` ya cerro: hoy > dia `dia_cierre` del mes
    siguiente. Sin fecha parseable -> False (no se congela lo que no se puede
    ubicar en el calendario)."""
    f = _a_fecha(fecha)
    if f is None:
        return False
    hoy = hoy or date.today()
    anio, mes = (f.year + 1, 1) if f.month == 12 else (f.year, f.month + 1)
    return hoy > date(anio, mes, dia_cierre)


def firma(*valores) -> str:
    """Huella corta y estable de los campos de cabecera que, si cambian,
    obligan a recrawlear el item. None y '' se tratan igual; los floats se
    redondean a 2 decimales para no diferir por ruido de coma flotante."""
    partes = []
    for v in valores:
        if v is None:
            v = ""
        elif isinstance(v, float):
            v = f"{v:.2f}"
        partes.append(str(v).strip())
    return hashlib.sha1("\x1f".join(partes).encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------
# Decision: que recrawlear
# --------------------------------------------------------------------------
@dataclass
class Candidato:
    clave: str
    firma: str = ""
    fecha: object = None  # fecha del registro (recibo/factura), para cierre de mes/recientes


@dataclass
class EntradaCache:
    firma: str
    fecha_dato: str | None
    fecha_crawl: str | None
    n_filas: int
    n_ok: int


@dataclass
class Politica:
    """Que significa 'sigue vigente' para un tipo de item."""
    congelar_mes_cerrado: bool = True      # recibos/facturas: si; OC/OP: no
    dias_recientes: int | None = None      # recrawlear siempre si fecha >= hoy-N
    reintentar_sin_ok: bool = False        # item cacheado sin resultado util -> reintentar
    dia_cierre: int = DIA_CIERRE


def decidir(cand: Candidato, entrada: EntradaCache | None, politica: Politica,
            hoy: date | None = None, completo: bool = False) -> tuple[bool, str]:
    """(recrawlear?, motivo). El orden importa: completo > sin cache >
    congelado por cierre > reciente > firma > sin resultado util."""
    hoy = hoy or date.today()
    if completo:
        return True, "completo"
    if entrada is None:
        return True, "nuevo"
    if politica.congelar_mes_cerrado and mes_cerrado(cand.fecha, hoy, politica.dia_cierre):
        return False, "mes cerrado"
    f = _a_fecha(cand.fecha)
    if politica.dias_recientes is not None and f is not None and f >= hoy - timedelta(days=politica.dias_recientes):
        return True, "reciente"
    if cand.firma and cand.firma != (entrada.firma or ""):
        return True, "firma cambio"
    if politica.reintentar_sin_ok and not entrada.n_ok:
        return True, "sin resultado util"
    return False, "vigente"


def seleccionar(candidatos: Iterable[Candidato], cache: "CrawlCache", politica: Politica,
                hoy: date | None = None, completo: bool = False):
    """Devuelve (a_visitar, saltados, motivos) -- motivos: dict motivo -> cantidad."""
    entradas = cache.cargar()
    a_visitar, saltados, motivos = [], [], {}
    for c in candidatos:
        visitar, motivo = decidir(c, entradas.get(c.clave), politica, hoy, completo)
        motivos[motivo] = motivos.get(motivo, 0) + 1
        (a_visitar if visitar else saltados).append(c)
    return a_visitar, saltados, motivos


# --------------------------------------------------------------------------
# Cache en SQLite
# --------------------------------------------------------------------------
class CrawlCache:
    def __init__(self, modulo: str):
        self.modulo = modulo
        with db.get_connection() as conn:
            conn.execute(SCHEMA_CACHE)
            conn.commit()

    def cargar(self) -> dict[str, EntradaCache]:
        with db.get_connection() as conn:
            filas = conn.execute(
                "SELECT clave, firma, fecha_dato, fecha_crawl, n_filas, n_ok FROM crawl_cache WHERE modulo = ?",
                (self.modulo,),
            ).fetchall()
        return {
            r["clave"]: EntradaCache(r["firma"] or "", r["fecha_dato"], r["fecha_crawl"], r["n_filas"] or 0, r["n_ok"] or 0)
            for r in filas
        }

    def guardar(self, clave: str, firma_: str, fecha_dato, n_filas: int, n_ok: int, fecha_crawl: str | None = None):
        fecha_crawl = fecha_crawl or datetime.now().isoformat(timespec="seconds")
        fd = _a_fecha(fecha_dato)
        with db.get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO crawl_cache (modulo, clave, firma, fecha_dato, fecha_crawl, n_filas, n_ok) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (self.modulo, clave, firma_, fd.isoformat() if fd else None, fecha_crawl, n_filas, n_ok),
            )
            conn.commit()

    def olvidar_fuera_de(self, claves_vigentes: Iterable[str]) -> int:
        """Borra de la cache las claves que ya no estan en la ventana."""
        vigentes = set(claves_vigentes)
        with db.get_connection() as conn:
            existentes = [r[0] for r in conn.execute("SELECT clave FROM crawl_cache WHERE modulo = ?", (self.modulo,))]
            sobran = [c for c in existentes if c not in vigentes]
            conn.executemany("DELETE FROM crawl_cache WHERE modulo = ? AND clave = ?", [(self.modulo, c) for c in sobran])
            conn.commit()
        return len(sobran)


def reemplazar_por_clave(tabla: str, columna_clave: str, columnas: list[str], registros: list[dict],
                         claves_recrawleadas: Iterable[str], claves_vigentes: Iterable[str]) -> int:
    """Upsert por clave en la tabla de resultados: borra las filas de las
    claves recrawleadas (y las que salieron de la ventana) y reinserta lo
    nuevo. Lo demas queda intacto. Devuelve el total de filas resultante."""
    a_borrar = set(claves_recrawleadas)
    vigentes = set(claves_vigentes)
    with db.get_connection() as conn:
        existentes = {r[0] for r in conn.execute(f"SELECT DISTINCT {columna_clave} FROM {tabla}")}
        a_borrar |= {c for c in existentes if c not in vigentes}
        conn.executemany(f"DELETE FROM {tabla} WHERE {columna_clave} = ?", [(c,) for c in a_borrar])
        if registros:
            ph = ", ".join("?" for _ in columnas)
            conn.executemany(
                f"INSERT INTO {tabla} ({', '.join(columnas)}) VALUES ({ph})",
                [tuple(r.get(c) for c in columnas) for r in registros],
            )
        conn.commit()
        return conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]


# --------------------------------------------------------------------------
# Paralelismo: un navegador + login por hilo
# --------------------------------------------------------------------------
_print_lock = threading.Lock()


def log(msg: str):
    with _print_lock:
        print(msg, flush=True)


@dataclass
class Resultado:
    item: object
    valor: object = None
    error: str | None = None


def correr_en_paralelo(items: list, procesar: Callable, n_workers: int = 1,
                       etiqueta: Callable[[object], str] = str,
                       max_errores_seguidos: int = 3) -> list[Resultado]:
    """Procesa `items` con `procesar(page, item) -> valor`. Cada hilo abre su
    propio sync_playwright + login (las paginas de Playwright sync no se
    comparten entre hilos). Devuelve un Resultado por item, en el orden
    original. Un item que falla no frena a los demas; `max_errores_seguidos`
    fallos seguidos en un hilo -> relogin de ese hilo. Con n_workers=1 corre
    en el hilo actual (mismo comportamiento que antes)."""
    from playwright.sync_api import sync_playwright
    from tools.advertys_session import AdvertysLoginError, login

    total = len(items)
    resultados: list[Resultado | None] = [None] * total
    cola: queue.Queue = queue.Queue()
    for idx, it in enumerate(items):
        cola.put((idx, it))
    hechos = [0]
    n_workers = max(1, min(n_workers, total or 1))

    def worker(nombre: str):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1500, "height": 1000})
            try:
                login(page)
            except AdvertysLoginError as e:
                log(f"[{nombre}] ERROR de login: {e}")
                browser.close()
                # Devolver lo que quedo en la cola para que lo tomen otros hilos
                # (si no hay otros, queda con error).
                return
            seguidos = 0
            while True:
                try:
                    idx, it = cola.get_nowait()
                except queue.Empty:
                    break
                t0 = time.time()
                try:
                    valor = procesar(page, it)
                    resultados[idx] = Resultado(it, valor)
                    seguidos = 0
                except Exception as e:  # noqa: BLE001 - un item roto no frena el resto
                    resultados[idx] = Resultado(it, error=str(e).splitlines()[0][:300] if str(e) else repr(e))
                    seguidos += 1
                    if seguidos >= max_errores_seguidos:
                        log(f"[{nombre}] {seguidos} fallos seguidos -- relogin")
                        try:
                            login(page)
                            seguidos = 0
                        except Exception as e2:  # noqa: BLE001
                            log(f"[{nombre}] no se pudo recuperar la sesion: {e2}")
                            break
                with _print_lock:
                    hechos[0] += 1
                    estado = "ERROR " + resultados[idx].error if resultados[idx].error else "ok"
                    print(f"  [{hechos[0]}/{total}] {etiqueta(it)} -- {estado} ({time.time() - t0:.1f}s)", flush=True)
            browser.close()

    if n_workers == 1:
        worker("w1")
    else:
        hilos = [threading.Thread(target=worker, args=(f"w{i + 1}",), daemon=True) for i in range(n_workers)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()

    # Items que nadie llego a procesar (todos los hilos cayeron)
    for idx, r in enumerate(resultados):
        if r is None:
            resultados[idx] = Resultado(items[idx], error="no procesado (sesion caida)")
    return resultados  # type: ignore[return-value]


# --------------------------------------------------------------------------
# Argumentos comunes de los crawls
# --------------------------------------------------------------------------
def parsear_args(descripcion: str, argv=None):
    """--completo / --legacy / --workers N, iguales en los 3 crawls y en
    tools/actualizar_cobranza.py (que los propaga)."""
    import argparse
    ap = argparse.ArgumentParser(description=descripcion)
    ap.add_argument("--completo", action="store_true", help="ignora la cache y revisita todo (con upsert, sin borrar antes)")
    ap.add_argument("--legacy", action="store_true", help="corrida vieja: borra la tabla y recrawlea todo, de a uno")
    ap.add_argument("--workers", type=int, default=1, help="navegadores en paralelo (default 1)")
    return ap.parse_args(argv)


def sembrar_si_vacia(cache: "CrawlCache", tabla: str, columna_clave: str, firmas: dict,
                     fechas: dict, columna_ok: str | None = None) -> int:
    """Primera corrida incremental: si la cache esta vacia pero la tabla de
    resultados ya tiene datos de una corrida anterior (legacy), se asume que
    reflejan el estado actual y se arma la cache a partir de ellas, para no
    pagar una corrida en frio. `firmas`/`fechas` son las de HOY por clave.
    Claves sin filas en la tabla no se siembran (se crawlean una vez)."""
    if cache.cargar():
        return 0
    cond_ok = (f"SUM(CASE WHEN {columna_ok} IS NOT NULL AND {columna_ok} != '' THEN 1 ELSE 0 END)"
               if columna_ok else "COUNT(*)")
    with db.get_connection() as conn:
        try:
            filas = conn.execute(
                f"SELECT {columna_clave} AS k, COUNT(*) AS n, {cond_ok} AS ok, MAX(fecha_crawl) AS fc "
                f"FROM {tabla} GROUP BY {columna_clave}"
            ).fetchall()
        except Exception:
            return 0
    n = 0
    for r in filas:
        k = r["k"]
        if k not in firmas:
            continue
        cache.guardar(k, firmas[k], fechas.get(k), r["n"], r["ok"] or 0, fecha_crawl=r["fc"])
        n += 1
    return n


# --------------------------------------------------------------------------
# Navegacion rapida de listados DevExpress (reusa la pagina entre items)
# --------------------------------------------------------------------------
FILTROS_DEFECTO = ("Mes Actual", "Abiertas", "Año Actual", "Ano Actual")
FILTROS_TODOS = ("Todas", "Todos")
_JS_COMBO = "(vals)=>[...document.querySelectorAll(\"input[id$='_Cb_I']\")].some(i=>vals.includes(i.value.trim()))"
_JS_COMBO_ID = ("(vals)=>{const i=[...document.querySelectorAll(\"input[id$='_Cb_I']\")]"
                ".find(i=>vals.includes(i.value.trim()));return i?i.id:null}")
_JS_BUSQUEDA_APLICADA = (
    "(txt)=>{const t=[...document.querySelectorAll(\"table[id*='DXMainTable']\")].find(e=>e.offsetParent!==null);"
    "if(!t)return false;const rows=[...t.querySelectorAll(\"tr[id*='DXDataRow']\")];"
    "return rows.every(r=>r.innerText.includes(txt));}"
)
_JS_HAY_BUSCADOR ="()=>document.querySelectorAll(\"input[id$='_Ed_I']\").length>0"


def esperar_postback_rapido(page, aparece: int = 1200, timeout: int = 15000):
    """Espera el spinner de DevExpress (si aparece) sin networkidle."""
    try:
        page.wait_for_selector(".dxlpLoadingDiv", state="visible", timeout=aparece)
    except Exception:
        pass
    try:
        page.wait_for_selector(".dxlpLoadingDiv", state="hidden", timeout=timeout)
    except Exception:
        pass


def texto_visible(page, texto: str):
    return page.get_by_text(texto, exact=True).filter(visible=True)


def esperar_texto(page, texto: str, timeout: int = 10000) -> bool:
    try:
        texto_visible(page, texto).first.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:
        return False


def click_texto(page, texto: str, timeout: int = 5000) -> bool:
    try:
        texto_visible(page, texto).first.click(timeout=timeout)
        return True
    except Exception:
        return False


def tabla_visible(page):
    """Tabla ASPxGridView visible (la primera). None si no hay."""
    loc = page.locator("table[id*='DXMainTable']").filter(visible=True)
    return loc.first if loc.count() > 0 else None


def esperar_filas(page, timeout: int = 3000) -> bool:
    """Espera a que la grilla visible muestre al menos una fila. False si
    vence (grilla vacia o lenta): el que llama decide, no es un error."""
    try:
        page.locator("table[id*='DXMainTable'] tr[id*='DXDataRow']").filter(visible=True).first.wait_for(
            state="visible", timeout=timeout)
        return True
    except Exception:
        return False


class Listado:
    """Un listado de Advertys (ViewID=..._ListView) con filtro 'Todos' y
    buscador, reutilizado entre items de la misma pagina.

    Flujo por item: `asegurar()` -> `buscar(texto)` -> `abrir_fila(...)` ->
    (el que llama lee el registro). El siguiente `asegurar()` vuelve con el
    'atras' del navegador (confirmado en vivo 2026-10-13: conserva el filtro
    'Todos' y deja el buscador limpio, ~1.5 s vs ~8 s de recargar); si algo
    no esta como se espera, recarga el listado completo como siempre.
    """

    def __init__(self, page, url_sufijo: str):
        from tools.advertys_session import base_url
        self.page = page
        self.url = base_url() + url_sufijo
        self.en_registro = False
        self.cargado = False
        self.recargas = 0
        self.reusos = 0

    # -- estado ---------------------------------------------------------
    def _buscador(self):
        return self.page.locator("input[id$='_Ed_I']").filter(visible=True).first

    def _listo(self) -> bool:
        try:
            if self.page.locator("input[id$='_Ed_I']").filter(visible=True).count() == 0:
                return False
            return bool(self.page.evaluate(_JS_COMBO, list(FILTROS_TODOS)))
        except Exception:
            return False

    # -- carga completa (camino de siempre) ----------------------------
    def recargar(self):
        page = self.page
        page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
        self.recargas += 1
        self.en_registro = False
        try:
            page.wait_for_function(_JS_COMBO, arg=list(FILTROS_DEFECTO + FILTROS_TODOS), timeout=20000)
        except Exception:
            # Algunos listados no tienen combo de filtro: seguir sin filtrar.
            esperar_postback_rapido(page)
            self.cargado = True
            return
        if not page.evaluate(_JS_COMBO, list(FILTROS_TODOS)):
            self._elegir_todos()
        self.cargado = True

    def _elegir_todos(self):
        page = self.page
        item = page.get_by_text("Todas", exact=True).or_(page.get_by_text("Todos", exact=True)).filter(visible=True).first
        # El combo se inicializa en el cliente un instante despues de que el
        # input existe: si el primer click no abre el desplegable, reintentar.
        for _ in range(6):
            btn_id = page.evaluate(_JS_COMBO_ID, list(FILTROS_DEFECTO))
            if btn_id:
                try:
                    page.locator("#" + btn_id.replace("_Cb_I", "_Cb_B-1")).click(timeout=3000)
                except Exception:
                    pass
            try:
                item.wait_for(state="visible", timeout=1500)
                break
            except Exception:
                continue
        item.click(timeout=4000)
        page.wait_for_function(_JS_COMBO, arg=list(FILTROS_TODOS), timeout=15000)
        esperar_postback_rapido(page)

    # -- uso por item ---------------------------------------------------
    def asegurar(self):
        """Deja el listado con filtro 'Todos' y buscador disponible."""
        if self.en_registro:
            try:
                self.page.go_back(timeout=8000)
                self.page.wait_for_function(_JS_HAY_BUSCADOR, timeout=8000)
                esperar_postback_rapido(self.page, aparece=300, timeout=8000)
                if self._listo():
                    self.en_registro = False
                    self.reusos += 1
                    return
            except Exception:
                pass
            self.recargar()
            return
        if not self.cargado or not self._listo():
            self.recargar()

    def buscar(self, texto) -> int:
        """Busca `texto` y devuelve cuantas filas quedan en la grilla visible."""
        b = self._buscador()
        b.click(timeout=5000)
        b.fill(str(texto))
        b.press("Enter")
        esperar_postback_rapido(self.page)
        # El spinner puede no verse (o verse tarde): la grilla vieja, sin
        # filtrar, sigue mostrando filas hasta que llega la respuesta (visto
        # 2026-10-13: 20 "facturas" con el mismo N Referencia). La busqueda
        # esta aplicada cuando TODAS las filas visibles contienen el texto,
        # o cuando no queda ninguna.
        try:
            self.page.wait_for_function(_JS_BUSQUEDA_APLICADA, arg=str(texto), timeout=6000)
        except Exception:
            pass
        t = tabla_visible(self.page)
        return t.locator("tr[id*='DXDataRow']").count() if t is not None else 0

    def abrir_fila(self, texto, idx: int = 0):
        """Click en la celda con `texto`, acotado a la fila `idx` de la grilla
        (no a toda la pagina: ver bug de filas duplicadas en
        modules/cobranza_proveedores/crawl_oc_por_factura.py)."""
        t = tabla_visible(self.page)
        fila = t.locator("tr[id*='DXDataRow']").nth(idx)
        celda = fila.get_by_text(str(texto), exact=True).first
        if celda.count() > 0:
            celda.click(timeout=5000)
        else:
            fila.locator("td").nth(1).click(timeout=5000)
        self.en_registro = True

    def filas_texto(self) -> list[dict]:
        """Filas de la grilla visible como dicts {encabezado: texto}."""
        t = tabla_visible(self.page)
        if t is None:
            return []
        heads = t.locator("td[class*='dxgvHeader']")
        nombres = [heads.nth(i).inner_text().strip() for i in range(heads.count())]
        out = []
        for fila in t.locator("tr[id*='DXDataRow']").all():
            celdas = fila.locator("td")
            n = celdas.count()
            out.append({h: (celdas.nth(j).inner_text().strip() if j < n else "") for j, h in enumerate(nombres)})
        return out


def listado_de(page, url_sufijo: str) -> Listado:
    """Un Listado por (pagina, vista): se crea la primera vez y se reusa."""
    d = page.__dict__.setdefault("_listados", {})
    if url_sufijo not in d:
        d[url_sufijo] = Listado(page, url_sufijo)
    return d[url_sufijo]


# --------------------------------------------------------------------------
# Esperas por condicion (reemplazan networkidle + sleeps fijos)
# --------------------------------------------------------------------------
_SEL_FILAS = "table[id*='DXMainTable'] tr[id*='DXDataRow']"
_SEL_VACIO = "table[id*='DXMainTable'] .dxgvEmptyData, table[id*='DXMainTable'] td[id*='DXEmptyRow']"


def esperar_grid(page, timeout: int = 8000) -> bool:
    """Espera a que la grilla visible muestre filas o el aviso de vacia.
    True si aparecio alguna de las dos, False si vencio el timeout. NO usa
    networkidle. (Selectores a confirmar en vivo en la Fase B.)"""
    try:
        page.wait_for_selector(f"{_SEL_FILAS}, {_SEL_VACIO}", state="visible", timeout=timeout)
        return True
    except Exception:
        return False


def esperar_sin_carga(page, timeout: int = 8000):
    """Espera a que desaparezca el spinner de DevExpress, sin networkidle."""
    try:
        page.wait_for_selector(".dxlpLoadingDiv", state="hidden", timeout=timeout)
    except Exception:
        pass


def volver_o_recargar(page, recargar: Callable[[], None], listo: Callable[[], bool]) -> bool:
    """Intenta volver al listado con el 'atras' del navegador (conserva el
    filtro 'Todos' y evita un goto + re-filtrado). `listo()` confirma que el
    buscador sigue disponible; si no, ejecuta `recargar()` (el camino completo
    de siempre). Devuelve True si pudo reusar el listado, False si recargo."""
    try:
        page.go_back(timeout=8000)
        esperar_sin_carga(page, 6000)
        if listo():
            return True
    except Exception:
        pass
    recargar()
    return False
