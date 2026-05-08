#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
BRANCH="${BRANCH:-main}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.staging.yml}"
ENV_FILE="${ENV_FILE:-.env.staging}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"

cd "$APP_DIR"

echo "[deploy] app dir: $APP_DIR"
echo "[deploy] branch : $BRANCH"

if [ ! -d ".git" ]; then
  echo "[deploy] ERROR: .git directory not found. Clone the private repository first." >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "[deploy] ERROR: $ENV_FILE not found. Copy .env.staging.example to $ENV_FILE and fill secrets on EC2." >&2
  exit 1
fi

if git status --porcelain | grep -q .; then
  echo "[deploy] ERROR: working tree has local changes. Commit/stash before deploying." >&2
  git status --short >&2
  exit 1
fi

echo "[deploy] fetch/pull"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

echo "[deploy] build images"
APP_ENV_FILE="$ENV_FILE" docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build

if [ "$RUN_MIGRATIONS" = "true" ]; then
  echo "[deploy] apply migrations"
  APP_ENV_FILE="$ENV_FILE" docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm travel-api python - <<'PY'
from pathlib import Path
import psycopg2
import config

migrations = [
    "migration_001_places_v2.sql",
    "migration_002_add_images.sql",
    "migration_002_incremental_sync.sql",
    "migration_003_add_culture_role.sql",
    "migration_004_add_indoor_outdoor.sql",
    "migration_005_add_saved_course_place_snapshots.sql",
    "migration_006_course_operation_logs.sql",
    "migration_007_data_update_pipeline.sql",
    "migration_008_external_places_pipeline.sql",
    "migration_009_place_enrichment.sql",
]

conn = psycopg2.connect(
    host=config.DB_HOST,
    port=config.DB_PORT,
    dbname=config.DB_NAME,
    user=config.DB_USER,
    password=config.DB_PASSWORD,
)
try:
    with conn:
        with conn.cursor() as cur:
            for name in migrations:
                path = Path(name)
                if not path.exists():
                    print(f"[migration] skip missing {name}")
                    continue
                print(f"[migration] apply {name}")
                cur.execute(path.read_text(encoding="utf-8"))
finally:
    conn.close()
PY
else
  echo "[deploy] skip migrations: RUN_MIGRATIONS=$RUN_MIGRATIONS"
fi

echo "[deploy] up"
APP_ENV_FILE="$ENV_FILE" docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d

echo "[deploy] ps"
APP_ENV_FILE="$ENV_FILE" docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps

echo "[deploy] smoke"
API_PORT="$(grep -E '^API_PORT=' "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true)"
API_PORT="${API_PORT:-5000}"
FRONTEND_PORT="$(grep -E '^FRONTEND_PORT=' "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true)"
FRONTEND_PORT="${FRONTEND_PORT:-4175}"
curl -fsS "http://127.0.0.1:${API_PORT}/docs" >/dev/null
curl -fsS "http://127.0.0.1:${API_PORT}/api/regions" >/dev/null
curl -fsS "http://127.0.0.1:${FRONTEND_PORT}/" >/dev/null

echo "[deploy] done"
