# =============================================================================
# kirannn v3 — Production Upgrade Installer
# Run this in PowerShell from C:\my_ai_team
# =============================================================================

Write-Host "
 ██╗  ██╗██╗██████╗  █████╗ ███╗   ██╗███╗   ██╗███╗   ██╗
 ██║ ██╔╝██║██╔══██╗██╔══██╗████╗  ██║████╗  ██║████╗  ██║
 █████╔╝ ██║██████╔╝███████║██╔██╗ ██║██╔██╗ ██║██╔██╗ ██║
 ██╔═██╗ ██║██╔══██╗██╔══██║██║╚██╗██║██║╚██╗██║██║╚██╗██║
 ██║  ██╗██║██║  ██║██║  ██║██║ ╚████║██║ ╚████║██║ ╚████║
 v3.0 — Production Upgrade
" -ForegroundColor Cyan

$PROJECT = "C:\my_ai_team"
Set-Location $PROJECT

# ── Step 1: Python packages ───────────────────────────────────────────────────
Write-Host "[1/5] Installing Python packages..." -ForegroundColor Yellow

$packages = @(
    "chromadb",
    "celery",
    "redis",
    "prometheus-client",
    "psutil",
    "pyyaml",
    "pypdf",
    "google-auth",
    "google-auth-oauthlib",
    "google-api-python-client",
    "playwright",
    "apscheduler"
)

foreach ($pkg in $packages) {
    Write-Host "  Installing $pkg..." -NoNewline
    $result = & python -m pip install $pkg --quiet 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host " OK" -ForegroundColor Green
    } else {
        Write-Host " FAILED (continuing)" -ForegroundColor Red
    }
}

# ── Step 2: Playwright browsers ───────────────────────────────────────────────
Write-Host "[2/5] Installing Playwright Chromium..." -ForegroundColor Yellow
python -m playwright install chromium 2>&1 | Out-Null
Write-Host "  Chromium installed" -ForegroundColor Green

# ── Step 3: Pull Ollama models ────────────────────────────────────────────────
Write-Host "[3/5] Pulling Ollama models (this takes a while)..." -ForegroundColor Yellow

$models = @(
    @{name="llama3.1:8b";     desc="Fallback model"},
    @{name="qwen2.5:14b";     desc="Planner model"},
    @{name="deepseek-coder:33b"; desc="Code model (large — ~20GB)"}
)

Write-Host ""
Write-Host "  Models to pull:" -ForegroundColor Cyan
foreach ($m in $models) {
    Write-Host "  - $($m.name): $($m.desc)"
}
Write-Host ""
$pull = Read-Host "  Pull all models now? This may take 30-60 min (y/n)"

if ($pull -eq "y") {
    foreach ($m in $models) {
        Write-Host "  Pulling $($m.name)..." -ForegroundColor Yellow
        ollama pull $m.name
        Write-Host "  Done: $($m.name)" -ForegroundColor Green
    }
} else {
    Write-Host "  Skipping model pull. Pull manually: ollama pull <model>" -ForegroundColor Yellow
}

# ── Step 4: Create directories ─────────────────────────────────────────────────
Write-Host "[4/5] Creating directories..." -ForegroundColor Yellow

$dirs = @(
    "$PROJECT\config",
    "$PROJECT\memory\chroma_db",
    "$PROJECT\workers",
    "$PROJECT\monitoring",
    "$PROJECT\core\agents",
    "$PROJECT\logs",
    "$PROJECT\data\docs",
    "$PROJECT\reports",
    "$PROJECT\skills_hub"
)

foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}
Write-Host "  All directories created" -ForegroundColor Green

# ── Step 5: Copy new files ─────────────────────────────────────────────────────
Write-Host "[5/5] Copying upgraded files..." -ForegroundColor Yellow

# Get the download location (wherever this script is)
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

$copies = @(
    @{src="$SCRIPT_DIR\config\settings.yaml"; dst="$PROJECT\config\settings.yaml"},
    @{src="$SCRIPT_DIR\config\loader.py";     dst="$PROJECT\config\loader.py"},
    @{src="$SCRIPT_DIR\config\__init__.py";   dst="$PROJECT\config\__init__.py"},
    @{src="$SCRIPT_DIR\memory\vector_store.py"; dst="$PROJECT\memory\vector_store.py"},
    @{src="$SCRIPT_DIR\core\rag.py";          dst="$PROJECT\core\rag.py"},
    @{src="$SCRIPT_DIR\core\retry.py";        dst="$PROJECT\core\retry.py"},
    @{src="$SCRIPT_DIR\core\watchdog.py";     dst="$PROJECT\core\watchdog.py"},
    @{src="$SCRIPT_DIR\core\agents\roles.py"; dst="$PROJECT\core\agents\roles.py"},
    @{src="$SCRIPT_DIR\workers\celery_worker.py"; dst="$PROJECT\workers\celery_worker.py"},
    @{src="$SCRIPT_DIR\monitoring\metrics.py"; dst="$PROJECT\monitoring\metrics.py"},
    @{src="$SCRIPT_DIR\api\server.py";        dst="$PROJECT\api\server.py"}
)

foreach ($c in $copies) {
    if (Test-Path $c.src) {
        Copy-Item $c.src $c.dst -Force
        Write-Host "  Copied: $($c.dst)" -ForegroundColor Green
    } else {
        Write-Host "  Missing: $($c.src) — copy manually" -ForegroundColor Red
    }
}

# Create __init__.py files
@("$PROJECT\config", "$PROJECT\workers", "$PROJECT\monitoring", 
  "$PROJECT\core\agents", "$PROJECT\memory") | ForEach-Object {
    $init = "$_\__init__.py"
    if (-not (Test-Path $init)) { New-Item $init -Force | Out-Null }
}

# ── Done ───────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " kirannn v3 — Upgrade Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host " New features:" -ForegroundColor White
Write-Host "   Vector memory (ChromaDB)" -ForegroundColor Green
Write-Host "   RAG pipeline (document retrieval)" -ForegroundColor Green
Write-Host "   Streaming responses (/chat/agent?stream=true)" -ForegroundColor Green
Write-Host "   Prometheus metrics (/metrics)" -ForegroundColor Green
Write-Host "   Watchdog auto-recovery" -ForegroundColor Green
Write-Host "   Critic + Executor + Security agents" -ForegroundColor Green
Write-Host "   Rate limiting + input validation" -ForegroundColor Green
Write-Host "   Response caching" -ForegroundColor Green
Write-Host "   Retry + fallback for all model calls" -ForegroundColor Green
Write-Host ""
Write-Host " Start: python main.py" -ForegroundColor Yellow
Write-Host " Docs:  http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host " Stats: http://localhost:8000/stats" -ForegroundColor Yellow
Write-Host " Metrics: http://localhost:8000/metrics" -ForegroundColor Yellow
Write-Host ""
Write-Host " Optional (for task queue):" -ForegroundColor Yellow
Write-Host "   docker run -d -p 6379:6379 redis" -ForegroundColor Gray
Write-Host "   celery -A workers.celery_worker worker --loglevel=info" -ForegroundColor Gray
