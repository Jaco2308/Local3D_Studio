"""
Local3D Studio Core Configuration
Handles environment variables, global directories, and hardware tiering settings.
"""

import os
from pathlib import Path

# Base Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load .env file manually if exists to avoid requiring dotenv dependency
def load_env_file():
    env_paths = [
        PROJECT_ROOT / ".env",
        Path.cwd() / ".env"
    ]
    for p in env_paths:
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key not in os.environ:
                        os.environ[key] = val

load_env_file()

# Core Settings
WORKER_HOST = os.getenv("WORKER_HOST", "0.0.0.0")
WORKER_PORT = int(os.getenv("WORKER_PORT", "8000"))
WORKER_URL = os.getenv("WORKER_URL", f"http://127.0.0.1:{WORKER_PORT}")

BLENDER_PATH = os.getenv("BLENDER_PATH", "")
HF_TOKEN = os.getenv("HF_TOKEN", "")

# Hardware Tiering Settings
FORCE_TIER = os.getenv("FORCE_TIER", "AUTO").upper()

# Overrides (if set by user; otherwise dynamically resolved by HardwareManager tier)
MODEL_TIER = os.getenv("MODEL_TIER", "").lower()
MEMORY_MODE = os.getenv("MEMORY_MODE", "AUTO").upper()
MODEL_TIER_OVERRIDE = MODEL_TIER
OCTREE_RESOLUTION_OVERRIDE = int(os.getenv("OCTREE_RESOLUTION", "0"))
INFERENCE_STEPS_OVERRIDE = int(os.getenv("INFERENCE_STEPS", "0"))
BLENDER_VOXEL_SIZE_OVERRIDE = float(os.getenv("BLENDER_VOXEL_SIZE", "0.0"))
TARGET_TRIANGLES_OVERRIDE = int(os.getenv("TARGET_TRIANGLES", "0"))


def get_tier_config():
    """Returns active tier configuration from HardwareManager."""
    from core.hardware_backend import HardwareManager
    return HardwareManager.get_instance().tier_config


def get_effective_3d_settings():
    """Returns the effective 3D generation settings taking user overrides into account."""
    tier = get_tier_config()
    model_tier = MODEL_TIER_OVERRIDE if MODEL_TIER_OVERRIDE in ["mini", "full"] else tier.model_tier
    octree = OCTREE_RESOLUTION_OVERRIDE if OCTREE_RESOLUTION_OVERRIDE > 0 else tier.octree_resolution
    steps = INFERENCE_STEPS_OVERRIDE if INFERENCE_STEPS_OVERRIDE > 0 else tier.inference_steps
    voxel_size = BLENDER_VOXEL_SIZE_OVERRIDE if BLENDER_VOXEL_SIZE_OVERRIDE > 0 else tier.blender_voxel_size
    triangles = TARGET_TRIANGLES_OVERRIDE if TARGET_TRIANGLES_OVERRIDE > 0 else tier.target_triangles
    
    return {
        "model_tier": model_tier,
        "model_3d_id": "tencent/Hunyuan3D-2" if model_tier == "full" else "tencent/Hunyuan3D-2mini",
        "octree_resolution": octree,
        "inference_steps": steps,
        "blender_voxel_size": voxel_size,
        "target_triangles": triangles,
        "memory_strategy": tier.memory_strategy,
    }
