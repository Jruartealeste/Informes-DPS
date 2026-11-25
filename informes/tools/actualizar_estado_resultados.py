"""
Refresh del Estado de Resultados: baja de Advertys (solo lectura) los tres
exports que necesita, regenera salida/informe_estado_resultados.html y el
dashboard.

Exports:
    1. Balance Mensual   (modules.balance_mensual.export)  -> ingresos/costos por cuenta
    2. Compras           (modules.compras, via actualizar_todo.exportar_e_ingerir) -> compras en USD
    3. Imputaciones      (modules.iibb.export, el mas pesado) -> cotizacion que se cargo a mano
Pasos 2 y 3 sirven para el ajuste de compras en USD al dolar BNA comprador
(ver modules/estado_resultados/ajuste_usd.py).

No esta en tools/actualizar_todo.py porque no ingesta nada nuevo a
advertys.db (el balance se lee directo del CSV). Los valores manuales
(Staff, Retiro socio) viven en modules/estado_resultados/inputs.json --
actualizarlos antes de correr esto, sobre todo `meses_incompletos` cuando
llegan las facturas de staff del mes.

Uso (parado en informes/):
    python -m tools.actualizar_estado_resultados                # todo
    python -m tools.actualizar_estado_resultados --sin-export   # solo regenera con lo ya bajado
"""
import subprocess
import sys

from tools.actualizar_todo import exportar_e_ingerir


def _correr(args: list[str]) -> int:
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
    return r.returncode


def _exportar_todo() -> bool:
    print("1/5 Exportando Balance Mensual...")
    if _correr(["-m", "modules.balance_mensual.export"]) != 0:
        return False
    print("2/5 Exportando Compras...")
    ok, detalle = exportar_e_ingerir("compras")
    if not ok:  # el nodo del menu a veces no aparece en el primer intento
        print(f"    reintentando ({detalle})")
        ok, detalle = exportar_e_ingerir("compras")
    print(f"    {detalle}")
    if not ok:
        return False
    print("3/5 Exportando Imputaciones (pesado)...")
    return _correr(["-m", "modules.iibb.export"]) == 0


def main():
    if "--sin-export" not in sys.argv and not _exportar_todo():
        print("ERROR: fallo un export; no se regenera el informe para no mostrar datos viejos como frescos.")
        sys.exit(1)
    print("4/5 Generando informe de Estado de Resultados...")
    if _correr(["-m", "modules.estado_resultados.generate_html_report"]) != 0:
        sys.exit(1)
    print("5/5 Regenerando dashboard...")
    sys.exit(_correr(["generate_dashboard.py"]))


if __name__ == "__main__":
    main()
