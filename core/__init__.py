"""
Local3D Studio Core Package
"""

from core.hardware_backend import HardwareManager
from core.memory import cleanup_memory, offload_or_cleanup
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
