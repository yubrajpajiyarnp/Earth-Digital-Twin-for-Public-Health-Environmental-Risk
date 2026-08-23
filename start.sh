#!/bin/bash
# Starts both the backend (FastAPI) and frontend (Vite/React) for the Earth Digital Twin
# project, waits until each responds, then prints the dashboard link.

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
LOG_DIR="$PROJECT_ROOT/.logs"
BACKEND_PORT=8000
FRONTEND_PORT=5173

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

echo "Starting Earth Digital Twin..."

# Free up the ports from any previous run before starting fresh.
lsof -ti:$BACKEND_PORT 2>/dev/null | xargs kill -9 2>/dev/null
lsof -ti:$FRONTEND_PORT 2>/dev/null | xargs kill -9 2>/dev/null
sleep 1

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

wait_for "http://127.0.0.1:$BACKEND_PORT/api/health" backend
wait_for "http://localhost:$FRONTEND_PORT/" frontend

echo ""
echo "Backend:   http://127.0.0.1:$BACKEND_PORT   (API docs: http://127.0.0.1:$BACKEND_PORT/docs)"
echo "Frontend:  http://localhost:$FRONTEND_PORT"
echo ""
echo "Open the dashboard here: http://localhost:$FRONTEND_PORT"
echo ""
echo "Logs: $LOG_DIR/backend.log, $LOG_DIR/frontend.log"
echo "To stop: lsof -ti:$BACKEND_PORT | xargs kill; lsof -ti:$FRONTEND_PORT | xargs kill"
