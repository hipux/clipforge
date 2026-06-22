# ClipForge GPU-Accelerated Setup
# PowerShell version - works reliably on all Windows configurations

$Host.UI.RawUI.WindowTitle = "ClipForge Setup"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   ClipForge GPU-Accelerated Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "[+] Checking Python..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "[OK] $pyVersion found" -ForegroundColor Green
} catch {
    Write-Host "[X] Python not found. Download from https://www.python.org/downloads/" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Create or check venv
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

# Activate venv
Write-Host "[+] Activating virtual environment..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1" 2>$null
if ($LASTEXITCODE -ne 0) {
    # Try the pip directly from venv
    $env:PATH = "$(Get-Location)\venv\Scripts;" + $env:PATH
}

# Upgrade pip
Write-Host "[+] Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet

# Check NVIDIA GPU
Write-Host ""
Write-Host "[+] Checking for NVIDIA GPU..." -ForegroundColor Yellow
$gpuAvailable = $false
try {
    $nvidiaSmi = Get-Command "nvidia-smi" -ErrorAction Stop
    $nvOutput = & nvidia-smi 2>&1
    if ($LASTEXITCODE -eq 0) {
        $gpuAvailable = $true
        # Extract GPU name
        $gpuLine = $nvOutput | Where-Object { $_ -match "RTX|GTX|Quadro|Tesla" } | Select-Object -First 1
        if ($gpuLine) {
            Write-Host "[OK] NVIDIA GPU detected: $($gpuLine.Trim())" -ForegroundColor Green
        } else {
            Write-Host "[OK] NVIDIA GPU detected" -ForegroundColor Green
        }
    }
} catch {
    Write-Host "[!] nvidia-smi not found - installing CPU-only packages" -ForegroundColor Yellow
}

if ($gpuAvailable) {
    Write-Host "[+] Installing PyTorch with CUDA 12.1 (~2.5 GB)..." -ForegroundColor Yellow
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

    Write-Host "[+] Installing llama-cpp-python with CUDA support..." -ForegroundColor Yellow
    $env:CMAKE_ARGS = "-DGGML_CUDA=on"
    pip install llama-cpp-python --no-cache-dir

    Write-Host "[OK] GPU packages installed" -ForegroundColor Green
} else {
    Write-Host "[!] No NVIDIA GPU - installing CPU-only packages" -ForegroundColor Yellow
    Write-Host "    GPU pipeline will not be available" -ForegroundColor Yellow
    Write-Host ""

    Write-Host "[+] Installing PyTorch (CPU-only)..." -ForegroundColor Yellow
    pip install torch torchvision torchaudio

    Write-Host "[+] Installing llama-cpp-python (CPU-only)..." -ForegroundColor Yellow
    pip install llama-cpp-python
}

# Install Python dependencies
Write-Host ""
Write-Host "[+] Installing Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# Check Node.js
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

# Install frontend dependencies
Write-Host "[+] Installing frontend dependencies..." -ForegroundColor Yellow
Set-Location frontend
npm install
Set-Location ..

# Create directories
Write-Host ""
Write-Host "[+] Creating workspace directories..." -ForegroundColor Yellow
@("workspace\downloads", "workspace\output", "workspace\temp", "models") | ForEach-Object {
    if (-not (Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
}
Write-Host "[OK] Directories created" -ForegroundColor Green

# Database migration
Write-Host ""
Write-Host "[+] Running database migration..." -ForegroundColor Yellow
python backend\migrate_gpu_fields.py
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Database migration completed" -ForegroundColor Green
} else {
    Write-Host "[!] Migration skipped (already up to date)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Models will be downloaded automatically on first run:" -ForegroundColor White
Write-Host "  - Whisper (~1.5 GB)    ->  models\whisper\" -ForegroundColor Gray
Write-Host "  - YOLOv8n-face (~6 MB) ->  models\yolov8n-face.pt" -ForegroundColor Gray
Write-Host "  - Qwen3-8B (~4.7 GB)   ->  models\qwen3-8b-q4_k_m.gguf" -ForegroundColor Gray
Write-Host ""
Write-Host "To start ClipForge:" -ForegroundColor White
Write-Host "  Backend:  cd backend && python main.py" -ForegroundColor Cyan
Write-Host "  Frontend: cd frontend && npm run dev" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to close"
