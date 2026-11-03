"""
Script de ESCRITURA en Advertys (ver salvaguarda en CLAUDE.md). Alcance
aprobado por Javier (2026-11-03, Estimado 599): carga los ITEMS de un
Estimado de Costo ya existente a partir de una lista (sacada del Google Sheet
de la pestana "Presentacion", desde la fila 15: B titulo, C articulo,
D cantidad, E precio).

Flujo (relevado en vivo el 2026-11-03 sobre el Estimado 599):
  OT -> pestana "Estimados Costo" -> click en el Estimado -> "Editar" ->
  "Provisorio" (cambiar estado; recien ahi aparece "Nuevo" en la grilla de
  Items) -> por cada item: "Nuevo" -> popup "Estimado Detalle Presupuesto"
  (iframe propio, Dialog=true): Rubro Produccion = SERVICIOS PROPIOS Y
  TARIFARIO (combo; al elegirlo, Articulo pasa a ser un buscador con lupa),
  Articulo (popup de busqueda propio, ActionID=), Titulo, Detalle (= Titulo),
  Cantidad y Precio Unitario -> "Aceptar" (uno por item) -> al final
  "Guardar y cerrar" del Estimado.

Articulo: se busca por el nombre de la columna C. Los articulos de Advertys
se llaman "Categoria - Item" (ej. "Grafica - Adaptacion 1/2 pagina"): se
elige el que coincide exacto con el item (con o sin la categoria). Si no
hay una coincidencia exacta (decision de Javier) se usa "Otros".

Modo de precio (--modo):
  cantidad -> Cantidad = D y Precio Unitario = E / D (el Total da E).
  total    -> Cantidad = 1 y Precio Unitario = E (precio final directo).
Antes de "Aceptar" se verifica que el Total del popup sea igual a E: si no,
se frena sin guardar ese item.

Uso (parado en informes/):
    python -m modules.estimados_costos.cargar_items_estimado 302 599 items.json --modo cantidad
items.json: lista de {"titulo": ..., "articulo": ..., "cantidad": 3, "precio": 202926}
"""
import argparse
import json
import re
import sys
import unicodedata
from decimal import Decimal
from pathlib import Path

from playwright.sync_api import sync_playwright

from modules.estimados_costos.crear_estimado import click_boton_visible, ir_a_ot, shot
from tools.advertys_session import AdvertysLoginError, esperar_postback, login

RUBRO = "SERVICIOS PROPIOS Y TARIFARIO"
ARTICULO_FALLBACK = "Otros"


class CargarItemsError(RuntimeError):
    pass


def _norm(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sin_tildes).strip().casefold()


def _num_ar(valor: Decimal) -> str:
    """Decimal -> texto con coma decimal, sin separador de miles ("202926,00")."""
    return f"{valor:.2f}".replace(".", ",")


def _parse_importe(texto: str) -> Decimal:
    """'$ 202.926,00' -> Decimal('202926.00')"""
    limpio = re.sub(r"[^\d,]", "", texto).replace(",", ".")
    return Decimal(limpio or "0")


def frame_item(page):
    for f in page.frames:
        if "Dialog=true" in f.url and "ActionID=" not in f.url:
            return f
    raise CargarItemsError("No se encontro el popup del item (revisar si cambio la estructura).")


def frame_busqueda(page):
    for f in page.frames:
        if "ActionID=" in f.url:
            return f
    raise CargarItemsError("No se encontro el popup de busqueda de Articulo.")


def _campo(frame, nombre):
    return frame.locator(f"input[id$='_xaf_dvi{nombre}_Edit_I'], textarea[id$='_xaf_dvi{nombre}_Edit_I']").first


def _escribir(frame, page, nombre, valor: str):
    campo = _campo(frame, nombre)
    campo.click()
    page.keyboard.press("Control+A")
    page.keyboard.type(valor)
    page.keyboard.press("Tab")
    page.wait_for_timeout(500)


