"""
Local3D Studio Diagnostics & Doctor Subsystem (Inspired by REA Doctor Architecture)
Performs comprehensive deep health checks: host, python, memory, AI accelerator,
Blender installation, dependencies, and client MCP registrations with actionable remediations.
"""

import os
import sys
import json
import shutil
import platform
import subprocess
from pathlib import Path
from typing import Dict, Any, List

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


def get_client_configs() -> Dict[str, Dict[str, Any]]:
    """Returns catalog of supported MCP client configuration paths across platforms."""
    home = Path.home()
    configs = {}

    # 1. Google Antigravity
    configs["antigravity"] = {
        "displayName": "Google Antigravity",
        "path": home / ".gemini" / "config" / "mcp_config.json",
        "type": "json_mcpServers",
    }

    # 2. Claude Desktop
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        claude_path = Path(appdata) / "Claude" / "claude_desktop_config.json" if appdata else home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        claude_path = home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        claude_path = home / ".config" / "Claude" / "claude_desktop_config.json"
    configs["claude_desktop"] = {
        "displayName": "Claude Desktop",
        "path": claude_path,
        "type": "json_mcpServers",
    }

    # 3. Cursor IDE
    configs["cursor"] = {
        "displayName": "Cursor IDE",
        "path": home / ".cursor" / "mcp.json",
        "type": "json_mcpServers",
    }

    # 4. VS Code
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        vscode_path = Path(appdata) / "Code" / "User" / "mcp.json" if appdata else home / "AppData" / "Roaming" / "Code" / "User" / "mcp.json"
    elif sys.platform == "darwin":
        vscode_path = home / "Library" / "Application Support" / "Code" / "User" / "mcp.json"
    else:
        vscode_path = home / ".config" / "Code" / "User" / "mcp.json"
    configs["vscode"] = {
        "displayName": "VS Code",
        "path": vscode_path,
        "type": "json_mcpServers",
    }

    # 5. Gemini CLI
    configs["gemini_cli"] = {
        "displayName": "Gemini CLI",
        "path": home / ".gemini" / "settings.json",
        "type": "json_mcpServers",
    }

    return configs


def inspect_client_registration(client_id: str, client_info: Dict[str, Any]) -> Dict[str, Any]:
    """Inspects whether Local3D Studio is registered in the given client configuration."""
    cfg_path: Path = client_info["path"]
    if not cfg_path.exists():
        return {
            "client": client_id,
            "displayName": client_info["displayName"],
            "configPath": str(cfg_path),
            "state": "missing_config_file",
            "ok": False,
            "remediation": f"Client config file not found at {cfg_path}. Run 'local3d setup --client {client_id}' to create it."
        }

    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        servers = data.get("mcpServers", {})
        if "local3d" not in servers:
            return {
                "client": client_id,
                "displayName": client_info["displayName"],
                "configPath": str(cfg_path),
                "state": "unconfigured",
                "ok": False,
                "remediation": f"Local3D Studio is not registered. Run 'local3d setup --client {client_id}'."
            }

        server_entry = servers["local3d"]
        cmd = server_entry.get("command", "")
        args = server_entry.get("args", [])
        expected_python = str(PROJECT_ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / ("python.exe" if sys.platform == "win32" else "python"))
        expected_script = str(PROJECT_ROOT / "server.py")

        # Check for path drift
        if expected_script not in " ".join(args) and not cmd.endswith("server.py"):
            return {
                "client": client_id,
                "displayName": client_info["displayName"],
                "configPath": str(cfg_path),
                "state": "config_drift",
                "ok": False,
                "remediation": f"Registration points to different path. Run 'local3d setup --client {client_id}' to refresh."
            }

        return {
            "client": client_id,
            "displayName": client_info["displayName"],
            "configPath": str(cfg_path),
            "state": "aligned",
            "ok": True,
            "remediation": None
        }
    except Exception as e:
        return {
            "client": client_id,
            "displayName": client_info["displayName"],
            "configPath": str(cfg_path),
            "state": "corrupted",
            "ok": False,
            "remediation": f"Failed to parse {cfg_path}: {e}"
        }


