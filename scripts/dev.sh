#!/usr/bin/env bash
# One-command local dev on macOS/Linux/Git Bash: ./scripts/dev.sh
# Starts FastAPI on :8000 (auto-reload) and Vite on :5173. Ctrl+C stops both.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ ! -f "$ROOT/.env" ]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "Created .env from .env.example (add GEMINI_API_KEY when you need AI features)."
fi

(cd "$ROOT/backend" && uv sync --quiet)
[ -d "$ROOT/frontend/node_modules" ] || (cd "$ROOT/frontend" && npm install --no-fund --no-audit)

(cd "$ROOT/backend" && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT INT TERM

echo
echo "  Backend : http://127.0.0.1:8000/api/docs"
echo "  Frontend: http://localhost:5173"
echo
cd "$ROOT/frontend" && npm run dev