def elegir_rubro(page):
    dlg = frame_item(page)
    inp = dlg.locator("input[id$='xaf_dviRubroProduccion_Edit_dropdown_DD_I']")
    btn_id = inp.get_attribute("id").replace("_DD_I", "_DD_B-1")
    dlg.locator(f"#{btn_id}").click()
    page.wait_for_timeout(1000)
    dlg.get_by_text(RUBRO, exact=True).last.click()
    esperar_postback(page)
    page.wait_for_timeout(1500)


def _nombre_fila(fila) -> str:
    texto = " ".join(fila.inner_text().split())
    return re.split(r"\s+\$\s", texto)[0].strip()


def _buscar_filas(page, consulta):
    pop = frame_busqueda(page)
    box = pop.locator("input[id$='_Ed_I']").first
    box.click()
    box.fill(consulta)
    box.press("Enter")
    page.wait_for_timeout(1500)
    filas = pop.locator("tr[id*='DXDataRow']")
    return pop, filas, [_nombre_fila(filas.nth(i)) for i in range(filas.count())]


def _coincide(nombre_fila: str, articulo: str) -> bool:
    objetivo = _norm(articulo)
    completo = _norm(nombre_fila)
    sufijo = _norm(nombre_fila.split(" - ", 1)[-1])
    return objetivo in (completo, sufijo)


def elegir_articulo(page, articulo: str) -> str:
    """Abre la lupa de Articulo, busca y elige la coincidencia exacta; si no
    hay, usa "Otros". Devuelve el nombre elegido."""
    dlg = frame_item(page)
    dlg.locator("td[id$='_xaf_dviArticulo_Edit_find_Edit_B0']").first.click()
    page.wait_for_timeout(2000)

    _, filas, nombres = _buscar_filas(page, articulo)
    exactas = [i for i, n in enumerate(nombres) if _coincide(n, articulo)]
    if len(exactas) == 1:
        elegido = exactas[0]
    else:
        motivo = "varias coincidencias exactas" if exactas else "sin coincidencia exacta"
        print(f"  AVISO: articulo {articulo!r}: {motivo} ({nombres}); se usa {ARTICULO_FALLBACK!r}.")
        _, filas, nombres = _buscar_filas(page, ARTICULO_FALLBACK)
        exactas = [i for i, n in enumerate(nombres) if _norm(n) == _norm(ARTICULO_FALLBACK)]
        if len(exactas) != 1:
            raise CargarItemsError(f"No se encontro el articulo {ARTICULO_FALLBACK!r} como alternativa: {nombres}")
        elegido = exactas[0]

    nombre = nombres[elegido]
    filas.nth(elegido).click(timeout=5000)
    page.wait_for_timeout(400)
    try:
        click_boton_visible(frame_busqueda(page), "Aceptar")
    except Exception:
        pass
    esperar_postback(page)
    page.wait_for_timeout(1000)
    return nombre


def cargar_item(page, it: dict, modo: str, n: int) -> None:
    titulo = it["titulo"].strip()
    cantidad = Decimal(str(it["cantidad"]))
    precio = Decimal(str(it["precio"]))
    if cantidad <= 0:
        raise CargarItemsError(f"Item {n} ({titulo!r}): cantidad invalida ({cantidad}).")
    if modo == "cantidad":
        cant_final, unitario = cantidad, (precio / cantidad)
    else:
        cant_final, unitario = Decimal(1), precio

    if not click_boton_visible(page, "Nuevo"):
        raise CargarItemsError("No se encontro el boton 'Nuevo' de la grilla de Items.")
    esperar_postback(page)
    page.wait_for_timeout(2000)

    elegir_rubro(page)
    articulo = elegir_articulo(page, it["articulo"])

    dlg = frame_item(page)
    _escribir(dlg, page, "Titulo", titulo)
    _escribir(dlg, page, "Detalle", titulo)
    dlg = frame_item(page)
    _escribir(dlg, page, "Cantidad", f"{cant_final:f}".rstrip("0").rstrip(".") if cant_final % 1 else str(int(cant_final)))
    dlg = frame_item(page)
    _escribir(dlg, page, "PrecioUnitario", _num_ar(unitario))
    page.wait_for_timeout(800)

    dlg = frame_item(page)
    total = _parse_importe(_campo(dlg, "Total").input_value())
    shot(page, f"est_items_cargar_{n}_antes_aceptar")
    if abs(total - precio) > Decimal("0.05"):
        raise CargarItemsError(
            f"Item {n} ({titulo!r}): el Total del popup es {total} y deberia ser {precio}. No se guardo ese item."
        )
    print(f"  item {n}: {titulo!r} | articulo {articulo!r} | cant {cant_final} x {_num_ar(unitario)} = {total}")

    if not click_boton_visible(dlg, "Aceptar"):
        raise CargarItemsError(f"Item {n}: no se encontro el boton 'Aceptar' del popup.")
    esperar_postback(page)
    page.wait_for_timeout(1500)


