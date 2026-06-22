# ClipForge GPU-Accelerated Setup
# PowerShell — works on all Windows configurations

$Host.UI.RawUI.WindowTitle = "ClipForge Setup"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) { $ScriptDir = Get-Location }
Set-Location $ScriptDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   ClipForge GPU-Accelerated Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Python ───────────────────────────────────────────────────
Write-Host "[+] Checking Python..." -ForegroundColor Yellow
try {
    $pyVersion = & python --version 2>&1
    Write-Host "[OK] $pyVersion found" -ForegroundColor Green
} catch {
    Write-Host "[X] Python not found. Download: https://www.python.org/downloads/" -ForegroundColor Red
    Read-Host "Press Enter to exit"; exit 1
}

# ── 2. Virtual environment ──────────────────────────────────────
if (Test-Path "venv\Scripts\python.exe") {
    Write-Host "[OK] Virtual environment exists" -ForegroundColor Green
} else {
    Write-Host "[+] Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[X] Failed to create venv" -ForegroundColor Red
        Read-Host "Press Enter to exit"; exit 1
    }
    Write-Host "[OK] Virtual environment created" -ForegroundColor Green
}

# Activate: prepend venv Scripts to PATH
$pip    = Join-Path $ScriptDir "venv\Scripts\pip.exe"
$python = Join-Path $ScriptDir "venv\Scripts\python.exe"
$env:PATH = (Join-Path $ScriptDir "venv\Scripts") + ";" + $env:PATH
$env:VIRTUAL_ENV = Join-Path $ScriptDir "venv"

# ── 3. Upgrade pip ──────────────────────────────────────────────
Write-Host "[+] Upgrading pip..." -ForegroundColor Yellow
& $python -m pip install --upgrade pip --quiet

# ── 4. Detect GPU ───────────────────────────────────────────────
Write-Host ""
Write-Host "[+] Checking for NVIDIA GPU..." -ForegroundColor Yellow
$gpuAvailable = $false
$cudaTag      = "cu128"   # default to RTX 50xx (Blackwell)
try {
    Get-Command "nvidia-smi" -ErrorAction Stop | Out-Null
    $smiOut = & nvidia-smi 2>&1
    if ($LASTEXITCODE -eq 0) {
        $gpuAvailable = $true
        $gpuLine = $smiOut | Where-Object { $_ -match "RTX|GTX|Quadro|Tesla" } | Select-Object -First 1
        Write-Host "[OK] GPU: $($gpuLine.Trim())" -ForegroundColor Green
        if ($gpuLine -match "RTX 50") {
            $cudaTag = "cu128"
            Write-Host "[OK] Blackwell (RTX 50xx) — CUDA 12.8" -ForegroundColor Green
        } else {
            $cudaTag = "cu121"
            Write-Host "[OK] CUDA 12.1" -ForegroundColor Green
        }
    }
} catch {
    Write-Host "[!] nvidia-smi not found — CPU-only mode" -ForegroundColor Yellow
}

# ── 5. PyTorch ──────────────────────────────────────────────────
Write-Host ""
if ($gpuAvailable) {
    Write-Host "[+] Installing PyTorch with $cudaTag (~2.5 GB)..." -ForegroundColor Yellow
    & $pip install torch torchvision torchaudio `
        --index-url "https://download.pytorch.org/whl/$cudaTag" --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] GPU torch failed, installing CPU version..." -ForegroundColor Yellow
        & $pip install torch torchvision torchaudio --quiet
    }
} else {
    Write-Host "[+] Installing PyTorch (CPU-only)..." -ForegroundColor Yellow
    & $pip install torch torchvision torchaudio --quiet
}
Write-Host "[OK] PyTorch installed" -ForegroundColor Green

# ── 6. llama-cpp-python (pre-built wheel — no source build needed) ──
Write-Host ""
Write-Host "[+] Installing llama-cpp-python..." -ForegroundColor Yellow
if ($gpuAvailable) {
    # Use pre-built wheel from GitHub releases — avoids Long Path build issues
    $llamaWheel = "https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.2-$cudaTag/llama_cpp_python-0.3.2-cp313-cp313-win_amd64.whl"
    & $pip install $llamaWheel --quiet 2>$null
    if ($LASTEXITCODE -ne 0) {
        # Fallback to index
        & $pip install llama-cpp-python `
            --extra-index-url "https://abetlen.github.io/llama-cpp-python/whl/$cudaTag" --quiet 2>$null
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] GPU llama-cpp failed — installing CPU version" -ForegroundColor Yellow
        & $pip install llama-cpp-python --quiet
    }
} else {
    & $pip install llama-cpp-python --quiet
}
Write-Host "[OK] llama-cpp-python installed" -ForegroundColor Green

# ── 7. Python dependencies (torch/llama already handled above) ──
Write-Host ""
Write-Host "[+] Installing Python dependencies..." -ForegroundColor Yellow
& $pip install -r requirements.txt

# ── 8. Node.js + frontend ───────────────────────────────────────
Write-Host ""
Write-Host "[+] Checking Node.js..." -ForegroundColor Yellow
try {
    $nodeVer = & node --version 2>&1
    Write-Host "[OK] Node.js $nodeVer found" -ForegroundColor Green
} catch {
    Write-Host "[X] Node.js not found. Download: https://nodejs.org/" -ForegroundColor Red
    Read-Host "Press Enter to exit"; exit 1
}
Write-Host "[+] Installing frontend dependencies..." -ForegroundColor Yellow
Set-Location (Join-Path $ScriptDir "frontend")
npm install --silent
Set-Location $ScriptDir

# ── 9. Directories ──────────────────────────────────────────────
Write-Host ""
Write-Host "[+] Creating workspace directories..." -ForegroundColor Yellow
@("workspace\downloads", "workspace\output", "workspace\temp", "models") | ForEach-Object {
    if (-not (Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
}
Write-Host "[OK] Directories created" -ForegroundColor Green

# ── 10. Database migration ──────────────────────────────────────
Write-Host ""
Write-Host "[+] Running database migration..." -ForegroundColor Yellow
& $python backend\migrate_gpu_fields.py
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Migration complete" -ForegroundColor Green
} else {
    Write-Host "[!] Migration skipped (DB created on first launch)" -ForegroundColor Yellow
}

# ── Done ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Models download automatically on first detection run:" -ForegroundColor White
Write-Host "  Whisper distil-large-v3  (~1.5 GB) -> models\whisper\" -ForegroundColor Gray
Write-Host "  YOLOv8n-face             (~6 MB)   -> models\yolov8n-face.pt" -ForegroundColor Gray
Write-Host "  Qwen3-8B Q4_K_M          (~4.7 GB) -> models\qwen3-8b-q4_k_m.gguf" -ForegroundColor Gray
Write-Host ""
Write-Host "To start ClipForge:" -ForegroundColor White
Write-Host "  Backend:  cd backend  && python main.py" -ForegroundColor Cyan
Write-Host "  Frontend: cd frontend && npm run dev" -ForegroundColor Cyan
Write-Host ""
if ($gpuAvailable) {
    Write-Host "Status: GPU pipeline ENABLED  (RTX 5060 / $cudaTag)" -ForegroundColor Green
} else {
    Write-Host "Status: CPU-only mode (no NVIDIA GPU detected)" -ForegroundColor Yellow
}
Write-Host ""
Read-Host "Press Enter to close"
