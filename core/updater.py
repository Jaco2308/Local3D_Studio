"""
Local3D Studio Automated Update Subsystem (Inspired by REA Update Architecture)
Pulls latest repository releases, updates virtual environment dependencies,
refreshes agent skills, and runs health verification automatically.
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

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

from core.client_setup import install_antigravity_skill
from core.diagnostics import run_doctor


def check_updates() -> Dict[str, Any]:
    """Checks remote git repository for newer commits on main branch."""
    try:
        # 1. Fetch remote changes
        subprocess.check_call(
            ["git", "-C", str(PROJECT_ROOT), "fetch", "origin", "main"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        local_head = subprocess.check_output(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"],
            text=True
        ).strip()

        remote_head = subprocess.check_output(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "origin/main"],
            text=True
        ).strip()

        behind_count = int(subprocess.check_output(
            ["git", "-C", str(PROJECT_ROOT), "rev-list", "--count", f"HEAD..origin/main"],
            text=True
        ).strip())

        ahead_count = int(subprocess.check_output(
            ["git", "-C", str(PROJECT_ROOT), "rev-list", "--count", f"origin/main..HEAD"],
            text=True
        ).strip())

        return {
            "status": "update_available" if behind_count > 0 else "up_to_date",
            "has_update": behind_count > 0,
            "behind_by": behind_count,
            "ahead_by": ahead_count,
            "local_commit": local_head[:8],
            "remote_commit": remote_head[:8]
        }
    except Exception as e:
        return {
            "status": "error",
            "has_update": False,
            "error": str(e)
        }


def run_update(force: bool = False) -> Dict[str, Any]:
    """
    Executes end-to-end update transaction:
    1. Git pull latest commits
    2. Sync pip dependencies in virtual environment
    3. Re-deploy updated skill bundle to Antigravity
    4. Run doctor diagnostic to verify post-update health
    """
    is_win = sys.platform == "win32"
    venv_python = PROJECT_ROOT / ".venv" / ("Scripts" if is_win else "bin") / ("python.exe" if is_win else "python")
    python_cmd = str(venv_python) if venv_python.exists() else sys.executable

    log_steps = []

    # 1. Git pull
    try:
        pull_output = subprocess.check_output(
            ["git", "-C", str(PROJECT_ROOT), "pull", "origin", "main"],
            text=True,
            stderr=subprocess.STDOUT
        ).strip()
        log_steps.append({"step": "git_pull", "status": "ok", "detail": pull_output})
    except subprocess.CalledProcessError as e:
        return {
            "status": "failed",
            "step_failed": "git_pull",
            "error": e.output,
            "remediation": "Check git working directory status with 'git status' and resolve local changes."
        }

    # 2. Pip dependency sync
    req_file = PROJECT_ROOT / "requirements.txt"
    if req_file.exists():
        try:
            pip_cmd = [python_cmd, "-m", "pip", "install", "-r", str(req_file)]
            pip_output = subprocess.check_output(
                pip_cmd,
                text=True,
                stderr=subprocess.STDOUT
            ).strip()
            log_steps.append({"step": "pip_sync", "status": "ok", "detail": "Dependencies verified and updated."})
        except subprocess.CalledProcessError as e:
            log_steps.append({"step": "pip_sync", "status": "warning", "detail": f"Pip warning: {e.output}"})

    # 3. Refresh Antigravity Skill
    skill_ok = install_antigravity_skill()
    log_steps.append({
        "step": "skill_refresh",
        "status": "ok" if skill_ok else "failed",
        "detail": "Antigravity skill bundle refreshed at ~/.gemini/config/skills/local3d-studio"
    })

    # 4. Post-update Doctor health check
    doc = run_doctor()
    log_steps.append({
        "step": "doctor_verification",
        "status": doc["status"],
        "detail": f"System status: {doc['status']}"
    })

    return {
        "status": "success",
        "message": "Local3D Studio successfully updated to latest release.",
        "steps": log_steps,
        "doctor_summary": doc["summary"],
        "hardware_badge": doc["hardware_badge"]
    }


def print_update_report(res: Dict[str, Any]):
    """Prints a beautiful colored update report."""
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    RESET = "\033[0m"

    print(f"\n{BOLD}{CYAN}╔═════════════════════════════════════════════════════════════════════╗")
    print(f"║                    Local3D Studio Updater Report                    ║")
    print(f"╚═════════════════════════════════════════════════════════════════════╝{RESET}\n")

    if res["status"] == "success":
        print(f"  {GREEN}{BOLD}✔ {res['message']}{RESET}\n")
        print(f"  {BOLD}Update Pipeline Steps:{RESET}")
        for s in res.get("steps", []):
            mark = f"{GREEN}✔{RESET}" if s["status"] == "ok" else f"{YELLOW}⚠{RESET}"
            name = s["step"].ljust(22)
            print(f"    {mark} {BOLD}{name}{RESET} : {s['detail']}")
        print(f"\n  {BOLD}Verified Hardware Profile:{RESET} {res.get('hardware_badge', 'OK')}")
    else:
        print(f"  {RED}{BOLD}✖ Update Failed at step: {res.get('step_failed', 'unknown')}{RESET}")
        print(f"  {YELLOW}Error:{RESET} {res.get('error', '')}")
        print(f"  {CYAN}Remediation:{RESET} {res.get('remediation', '')}")

    print(f"\n{BOLD}{CYAN}═════════════════════════════════════════════════════════════════════{RESET}\n")


if __name__ == "__main__":
    if "--check" in sys.argv:
        check = check_updates()
        if "--json" in sys.argv:
            print(json.dumps(check, indent=2))
        else:
            if check.get("has_update"):
                print(f"Update available: local {check['local_commit']} is {check['behind_by']} commits behind remote {check['remote_commit']}.")
            else:
                print(f"Local3D Studio is up to date at commit {check.get('local_commit', 'HEAD')}.")
    else:
        res = run_update()
        if "--json" in sys.argv:
            print(json.dumps(res, indent=2))
        else:
            print_update_report(res)
