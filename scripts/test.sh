#!/usr/bin/env bash
# Run all checks: ./scripts/test.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT/backend"
uv sync --quiet
uv run ruff check .
uv run pytest

cd "$ROOT/frontend"
[ -d node_modules ] || npm install --no-fund --no-audit
npm run typecheck
npm test

echo "All checks passed."
