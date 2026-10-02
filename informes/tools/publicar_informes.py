"""
Prepara (y opcionalmente despliega) el sitio estatico de Vercel con el
dashboard y los informes, para que los vea otra gente por una URL.

Sin login a pedido de Javier (2026-10-01): cualquiera con el link ve los
informes. OJO, traen montos, clientes, proveedores y CUITs. Para no
indexarlos, el sitio sale con `X-Robots-Tag: noindex` y robots.txt que
bloquea todo (publicar/vercel.json), pero eso NO es proteccion: quien tenga
la URL entra. Si mas adelante se quiere restringir, se activa
"Vercel Authentication" / "Password Protection" en el proyecto (Settings >
Deployment Protection) sin tocar este script.

Que hace:
  1. Copia salida/dashboard.html y salida/informe_*.html a publicar/public/
     (el dashboard referencia cada informe por nombre de archivo relativo,
     asi que tienen que vivir juntos). No copia .xlsx ni nada mas de salida/.
  2. Agrega index.html (redirige al dashboard) y robots.txt.
  3. Con --deploy, corre `vercel deploy --prod` desde publicar/ (requiere
     `vercel login` y `vercel link` hechos una vez en esa carpeta).

publicar/public/ esta en .gitignore: son datos generados, no se versionan.

Uso (desde informes/):
    python -m tools.publicar_informes            # solo arma publicar/public/
    python -m tools.publicar_informes --deploy   # arma y despliega a produccion
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SALIDA = Path("salida")
PUBLICAR = Path("publicar")
PUBLIC = PUBLICAR / "public"

INDEX_HTML = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="robots" content="noindex,nofollow">
<meta http-equiv="refresh" content="0; url=dashboard.html">
<title>ALESTE ADS - Informes</title></head>
<body><a href="dashboard.html">Ir al dashboard</a></body></html>
"""


def armar() -> list[str]:
    if not (SALIDA / "dashboard.html").exists():
        print("ERROR: no existe salida/dashboard.html. Correr 'python generate_dashboard.py' primero.")
        sys.exit(1)
    # Se vacia el CONTENIDO en vez de borrar la carpeta: en Windows/OneDrive
    # la carpeta puede quedar bloqueada (WinError 5, visto 2026-10-02) y
    # rmtree falla aunque los archivos se puedan borrar.
    PUBLIC.mkdir(parents=True, exist_ok=True)
    for viejo in PUBLIC.iterdir():
        if viejo.is_dir():
            shutil.rmtree(viejo)
        else:
            viejo.unlink()

    archivos = ["dashboard.html"] + sorted(p.name for p in SALIDA.glob("informe_*.html"))
    for nombre in archivos:
        shutil.copy2(SALIDA / nombre, PUBLIC / nombre)
    (PUBLIC / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (PUBLIC / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    return archivos


def main():
    parser = argparse.ArgumentParser(description="Arma (y despliega) el sitio de informes para Vercel")
    parser.add_argument("--deploy", action="store_true", help="despliega a produccion con la CLI de Vercel")
    args = parser.parse_args()

    archivos = armar()
    print(f"OK: {len(archivos)} archivos copiados a {PUBLIC}/ ({', '.join(archivos)})")

    if not args.deploy:
        print("No se desplego (falta --deploy). Para ver como queda: cd publicar && vercel deploy --prod")
        return

    if not (PUBLICAR / ".vercel").exists():
        print("ERROR: publicar/ todavia no esta vinculada a un proyecto de Vercel. Una sola vez:")
        print("  cd publicar && vercel login && vercel link")
        sys.exit(1)
    resultado = subprocess.run(["vercel", "deploy", "--prod", "--yes"], cwd=PUBLICAR, shell=(sys.platform == "win32"))
    sys.exit(resultado.returncode)


if __name__ == "__main__":
    main()
