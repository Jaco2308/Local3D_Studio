"""
Local3D Studio Safe Memory Manager
Handles immediate deallocation, garbage collection, and GPU cache clearing
tailored to the active performance tier memory strategy:
- STRICT_DISK_UNLOAD: complete deallocation & cache flush (Tier 1 Eco / 16GB Safe)
- SINGLE_RAM_CACHE: keeps 3D model in CPU RAM (Tier 2 Balanced)
- DDR5_HOT_SWAP: preloads models into fast system RAM, swaps to GPU in 0.3s (Tier 3 Pro)
- VRAM_PINNED: models pinned permanently in GPU VRAM (Tier 4 Ultra)
"""

import gc
import psutil
from typing import Optional, Any
from core.hardware_backend import HardwareManager

try:
    import torch
except ImportError:
    torch = None


def cleanup_memory(obj_to_delete: Optional[Any] = None, label: str = ""):
    """
    Deallocates an AI pipeline or tensor, invokes garbage collection,
    and flushes GPU memory caches (CUDA, ROCm, and MPS).
    """
    if obj_to_delete is not None:
        try:
            del obj_to_delete
        except Exception:
            pass

    # Standard Python garbage collector
    gc.collect()

    # Hardware-specific cache flushing
    if torch is not None:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            try:
                torch.mps.empty_cache()
            except Exception:
                pass

    hw = HardwareManager.get_instance()
    vm = psutil.virtual_memory()
    available_gb = round(vm.available / (1024 ** 3), 2)
    tag = f" [{label}]" if label else ""
    print(f"[MemoryManager]{tag} Cache flushed. Available RAM: {available_gb} GB (Tier: {hw.tier_config.label} | Strategy: {hw.tier_config.memory_strategy})")


def offload_or_cleanup(pipeline: Any, label: str = "") -> Optional[Any]:
    """
    Manages pipeline lifecycle based on active performance tier strategy:
    - STRICT_DISK_UNLOAD: Destroys pipeline and flushes all caches.
    - SINGLE_RAM_CACHE / DDR5_HOT_SWAP: Offloads pipeline weights to CPU RAM.
    - VRAM_PINNED: Keeps pipeline pinned in GPU VRAM.
    """
    if pipeline is None:
        return None

    hw = HardwareManager.get_instance()
    strategy = hw.tier_config.memory_strategy

    if strategy == "STRICT_DISK_UNLOAD":
        cleanup_memory(pipeline, label=f"Unload {label} (Strict Disk Unload)")
        return None

    elif strategy in ["SINGLE_RAM_CACHE", "DDR5_HOT_SWAP"]:
        try:
            if hasattr(pipeline, "to"):
                pipeline.to("cpu")
                print(f"[MemoryManager] Offloaded {label} to CPU RAM cache ({strategy}).")
                # Flush GPU caches now that weights reside in system RAM
                if torch is not None:
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                        try:
                            torch.mps.empty_cache()
                        except Exception:
                            pass
                return pipeline
        except Exception as e:
            print(f"[MemoryManager] Could not offload {label} to CPU ({e}). Destroying instead.")
            cleanup_memory(pipeline, label=f"Fallback Unload {label}")
            return None

    elif strategy == "VRAM_PINNED":
        print(f"[MemoryManager] Keeping {label} pinned in VRAM ({strategy}).")
        gc.collect()
        return pipeline

    return pipeline
