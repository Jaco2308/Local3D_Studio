"""
Local3D Studio Hardware & OS Auto-Detection Module with Dynamic Hardware Tiering.
Automatically discovers Blender, detects CPU, GPU, VRAM and system RAM,
and selects the optimal Performance Tier (TIER 1 ECO, TIER 2 BALANCED,
TIER 3 PRO 64GB, TIER 4 ULTRA).
"""

import os
import sys
import glob
import shutil
import platform
import subprocess
import psutil
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

try:
    import torch
except ImportError:
    torch = None


@dataclass
class PerformanceTierConfig:
    name: str                   # "TIER_1_ECO", "TIER_2_BALANCED", "TIER_3_PRO_64GB", "TIER_4_ULTRA"
    label: str                  # Short display label: "TIER 1 ECO", "TIER 2 BALANCED", "TIER 3 PRO", "TIER 4 ULTRA"
    display_badge_name: str     # Badge label with details
    model_2d_desc: str          # Description of 2D model
    model_3d_id: str            # HuggingFace repo for 3D model
    model_tier: str             # "mini" or "full"
    octree_resolution: int      # 256, 320, 384, 512
    inference_steps: int        # 18, 25, 30, 35
    blender_voxel_size: float   # 0.0085, 0.0060, 0.0042, 0.0035
    target_triangles: int       # 50000, 65000, 90000, 120000
    memory_strategy: str        # "STRICT_DISK_UNLOAD", "SINGLE_RAM_CACHE", "DDR5_HOT_SWAP", "VRAM_PINNED"
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Predefined Performance Tier Catalog
TIER_CATALOG: Dict[str, PerformanceTierConfig] = {
    "TIER_1_ECO": PerformanceTierConfig(
        name="TIER_1_ECO",
        label="TIER 1 ECO",
        display_badge_name="TIER 1 ECO (Hunyuan3D-2 @ 320p - 80k tris - High Fidelity)",
        model_2d_desc="Client AI Native / User Photo (0 MB Local VRAM - 100% RAM to 3D)",
        model_3d_id="tencent/Hunyuan3D-2mini",
        model_tier="mini",
        octree_resolution=320,
        inference_steps=25,
        blender_voxel_size=0.0025,
        target_triangles=80000,
        memory_strategy="STRICT_DISK_UNLOAD",
        description="16GB Unified RAM (e.g. Apple M4 16GB) or PC VRAM <= 8GB: High-fidelity 320p octree, 25 steps, ultra-fine detail preservation (80k tris)."
    ),
    "TIER_2_BALANCED": PerformanceTierConfig(
        name="TIER_2_BALANCED",
        label="TIER 2 BALANCED",
        display_badge_name="TIER 2 BALANCED (Hunyuan3D-2mini @ 320p - 65k tris)",
        model_2d_desc="Client AI Native / User Photo (0 MB Local VRAM - 100% RAM to 3D)",
        model_3d_id="tencent/Hunyuan3D-2mini",
        model_tier="mini",
        octree_resolution=320,
        inference_steps=25,
        blender_voxel_size=0.0060,
        target_triangles=65000,
        memory_strategy="SINGLE_RAM_CACHE",
        description="Mac 24-36GB or PC with 10-12GB VRAM & 32GB RAM: Hunyuan3D-2mini cached in system RAM, 320p octree resolution."
    ),
    "TIER_3_PRO_64GB": PerformanceTierConfig(
        name="TIER_3_PRO_64GB",
        label="TIER 3 PRO",
        display_badge_name="TIER 3 PRO (Hunyuan3D-2 Full @ 384p - 90k tris)",
        model_2d_desc="Client AI Native / User Photo (0 MB Local VRAM - 100% RAM to 3D)",
        model_3d_id="tencent/Hunyuan3D-2",
        model_tier="full",
        octree_resolution=384,
        inference_steps=25,
        blender_voxel_size=0.0025,
        target_triangles=90000,
        memory_strategy="DDR5_HOT_SWAP",
        description=">= 48GB System RAM + >= 15GB VRAM (e.g. Ryzen 9800X3D + 64GB DDR5 + RX 9070 XT 16GB): Hunyuan3D-2 Full 1.1B, DDR5 hot-swap (0.3s GPU upload), micro-detail remesh."
    ),
    "TIER_4_ULTRA": PerformanceTierConfig(
        name="TIER_4_ULTRA",
        label="TIER 4 ULTRA",
        display_badge_name="TIER 4 ULTRA (Hunyuan3D-2 Full @ 512p - 120k tris)",
        model_2d_desc="High Quality 2D (float16/bfloat16)",
        model_3d_id="tencent/Hunyuan3D-2",
        model_tier="full",
        octree_resolution=512,
        inference_steps=35,
        blender_voxel_size=0.0035,
        target_triangles=120000,
        memory_strategy="VRAM_PINNED",
        description="PC with VRAM >= 22GB & RAM >= 64GB, or Mac >= 64GB Unified: Models permanently pinned in VRAM, 512p octree, ultra-high triangle density."
    ),
}

