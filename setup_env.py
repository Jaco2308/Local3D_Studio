#!/usr/bin/env python3
"""
Local3D Studio Universal Cross-Platform Environment Setup
Zero external dependencies setup script for GitHub users.
Automatically detects hardware, installs correct PyTorch wheel, dependencies,
verifies Blender, and initializes configuration.
"""

import os
import sys
import shutil
import platform
import subprocess
from pathlib import Path

# ANSI Color codes for clean terminal output
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def log_step(msg: str):
    print(f"\n{BOLD}{CYAN}==> {msg}{RESET}")


def log_success(msg: str):
    print(f"{GREEN}✔ {msg}{RESET}")


def log_warn(msg: str):
    print(f"{YELLOW}⚠ {msg}{RESET}")


def log_error(msg: str):
    print(f"{RED}✖ {msg}{RESET}")


def detect_hardware():
    """Detects OS, Architecture, and GPU type (NVIDIA CUDA, AMD ROCm, Apple MPS, DirectML, CPU)."""
    os_name = platform.system()
    arch = platform.machine().lower()
    gpu_type = "cpu"
    gpu_name = "Host CPU"
    pytorch_cmd = [sys.executable, "-m", "pip", "install", "torch", "torchvision"]

    if os_name == "Darwin":
        if arch in ["arm64", "aarch64"]:
            gpu_type = "apple_silicon"
            gpu_name = f"Apple Silicon ({arch.upper()}) Unified GPU"
            pytorch_cmd = [sys.executable, "-m", "pip", "install", "torch", "torchvision"]
        else:
            gpu_type = "cpu"
            gpu_name = "Intel Mac CPU"

    elif os_name == "Linux":
        # Check NVIDIA
        if shutil.which("nvidia-smi") or os.path.exists("/proc/driver/nvidia"):
            gpu_type = "nvidia_cuda"
            gpu_name = "NVIDIA CUDA GPU"
            pytorch_cmd = [
                sys.executable, "-m", "pip", "install", "torch", "torchvision",
                "--index-url", "https://download.pytorch.org/whl/cu124"
            ]
        # Check AMD ROCm
        elif shutil.which("rocm-smi") or os.path.exists("/dev/kfd"):
            gpu_type = "amd_rocm"
            gpu_name = "AMD ROCm GPU"
            pytorch_cmd = [
                sys.executable, "-m", "pip", "install", "torch", "torchvision",
                "--index-url", "https://download.pytorch.org/whl/rocm6.2"
            ]

    elif os_name == "Windows":
        # Check NVIDIA
        if shutil.which("nvidia-smi"):
            gpu_type = "nvidia_cuda"
            gpu_name = "NVIDIA CUDA GPU"
            pytorch_cmd = [
                sys.executable, "-m", "pip", "install", "torch", "torchvision",
                "--index-url", "https://download.pytorch.org/whl/cu124"
            ]
        else:
            # Check for AMD GPU via WMIC
            try:
                out = subprocess.check_output(
                    ["wmic", "path", "win32_VideoController", "get", "caption"],
                    text=True
                ).lower()
                if "amd" in out or "radeon" in out:
                    gpu_type = "amd_directml"
                    gpu_name = "AMD Radeon GPU (DirectML)"
                    pytorch_cmd = [sys.executable, "-m", "pip", "install", "torch", "torchvision", "torch-directml"]
            except Exception:
                pass

    return {
        "os": os_name,
        "arch": arch,
        "gpu_type": gpu_type,
        "gpu_name": gpu_name,
        "pytorch_cmd": pytorch_cmd
    }


