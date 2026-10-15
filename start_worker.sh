#!/usr/bin/env bash
# Local3D Studio 3D Compute Worker Launcher (macOS / Linux)
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "${DIR}"

echo "==> Starting Local3D Studio 3D Compute Worker on port 8000..."
if [ -f ".venv/bin/python" ]; then
    exec ".venv/bin/python" worker_api.py
else
    exec python3 worker_api.py
fi
