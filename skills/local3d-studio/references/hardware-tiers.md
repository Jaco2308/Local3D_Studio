# Dynamic Hardware Tiering & Profiles

Local3D Studio automatically maps your system's hardware to the optimal performance tier:

| Tier | Target Specs | 3D Engine Configuration | Remesh & Polygons |
| :--- | :--- | :--- | :--- |
| **TIER 1 ECO** | 16GB Unified RAM (Apple Silicon M-series) or PC VRAM ≤ 8GB | Hunyuan3D-2mini @ 320p, 25 inference steps | 80,000 triangles, strictly unloaded from RAM when idle |
| **TIER 2 BALANCED** | Mac 24-36GB Unified or PC 10-12GB VRAM & 32GB RAM | Hunyuan3D-2mini @ 320p, 25 inference steps | 65,000 triangles, cached in system RAM |
| **TIER 3 PRO 64GB** | ≥ 48GB System RAM + ≥ 15GB Dedicated VRAM (e.g. Ryzen 9800X3D + 64GB DDR5 + RX 9070 XT) | Hunyuan3D-2 Full (1.1B) @ 384p, 25 steps | 90,000 triangles, DDR5 hot-swap memory strategy |
| **TIER 4 ULTRA** | PC VRAM ≥ 22GB & RAM ≥ 64GB, or Mac ≥ 64GB Unified | Hunyuan3D-2 Full (1.1B) @ 512p, 35 steps | 120,000 triangles, permanent VRAM pin |

### Quality Mode Presets
Override dynamically via `set_quality_preset`:
- `fast_draft`: Rapid preview (192p octree, 12 steps, 30,000 tris).
- `auto`: System-optimal based on detected hardware tier.
- `ultra_production`: Maximum quality (Hunyuan Full 384p, 100,000 tris).
