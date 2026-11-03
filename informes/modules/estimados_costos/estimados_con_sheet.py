"""
Lista los Estimados de la app `ot/` que ya tienen número en Advertys y un
Google Sheet cargado (link, pestaña, fila inicial, modo de precio). Solo
lectura: es el primer paso del skill `cargar-items-estimado`.

Uso (parado en informes/):
    python -m modules.estimados_costos.estimados_con_sheet --prod
"""
import argparse
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

PROD_URL = "https://ot-sand-iota.vercel.app"
TIMEOUT_HTTP = 60  # arranque en frio de Vercel + Neon


def main():
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Estimados de ot/ con Google Sheet de items")
    destino = ap.add_mutually_exclusive_group()
    destino.add_argument("--prod", action="store_true", help=f"Produccion ({PROD_URL})")
    destino.add_argument("--url", help="URL base de ot/ (default: OT_SYNC_URL del .env)")
    args = ap.parse_args()

    url_base = PROD_URL if args.prod else (args.url or os.environ.get("OT_SYNC_URL"))
    token = os.environ.get("OT_SYNC_TOKEN")
    if not url_base or not token:
        print("ERROR: indicar --prod o --url, y definir OT_SYNC_TOKEN en el .env de la raiz.")
        sys.exit(2)
    try:
        r = httpx.get(
            f"{url_base.rstrip('/')}/api/sync/estimados-con-sheet",
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT_HTTP,
        )
    except httpx.HTTPError as e:
        print(f"ERROR: no se pudo conectar a {url_base}: {e}")
        sys.exit(1)
    if r.status_code != 200:
        print(f"ERROR: ot/ respondio {r.status_code}: {r.text[:300]}")
        sys.exit(1)

    estimados = r.json()
    if not estimados:
        print("No hay Estimados con Google Sheet cargado y numero de Advertys.")
        return
    for e in estimados:
        print(
            f"Estimado {e['numero_estimado']} (OT {e['numero_ot_advertys']}) - {e['titulo']}\n"
            f"  Sheet:   {e['sheet_url']}\n"
            f"  Pestana: {e['sheet_pestana']}  desde la fila {e['sheet_fila_inicio']}  modo de precio: {e['items_modo']}"
        )


if __name__ == "__main__":
    main()