def run_doctor() -> Dict[str, Any]:
    """Executes full diagnostic suite and returns comprehensive health report."""
    from core.hardware_backend import HardwareManager
    hw = HardwareManager.get_instance()

    checks = []

    # 1. Host & Python Runtime
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)
    checks.append({
        "name": "runtime:python",
        "ok": py_ok,
        "detail": f"Python {py_ver} ({'64-bit' if sys.maxsize > 2**32 else '32-bit'})",
        "remediation": None if py_ok else "Install Python 3.10 or newer (64-bit)."
    })

    in_venv = sys.prefix != sys.base_prefix
    checks.append({
        "name": "runtime:virtual_env",
        "ok": in_venv,
        "detail": str(sys.prefix) if in_venv else "System Python (venv recommended)",
        "remediation": None if in_venv else "Activate Local3D virtual environment: .venv\\Scripts\\activate"
    })

    # 2. Host Hardware & Memory
    ram_gb = hw.memory_info["total_ram_gb"]
    avail_gb = hw.memory_info["available_ram_gb"]
    checks.append({
        "name": "hardware:cpu",
        "ok": True,
        "detail": hw.cpu_name,
        "remediation": None
    })
    checks.append({
        "name": "hardware:memory",
        "ok": ram_gb >= 15.0,
        "detail": f"{ram_gb} GB Total RAM ({avail_gb} GB Available)",
        "remediation": None if ram_gb >= 15.0 else "Local3D Studio recommends at least 16GB RAM for local neural 3D synthesis."
    })

    # 3. AI Accelerator
    acc = hw.device_info
    acc_vendor = acc.get("vendor", "cpu")
    checks.append({
        "name": "hardware:ai_accelerator",
        "ok": True,
        "detail": f"{acc.get('name', 'CPU')} [{acc_vendor}]",
        "remediation": None if acc_vendor != "cpu" else "Host CPU mode active. For 10x faster generation on NVIDIA/AMD/Apple, enable GPU compute or use cloud fallback."
    })

    # 4. Performance Tier
    checks.append({
        "name": "profile:performance_tier",
        "ok": True,
        "detail": hw.tier_config.display_badge_name,
        "remediation": None
    })

    # 5. Blender 3D Manufacturing Engine
    blender_path = hw.blender_path
    blender_ok = bool(blender_path and os.path.exists(blender_path))
    blender_ver = "Unknown"
    bpy_ok = False

    if blender_ok:
        try:
            res = subprocess.check_output(
                [blender_path, "--background", "--factory-startup", "-noaudio", "--python-expr", "import bpy; print('VER:' + bpy.app.version_string)"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=15
            )
            for line in res.splitlines():
                if line.startswith("VER:"):
                    blender_ver = line.replace("VER:", "").strip()
                    bpy_ok = True
                    break
        except Exception as e:
            blender_ver = f"Installed but failed test: {e}"

    checks.append({
        "name": "engine:blender",
        "ok": blender_ok and bpy_ok,
        "detail": f"Blender {blender_ver} at {blender_path}" if blender_ok else "NOT_FOUND",
        "remediation": None if (blender_ok and bpy_ok) else "Install Blender 4.x or 5.x from https://www.blender.org/ or run 'winget install BlenderFoundation.Blender' on Windows."
    })

    # 6. Critical Dependencies
    dep_list = ["torch", "diffusers", "transformers", "trimesh", "rembg", "fastapi", "mcp"]
    missing_deps = []
    for dep in dep_list:
        try:
            __import__(dep)
        except ImportError:
            missing_deps.append(dep)

    checks.append({
        "name": "dependencies:core",
        "ok": len(missing_deps) == 0,
        "detail": "All core packages verified" if not missing_deps else f"Missing: {', '.join(missing_deps)}",
        "remediation": None if not missing_deps else f"Run 'pip install {' '.join(missing_deps)}'"
    })

    # 7. Antigravity Skill Bundle Check
    skill_dst = Path.home() / ".gemini" / "config" / "skills" / "local3d-studio" / "SKILL.md"
    skill_ok = skill_dst.exists()
    checks.append({
        "name": "skill:antigravity",
        "ok": skill_ok,
        "detail": f"Installed at {skill_dst}" if skill_ok else "Missing global skill",
        "remediation": None if skill_ok else "Run 'local3d setup --skill' to install the agent workflow skill."
    })

    # 8. Client Registrations
    client_catalog = get_client_configs()
    registrations = []
    for cid, cinfo in client_catalog.items():
        reg = inspect_client_registration(cid, cinfo)
        registrations.append(reg)
        checks.append({
            "name": f"registration:{cid}",
            "ok": reg["ok"],
            "detail": f"{reg['state']} ({reg['configPath']})",
            "remediation": reg["remediation"]
        })

    all_healthy = all(c["ok"] for c in checks if not c["name"].startswith("registration:"))

    return {
        "status": "healthy" if all_healthy else "degraded",
        "hardware_badge": hw.get_hardware_badge(),
        "summary": {
            "os": f"{platform.system()} ({platform.machine()})",
            "cpu": hw.cpu_name,
            "ram": f"{ram_gb} GB",
            "tier": hw.tier_config.name,
            "blender": blender_ver,
            "accelerator": acc.get("name", "CPU")
        },
        "checks": checks,
        "registrations": registrations
    }


def print_doctor_report(doc: Dict[str, Any]):
    """Prints a beautiful colored diagnostic report in terminal."""
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    RESET = "\033[0m"

    print(f"\n{BOLD}{CYAN}╔═════════════════════════════════════════════════════════════════════╗")
    print(f"║                    Local3D Studio Doctor Diagnostic                 ║")
    print(f"╚═════════════════════════════════════════════════════════════════════╝{RESET}\n")

    print(f"  {BOLD}Hardware Telemetry:{RESET} {doc['hardware_badge']}\n")

    print(f"  {BOLD}System Health Checks:{RESET}")
    for c in doc["checks"]:
        if c["name"].startswith("registration:"):
            continue
        mark = f"{GREEN}✔{RESET}" if c["ok"] else f"{RED}✖{RESET}"
        name = c["name"].ljust(26)
        print(f"    {mark} {BOLD}{name}{RESET} : {c['detail']}")
        if not c["ok"] and c["remediation"]:
            print(f"      {YELLOW}↳ Remediation:{RESET} {c['remediation']}")

    print(f"\n  {BOLD}MCP Client Registrations:{RESET}")
    for r in doc["registrations"]:
        mark = f"{GREEN}✔{RESET}" if r["ok"] else f"{YELLOW}⚠{RESET}"
        dname = r["displayName"].ljust(22)
        state = r["state"].ljust(18)
        print(f"    {mark} {BOLD}{dname}{RESET} : [{state}] {r['configPath']}")
        if not r["ok"] and r["remediation"]:
            print(f"      {CYAN}↳ Fix:{RESET} {r['remediation']}")

    print(f"\n{BOLD}{CYAN}═════════════════════════════════════════════════════════════════════{RESET}\n")


if __name__ == "__main__":
    doc = run_doctor()
    if "--json" in sys.argv:
        print(json.dumps(doc, indent=2))
    else:
        print_doctor_report(doc)