def detect_blender(os_name: str) -> str:
    """Finds Blender executable across operating systems."""
    env_path = os.getenv("BLENDER_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    candidates = []
    if os_name == "Darwin":
        candidates = [
            "/Applications/Blender.app/Contents/MacOS/Blender",
            os.path.expanduser("~/Applications/Blender.app/Contents/MacOS/Blender")
        ]
        import glob
        candidates.extend(glob.glob("/Applications/Blender*.app/Contents/MacOS/Blender"))
    elif os_name == "Windows":
        candidates = [r"C:\Program Files\Blender Foundation\Blender\blender.exe"]
        import glob
        candidates.extend(glob.glob(r"C:\Program Files\Blender Foundation\Blender *\blender.exe"))
    elif os_name == "Linux":
        candidates = ["/usr/bin/blender", "/usr/local/bin/blender", "/snap/bin/blender"]

    for c in candidates:
        if os.path.isfile(c):
            return c

    which_blender = shutil.which("blender")
    if which_blender:
        return which_blender

    return ""


def main():
    print(f"""
{BOLD}{GREEN}╔═════════════════════════════════════════════════════════════════════╗
║                   Local3D Studio 3D Suite Setup                     ║
║       Open-Source 16GB-Friendly Cross-Platform AI & 3D Worker       ║
╚═════════════════════════════════════════════════════════════════════╝{RESET}
""")

    # 1. Hardware Detection
    log_step("Step 1: Detecting System Hardware and Accelerator...")
    hw = detect_hardware()
    print(f"  • Operating System: {BOLD}{hw['os']} ({hw['arch']}){RESET}")
    print(f"  • Detected AI Accelerator: {BOLD}{GREEN}{hw['gpu_name']} [{hw['gpu_type']}]{RESET}")

    # 2. PyTorch Installation
    log_step("Step 2: Checking / Installing PyTorch for target hardware...")
    try:
        import torch
        log_success(f"PyTorch already installed (version {torch.__version__})")
    except ImportError:
        print(f"  Running: {' '.join(hw['pytorch_cmd'])}")
        subprocess.check_call(hw['pytorch_cmd'])
        log_success("PyTorch installed successfully.")

    # 3. Core Dependencies
    log_step("Step 3: Installing Core Dependencies...")
    core_deps = [
        "mcp",
        "fastapi",
        "uvicorn",
        "websockets",
        "pydantic",
        "diffusers",
        "transformers",
        "accelerate",
        "safetensors",
        "rembg",
        "onnxruntime",
        "trimesh",
        "psutil",
        "pillow",
        "requests",
        "gradio_client"
    ]
    install_cmd = [sys.executable, "-m", "pip", "install"] + core_deps
    print(f"  Running: {' '.join(install_cmd)}")
    subprocess.check_call(install_cmd)
    log_success("All core dependencies installed successfully.")

    # Try optional hy3dgen
    try:
        print("  Attempting optional hy3dgen installation for local Hunyuan3D-2mini...")
        subprocess.run([sys.executable, "-m", "pip", "install", "hy3dgen"], capture_output=True, text=True)
    except Exception:
        pass

    # 4. Blender Detection
    log_step("Step 4: Detecting Blender Installation...")
    blender_path = detect_blender(hw['os'])
    if blender_path:
        log_success(f"Blender detected at: {BOLD}{blender_path}{RESET}")
    else:
        log_warn("Blender not found automatically in standard locations.")
        print(f"  Please install Blender from {CYAN}https://www.blender.org/download/{RESET}")
        print("  You can set the BLENDER_PATH environment variable in your .env file.")

    # 5. Environment File Initialization
    log_step("Step 5: Initializing .env configuration...")
    project_root = Path(__file__).resolve().parent
    env_file = project_root / ".env"
    env_example = project_root / ".env.example"

    if not env_file.exists():
        env_content = f"""# Local3D Studio Production Environment Configuration
WORKER_HOST=0.0.0.0
WORKER_PORT=8000
WORKER_URL=http://127.0.0.1:8000

# Path to Blender 4.x / 5.x executable
BLENDER_PATH={blender_path}

# Memory profile: AUTO (defaults to 16GB_SAFE on <=32GB, HIGH_RAM_CACHE on >32GB)
MEMORY_MODE=AUTO

# Model tier: mini (16GB RAM/VRAM friendly) or full (16-24GB dedicated VRAM)
MODEL_TIER=mini

# Optional Hugging Face Token for cloud fallback spaces
HF_TOKEN=
"""
        env_file.write_text(env_content)
        log_success("Created .env with detected system settings.")
    else:
        log_success(".env file already exists. Preserving existing settings.")

    # Summary
    print(f"""
{BOLD}{GREEN}═════════════════════════════════════════════════════════════════════
Setup Complete! Ready for 3D Generation.
═════════════════════════════════════════════════════════════════════{RESET}

{BOLD}How to Run Local3D Studio:{RESET}

1. {CYAN}Start the 3D Compute Worker (Local or Remote Server):{RESET}
   ./start_worker.sh   (or: python worker_api.py)

2. {CYAN}Run the MCP Server with Antigravity / Claude Desktop:{RESET}
   ./run_mcp.sh        (or: python server.py)

3. {CYAN}Wi-Fi LAN Remote Compute (e.g. MacBook Air -> Desktop PC):{RESET}
   On your Desktop PC, run: {BOLD}./start_worker.sh{RESET} (or python worker_api.py)
   On your MacBook Air, edit {BOLD}.env{RESET} to set:
   {BOLD}WORKER_URL=http://192.168.1.XX:8000{RESET} (replace with your Desktop IP)
   Then launch the MCP Server on your MacBook!
""")


if __name__ == "__main__":
    main()
