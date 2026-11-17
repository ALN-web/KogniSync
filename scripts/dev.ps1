# One-command local dev on Windows: .\scripts\dev.ps1
# Starts FastAPI on :8000 (auto-reload) and Vite on :5173. Ctrl+C stops both.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path "$root\.env")) {
    Copy-Item "$root\.env.example" "$root\.env"
    Write-Host "Created .env from .env.example (add GEMINI_API_KEY when you need AI features)."
}

Write-Host "Installing backend deps (uv sync)..."
Push-Location "$root\backend"; uv sync --quiet; Pop-Location

if (-not (Test-Path "$root\frontend\node_modules")) {
    Write-Host "Installing frontend deps (npm install)..."
    Push-Location "$root\frontend"; npm install --no-fund --no-audit; Pop-Location
}

$backend = Start-Process -PassThru -NoNewWindow -WorkingDirectory "$root\backend" `
    -FilePath "uv" -ArgumentList "run", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"

try {
    Write-Host ""
    Write-Host "  Backend : http://127.0.0.1:8000/api/docs"
    Write-Host "  Frontend: http://localhost:5173"
    Write-Host ""
    Push-Location "$root\frontend"
    npm run dev
}
finally {
    Pop-Location
    if (-not $backend.HasExited) {
        # /T also stops uvicorn's reload worker process.
        taskkill /PID $backend.Id /T /F | Out-Null
    }
}
