#!/usr/bin/env bash
# Levanta (o reutiliza) el Postgres local descartable para el QA de ot/.
# Contenedor propio "ot-qa-pg" en 127.0.0.1:54329, volumen propio. No toca
# Neon ni el stack de Supabase de otros proyectos. Idempotente.
# Reusa la imagen de Postgres 17 que ya esta en el disco (no descarga nada).
# Uso: bash levantar-entorno.sh [--reset]   (--reset borra el volumen y la base)
set -euo pipefail

NAME="ot-qa-pg"; VOL="ot-qa-pgdata"; PORT=54329; DBNAME="ot_qa"; PW="qa_local_only"
IMAGE="$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E '/postgres:17|^postgres:17' | head -1 || true)"

command -v docker >/dev/null || { echo "Falta Docker"; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker no esta corriendo"; exit 1; }
[ -n "$IMAGE" ] || { echo "No hay imagen local de Postgres 17. Hace 'docker pull postgres:17-alpine' (~100MB) y volve a correr."; exit 1; }

if [ "${1:-}" = "--reset" ]; then
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  docker volume rm "$VOL" >/dev/null 2>&1 || true
  echo "Reset: contenedor y volumen borrados"
fi

if ! docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  docker run -d --name "$NAME" -e POSTGRES_PASSWORD="$PW" -e POSTGRES_DB="$DBNAME" \
    -v "$VOL":/var/lib/postgresql/data -p 127.0.0.1:$PORT:5432 "$IMAGE" >/dev/null
  echo "Contenedor creado ($IMAGE)"
elif ! docker ps --format '{{.Names}}' | grep -qx "$NAME"; then
  docker start "$NAME" >/dev/null; echo "Contenedor reiniciado"
fi

for _ in $(seq 1 60); do
  docker exec "$NAME" pg_isready -U postgres -d "$DBNAME" >/dev/null 2>&1 && break; sleep 1
done
docker exec "$NAME" pg_isready -U postgres -d "$DBNAME" >/dev/null || { echo "Postgres no arranco"; exit 1; }

# La imagen de Supabase deja el schema public a nombre de supabase_admin; la app
# (y alembic) corren como postgres y necesitan ser duenios. No-op en postgres comun.
docker exec "$NAME" psql -U supabase_admin -d "$DBNAME" -qc "ALTER DATABASE $DBNAME OWNER TO postgres; ALTER SCHEMA public OWNER TO postgres" >/dev/null 2>&1 || true

echo "LISTO. DATABASE_URL de QA: postgresql+psycopg://postgres:$PW@127.0.0.1:$PORT/$DBNAME"
echo "SQL ad hoc: docker exec $NAME psql -U postgres -d $DBNAME -tAc \"select ...\""
