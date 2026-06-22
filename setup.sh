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
if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
    echo "[OK] CUDA detected! Installing GPU-accelerated packages..."
    echo ""
    
    # Install PyTorch with CUDA 12.1
    echo "[+] Installing PyTorch with CUDA 12.1 (~2.5 GB)..."
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
    
    # Install llama-cpp-python with CUDA
    echo "[+] Installing llama-cpp-python with CUDA support..."
    CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python --no-cache-dir
    
    echo "[OK] GPU packages installed"
else
    echo "[!] CUDA not detected - installing CPU-only packages"
    echo "    GPU pipeline will not be available"
    echo ""
    
    # Install PyTorch CPU-only
    echo "[+] Installing PyTorch (CPU-only)..."
    pip install torch torchvision torchaudio
    
    # Install llama-cpp-python CPU-only
    echo "[+] Installing llama-cpp-python (CPU-only)..."
    pip install llama-cpp-python
fi

# Install remaining Python dependencies
echo ""
echo "[+] Installing Python dependencies..."
pip install -r requirements.txt

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
echo "[+] Installing frontend dependencies..."
cd frontend
npm install
cd ..

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