def cargar_items(numero_ot: str, numero_estimado: str, items: list[dict], modo: str) -> int:
    if not items:
        raise CargarItemsError("La lista de items esta vacia.")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        try:
            try:
                login(page)
            except AdvertysLoginError as e:
                raise CargarItemsError(str(e)) from e

            ir_a_ot(page, numero_ot)
            if not click_boton_visible(page, "Estimados Costo"):
                raise CargarItemsError("No se encontro la pestana 'Estimados Costo' en esta OT.")
            esperar_postback(page)
            page.wait_for_timeout(1000)
            fila = page.get_by_text(str(numero_estimado), exact=True)
            if fila.count() == 0:
                raise CargarItemsError(f"No se encontro el Estimado {numero_estimado} en la OT {numero_ot}.")
            fila.first.click(timeout=5000)
            esperar_postback(page)
            page.wait_for_timeout(1500)

            page.locator('a[title="Editar"]').first.click(timeout=5000)
            esperar_postback(page)
            page.wait_for_timeout(1500)
            if click_boton_visible(page, "Provisorio"):
                esperar_postback(page)
                page.wait_for_timeout(1500)
            else:
                print("  (no hay boton 'Provisorio': el Estimado ya no esta en un estado que lo permita; sigo)")
            shot(page, f"est_items_cargar_{numero_estimado}_00_provisorio")

            cargados = 0
            for n, it in enumerate(items, start=1):
                cargar_item(page, it, modo, n)
                cargados += 1

            shot(page, f"est_items_cargar_{numero_estimado}_99_antes_guardar")
            if not click_boton_visible(page, "Guardar y cerrar"):
                raise CargarItemsError("No se encontro 'Guardar y cerrar' del Estimado: los items quedaron sin guardar.")
            esperar_postback(page)
            page.wait_for_timeout(2000)
            shot(page, f"est_items_cargar_{numero_estimado}_100_guardado")
            return cargados
        finally:
            browser.close()


def main():
    ap = argparse.ArgumentParser(description="Carga los items de un Estimado de Costo en Advertys")
    ap.add_argument("numero_ot")
    ap.add_argument("numero_estimado")
    ap.add_argument("items_json", help="JSON: lista de {titulo, articulo, cantidad, precio}")
    ap.add_argument("--modo", choices=("cantidad", "total"), required=True,
                    help="cantidad: D x (E/D); total: cantidad 1 y precio final E")
    args = ap.parse_args()
    items = json.loads(Path(args.items_json).read_text(encoding="utf-8"))
    try:
        n = cargar_items(args.numero_ot, args.numero_estimado, items, args.modo)
    except CargarItemsError as e:
        print(f"ERROR: {e}")
        print("No reintentar a ciegas: revisar el Estimado en Advertys (puede haber items ya cargados).")
        sys.exit(1)
    print(f"OK: {n} item(s) cargados en el Estimado {args.numero_estimado}.")


if __name__ == "__main__":
    main()
