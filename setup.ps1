# ClipForge GPU-Accelerated Setup
# PowerShell version - works reliably on all Windows configurations

$Host.UI.RawUI.WindowTitle = "ClipForge Setup"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   ClipForge GPU-Accelerated Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python
Write-Host "[+] Checking Python..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "[OK] $pyVersion found" -ForegroundColor Green
} catch {
    Write-Host "[X] Python not found. Download from https://www.python.org/downloads/" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# 2. Virtual environment
if (Test-Path "venv\Scripts\activate.bat") {
    Write-Host "[OK] Virtual environment already exists" -ForegroundColor Green
} else {
    Write-Host "[+] Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[X] Failed to create virtual environment" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "[OK] Virtual environment created" -ForegroundColor Green
}

# Activate venv by adding Scripts to PATH
Write-Host "[+] Activating virtual environment..." -ForegroundColor Yellow
$venvScripts = Join-Path $ScriptDir "venv\Scripts"
$env:PATH = "$venvScripts;" + $env:PATH
$env:VIRTUAL_ENV = Join-Path $ScriptDir "venv"

# 3. Upgrade pip
Write-Host "[+] Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet

# 4. Enable Windows Long Path (needed for llama-cpp-python build)
Write-Host ""
Write-Host "[+] Enabling Windows Long Path support..." -ForegroundColor Yellow
try {
    $regPath = "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem"
    $current = (Get-ItemProperty -Path $regPath -Name LongPathsEnabled -ErrorAction SilentlyContinue).LongPathsEnabled
    if ($current -eq 1) {
        Write-Host "[OK] Long Path already enabled" -ForegroundColor Green
    } else {
        Set-ItemProperty -Path $regPath -Name LongPathsEnabled -Value 1 -Type DWord
        Write-Host "[OK] Long Path enabled" -ForegroundColor Green
    }
} catch {
    Write-Host "[!] Need admin to enable Long Path - using short temp workaround..." -ForegroundColor Yellow
    $env:TMPDIR = "C:\T"
    $env:TEMP   = "C:\T"
    $env:TMP    = "C:\T"
    New-Item -ItemType Directory -Path "C:\T" -Force | Out-Null
    Write-Host "[OK] Using C:\T as temp dir" -ForegroundColor Green
}

# 5. Detect NVIDIA GPU and CUDA version
Write-Host ""
Write-Host "[+] Checking for NVIDIA GPU..." -ForegroundColor Yellow
$gpuAvailable = $false
$cudaIndex = "https://download.pytorch.org/whl/cu128"
try {
    Get-Command "nvidia-smi" -ErrorAction Stop | Out-Null
    $nvOutput = & nvidia-smi 2>&1
    if ($LASTEXITCODE -eq 0) {
        $gpuAvailable = $true
        $gpuLine = $nvOutput | Where-Object { $_ -match "RTX|GTX|Quadro|Tesla|NVIDIA" } | Select-Object -First 1
        Write-Host "[OK] GPU: $($gpuLine.Trim())" -ForegroundColor Green

        # RTX 50xx (Blackwell) -> cu128; older -> cu121
        if ($gpuLine -match "RTX 50") {
            $cudaIndex = "https://download.pytorch.org/whl/cu128"
            Write-Host "[OK] Blackwell architecture detected - using CUDA 12.8" -ForegroundColor Green
        } else {
            $cudaIndex = "https://download.pytorch.org/whl/cu121"
            Write-Host "[OK] Using CUDA 12.1" -ForegroundColor Green
        }
    }
} catch {
    Write-Host "[!] nvidia-smi not found - CPU-only mode" -ForegroundColor Yellow
}

# 6. Install PyTorch
Write-Host ""
if ($gpuAvailable) {
    Write-Host "[+] Installing PyTorch with CUDA (~2.5 GB)..." -ForegroundColor Yellow
    pip install torch torchvision torchaudio --index-url $cudaIndex
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] GPU torch failed, falling back to CPU version..." -ForegroundColor Yellow
        pip install torch torchvision torchaudio
    }
} else {
    Write-Host "[+] Installing PyTorch (CPU-only)..." -ForegroundColor Yellow
    pip install torch torchvision torchaudio
}

# 7. Install llama-cpp-python
Write-Host ""
Write-Host "[+] Installing llama-cpp-python..." -ForegroundColor Yellow
if ($gpuAvailable) {
    $env:CMAKE_ARGS = "-DGGML_CUDA=on"
    # Try pre-built CUDA wheel first (avoids long-path build issue)
    $cudaTag = if ($cudaIndex -match "cu128") { "cu128" } else { "cu121" }
    pip install llama-cpp-python --extra-index-url "https://abetlen.github.io/llama-cpp-python/whl/$cudaTag" --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] Pre-built wheel failed, trying from source..." -ForegroundColor Yellow
        pip install llama-cpp-python --no-cache-dir
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[!] CUDA build failed - installing CPU version of llama-cpp-python" -ForegroundColor Yellow
            pip install llama-cpp-python
        }
    }
} else {
    pip install llama-cpp-python
}

Write-Host "[OK] llama-cpp-python installed" -ForegroundColor Green

# 8. Install remaining Python dependencies
Write-Host ""
Write-Host "[+] Installing Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# 9. Install instructor
Write-Host "[+] Installing instructor..." -ForegroundColor Yellow
pip install instructor --quiet

# 10. Node.js + frontend
Write-Host ""
Write-Host "[+] Checking Node.js..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version 2>&1
    Write-Host "[OK] Node.js $nodeVersion found" -ForegroundColor Green
} catch {
    Write-Host "[X] Node.js not found. Download from https://nodejs.org/" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[+] Installing frontend dependencies..." -ForegroundColor Yellow
Set-Location (Join-Path $ScriptDir "frontend")
npm install --silent
Set-Location $ScriptDir

# 11. Create directories
Write-Host ""
Write-Host "[+] Creating workspace directories..." -ForegroundColor Yellow
@("workspace\downloads", "workspace\output", "workspace\temp", "models") | ForEach-Object {
    if (-not (Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
}
Write-Host "[OK] Directories created" -ForegroundColor Green

# 12. Database migration
Write-Host ""
Write-Host "[+] Running database migration..." -ForegroundColor Yellow
python backend\migrate_gpu_fields.py
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Migration complete" -ForegroundColor Green
} else {
    Write-Host "[!] Migration skipped (DB not created yet - will run on first launch)" -ForegroundColor Yellow
}

# Done
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Models download automatically on first detection run:" -ForegroundColor White
Write-Host "  Whisper distil-large-v3  (~1.5 GB)  ->  models\whisper\" -ForegroundColor Gray
Write-Host "  YOLOv8n-face             (~6 MB)    ->  models\yolov8n-face.pt" -ForegroundColor Gray
Write-Host "  Qwen3-8B Q4_K_M          (~4.7 GB)  ->  models\qwen3-8b-q4_k_m.gguf" -ForegroundColor Gray
Write-Host ""
Write-Host "To start ClipForge:" -ForegroundColor White
Write-Host "  Backend:   cd backend  && python main.py" -ForegroundColor Cyan
Write-Host "  Frontend:  cd frontend && npm run dev" -ForegroundColor Cyan
Write-Host ""
if ($gpuAvailable) {
    Write-Host "Status: GPU pipeline ENABLED (RTX 5060 detected)" -ForegroundColor Green
} else {
    Write-Host "Status: GPU pipeline DISABLED (no NVIDIA GPU)" -ForegroundColor Yellow
}
Write-Host ""
Read-Host "Press Enter to close"
