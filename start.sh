#!/bin/bash
# Starts every piece of the Nepal Disaster Digital Twin at once: the backend (FastAPI),
# the frontend (Vite/React), and the local Ollama LLM server used for narrative text.
# Waits until each responds, then prints the dashboard link.

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
LOG_DIR="$PROJECT_ROOT/.logs"
BACKEND_PORT=8000
FRONTEND_PORT=5173

# Ollama's base URL can be overridden in backend/.env (OLLAMA_BASE_URL=...); fall back to
# the same default as app/core/config.py.
OLLAMA_BASE_URL="http://localhost:11434"
if [ -f "$BACKEND_DIR/.env" ]; then
  env_value="$(grep -m1 '^OLLAMA_BASE_URL=' "$BACKEND_DIR/.env" | cut -d= -f2- | tr -d '"'"'"'')"
  [ -n "$env_value" ] && OLLAMA_BASE_URL="$env_value"
fi

mkdir -p "$LOG_DIR"

if [ ! -x "$BACKEND_DIR/.venv/bin/uvicorn" ]; then
  echo "Backend virtualenv not found at backend/.venv."
  echo "Set it up first: cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "Frontend dependencies not installed."
  echo "Set them up first: cd frontend && npm install"
  exit 1
fi

echo "Starting Nepal Disaster Digital Twin..."

# Free up the ports from any previous run before starting fresh.
lsof -ti:$BACKEND_PORT 2>/dev/null | xargs kill -9 2>/dev/null
lsof -ti:$FRONTEND_PORT 2>/dev/null | xargs kill -9 2>/dev/null
sleep 1

OLLAMA_STARTED=0
if curl -s -o /dev/null --max-time 1 "$OLLAMA_BASE_URL/api/tags"; then
  : # already running (e.g. as a system service) — leave it alone
elif command -v ollama >/dev/null 2>&1; then
  ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
  OLLAMA_PID=$!
  disown
  OLLAMA_STARTED=1
else
  echo "Note: 'ollama' not found — AI narrative text will fall back to templates."
fi

(cd "$BACKEND_DIR" && .venv/bin/uvicorn app.main:app --reload --port "$BACKEND_PORT") \
  > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
disown

(cd "$FRONTEND_DIR" && npm run dev -- --port "$FRONTEND_PORT") \
  > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
disown

wait_for() {
  local url=$1
  local name=$2
  echo -n "Waiting for $name"
  for _ in $(seq 1 30); do
    if curl -s -o /dev/null --max-time 1 "$url"; then
      echo " ready"
      return 0
    fi
    echo -n "."
    sleep 1
  done
  echo " timed out — check $LOG_DIR/${name}.log"
  return 1
}

if [ "$OLLAMA_STARTED" -eq 1 ]; then
  wait_for "$OLLAMA_BASE_URL/api/tags" ollama || echo "  (narrative text will fall back to templates)"
fi
wait_for "http://127.0.0.1:$BACKEND_PORT/api/health" backend
wait_for "http://localhost:$FRONTEND_PORT/" frontend

echo ""
echo "Backend:   http://127.0.0.1:$BACKEND_PORT   (API docs: http://127.0.0.1:$BACKEND_PORT/docs)"
echo "Frontend:  http://localhost:$FRONTEND_PORT"
echo "Ollama:    $OLLAMA_BASE_URL"
echo ""
echo "Open the dashboard here: http://localhost:$FRONTEND_PORT"
echo ""
echo "Logs: $LOG_DIR/backend.log, $LOG_DIR/frontend.log, $LOG_DIR/ollama.log"
stop_cmd="lsof -ti:$BACKEND_PORT,$FRONTEND_PORT | xargs kill"
if [ "$OLLAMA_STARTED" -eq 1 ]; then
  stop_cmd="$stop_cmd; kill $OLLAMA_PID"
fi
echo "To stop: $stop_cmd"
