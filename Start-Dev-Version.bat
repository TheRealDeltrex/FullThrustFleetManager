@echo off
rem Starts the Full Thrust Fleet Manager dev version from source (README "Running from source").
rem Close this window or press Ctrl+C to stop the server.
cd /d "%~dp0"
title Full Thrust Fleet Manager (dev)

if not exist ".venv\Scripts\python.exe" (
    echo No .venv found. Set it up first:
    echo   python -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
    pause
    exit /b 1
)

if not defined PORT set PORT=5000

rem Open the browser once the server has had a moment to come up.
if not defined FTFM_NO_BROWSER start "" /b cmd /c "timeout /t 3 /nobreak >nul & start "" http://127.0.0.1:%PORT%/"

".venv\Scripts\python.exe" app.py
if errorlevel 1 pause
