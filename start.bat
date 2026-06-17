@echo off
echo Starting ClipForge...
echo.
echo Two terminal windows will open:
echo   - Backend (Python/FastAPI) on port 8000
echo   - Frontend (Vite dev server) on port 5173
echo.
echo Keep both windows open while using ClipForge.
echo.

REM Start backend in a new cmd window (from clipforge root)
echo Starting backend...
start "ClipForge Backend" cmd /k "cd /d %~dp0 && call venv\Scripts\activate.bat && echo Backend starting on http://localhost:8000 && uvicorn backend.main:app --host 0.0.0.0 --port 8000"

REM Wait 3 seconds for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend in a new cmd window
echo Starting frontend...
start "ClipForge Frontend" cmd /k "cd /d %~dp0frontend && echo Frontend starting on http://localhost:5173 && npm run dev"

REM Wait 5 seconds for frontend to start
timeout /t 5 /nobreak >nul

REM Open browser
echo.
echo Opening browser...
start http://localhost:5173

echo.
echo ==================================================
echo ClipForge is running!
echo ==================================================
echo.
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:8000/docs
echo.

REM Show local IP for VPN/network access
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set LOCAL_IP=%%a
    goto :found
)
:found
if defined LOCAL_IP (
    set LOCAL_IP=%LOCAL_IP: =%
    echo With VPN or from other devices:
    echo   http://%LOCAL_IP%:5173
    echo.
)


REM Show local IP for VPN/network access
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set LOCAL_IP=%%a
    goto :found
)
:found
if defined LOCAL_IP (
    set LOCAL_IP=%LOCAL_IP: =%
    echo With VPN or from other devices:
    echo   http://%LOCAL_IP%:5173
    echo.
)

echo Two terminal windows are now open.
echo Close them to stop ClipForge.
echo.
pause