TIER_ALIASES = {
    "TIER_1": "TIER_1_ECO",
    "TIER1": "TIER_1_ECO",
    "ECO": "TIER_1_ECO",
    "1": "TIER_1_ECO",
    "TIER_2": "TIER_2_BALANCED",
    "TIER2": "TIER_2_BALANCED",
    "BALANCED": "TIER_2_BALANCED",
    "2": "TIER_2_BALANCED",
    "TIER_3": "TIER_3_PRO_64GB",
    "TIER3": "TIER_3_PRO_64GB",
    "PRO": "TIER_3_PRO_64GB",
    "3": "TIER_3_PRO_64GB",
    "TIER_4": "TIER_4_ULTRA",
    "TIER4": "TIER_4_ULTRA",
    "ULTRA": "TIER_4_ULTRA",
    "4": "TIER_4_ULTRA",
}


class HardwareManager:
    _instance: Optional["HardwareManager"] = None

    def __init__(self):
        self.os_type = platform.system()  # 'Darwin', 'Windows', 'Linux'
        self.architecture = platform.machine().lower()
        self.cpu_name = self._detect_cpu_model()
        self.blender_path = self._detect_blender_path()
        self.device_info = self._detect_ai_device()
        self.memory_info = self._detect_memory_profile()
        self.tier_config = self.detect_performance_tier()
        self.hardware_badge = self.generate_hardware_badge()

    @classmethod
    def get_instance(cls) -> "HardwareManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _detect_cpu_model(self) -> str:
        """Extracts readable brand/model name of the CPU across OSes."""
        if self.os_type == "Darwin":
            try:
                res = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True, stderr=subprocess.DEVNULL).strip()
                if res:
                    return res
            except Exception:
                pass
            return f"Apple Silicon ({self.architecture.upper()})"
        elif self.os_type == "Linux":
            try:
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if "model name" in line:
                            return line.split(":", 1)[1].strip()
            except Exception:
                pass
        elif self.os_type == "Windows":
            try:
                # Query WMIC or PowerShell
                res = subprocess.check_output(["wmic", "cpu", "get", "name"], text=True, stderr=subprocess.DEVNULL)
                lines = [l.strip() for l in res.splitlines() if l.strip() and "name" not in l.lower()]
                if lines:
                    return lines[0]
            except Exception:
                pass
        return platform.processor() or "Host Multicore CPU"

    def _detect_blender_path(self) -> str:
        """Finds Blender executable across Windows, macOS, and Linux with .env override."""
        env_path = os.getenv("BLENDER_PATH")
        if env_path and os.path.isfile(env_path) and os.access(env_path, os.X_OK):
            return env_path

        candidates = []
        if self.os_type == "Darwin":
            candidates = [
                "/Applications/Blender.app/Contents/MacOS/Blender",
                os.path.expanduser("~/Applications/Blender.app/Contents/MacOS/Blender"),
            ]
            candidates.extend(glob.glob("/Applications/Blender*.app/Contents/MacOS/Blender"))
        elif self.os_type == "Windows":
            candidates = [
                r"C:\Program Files\Blender Foundation\Blender\blender.exe",
            ]
            candidates.extend(glob.glob(r"C:\Program Files\Blender Foundation\Blender *\blender.exe"))
            candidates.extend(glob.glob(r"C:\Program Files (x86)\Blender Foundation\Blender *\blender.exe"))
            candidates.extend(glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Blender Foundation\*\blender.exe")))
        elif self.os_type == "Linux":
            candidates = [
                "/usr/bin/blender",
                "/usr/local/bin/blender",
                "/opt/blender/blender",
                "/var/lib/flatpak/exports/bin/org.blender.Blender",
                os.path.expanduser("~/.local/share/flatpak/exports/bin/org.blender.Blender"),
                "/snap/bin/blender",
            ]

        for c in candidates:
            if os.path.isfile(c) and os.access(c, os.X_OK):
                return c

        which_path = shutil.which("blender")
        if which_path and os.path.isfile(which_path):
            return which_path

        return ""

    def _detect_ai_device(self) -> Dict[str, Any]:
        """
        Determines the optimal hardware backend:
        - NVIDIA CUDA (with SDPA attention and float16)
        - AMD ROCm/HIP (with SDPA attention and float16, zero proprietary CUDA dependencies)
        - Apple Silicon MPS (with MPS fallback enabled and float16)
        - Windows AMD DirectML (torch-directml)
        - Multicore CPU fallback
        """
        if torch is None:
            return {
                "device": "cpu",
                "vendor": "unknown_no_torch",
                "name": "CPU (PyTorch not installed)",
                "torch_dtype": "float32",
                "attn_implementation": "eager",
                "vram_gb": 0.0,
                "is_unified": False,
            }

        # 1. CUDA or AMD ROCm
        if torch.cuda.is_available():
            is_hip = hasattr(torch.version, "hip") and torch.version.hip is not None
            vendor = "amd_rocm" if is_hip else "nvidia"
            device_name = torch.cuda.get_device_name(0)
            try:
                vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024 ** 3), 1)
            except Exception:
                vram_gb = 0.0

            return {
                "device": "cuda",
                "device_id": 0,
                "vendor": vendor,
                "name": device_name,
                "is_rocm": is_hip,
                "is_unified": False,
                "torch_dtype": "float16",
                "attn_implementation": "sdpa",
                "vram_gb": vram_gb,
            }

        # 2. Apple Silicon (MPS)
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
            unified_ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
            return {
                "device": "mps",
                "vendor": "apple_silicon",
                "name": f"Apple Silicon ({self.architecture.upper()}) Unified GPU",
                "is_rocm": False,
                "is_unified": True,
                "torch_dtype": "float16",
                "attn_implementation": "sdpa",
                "vram_gb": unified_ram_gb,
            }

        # 3. Windows AMD DirectML fallback (if torch_directml installed)
        try:
            import torch_directml
            dml_device = torch_directml.device()
            return {
                "device": dml_device,
                "vendor": "amd_directml",
                "name": "DirectML Accelerated Device (AMD / Intel)",
                "is_rocm": False,
                "is_unified": False,
                "torch_dtype": "float16",
                "attn_implementation": "eager",
                "vram_gb": 0.0,
            }
        except ImportError:
            pass

        # 4. Multicore CPU Fallback
        cpu_count = os.cpu_count() or 4
        torch.set_num_threads(max(1, cpu_count - 1))
        return {
            "device": "cpu",
            "vendor": "cpu",
            "name": f"Host CPU ({platform.processor() or 'Multicore'})",
            "is_rocm": False,
            "is_unified": False,
            "torch_dtype": "float32",
            "attn_implementation": "eager",
            "vram_gb": 0.0,
        }

    def _detect_memory_profile(self) -> Dict[str, Any]:
        """Calculates system RAM capacity and availability."""
        vm = psutil.virtual_memory()
        total_ram_gb = round(vm.total / (1024 ** 3), 1)
        available_ram_gb = round(vm.available / (1024 ** 3), 1)

        return {
            "total_ram_gb": total_ram_gb,
            "available_ram_gb": available_ram_gb,
            "is_16gb_constrained": total_ram_gb <= 16.5,
        }

    def detect_performance_tier(self) -> PerformanceTierConfig:
        """
        Dynamically analyzes system RAM and GPU VRAM to select the optimal tier.
        Supports manual override via FORCE_TIER in .env.
        """
        # 1. Check for manual override in .env
        forced_tier = os.getenv("FORCE_TIER", "").upper().strip()
        if forced_tier and forced_tier != "AUTO":
            mapped_key = TIER_ALIASES.get(forced_tier, forced_tier)
            if mapped_key in TIER_CATALOG:
                tier = TIER_CATALOG[mapped_key]
                print(f"[HardwareManager] Manual override active: FORCE_TIER={tier.name}", file=sys.stderr)
                return tier
            else:
                print(f"[HardwareManager] Warning: Unknown FORCE_TIER='{forced_tier}'. Falling back to auto-detection.", file=sys.stderr)

        # 2. Automated Hardware Assessment
        ram_gb = self.memory_info["total_ram_gb"]
        vram_gb = self.device_info.get("vram_gb", 0.0)
        is_unified = self.device_info.get("is_unified", False)

        # Profile 4: ULTRA
        # - PC: VRAM >= 22GB + RAM >= 60GB
        # - Mac: Unified RAM >= 64GB
        if (is_unified and ram_gb >= 62.0) or (not is_unified and vram_gb >= 22.0 and ram_gb >= 60.0):
            return TIER_CATALOG["TIER_4_ULTRA"]

        # Profile 3: PRO 64GB (The User Desktop: Ryzen 9800X3D + 64GB DDR5 + RX 9070 XT 16GB)
        # - PC: RAM >= 46GB + Dedicated VRAM >= 14.5GB
        if not is_unified and ram_gb >= 46.0 and vram_gb >= 14.5:
            return TIER_CATALOG["TIER_3_PRO_64GB"]

        # Profile 2: BALANCED
        # - Mac: 22GB <= Unified RAM < 62GB (e.g. M-series 24GB, 36GB, 48GB)
        # - PC: (VRAM >= 9.5GB and RAM >= 28GB) or VRAM >= 11.5GB
        if is_unified and 22.0 <= ram_gb < 62.0:
            return TIER_CATALOG["TIER_2_BALANCED"]
        if not is_unified and ((vram_gb >= 9.5 and ram_gb >= 28.0) or vram_gb >= 11.5):
            return TIER_CATALOG["TIER_2_BALANCED"]

        # Profile 1: ECO (Default for 16GB Unified Mac or PC VRAM <= 8GB / RAM <= 16GB)
        return TIER_CATALOG["TIER_1_ECO"]

    def generate_hardware_badge(self) -> str:
        """
        Builds a human-readable telemetry badge for logs and Web UI.
        Example:
        🚀 Hardware: AMD Ryzen 7 9800X3D | 64GB RAM | AMD Radeon RX 9070 XT 16GB -> Profilo Attivo: TIER 3 PRO (Hunyuan3D-2 Full @ 384p - 90k tris)
        """
        ram_gb = int(round(self.memory_info["total_ram_gb"]))
        is_unified = self.device_info.get("is_unified", False)
        
        if is_unified:
            ram_str = f"{ram_gb}GB RAM Unificata"
            gpu_str = "Apple Silicon GPU"
        else:
            ram_str = f"{ram_gb}GB RAM"
            vram_gb = int(round(self.device_info.get("vram_gb", 0.0)))
            dev_name = self.device_info.get("name", "GPU")
            gpu_str = f"{dev_name} {vram_gb}GB" if vram_gb > 0 else dev_name

        badge = (
            f"🚀 Hardware: {self.cpu_name} | {ram_str} | {gpu_str} -> "
            f"Profilo Attivo: {self.tier_config.display_badge_name}"
        )
        return badge

    def get_hardware_badge(self) -> str:
        """Returns the cached hardware badge string."""
        return self.hardware_badge

    def get_summary(self) -> Dict[str, Any]:
        """Returns a comprehensive diagnostic dictionary of the hardware environment."""
        return {
            "badge": self.hardware_badge,
            "os": {
                "system": self.os_type,
                "architecture": self.architecture,
                "release": platform.release(),
            },
            "cpu": {
                "name": self.cpu_name,
                "cores_logical": os.cpu_count() or 4,
            },
            "blender": {
                "available": bool(self.blender_path),
                "path": self.blender_path or "NOT_FOUND",
            },
            "ai_accelerator": self.device_info,
            "memory": self.memory_info,
            "tier": self.tier_config.to_dict(),
        }

    def get_torch_device(self):
        """Returns the actual PyTorch device object or string."""
        dev = self.device_info.get("device", "cpu")
        if isinstance(dev, str):
            return torch.device(dev)
        return dev

    def get_torch_dtype(self):
        """Returns the recommended torch dtype (float16 vs float32)."""
        dt_str = self.device_info.get("torch_dtype", "float32")
        if torch is None:
            return None
        return torch.float16 if dt_str == "float16" else torch.float32

    def is_16gb_safe(self) -> bool:
        """Returns True if the engine must run in strict 16GB memory safety mode."""
        return self.tier_config.name == "TIER_1_ECO"
