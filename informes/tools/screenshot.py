"""
Herramienta generica de captura de pantalla (Playwright, Chromium headless).
Parte del framework WAT del proyecto: es un "tool" de la capa de ejecucion,
pensado para que el agente verifique visualmente un informe HTML antes de
darlo por bueno (ver workflows/verificar_informe_visual.md).

Uso:
    python tools/screenshot.py <path-o-url> [label] [--mode light|dark|print|all] [--slide N]

Ejemplos:
    python tools/screenshot.py informe_dinamico.html
    python tools/screenshot.py informe_compras.html compras --mode dark
    python tools/screenshot.py informe_facturas.html facturas --mode all
    python tools/screenshot.py http://localhost:5000/resumen/por-mes
    python tools/screenshot.py informe_compras_slides.html compras-slides --slide 3 --mode dark

Notas:
- Si <path-o-url> no empieza con "http", se trata como archivo local y se
  abre via file:// (asi se capturan los informes .html autocontenidos sin
  necesidad de levantar un server).
- Tambien funciona contra cualquier URL de un server local en desarrollo
  (por ejemplo una vista de la app ot/ en http://localhost:8000/...): es
  un cliente Playwright generico, no le importa que proceso esta del otro
  lado. No hace falta que ot/ tenga Playwright como dependencia propia; se
  corre desde aca. Ver skill `captura-visual` para el caso de uso de
  "captura puntual para ver un diseno en curso", separado del checklist de
  regresion de `verificar-visual`.
- "--mode" controla que emula Playwright:
    light (default) | dark | print | all (los tres, un PNG por cada uno)
  Los informes de este proyecto no tienen boton de tema: el claro/oscuro
  sale puro de "@media (prefers-color-scheme)" en html_report.py, asi que
  alcanza con que Playwright emule el color-scheme (no hace falta clickear
  ningun toggle). "print" emula el media type "print" (la barra de filtro
  se oculta via .no-print, ver html_report.py).
- "--slide N" es para los informes en formato presentacion (slide_shell en
  html_report.py, ver modules/compras/generate_slides_report.py): el scroll
  vive adentro de #deck (no del body), asi que una captura full_page normal
  solo alcanza a la primera slide. Con --slide N (1-indexado) se hace
  scrollIntoView() a esa slide antes de capturar, y la captura pasa a ser de
  viewport (no full_page), porque cada slide ya ocupa toda la pantalla. No
  tiene efecto en "print" (ahi todas las slides ya se apilan en una sola
  pagina larga, capturada entera).
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


def capturar(page, target: str, modo: str, nombre: str, slide: int | None = None):
    if modo == "print":
        page.emulate_media(media="print")
    else:
        page.emulate_media(media="screen", color_scheme=modo)
    page.goto(target, wait_until="networkidle", timeout=30000)
    destino = OUT_DIR / nombre
    if slide and modo != "print":
        # scrollTop directo (no scrollIntoView): el deck tiene scroll-behavior
        # smooth + scroll-snap, y la animacion no llega a terminar en un
        # tiempo de espera corto -> la captura quedaba a mitad de camino
        # entre dos slides.
        page.evaluate(
            """(n) => {
                var deck = document.getElementById('deck');
                var target = document.querySelectorAll('.slide')[n - 1];
                if (deck && target) {
                    // .deck tiene scroll-behavior:smooth (CSS) -- Chromium
                    // anima incluso la asignacion directa de scrollTop, asi
                    // que sin desactivarlo la captura llega a mitad de
                    // camino. Se fuerza instantaneo solo para esta sesion.
                    deck.style.scrollBehavior = 'auto';
                    deck.style.scrollSnapType = 'none';
                    deck.scrollTop = target.offsetTop;
                }
            }""",
            slide,
        )
        page.wait_for_timeout(100)
        page.screenshot(path=str(destino), full_page=False)
    else:
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

    slide = None
    if "--slide" in args:
        i = args.index("--slide")
        slide = int(args[i + 1])
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
            capturar(page, target, m, nombre, slide)
            idx += 1
        browser.close()


if __name__ == "__main__":
    main()
