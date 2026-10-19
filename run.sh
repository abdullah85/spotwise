#!/usr/bin/env bash
# Run SpotWise locally.
#
#   ./run.sh          build the frontend, serve everything at http://localhost:8000
#   ./run.sh dev      backend with --reload on :8000 + Vite dev server on :5173
#
# Data source: DATABASE_URL if set (e.g. your Neon database), otherwise
# backend/data/prices.json, otherwise SYNTHETIC sample data (generated if missing).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
PORT="${PORT:-8000}"
PY="$BACKEND/.venv/bin/python"

if [ ! -x "$PY" ]; then
  echo "==> creating backend/.venv"
  python3 -m venv "$BACKEND/.venv"
fi
if [ ! -f "$BACKEND/.venv/.deps" ] || [ "$BACKEND/requirements.txt" -nt "$BACKEND/.venv/.deps" ]; then
  echo "==> installing backend dependencies"
  "$PY" -m pip install -q -r "$BACKEND/requirements.txt"
  touch "$BACKEND/.venv/.deps"
fi

if [ -n "${DATABASE_URL:-}" ]; then
  echo "==> data: Postgres (DATABASE_URL)"
elif [ -f "$BACKEND/data/prices.json" ]; then
  echo "==> data: backend/data/prices.json"
else
  [ -f "$BACKEND/data/sample_prices.json" ] || "$PY" "$BACKEND/scripts/make_sample.py"
  echo "==> data: SYNTHETIC sample (not real prices)"
fi

[ -d "$FRONTEND/node_modules" ] || (echo "==> installing frontend dependencies" && cd "$FRONTEND" && npm install)

cd "$BACKEND"
if [ "${1:-}" = "dev" ]; then
  "$PY" -m uvicorn spotwise.main:app --reload --port "$PORT" &
  trap 'kill $! 2>/dev/null' EXIT
  cd "$FRONTEND" && npm run dev
else
  echo "==> building frontend"
  (cd "$FRONTEND" && npm run build --silent)
  echo "==> SpotWise at http://localhost:$PORT  (API docs: /api/docs, Ctrl+C to stop)"
  exec "$PY" -m uvicorn spotwise.main:app --port "$PORT"
fi
