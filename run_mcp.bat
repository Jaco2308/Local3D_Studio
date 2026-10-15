@echo off
REM Local3D Studio Universal MCP Server Launcher (Windows)
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python server.py
