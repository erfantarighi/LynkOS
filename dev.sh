#!/usr/bin/env bash
# Start backend + frontend for local development. Ctrl-C stops both.
set -euo pipefail

cd "$(dirname "$0")"

: "${LYNKOS_MOCK_MODE:=true}"
: "${LYNKOS_JWT_SECRET:=dev-secret-change-me}"
export LYNKOS_MOCK_MODE LYNKOS_JWT_SECRET

if [ ! -d .venv ]; then
    echo ">> uv sync"
    uv sync
fi

if [ ! -d frontend/node_modules ]; then
    echo ">> npm install"
    (cd frontend && npm install)
fi

pids=()
cleanup() {
    echo
    echo ">> stopping"
    for pid in "${pids[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo ">> backend http://localhost:8000  (mock_mode=$LYNKOS_MOCK_MODE)"
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
pids+=($!)

echo ">> frontend http://localhost:5173  (admin/admin)"
(cd frontend && npm run dev -- --host 0.0.0.0) &
pids+=($!)

wait
