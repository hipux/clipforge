#!/bin/bash
set -e

echo "🎬 Setting up ClipForge..."
echo ""

# Detect OS
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OSTYPE" == "cygwin" ]]; then
    echo "⚠️  Windows detected. This script is designed for WSL2 (Windows Subsystem for Linux)."
    echo "   If you're running in WSL2, continue. Otherwise use Git Bash."
    echo ""
fi

# Check if FFmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "📦 FFmpeg not found. Installing..."
    # Linux/WSL2
    if command -v apt-get &> /dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y ffmpeg
    elif command -v brew &> /dev/null; then
        brew install ffmpeg
    else
        echo "❌ Could not auto-install FFmpeg."
        echo "   Windows/WSL2: Run 'sudo apt-get install ffmpeg' in WSL2 terminal"
        echo "   Or download from https://ffmpeg.org/download.html"
        exit 1
    fi
else
    echo "✅ FFmpeg already installed"
fi

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.11 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✅ Python $PYTHON_VERSION found"

# Create Python virtual environment
echo "📦 Creating Python virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "📦 Setting up frontend..."

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 18 or higher"
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
echo "✅ Node.js v$NODE_VERSION found"

# Install frontend dependencies
cd frontend
npm install
cd ..

# Create workspace directories
echo "📁 Creating workspace directories..."
mkdir -p workspace/downloads
mkdir -p workspace/output
mkdir -p workspace/temp
mkdir -p workspace/models

echo ""
echo "🤖 Downloading Whisper AI model (one-time, ~150MB)..."
python3 -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-base', local_dir='workspace/models/whisper-base')" && echo "✅ Whisper model downloaded successfully!" || echo "⚠️  Whisper model download failed. It will be downloaded on first use."

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "  1. (Optional) Set up YouTube API credentials:"
echo "     - Go to https://console.cloud.google.com"
echo "     - Create a project and enable YouTube Data API v3"
echo "     - Create OAuth 2.0 credentials"
echo "     - Download client_secrets.json to project root"
echo ""
echo "  2. Start ClipForge:"
echo "     ./start.sh"
echo ""
echo "🎉 Enjoy creating clips!"
