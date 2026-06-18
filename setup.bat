@echo off
echo ClipForge Setup (Windows)
echo.

where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo FFmpeg not found. Install via winget: winget install Gyan.FFmpeg
    echo Or via chocolatey: choco install ffmpeg
    pause
    exit /b 1
)
echo [OK] FFmpeg found

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Download from https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python found

python -m venv venv
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt

cd frontend
npm install
cd ..

mkdir workspace\downloads 2>nul
mkdir workspace\output 2>nul
mkdir workspace\temp 2>nul
mkdir workspace\models 2>nul

echo.
echo Downloading Whisper AI model (one-time, ~150MB)...
python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-base', local_dir='workspace/models/whisper-base')"
if %errorlevel% equ 0 (
    echo [OK] Whisper model downloaded successfully!
) else (
    echo [WARNING] Whisper model download failed. It will be downloaded on first use.
)

echo.
echo Setup complete! Run start.bat to launch ClipForge.
pause
