@echo off
REM Local3D Studio 3D Compute Worker Launcher (Windows)
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

echo ==> Starting Local3D Studio 3D Compute Worker on port 8000...
python worker_api.py
pause
