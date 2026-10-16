"""
Local3D Studio Core Package
"""

from core.config import (
    PROJECT_ROOT,
    OUTPUT_DIR,
    WORKER_URL,
    WORKER_HOST,
    WORKER_PORT,
    BLENDER_PATH,
    MODEL_TIER,
    MEMORY_MODE
)

__all__ = [
    "HardwareManager",
    "cleanup_memory",
    "offload_or_cleanup",
    "PROJECT_ROOT",
    "OUTPUT_DIR",
    "WORKER_URL",
    "WORKER_HOST",
    "WORKER_PORT",
    "BLENDER_PATH",
    "MODEL_TIER",
    "MEMORY_MODE"
]


def __getattr__(name: str):
    if name == "HardwareManager":
        from core.hardware_backend import HardwareManager
        return HardwareManager
    if name in ("cleanup_memory", "offload_or_cleanup"):
        from core import memory
        return getattr(memory, name)
    raise AttributeError(f"module 'core' has no attribute {name!r}")

