#!/usr/bin/env bash
# Local3D Studio Universal MCP Server Launcher (macOS / Linux)
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "${DIR}"

if [ -f ".venv/bin/python" ]; then
    exec ".venv/bin/python" server.py
else
    exec python3 server.py
fi
