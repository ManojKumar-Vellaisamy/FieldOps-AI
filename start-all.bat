@echo off
title FieldOps AI Launcher
echo ========================================================
echo               Starting FieldOps AI
echo ========================================================

set "BASE_DIR=%~dp0"
if exist "%BASE_DIR%fieldops-ai" (
    set "PROJECT_ROOT=%BASE_DIR%fieldops-ai"
) else (
    set "PROJECT_ROOT=%BASE_DIR%"
)

echo [1/2] Starting Backend (FastAPI on http://localhost:8000)...
start "FieldOps Backend (FastAPI)" cmd /k "cd /d "%PROJECT_ROOT%\backend" && .venv\Scripts\activate && uvicorn app.main:app --reload --port 8000"

echo [2/2] Starting Frontend (React Vite on http://localhost:5173)...
start "FieldOps Frontend (React)" cmd /k "cd /d "%PROJECT_ROOT%\frontend" && npm run dev"

echo.
echo ========================================================
echo   Backend:    http://localhost:8000
echo   API Docs:   http://localhost:8000/docs
echo   Frontend:   http://localhost:5173
echo ========================================================
echo Both services are now running in separate windows.
timeout /t 5
