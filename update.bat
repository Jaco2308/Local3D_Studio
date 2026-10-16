@echo off
REM Local3D Studio One-Click Automated Updater (Windows)
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python server.py update %*
pause
