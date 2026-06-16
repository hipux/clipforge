@echo off
echo Starting ClipForge...
echo.

call venv\Scripts\activate.bat

echo Starting backend on http://localhost:8000
start /B uvicorn backend.main:app --host 0.0.0.0 --port 8000

echo Starting frontend on http://localhost:5173
cd frontend
start /B npm run dev
cd ..

echo.
echo ClipForge is running!
echo Open http://localhost:5173 in your browser
echo Press Ctrl+C to stop
pause
