#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE_FILE=${NETWISE_PRODUCTION_COMPOSE_FILE:-$ROOT_DIR/compose.production.yml}
ENV_FILE=${NETWISE_PRODUCTION_ENV_FILE:-$ROOT_DIR/.env.production}
PROJECT_NAME=${NETWISE_PRODUCTION_PROJECT:-netwise}
DESTINATION=${1:-$ROOT_DIR/backups}

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

umask 077
mkdir -p "$DESTINATION"
DESTINATION=$(cd "$DESTINATION" && pwd -P)

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
archive="$DESTINATION/netwise-$timestamp.dump"
sequence=1
while [[ -e "$archive" || -e "$archive.sha256" ]]; do
  archive="$DESTINATION/netwise-$timestamp-$sequence.dump"
  sequence=$((sequence + 1))
done
partial="$archive.partial"
completed=0

cleanup() {
  status=$?
  trap - EXIT INT TERM
  rm -f "$partial"
  if [[ $completed -eq 0 ]]; then
    rm -f "$archive" "$archive.sha256"
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

compose config --quiet
compose up --detach --wait --wait-timeout 180 postgres >/dev/null
compose exec --no-TTY postgres pg_dump \
  --username=netwise \
  --dbname=netwise \
  --format=custom \
  --compress=6 \
  --create \
  --no-owner \
  --no-privileges \
  >"$partial"

if [[ ! -s "$partial" ]]; then
  echo "PostgreSQL produced an empty backup archive" >&2
  exit 1
fi
compose exec --no-TTY postgres pg_restore --list <"$partial" >/dev/null
mv "$partial" "$archive"
checksum=$(sha256_file "$archive")
printf '%s  %s\n' "$checksum" "$(basename "$archive")" >"$archive.sha256"
completed=1
trap - EXIT INT TERM

printf 'Backup created: %s\n' "$archive"
printf 'Checksum: %s\n' "$archive.sha256"
