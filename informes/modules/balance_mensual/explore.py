"""
Script de exploracion (no productivo): relevamiento en vivo de "Balance
Mensual" y las vistas relacionadas de Contabilidad, hecho para el pedido
puntual de Javier de un Excel de balance mensual (1/7/25-31/8/26) con
detalle de cliente/proveedor (2026-09-16).

Hallazgos del relevamiento (ver export.py y generate_excel.py, que ya usan
esto en produccion):

- "Balance Mensual" (Consultas > Contabilidad > Balance Mensual, ViewID=
  ReporteBalanceMensual_ListView) es un agregado por cuenta x mes (Año, Mes,
  Clase, Sub Clase, Rubro, Nombre, Saldo Anterior, Debe, Haber, Neto Mes,
  Saldo Actual). Filtro por combo con presets (Año Actual/Todos/etc, no un
  rango libre) -- default "Año Actual". NO tiene columna de Cliente ni
  Proveedor en ningun lado, y no hay selector de columnas ocultas en el
  grid (confirmado con click derecho en el header: no aparece un menu de
  columnas, solo el buscador global "Quick create").
- "Mayor Analitico" (misma carpeta) permite elegir rango de cuentas+fechas
  (boton "Parametros") pero tampoco trae Cliente/Proveedor como columna
  propia -- solo Cuenta/Fecha/Asiento/Descripcion/Referencia/Debe/Haber/
  Saldo Acumulado/Centro Costo/Moneda.
- "Resumen Cta.Ctes" (Consultas > Resumen Cta.Ctes, ViewID=
  ReporteCtaCte_ListView) es un agregado mensual Deudora/Acreedora total,
  tampoco por entidad.
- "Cuentas a Cobrar" / "Cuentas a Pagar" (bajo Consultas) NO son listados:
  son formularios de alta de un registro individual -- el primer click de
  relevamiento aterrizo sin querer en un formulario en blanco (nunca se
  toco Guardar/Guardar y cerrar, no se creo nada). Evitar clickearlos de
  nuevo sin necesidad real de dar de alta algo.
- La solucion real (sugerida por Javier): "Imputaciones" (ya usada por
  modules/iibb) trae, en su columna "Leyenda", el nombre real de cliente o
  proveedor por linea de asiento -- confirmado en vivo buscando la cuenta
  112110 (DEUDORES EN CTAS. CTES.): Leyenda trae razones sociales reales
  (ALUAR ALUMINIO ARGENTINO, NORDELTA S.A., etc.) y lo mismo se confirmo
  para cuentas de Proveedores (211020, Leyenda con nombre de proveedor).
  Es texto libre (no una columna de entidad garantizada en el 100% de las
  filas -- medido: ~97% de cobertura no nula), pero es lo mas cercano que
  tiene Advertys a un cruce cuenta+cliente/proveedor exportable en bulk.
  Por eso modules/balance_mensual/generate_excel.py cruza el CSV de Balance
  Mensual con el XLSX crudo de modules/iibb/export.py (que exporta TODAS
  las cuentas de Imputaciones, no solo las de IIBB) en vez de armar un
  export nuevo de Imputaciones desde cero.

Uso (solo para volver a confirmar navegacion/IDs si Advertys cambia algo):
    python -m modules.balance_mensual.explore
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

URL = os.environ.get("ADVERTYS_URL")
USER = os.environ.get("ADVERTYS_USER")
PASSWORD = os.environ.get("ADVERTYS_PASSWORD")

OUT_DIR = Path("exploracion")
OUT_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = OUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)


def esperar_postback(page, timeout=25000):
    try:
        page.wait_for_selector(".dxlpLoadingDiv", state="visible", timeout=3000)
    except Exception:
        pass
    try:
        page.wait_for_selector(".dxlpLoadingDiv", state="hidden", timeout=timeout)
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass


def click_por_texto_o_title(page, texto) -> bool:
    click_js = """(texto) => {
        const candidatos = [...document.querySelectorAll('[title], span, div')];
        const el = candidatos.find(e =>
            (e.getAttribute && e.getAttribute('title') && e.getAttribute('title').trim().startsWith(texto)) ||
            e.textContent.trim() === texto
        );
        if (!el) return false;
        el.click();
        return true;
    }"""
    return page.evaluate(click_js, texto)


def main():
    if not URL or not USER or not PASSWORD:
        print("ERROR: completa ADVERTYS_URL, ADVERTYS_USER y ADVERTYS_PASSWORD en .env")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)

        print(f"Abriendo {URL}")
        page.goto(URL, wait_until="networkidle", timeout=30000)

        user_input = page.locator('input[id$="xaf_dviUserName_Edit_I"]')
        pass_input = page.locator('input[id$="xaf_dviPassword_Edit_I"]')
        user_input.wait_for(state="visible", timeout=15000)

        user_input.click()
        user_input.fill(USER)
        pass_input.click()
        pass_input.fill(PASSWORD)
        pass_input.press("Enter")
        esperar_postback(page)

        if "Login.aspx" in page.url:
            login_link = page.locator('a[title="Iniciar sesión"], a[title="Iniciar sesion"]')
            if login_link.count() > 0:
                login_link.first.click(force=True, timeout=10000)
                esperar_postback(page)

        if "Login.aspx" in page.url:
            print("ERROR: no se pudo hacer login. Revisa usuario/contraseña en .env")
            page.screenshot(path=str(SCREENSHOT_DIR / "balance_error_login.png"))
            browser.close()
            sys.exit(1)

        print(f"Login OK. URL actual: {page.url}")
        page.wait_for_timeout(1200)

        # "Balance Mensual" es hoja de la carpeta "Contabilidad" (bajo
        # Consultas), hermana de "Imputaciones" -- mismo grupo que ya usa
        # modules/iibb. Navega por ID exacto (hay mas de un nodo
        # "Contabilidad" en el menu completo).
        CONTABILIDAD_ID = "Vertical_NC_NB_ITC3i0_TL_N1"
        BALANCE_MENSUAL_ID = "Vertical_NC_NB_ITC3i0_TL_N1_2"

        print("Expandiendo grupo 'Consultas' del menu...")
        if not click_por_texto_o_title(page, "Consultas"):
            print("Aviso: no se encontro el grupo 'Consultas' por texto exacto, sigo igual.")
        page.wait_for_timeout(800)

        print("Expandiendo carpeta 'Contabilidad' (dentro de Consultas, por ID)...")
        try:
            page.locator(f"#{CONTABILIDAD_ID}").click(timeout=10000)
        except Exception as e:
            print(f"ERROR: no se pudo clickear la carpeta Contabilidad por ID: {e}")
            page.screenshot(path=str(SCREENSHOT_DIR / "balance_error_menu.png"), full_page=True)
            browser.close()
            sys.exit(1)
        page.wait_for_timeout(800)

        print("Haciendo click en 'Balance Mensual' (por ID)...")
        try:
            page.locator(f"#{BALANCE_MENSUAL_ID}").click(timeout=10000)
        except Exception as e:
            print(f"ERROR: no se pudo clickear el nodo Balance Mensual por ID: {e}")
            page.screenshot(path=str(SCREENSHOT_DIR / "balance_error_click.png"), full_page=True)
            browser.close()
            sys.exit(1)
        esperar_postback(page)
        print(f"URL tras click en Balance Mensual: {page.url}")
        page.screenshot(path=str(SCREENSHOT_DIR / "balance_01_listado.png"), full_page=True)

        browser.close()


if __name__ == "__main__":
    main()
