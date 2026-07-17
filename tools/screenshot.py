"""
Herramienta generica de captura de pantalla (Playwright, Chromium headless).
Parte del framework WAT del proyecto: es un "tool" de la capa de ejecucion,
pensado para que el agente verifique visualmente un informe HTML antes de
darlo por bueno (ver workflows/verificar_informe_visual.md).

Uso:
    python tools/screenshot.py <path-o-url> [label] [--mode light|dark|print|all]

Ejemplos:
    python tools/screenshot.py informe_dinamico.html
    python tools/screenshot.py informe_compras.html compras --mode dark
    python tools/screenshot.py informe_facturas.html facturas --mode all
    python tools/screenshot.py http://localhost:5000/resumen/por-mes

Notas:
- Si <path-o-url> no empieza con "http", se trata como archivo local y se
  abre via file:// (asi se capturan los informes .html autocontenidos sin
  necesidad de levantar un server).
- "--mode" controla que emula Playwright:
    light (default) | dark | print | all (los tres, un PNG por cada uno)
  Los informes de este proyecto no tienen boton de tema: el claro/oscuro
  sale puro de "@media (prefers-color-scheme)" en html_report.py, asi que
  alcanza con que Playwright emule el color-scheme (no hace falta clickear
  ningun toggle). "print" emula el media type "print" (la barra de filtro
  se oculta via .no-print, ver html_report.py).
- Los PNG se guardan en exploracion/screenshots/ (carpeta ya gitignorada
  via exploracion/), numerados y sin pisar capturas previas.
- Despues de correr esto, leé el PNG resultante con la tool Read: Claude
  puede ver la imagen directamente y comparar spacing/colores/truncado.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT_DIR = Path("exploracion/screenshots")
MODES = ("light", "dark", "print")


def next_index() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    numeros = []
    for f in OUT_DIR.glob("screenshot-*.png"):
        try:
            numeros.append(int(f.stem.split("-")[1]))
        except (IndexError, ValueError):
            continue
    return (max(numeros) + 1) if numeros else 1


def capturar(page, target: str, modo: str, nombre: str):
    if modo == "print":
        page.emulate_media(media="print")
    else:
        page.emulate_media(media="screen", color_scheme=modo)
    page.goto(target, wait_until="networkidle", timeout=30000)
    destino = OUT_DIR / nombre
    page.screenshot(path=str(destino), full_page=True)
    print(f"OK: {destino}")


def main():
    if len(sys.argv) < 2:
        print("Uso: python tools/screenshot.py <path-o-url> [label] [--mode light|dark|print|all]")
        sys.exit(1)

    target = sys.argv[1]
    args = sys.argv[2:]

    modo = "light"
    if "--mode" in args:
        i = args.index("--mode")
        modo = args[i + 1]
        del args[i:i + 2]
    label = args[0] if args else None

    if modo not in MODES + ("all",):
        print(f"ERROR: --mode debe ser uno de {MODES + ('all',)}")
        sys.exit(1)

    if not target.startswith("http"):
        ruta = Path(target).resolve()
        if not ruta.exists():
            print(f"ERROR: no existe el archivo {ruta}")
            sys.exit(1)
        target = ruta.as_uri()

    modos = list(MODES) if modo == "all" else [modo]
    idx = next_index()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        for m in modos:
            sufijo = f"-{label}" if label else ""
            sufijo += f"-{m}" if modo == "all" else ""
            nombre = f"screenshot-{idx}{sufijo}.png"
            capturar(page, target, m, nombre)
            idx += 1
        browser.close()


if __name__ == "__main__":
    main()
