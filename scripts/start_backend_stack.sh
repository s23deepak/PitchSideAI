#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="docker"
BUILD=""
FOLLOW_LOGS="false"
WITH_BEAT="true"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8080}"
WORKER_CONCURRENCY="${WORKER_CONCURRENCY:-1}"
PYTHON_BIN="${PYTHON_BIN:-}"
CELERY_BIN="${CELERY_BIN:-}"

usage() {
  cat <<'EOF'
Usage: scripts/start_backend_stack.sh [options]

Start the PitchSideAI backend stack in one command.

Default mode starts the backend applications in Docker:
  redis, postgres, FastAPI backend, Celery worker, Celery beat.

Options:
  --docker          Start all backend applications with docker compose. Default.
  --local          Start redis/postgres in Docker, then run FastAPI and Celery locally.
  --build          Rebuild Docker images before starting services.
  --logs           Follow logs after starting services.
  --no-beat        Do not start the Celery beat scheduler.
  --host HOST      Host for local FastAPI mode. Default: 127.0.0.1.
  --port PORT      Port for local FastAPI mode. Default: 8080.
  -h, --help       Show this help.

Examples:
  scripts/start_backend_stack.sh
  scripts/start_backend_stack.sh --build --logs
  scripts/start_backend_stack.sh --local
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --docker)
      MODE="docker"
      shift
      ;;
    --local)
      MODE="local"
      shift
      ;;
    --build)
      BUILD="--build"
      shift
      ;;
    --logs)
      FOLLOW_LOGS="true"
      shift
      ;;
    --no-beat)
      WITH_BEAT="false"
      shift
      ;;
    --host)
      HOST="${2:?--host requires a value}"
      shift 2
      ;;
    --port)
      PORT="${2:?--port requires a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    echo "Docker Compose is required: install docker compose or docker-compose." >&2
    exit 1
  fi
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

wait_for_http() {
  local url="$1"
  local label="$2"
  local attempts="${3:-30}"

  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "$label is ready: $url"
      return 0
    fi
    sleep 1
  done

  echo "$label did not become ready: $url" >&2
  return 1
}

start_docker_stack() {
  local services=(redis postgres backend notes-worker)
  if [[ "$WITH_BEAT" == "true" ]]; then
    services+=(notes-scheduler)
  fi

  echo "Starting Docker backend stack: ${services[*]}"
  compose up -d $BUILD "${services[@]}"
  compose ps "${services[@]}"

  echo
  echo "FastAPI health: http://localhost:8080/health"
  echo "FastAPI readiness: http://localhost:8080/ready"
  echo "Celery worker service: notes-worker"
  if [[ "$WITH_BEAT" == "true" ]]; then
    echo "Celery beat service: notes-scheduler"
  fi

  if [[ "$FOLLOW_LOGS" == "true" ]]; then
    compose logs -f "${services[@]}"
  fi
}

start_local_stack() {
  require_command curl

  if [[ -z "$PYTHON_BIN" ]]; then
    if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
      PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
    else
      require_command python
      PYTHON_BIN="python"
    fi
  fi

  if [[ -z "$CELERY_BIN" ]]; then
    if [[ -x "$ROOT_DIR/.venv/bin/celery" ]]; then
      CELERY_BIN="$ROOT_DIR/.venv/bin/celery"
    else
      require_command celery
      CELERY_BIN="celery"
    fi
  fi

  echo "Starting Docker infrastructure: redis postgres"
  compose up -d redis postgres
  compose ps redis postgres

  export HOST="$HOST"
  export PORT="$PORT"
  export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://pitchai:pitchai@localhost:5432/pitchai}"
  export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
  export CELERY_BROKER_URL="${CELERY_BROKER_URL:-$REDIS_URL}"
  export CELERY_RESULT_BACKEND="${CELERY_RESULT_BACKEND:-$REDIS_URL}"

  local pids=()

  cleanup() {
    if [[ ${#pids[@]} -gt 0 ]]; then
      echo
      echo "Stopping local backend processes..."
      kill "${pids[@]}" >/dev/null 2>&1 || true
      wait "${pids[@]}" >/dev/null 2>&1 || true
    fi
  }
  trap cleanup EXIT INT TERM

  echo "Starting local Celery worker..."
  "$CELERY_BIN" -A jobs.celery_app.celery_app worker --loglevel=INFO --concurrency="$WORKER_CONCURRENCY" &
  pids+=("$!")

  if [[ "$WITH_BEAT" == "true" ]]; then
    echo "Starting local Celery beat..."
    "$CELERY_BIN" -A jobs.celery_app.celery_app beat --loglevel=INFO &
    pids+=("$!")
  fi

  echo "Starting local FastAPI: http://$HOST:$PORT"
  "$PYTHON_BIN" -m uvicorn api.server:app --host "$HOST" --port "$PORT" &
  pids+=("$!")

  wait_for_http "http://$HOST:$PORT/health" "FastAPI"

  echo
  echo "Backend stack is running. Press Ctrl-C to stop local FastAPI/Celery."
  echo "Docker infrastructure remains running; stop it with: docker compose stop redis postgres"
  wait -n "${pids[@]}"
}

case "$MODE" in
  docker)
    start_docker_stack
    ;;
  local)
    start_local_stack
    ;;
  *)
    echo "Unsupported mode: $MODE" >&2
    exit 2
    ;;
esac
