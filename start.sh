#!/bin/bash
set -e

echo "🎬 Starting ClipForge..."
echo ""

# Check if setup was run
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run ./setup.sh first"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if concurrently is available
if command -v concurrently &> /dev/null; then
    # Use concurrently if available (better output)
    concurrently \
        --names "BACKEND,FRONTEND" \
        --prefix-colors "blue,magenta" \
        "uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload" \
        "cd frontend && npm run dev"
else
    echo "💡 Tip: Install 'concurrently' globally for better output: npm install -g concurrently"
    echo ""
    
    # Fallback: run in background
    echo "🚀 Starting backend on http://localhost:8000"
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!
    
    echo "🚀 Starting frontend on http://localhost:5173"
    cd frontend && npm run dev &
    FRONTEND_PID=$!
    
    # Wait for both processes
    wait $BACKEND_PID $FRONTEND_PID
fi
