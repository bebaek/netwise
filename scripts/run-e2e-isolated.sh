#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE_FILE="$ROOT_DIR/docker-compose.e2e.yml"
PROJECT_NAME=${NETWISE_E2E_PROJECT:-netwise-e2e}
E2E_PORT=${NETWISE_E2E_PORT:-55173}
KEEP_STACK=${NETWISE_E2E_KEEP:-0}

compose() {
  NETWISE_E2E_PORT="$E2E_PORT" docker compose \
    --project-name "$PROJECT_NAME" \
    --file "$COMPOSE_FILE" \
    "$@"
}

cleanup() {
  status=$?
  trap - EXIT INT TERM

  if [[ $status -ne 0 ]]; then
    echo "E2E run failed; recent isolated stack logs follow:" >&2
    compose logs --no-color --tail=200 >&2 || true
  fi

  if [[ "$KEEP_STACK" == "1" ]]; then
    echo "Keeping isolated E2E stack '$PROJECT_NAME' for inspection." >&2
  else
    compose down --volumes --remove-orphans >/dev/null 2>&1 || true
  fi

  exit "$status"
}
trap cleanup EXIT INT TERM

echo "Starting isolated Netwise E2E stack '$PROJECT_NAME' on port $E2E_PORT..."
compose down --volumes --remove-orphans >/dev/null 2>&1 || true
compose up --detach --build --wait --wait-timeout 180
compose exec --no-TTY backend python -m app.seed_demo --reset

PLAYWRIGHT_BASE_URL="http://127.0.0.1:$E2E_PORT" \
  npm --prefix "$ROOT_DIR/frontend" run test:e2e:local -- "$@"
