# Run all checks on Windows: .\scripts\test.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Push-Location "$root\backend"
try {
    uv sync --quiet
    uv run ruff check .; if ($LASTEXITCODE) { throw "ruff failed" }
    uv run pytest; if ($LASTEXITCODE) { throw "backend tests failed" }
}
finally { Pop-Location }

Push-Location "$root\frontend"
try {
    if (-not (Test-Path node_modules)) { npm install --no-fund --no-audit }
    npm run typecheck; if ($LASTEXITCODE) { throw "typecheck failed" }
    npm test; if ($LASTEXITCODE) { throw "frontend tests failed" }
}
finally { Pop-Location }

Write-Host "All checks passed."
