#!/bin/bash
# ClipForge GPU-Accelerated Setup Script
# Make executable with: chmod +x setup.sh

set -e

echo "========================================"
echo "   ClipForge GPU-Accelerated Setup"
echo "========================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[X] Python 3 not found"
    echo "    Install Python 3.11+ from https://www.python.org/"
    exit 1
fi
echo "[OK] Python found: $(python3 --version)"

# Create venv if not exists
if [ -d "venv" ]; then
    echo "[OK] Virtual environment already exists"
else
    echo "[+] Creating virtual environment..."
    python3 -m venv venv
    echo "[OK] Virtual environment created"
fi

# Activate venv
echo "[+] Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "[+] Upgrading pip..."
pip install --upgrade pip --quiet

# Check CUDA
echo ""
echo "[+] Checking for NVIDIA GPU..."
GPU_AVAILABLE=false
if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
    GPU_AVAILABLE=true
fi

# --- PyTorch (skip if already importable; reinstall if GPU expected but CPU build) ---
TORCH_OK=false
TORCH_CUDA=$(python3 -c "import torch; print(torch.cuda.is_available())" 2>/dev/null || echo "")
if [ -n "$TORCH_CUDA" ]; then
    if [ "$GPU_AVAILABLE" = true ] && [ "$TORCH_CUDA" != "True" ]; then
        echo "[!] torch installed but without CUDA - reinstalling GPU build"
    else
        TORCH_OK=true
    fi
fi
if [ "$TORCH_OK" = true ]; then
    echo "[OK] PyTorch already installed (cuda=$TORCH_CUDA), skipping"
elif [ "$GPU_AVAILABLE" = true ]; then
    echo "[+] Installing PyTorch with CUDA 12.1 (~2.5 GB)..."
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
else
    echo "[+] Installing PyTorch (CPU-only)..."
    pip install torch torchvision torchaudio
fi

# --- llama-cpp-python (skip if already importable) ---
if python3 -c "import llama_cpp" &> /dev/null; then
    echo "[OK] llama-cpp-python already installed, skipping"
elif [ "$GPU_AVAILABLE" = true ]; then
    echo "[+] Installing llama-cpp-python with CUDA support..."
    CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python --no-cache-dir
else
    echo "[+] Installing llama-cpp-python (CPU-only)..."
    pip install llama-cpp-python
fi

# Install remaining Python dependencies
echo ""
echo "[+] Installing Python dependencies..."
pip install -r requirements.txt

# YamNet audio-event model (laughter/applause/cheering)
echo ""
echo "[+] Checking YamNet audio-event classifier..."
# Check onnxruntime is present in THIS venv before doing anything.
if python3 -c "import onnxruntime" &> /dev/null; then
    echo "[OK] onnxruntime already in venv, skipping install"
else
    echo "[+] onnxruntime not in venv, installing..."
    pip install onnxruntime-gpu --quiet || pip install onnxruntime --quiet
fi
# Only download the model if it isn't already on disk.
if [ -f "models/yamnet/yamnet.onnx" ] && [ -f "models/yamnet/yamnet_class_map.csv" ]; then
    echo "[OK] YamNet model already present, skipping download"
else
    echo "[+] Downloading YamNet assets..."
    if ! python3 -m backend.scripts.download_yamnet; then
        echo "[!] YamNet model not fully downloaded (audio-event detection will stay disabled)."
        echo "    Set CLIPFORGE_YAMNET_URL to a direct .onnx link and re-run setup to enable it."
    fi
fi

# Check Node.js
echo ""
echo "[+] Checking Node.js..."
if ! command -v node &> /dev/null; then
    echo "[X] Node.js not found"
    echo "    Download from https://nodejs.org/"
    exit 1
fi
echo "[OK] Node.js found: $(node --version)"

# Install frontend dependencies
if [ -d "frontend/node_modules" ]; then
    echo "[OK] Frontend dependencies already installed, skipping"
else
    echo "[+] Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

# Create workspace directories
echo ""
echo "[+] Creating workspace directories..."
mkdir -p workspace/downloads
mkdir -p workspace/output
mkdir -p workspace/temp
mkdir -p models
echo "[OK] Directories created"

# Run database migration
echo ""
echo "[+] Running database migration..."
if python3 backend/migrate_gpu_fields.py; then
    echo "[OK] Database migration completed"
else
    echo "[!] Database migration failed (this is OK if already migrated)"
fi

echo ""
echo "========================================"
echo "    Setup Complete!"
echo "========================================"
echo ""
echo "Models will be downloaded automatically on first run:"
echo "  - Whisper (~1.5 GB) to models/whisper/"
echo "  - YOLOv8n-face (~6 MB) to models/yolov8n-face.pt"
echo "  - Qwen3-8B (~4.7 GB) to models/qwen3-8b-q4_k_m.gguf"
echo ""
echo "To start ClipForge:"
echo "  1. Backend:  ./start.sh"
echo "  2. Frontend: cd frontend && npm run dev"
echo ""
echo "Or check start.sh for combined startup"
echo ""
read -rp "Press Enter to close..." _