#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE_FILE=${NETWISE_PRODUCTION_COMPOSE_FILE:-$ROOT_DIR/compose.production.yml}
ENV_FILE=${NETWISE_PRODUCTION_ENV_FILE:-$ROOT_DIR/.env.production}
PROJECT_NAME=${NETWISE_PRODUCTION_PROJECT:-netwise}
ARCHIVE=${1:-}
CONFIRMATION=${2:-}

if [[ -z "$ARCHIVE" || "$CONFIRMATION" != "--confirm-destroy-current-data" ]]; then
  echo "Usage: $0 BACKUP.dump --confirm-destroy-current-data" >&2
  echo "Restore replaces the current production database." >&2
  exit 2
fi
if [[ ! -r "$ARCHIVE" || ! -s "$ARCHIVE" ]]; then
  echo "Backup archive is not a readable, non-empty file: $ARCHIVE" >&2
  exit 1
fi
ARCHIVE=$(cd "$(dirname "$ARCHIVE")" && pwd -P)/$(basename "$ARCHIVE")

compose_args=(
  --project-name "$PROJECT_NAME"
  --project-directory "$ROOT_DIR"
  --file "$COMPOSE_FILE"
)
if [[ "$ENV_FILE" != "-" ]]; then
  if [[ ! -r "$ENV_FILE" ]]; then
    echo "Production environment file is not readable: $ENV_FILE" >&2
    exit 1
  fi
  compose_args+=(--env-file "$ENV_FILE")
fi

compose() {
  docker compose "${compose_args[@]}" "$@"
}

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    openssl dgst -sha256 "$1" | awk '{print $NF}'
  fi
}

checksum_file="$ARCHIVE.sha256"
if [[ -f "$checksum_file" ]]; then
  expected_checksum=$(awk 'NR == 1 {print $1}' "$checksum_file")
  actual_checksum=$(sha256_file "$ARCHIVE")
  if [[ -z "$expected_checksum" || "$actual_checksum" != "$expected_checksum" ]]; then
    echo "Backup checksum verification failed: $ARCHIVE" >&2
    exit 1
  fi
fi

compose config --quiet
compose up --detach --wait --wait-timeout 180 postgres >/dev/null
if ! compose exec --no-TTY postgres pg_restore --list <"$ARCHIVE" >/dev/null; then
  echo "Backup archive validation failed: $ARCHIVE" >&2
  exit 1
fi

restore_started=0
on_exit() {
  status=$?
  trap - EXIT INT TERM
  if [[ $status -ne 0 && $restore_started -eq 1 ]]; then
    echo "Restore failed after application services were stopped." >&2
    echo "Inspect PostgreSQL and migration logs before restarting Netwise." >&2
  fi
  exit "$status"
}
trap on_exit EXIT INT TERM

compose stop frontend backend projection-worker >/dev/null
restore_started=1
compose exec --no-TTY postgres psql \
  --set=ON_ERROR_STOP=1 \
  --username=netwise \
  --dbname=postgres \
  --command="SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'netwise' AND pid <> pg_backend_pid();" \
  >/dev/null
compose exec --no-TTY postgres pg_restore \
  --username=netwise \
  --dbname=postgres \
  --clean \
  --if-exists \
  --create \
  --no-owner \
  --no-privileges \
  --exit-on-error \
  <"$ARCHIVE"

compose run --rm migrate
compose up --detach --wait --wait-timeout 180
restore_started=0
trap - EXIT INT TERM

printf 'Restore completed: %s\n' "$ARCHIVE"
printf 'Production services are running and healthy.\n'
