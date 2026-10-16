"""
Local3D Studio Automated Client Setup Subsystem (Inspired by REA Setup Architecture)
Configures Model Context Protocol (MCP) servers across Antigravity, Claude Desktop,
Cursor, VS Code, and installs agent workflow skills safely with backups.
"""

import os
import sys
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure UTF-8 output encoding on Windows consoles
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure") and sys.stdout is not None:
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure") and sys.stderr is not None:
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.diagnostics import get_client_configs


def get_server_registration_entry() -> Dict[str, Any]:
    """Builds standard MCP registration dictionary pointing to Local3D Studio."""
    is_win = sys.platform == "win32"
    venv_python = PROJECT_ROOT / ".venv" / ("Scripts" if is_win else "bin") / ("python.exe" if is_win else "python")
    python_cmd = str(venv_python) if venv_python.exists() else sys.executable
    server_script = str(PROJECT_ROOT / "server.py")

    return {
        "command": python_cmd,
        "args": [server_script],
        "env": {
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8"
        }
    }


def install_global_cli_shim() -> bool:
    """Installs a global 'local3d' CLI shim into user's PATH directories."""
    is_win = sys.platform == "win32"
    home = Path.home()
    installed = False

    if is_win:
        venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
        python_cmd = str(venv_python) if venv_python.exists() else sys.executable
        server_script = str(PROJECT_ROOT / "server.py")
        cmd_content = f'@echo off\n@"{python_cmd}" "{server_script}" %*\n'

        target_dirs = [
            home / "AppData" / "Local" / "Python" / "bin",
            home / ".gemini" / "antigravity" / "bin",
            home / "AppData" / "Local" / "Microsoft" / "WindowsApps",
        ]
        for tdir in target_dirs:
            if tdir.exists():
                try:
                    (tdir / "local3d.cmd").write_text(cmd_content, encoding="utf-8")
                    installed = True
                except Exception:
                    pass
    else:
        venv_python = PROJECT_ROOT / ".venv" / "bin" / "python3"
        python_cmd = str(venv_python) if venv_python.exists() else sys.executable
        server_script = str(PROJECT_ROOT / "server.py")
        sh_content = f'#!/usr/bin/env bash\nexec "{python_cmd}" "{server_script}" "$@"\n'

        target_dirs = [
            home / ".local" / "bin",
            home / "bin",
            Path("/usr/local/bin")
        ]
        for tdir in target_dirs:
            if tdir.exists():
                try:
                    target_file = tdir / "local3d"
                    target_file.write_text(sh_content, encoding="utf-8")
                    target_file.chmod(0o755)
                    installed = True
                except Exception:
                    pass

    return installed


def install_antigravity_skill() -> bool:
    """Installs the bundled local3d-studio skill into Antigravity global skills directory."""
    src_dir = PROJECT_ROOT / "skills" / "local3d-studio"
    if not src_dir.exists():
        return False

    dst_dir = Path.home() / ".gemini" / "config" / "skills" / "local3d-studio"
    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
        for item in src_dir.rglob("*"):
            rel = item.relative_to(src_dir)
            target = dst_dir / rel
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                shutil.copy2(item, target)
        return True
    except Exception as e:
        print(f"[Setup] Error installing Antigravity skill: {e}", file=sys.stderr)
        return False


def setup_client(client_id: str, dry_run: bool = False) -> Dict[str, Any]:
    """Safely configures Local3D Studio MCP server in the target client configuration."""
    catalog = get_client_configs()
    if client_id not in catalog:
        return {
            "client": client_id,
            "ok": False,
            "status": "unsupported_client",
            "message": f"Client '{client_id}' is not supported. Supported: {', '.join(catalog.keys())}"
        }

    cinfo = catalog[client_id]
    cfg_path: Path = cinfo["path"]
    reg_entry = get_server_registration_entry()

    # Load existing config or create empty base
    data = {}
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    if "mcpServers" not in data:
        data["mcpServers"] = {}

    # Check if already aligned
    existing = data["mcpServers"].get("local3d")
    if existing == reg_entry:
        return {
            "client": client_id,
            "ok": True,
            "status": "already_aligned",
            "path": str(cfg_path),
            "message": f"{cinfo['displayName']} is already configured correctly."
        }

    if dry_run:
        return {
            "client": client_id,
            "ok": True,
            "status": "planned",
            "path": str(cfg_path),
            "entry": reg_entry,
            "message": f"[DRY RUN] Would register Local3D in {cfg_path}"
        }

    # Backup before write
    if cfg_path.exists():
        backup_path = cfg_path.with_suffix(".local3d.backup")
        try:
            shutil.copy2(cfg_path, backup_path)
        except Exception:
            pass

    # Ensure parent directory exists
    cfg_path.parent.mkdir(parents=True, exist_ok=True)

    # Insert registration
    data["mcpServers"]["local3d"] = reg_entry

    # Write atomically
    tmp_path = cfg_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp_path.replace(cfg_path)

    return {
        "client": client_id,
        "ok": True,
        "status": "configured",
        "path": str(cfg_path),
        "message": f"Successfully registered Local3D Studio in {cinfo['displayName']} ({cfg_path})."
    }


def run_setup(clients: Optional[List[str]] = None, dry_run: bool = False) -> List[Dict[str, Any]]:
    """Runs setup across requested clients (or all detected clients)."""
    catalog = get_client_configs()
    target_clients = clients or ["antigravity"]

    results = []
    for cid in target_clients:
        res = setup_client(cid, dry_run=dry_run)
        results.append(res)

    # Also install skill and global CLI shim
    if not dry_run:
        skill_ok = install_antigravity_skill()
        results.append({
            "client": "skill_bundle",
            "ok": skill_ok,
            "status": "installed" if skill_ok else "failed",
            "message": "Antigravity skill bundle installed at ~/.gemini/config/skills/local3d-studio"
        })
        cli_ok = install_global_cli_shim()
        results.append({
            "client": "global_cli",
            "ok": cli_ok,
            "status": "installed" if cli_ok else "failed",
            "message": "Global 'local3d' command installed into system PATH."
        })

    return results


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    target_client = "antigravity"
    for i, arg in enumerate(sys.argv):
        if arg == "--client" and i + 1 < len(sys.argv):
            target_client = sys.argv[i + 1]

    res = run_setup(clients=[target_client], dry_run=dry_run)
    print(json.dumps(res, indent=2))
