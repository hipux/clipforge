@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    ClipForge GPU-Accelerated Setup
echo ========================================
echo.

REM Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Python not found
    echo     Download from https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python found

REM Create venv if not exists
if exist venv\ (
    echo [OK] Virtual environment already exists
) else (
    echo [+] Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [X] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
)

REM Activate venv
echo [+] Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo [+] Upgrading pip...
python -m pip install --upgrade pip --quiet

REM Check CUDA
echo.
echo [+] Checking for NVIDIA GPU...
nvidia-smi >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] CUDA detected! Installing GPU-accelerated packages...
    echo.
    
    REM Install PyTorch with CUDA 12.1
    echo [+] Installing PyTorch with CUDA 12.1 (~2.5 GB)...
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
    
    REM Install llama-cpp-python with CUDA
    echo [+] Installing llama-cpp-python with CUDA support...
    set CMAKE_ARGS=-DGGML_CUDA=on
    pip install llama-cpp-python --no-cache-dir
    
    echo [OK] GPU packages installed
) else (
    echo [!] CUDA not detected - installing CPU-only packages
    echo     GPU pipeline will not be available
    echo.
    
    REM Install PyTorch CPU-only
    echo [+] Installing PyTorch (CPU-only)...
    pip install torch torchvision torchaudio
    
    REM Install llama-cpp-python CPU-only
    echo [+] Installing llama-cpp-python (CPU-only)...
    pip install llama-cpp-python
)

REM Install remaining Python dependencies
echo.
echo [+] Installing Python dependencies...
pip install -r requirements.txt

REM Check Node.js
echo.
echo [+] Checking Node.js...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Node.js not found
    echo     Download from https://nodejs.org/
    pause
    exit /b 1
)
echo [OK] Node.js found

REM Install frontend dependencies
echo [+] Installing frontend dependencies...
cd frontend
call npm install
cd ..

REM Create workspace directories
echo.
echo [+] Creating workspace directories...
mkdir workspace\downloads 2>nul
mkdir workspace\output 2>nul
mkdir workspace\temp 2>nul
mkdir models 2>nul
echo [OK] Directories created

REM Run database migration
echo.
echo [+] Running database migration...
python backend\migrate_gpu_fields.py
if %errorlevel% equ 0 (
    echo [OK] Database migration completed
) else (
    echo [!] Database migration failed (this is OK if already migrated)
)

echo.
echo ========================================
echo    Setup Complete!
echo ========================================
echo.
echo Models will be downloaded automatically on first run:
echo   - Whisper (~1.5 GB) to models/whisper/
echo   - YOLOv8n-face (~6 MB) to models/yolov8n-face.pt
echo   - Qwen3-8B (~4.7 GB) to models/qwen3-8b-q4_k_m.gguf
echo.
echo To start ClipForge:
echo   1. Backend:  start.bat
echo   2. Frontend: cd frontend ^&^& npm run dev
echo.
echo Or use start.bat for both
echo.
pause
