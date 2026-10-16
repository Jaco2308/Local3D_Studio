"""
Local3D Studio 3D Compute Worker API
FastAPI service exposing heavy AI generation and headless Blender post-processing
over local loopback (localhost:8000) or local area network Wi-Fi (0.0.0.0:8000).

Features:
- Dark-Glassmorphism Three.js Web UI Overlay at / and /viewer
- Dynamic Hardware Tiering Telemetry
- Real-Time WebSocket Progress Pipeline (/ws/progress)
- Quality Mode Presets: Fast Draft (30k tris) | Auto Hardware Tier | Ultra Production (100k tris)
- 1-Click "Ricalcola in Ultra Production"
- Synchronized State API with MCP Server
"""

import os
import sys
import json
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List

# Ensure project root is in python path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from core.hardware_backend import HardwareManager
from core.config import OUTPUT_DIR, WORKER_HOST, WORKER_PORT, get_effective_3d_settings

from tools.prompt_enhancer import enhance_prompt_for_3d
from tools.rembg_engine import BackgroundRemovalEngine
from tools.neural_3d_engine import Neural3DEngine
from tools.blender_pipeline import BlenderPipeline
from frontend.web_viewer import generate_interactive_viewer

app = FastAPI(
    title="Local3D Studio 3D Compute Worker",
    description="Cross-platform local and LAN 3D generation worker with Dynamic Hardware Tiering & WebSocket progress",
    version="2.1.0"
)

# Enable CORS for local Studio web interface and LAN access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for directly streaming/downloading outputs
app.mount("/static/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output_static")


# ----------------------------------------------------------------------------
# Worker State & WebSocket Connection Manager
# ----------------------------------------------------------------------------

class WorkerStateManager:
    def __init__(self):
        self.quality_mode = "auto"  # "fast_draft", "auto", "ultra_production"
        self.art_style = "faithful_anatomical"
        self.current_image_path: Optional[str] = None
        self.current_glb_path: Optional[str] = None
        self.current_stl_path: Optional[str] = None
        self.current_3mf_path: Optional[str] = None
        self.current_sheet_path: Optional[str] = None
        self.current_mode_used: str = "auto"
        self.current_triangles: int = 0
        self.is_watertight: bool = True
        self.is_busy: bool = False
        self.progress: Dict[str, Any] = {
            "step": 0,
            "total": 3,
            "message": "Pronto",
            "percent": 0
        }
        self.active_websockets: List[WebSocket] = []
        self._recover_latest_assets()

    def _recover_latest_assets(self):
        try:
            if OUTPUT_DIR.exists():
                glbs = [p for p in OUTPUT_DIR.glob("*.glb") if not p.name.endswith("_raw.glb")]
                if glbs:
                    glbs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    self.current_glb_path = str(glbs[0])
                    base = glbs[0].stem
                    stl = OUTPUT_DIR / f"{base}.stl"
                    if stl.exists():
                        self.current_stl_path = str(stl)
                    threemf = OUTPUT_DIR / f"{base}.3mf"
                    if threemf.exists():
                        self.current_3mf_path = str(threemf)
                    sheet = OUTPUT_DIR / f"{base}_lookdev_sheet.png"
                    if sheet.exists():
                        self.current_sheet_path = str(sheet)
                imgs = [
                    p for p in OUTPUT_DIR.iterdir()
                    if p.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]
                    and not p.name.endswith("_lookdev_sheet.png")
                    and not p.name.endswith("_lookdev_sheet.jpg")
                ]
                if imgs:
                    imgs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    self.current_image_path = str(imgs[0])
        except Exception as e:
            print(f"[Worker] Asset recovery note: {e}")

    async def connect_ws(self, websocket: WebSocket):
        await websocket.accept()
        self.active_websockets.append(websocket)
        await websocket.send_text(json.dumps(self.progress))

    def disconnect_ws(self, websocket: WebSocket):
        if websocket in self.active_websockets:
            self.active_websockets.remove(websocket)

    async def broadcast_progress(self, step: int, total: int, message: str, percent: int, extra: Optional[Dict[str, Any]] = None):
        payload_dict = {
            "step": step,
            "total": total,
            "message": message,
            "percent": percent,
            **(extra or {})
        }
        self.progress = payload_dict
        payload_str = json.dumps(payload_dict)
        dead = []
        for ws in self.active_websockets:
            try:
                await ws.send_text(payload_str)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect_ws(ws)


state_mgr = WorkerStateManager()


def resolve_quality_preset_settings(preset: str = "auto") -> Dict[str, Any]:
    hw = HardwareManager.get_instance()
    preset = preset.lower().strip() if preset else "auto"

    if preset == "fast_draft":
        return {
            "preset": "fast_draft",
            "preset_label": "Fast Draft (8-10s | 30k tris)",
            "model_tier": "mini",
            "model_3d_id": "tencent/Hunyuan3D-2mini",
            "octree_resolution": 192,
            "inference_steps": 12,
            "voxel_size": 0.012,
            "smooth_iterations": 3,
            "smooth_factor": 0.35,
            "target_triangles": 30000,
            "memory_strategy": hw.tier_config.memory_strategy,
            "warning": None,
        }
    elif preset == "ultra_production":
        is_tier_1 = hw.tier_config.name == "TIER_1_ECO"
        if is_tier_1:
            model_tier = "mini"
            model_id = "tencent/Hunyuan3D-2mini"
            octree = 320
            steps = 28
            warning = "⚠️ Sistema a 16GB: Ultra Production utilizza Hunyuan3D-2mini spinto a 320p con remesh a 100k triangoli."
        else:
            model_tier = "full"
            model_id = "tencent/Hunyuan3D-2"
            octree = 384
            steps = 35
            warning = None

        return {
            "preset": "ultra_production",
            "preset_label": "Ultra Production (Hunyuan Full 384p | 100k tris)",
            "model_tier": model_tier,
            "model_3d_id": model_id,
            "octree_resolution": octree,
            "inference_steps": steps,
            "voxel_size": 0.0038,
            "smooth_iterations": 4,
            "smooth_factor": 0.25,
            "target_triangles": 100000,
            "memory_strategy": hw.tier_config.memory_strategy,
            "warning": warning,
        }
    else:  # "auto"
        eff = get_effective_3d_settings()
        return {
            "preset": "auto",
            "preset_label": f"Auto Hardware Tier ({hw.tier_config.label})",
            "model_tier": eff["model_tier"],
            "model_3d_id": eff["model_3d_id"],
            "octree_resolution": eff["octree_resolution"],
            "inference_steps": eff["inference_steps"],
            "voxel_size": eff["blender_voxel_size"],
            "smooth_iterations": 5,
            "smooth_factor": 0.35,
            "target_triangles": eff["target_triangles"],
            "memory_strategy": eff["memory_strategy"],
            "warning": None,
        }


# ----------------------------------------------------------------------------
# Pydantic Request Models
# ----------------------------------------------------------------------------

class PromptRequest(BaseModel):
    prompt: str
    mode: str = "3d_print"
    art_style: str = "faithful_anatomical"
    multiview: bool = True
    add_pedestal_base: bool = False


class ConceptRequest(BaseModel):
    prompt: str
    mode: str = "3d_print"
    art_style: str = "faithful_anatomical"
    multiview: bool = True
    add_pedestal_base: bool = False
    output_name: Optional[str] = "concept_latest"
    seed: Optional[int] = None


class QualityModeRequest(BaseModel):
    mode: Optional[str] = None
    quality_mode: Optional[str] = None


class ArtStyleRequest(BaseModel):
    art_style: str


class ImageTo3DRequest(BaseModel):
    image_path: str
    output_name: Optional[str] = "neural_raw"
    tier: Optional[str] = None
    octree_resolution: Optional[int] = None
    steps: Optional[int] = None
    caption: Optional[str] = "A highly detailed 3D model, watertight solid"
    seed: Optional[int] = None


class PostprocessRequest(BaseModel):
    input_glb_path: str
    target_height_mm: float = 100.0
    target_triangles: Optional[int] = None
    voxel_size: Optional[float] = None
    smooth_iterations: int = 5
    smooth_factor: float = 0.35
    add_pedestal: bool = False
    output_name: str = "production_model"


class PipelineRequest(BaseModel):
    image_path: str
    output_name: Optional[str] = "production_model"
    quality_preset: Optional[str] = None  # fast_draft, auto, ultra_production
    generation_strategy: Optional[str] = "auto"  # single_hero_34, multiview_turnaround, auto
    target_height_mm: float = 100.0
    add_pedestal: bool = False
    art_style: str = "faithful_anatomical"


class RetopoRequest(BaseModel):
    input_mesh_path: Optional[str] = None
    output_name: Optional[str] = "retopo_model"
    mode: str = "quad"  # "quad" or "tri"
    target_count: int = 10000


class BakeRequest(BaseModel):
    input_mesh_path: Optional[str] = None
    output_name: Optional[str] = "pbr_model"
    texture_resolution: int = 2048
    bake_normal: bool = True
    bake_ao: bool = True


class RecalculateRequest(BaseModel):
    quality_preset: str = "ultra_production"
    output_name: Optional[str] = None


# ----------------------------------------------------------------------------
# WebSocket Progress Endpoint
# ----------------------------------------------------------------------------

@app.websocket("/ws/progress")
async def websocket_progress(websocket: WebSocket):
    await state_mgr.connect_ws(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                parsed = json.loads(data)
                if "quality_mode" in parsed:
                    state_mgr.quality_mode = parsed["quality_mode"]
                    await state_mgr.broadcast_progress(
                        state_mgr.progress.get("step", 0),
                        3,
                        f"Modalità impostata a: {state_mgr.quality_mode}",
                        state_mgr.progress.get("percent", 0)
                    )
                if "art_style" in parsed:
                    state_mgr.art_style = parsed["art_style"]
                    print(f"[Worker] WebSocket Art Style synchronized to: {state_mgr.art_style}")
            except Exception:
                pass
    except WebSocketDisconnect:
        state_mgr.disconnect_ws(websocket)


# ----------------------------------------------------------------------------
# System & Diagnostics Endpoints
# ----------------------------------------------------------------------------

@app.get("/health")
def health_check():
    hw = HardwareManager.get_instance()
    return {
        "status": "online",
        "worker": "Local3D Studio 3D Compute Worker",
        "badge": hw.get_hardware_badge(),
        "device": hw.device_info["name"],
        "cpu": hw.cpu_name,
        "tier": hw.tier_config.name,
        "tier_label": hw.tier_config.label,
        "quality_mode": state_mgr.quality_mode,
        "art_style": state_mgr.art_style,
        "memory_strategy": hw.tier_config.memory_strategy,
        "blender_available": bool(hw.blender_path)
    }


@app.get("/api/hardware-status")
@app.get("/api/v1/hardware")
def api_hardware_status():
    hw = HardwareManager.get_instance()
    ram_gb = int(round(hw.memory_info["total_ram_gb"]))
    dev_name = hw.device_info.get("name", "GPU")
    vram_gb = int(round(hw.device_info.get("vram_gb", 0.0)))

    if hw.device_info.get("is_unified"):
        chip_summary = f"GPU: {dev_name} | {ram_gb}GB RAM Unificata [{hw.tier_config.label}]"
    else:
        vram_str = f"{vram_gb}GB" if vram_gb > 0 else ""
        chip_summary = f"GPU: {dev_name} {vram_str} | RAM: {ram_gb}GB [{hw.tier_config.label}]"

    curr_img = Path(state_mgr.current_image_path).name if state_mgr.current_image_path else ""

    return {
        "hardware_badge": hw.get_hardware_badge(),
        "chip_summary": chip_summary,
        "cpu": hw.cpu_name,
        "device": dev_name,
        "total_ram_gb": hw.memory_info["total_ram_gb"],
        "vram_gb": hw.device_info.get("vram_gb", 0.0),
        "tier": hw.tier_config.to_dict(),
        "quality_mode": state_mgr.quality_mode,
        "art_style": state_mgr.art_style,
        "current_mode_used": state_mgr.current_mode_used,
        "current_triangles": state_mgr.current_triangles,
        "current_image_filename": curr_img,
        "current_glb_filename": Path(state_mgr.current_glb_path).name if state_mgr.current_glb_path else "",
        "current_stl_filename": Path(state_mgr.current_stl_path).name if state_mgr.current_stl_path else "",
    }


@app.get("/api/v1/quality-mode")
def api_get_quality_mode():
    return {"quality_mode": state_mgr.quality_mode}


@app.post("/api/v1/quality-mode")
@app.post("/api/set-quality-mode")
async def api_set_quality_mode(req: QualityModeRequest):
    new_mode = (req.quality_mode or req.mode or "").strip().lower()
    if new_mode in ["fast_draft", "auto", "ultra_production"]:
        state_mgr.quality_mode = new_mode
        print(f"[Worker] Quality mode synchronized to: {new_mode}")
        return {"status": "success", "quality_mode": state_mgr.quality_mode}
    raise HTTPException(status_code=400, detail=f"Invalid quality mode: '{new_mode}'. Options: fast_draft, auto, ultra_production")


@app.get("/api/v1/art-style")
def api_get_art_style():
    return {"art_style": state_mgr.art_style}


@app.post("/api/v1/art-style")
@app.post("/api/set-art-style")
async def api_set_art_style(req: ArtStyleRequest):
    from tools.prompt_enhancer import SUPPORTED_ART_STYLES
    selected = req.art_style.strip().lower()
    if selected in SUPPORTED_ART_STYLES:
        state_mgr.art_style = selected
        print(f"[Worker] Art style synchronized to: {selected}")
        return {"status": "success", "art_style": state_mgr.art_style}
    raise HTTPException(status_code=400, detail=f"Invalid art style: '{selected}'. Options: {SUPPORTED_ART_STYLES}")


@app.get("/api/v1/state")
def api_get_full_state():
    return {
        "quality_mode": state_mgr.quality_mode,
        "art_style": state_mgr.art_style,
        "current_mode_used": state_mgr.current_mode_used,
        "current_image_path": state_mgr.current_image_path,
        "current_glb_path": state_mgr.current_glb_path,
        "current_stl_path": state_mgr.current_stl_path,
        "current_sheet_path": state_mgr.current_sheet_path,
        "current_triangles": state_mgr.current_triangles,
        "is_watertight": state_mgr.is_watertight,
        "is_busy": state_mgr.is_busy,
        "progress": state_mgr.progress
    }


# ----------------------------------------------------------------------------
# Core Pipeline & Recalculate Endpoints
# ----------------------------------------------------------------------------

@app.post("/api/v1/pipeline")
async def api_run_full_pipeline(req: PipelineRequest):
    if state_mgr.is_busy:
        raise HTTPException(status_code=429, detail="A 3D generation job is already in progress.")

    state_mgr.is_busy = True
    active_mode = req.quality_preset or state_mgr.quality_mode
    params = resolve_quality_preset_settings(active_mode)

    try:
        image_path = os.path.abspath(req.image_path)
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Source image not found: {image_path}")

        state_mgr.current_image_path = image_path
        state_mgr.current_mode_used = params["preset"]

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            clean_path = str(tmp_path / "clean_isolated.png")
            raw_glb = str(tmp_path / f"{req.output_name}_neural_raw.glb")
            viewer_html = str(tmp_path / f"{req.output_name}_viewer.html")

            # Step 1: Background Removal / Multiview Anti-Bleed Alignment in temp dir
            await state_mgr.broadcast_progress(
                step=1, total=3,
                message="1/3 Isolamento sagoma & Allineamento Multi-View...",
                percent=20
            )

            from PIL import Image
            from tools.multiview_aligner import MultiviewAligner

            strategy = (req.generation_strategy or "auto").lower().strip()
            is_multiview = False
            front_path = None
            left_path = None
            right_path = None
            back_path = None

            if strategy == "multiview_turnaround":
                is_multiview = True
            elif strategy == "single_hero_34":
                is_multiview = False
            else:  # auto
                try:
                    with Image.open(image_path) as test_im:
                        im_w, im_h = test_im.size
                        if im_w >= 1.25 * im_h:
                            is_multiview = True
                except Exception as e:
                    print(f"[Worker] Note reading image dimensions: {e}")

            if is_multiview:
                print("[Worker] Multi-View turnaround sheet mode active. Running MultiviewAligner (anti-bleed + Y-lock)...")
                align_res = MultiviewAligner.split_and_align_multiview(
                    concept_image_path=image_path,
                    output_dir=tmp_dir,
                    save_preview=False
                )
                front_path = align_res["front_path"]
                left_path = align_res["left_path"]
                right_path = align_res["right_path"]
                back_path = align_res["back_path"]
                clean_path = front_path
            else:
                left_path = right_path = back_path = None
                BackgroundRemovalEngine.remove_background(image_path, clean_path, replace_with_white=True)

            # Step 2: Neural 3D Shape Generation in temp dir
            strat_label = "Multi-View 4-Angle" if is_multiview else "Single-Hero (Meshy Style)"
            await state_mgr.broadcast_progress(
                step=2, total=3,
                message=f"2/3 Scultura Neurale 3D {strat_label} ({params['octree_resolution']}p - {params['model_tier'].upper()})...",
                percent=55
            )
            Neural3DEngine.generate_glb(
                image_path=clean_path,
                output_glb_path=raw_glb,
                tier=params["model_tier"],
                octree_resolution=params["octree_resolution"],
                num_inference_steps=params["inference_steps"],
                front_view_path=front_path,
                left_view_path=left_path,
                right_view_path=right_path,
                back_view_path=back_path,
                generation_strategy=strategy
            )

            # Step 3: Blender Post-Processing (Only final STL/GLB/Sheet saved to OUTPUT_DIR)
            await state_mgr.broadcast_progress(
                step=3, total=3,
                message=f"3/3 Blender High-Fidelity Boolean & Decimate ({params['target_triangles']:,} tris)...",
                percent=85
            )
            blender_res = BlenderPipeline.process_and_export(
                input_glb_path=raw_glb,
                target_height_mm=req.target_height_mm,
                target_triangles=params["target_triangles"],
                voxel_size=params["voxel_size"],
                smooth_iterations=params.get("smooth_iterations", 2),
                smooth_factor=params.get("smooth_factor", 0.20),
                add_pedestal=req.add_pedestal,
                output_name=req.output_name
            )

            stl_path = blender_res["stl_path"]
            glb_path = blender_res["glb_path"]
            threemf_path = blender_res.get("3mf_path")
            sheet_path = blender_res["lookdev_sheet_path"]

            state_mgr.current_glb_path = glb_path
            state_mgr.current_stl_path = stl_path
            state_mgr.current_3mf_path = threemf_path
            state_mgr.current_sheet_path = sheet_path
            state_mgr.current_triangles = blender_res.get("telemetry", {}).get("triangles", params["target_triangles"])

            stl_name = Path(stl_path).name
            glb_name = Path(glb_path).name
            threemf_name = Path(threemf_path).name if threemf_path else None
            sheet_name = Path(sheet_path).name

            generate_interactive_viewer(
                glb_path=glb_path,
                output_html_path=viewer_html,
                title=req.output_name.replace("_", " ").upper(),
                stl_path=stl_path,
                threemf_path=threemf_path,
                mode_used=params["preset"],
                image_path=image_path,
                art_style=req.art_style or state_mgr.art_style,
                embed_base64=False
            )

            final_extra = {
                "stl_url": f"/api/v1/files/{stl_name}",
                "3mf_url": f"/api/v1/files/{threemf_name}" if threemf_name else None,
                "glb_url": f"/api/v1/files/{glb_name}",
                "viewer_url": f"/viewer?model={glb_name}",
                "sheet_url": f"/api/v1/files/{sheet_name}",
                "triangles": state_mgr.current_triangles,
                "quality_mode": params["preset"]
            }

            await state_mgr.broadcast_progress(
                step=3, total=3,
                message=f"Completato! STL & 3MF ({state_mgr.current_triangles:,} tris) pronti per la stampa 3D.",
                percent=100,
                extra=final_extra
            )

        return {
            "status": "success",
            "quality_preset": params["preset"],
            "stl_path": stl_path,
            "glb_path": glb_path,
            "3mf_path": threemf_path,
            "lookdev_sheet_path": sheet_path,
            "viewer_html_path": viewer_html,
            "stl_download_url": final_extra["stl_url"],
            "3mf_download_url": final_extra.get("3mf_url"),
            "glb_download_url": final_extra["glb_url"],
            "telemetry": blender_res.get("telemetry", {}),
            "warning": params.get("warning")
        }
    finally:
        state_mgr.is_busy = False


@app.post("/api/v1/recalculate-production")
@app.post("/api/recalculate")
async def api_recalculate(req: RecalculateRequest):
    if not state_mgr.current_image_path or not os.path.exists(state_mgr.current_image_path):
        candidates = [
            p for p in OUTPUT_DIR.iterdir()
            if p.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]
            and not p.name.endswith("_lookdev_sheet.png")
            and not p.name.endswith("_lookdev_sheet.jpg")
        ]
        if candidates:
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            state_mgr.current_image_path = str(candidates[0])
        else:
            raise HTTPException(status_code=400, detail="Nessuna immagine 2D precedente trovata da ricalcolare.")

    out_name = req.output_name or f"{Path(state_mgr.current_image_path).stem}_ultra_100k"
    pipeline_req = PipelineRequest(
        image_path=state_mgr.current_image_path,
        output_name=out_name,
        quality_preset=req.quality_preset,
        target_height_mm=100.0,
        add_pedestal=False,
        art_style=state_mgr.art_style
    )
    return await api_run_full_pipeline(pipeline_req)


@app.post("/api/v1/direct-image-to-3d")
async def api_direct_image_to_3d(
    file: Optional[UploadFile] = File(None),
    image_path: Optional[str] = Form(None),
    output_name: Optional[str] = Form("direct_model"),
    quality_preset: Optional[str] = Form("auto"),
    generation_strategy: Optional[str] = Form("single_hero_34"),
    add_pedestal: bool = Form(False),
    target_height_mm: float = Form(100.0),
    art_style: Optional[str] = Form("faithful_anatomical")
):
    """
    Direct Image-to-3D endpoint (Meshy AI alternative):
    Accepts direct image upload or file path, bypassing 2D text-to-image concept phase.
    Supports 'single_hero_34' (Meshy Style) and 'multiview_turnaround' strategies.
    """
    target_path = None
    if file and file.filename:
        safe_filename = Path(file.filename).name
        dest_path = str(OUTPUT_DIR / safe_filename)
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        target_path = dest_path
    elif image_path:
        target_path = os.path.abspath(image_path)

    if not target_path or not os.path.exists(target_path):
        raise HTTPException(status_code=400, detail="Nessun file o percorso immagine valido fornito.")

    effective_out_name = output_name or f"{Path(target_path).stem}_3d"
    pipeline_req = PipelineRequest(
        image_path=target_path,
        output_name=effective_out_name,
        quality_preset=quality_preset or "auto",
        generation_strategy=generation_strategy or "single_hero_34",
        target_height_mm=target_height_mm,
        add_pedestal=add_pedestal,
        art_style=art_style or state_mgr.art_style
    )
    return await api_run_full_pipeline(pipeline_req)


@app.post("/api/v1/retopologize")
async def api_retopologize(req: RetopoRequest):
    """
    AI & Geometric Retopology endpoint:
    Remeshes an existing mesh to an all-quad manifold topology (Quadriflow) or decimate triangle budget.
    """
    mesh_path = req.input_mesh_path or state_mgr.current_glb_path or state_mgr.current_stl_path
    if not mesh_path or not os.path.exists(mesh_path):
        glbs = [p for p in OUTPUT_DIR.glob("*.glb") if not p.name.endswith("_raw.glb")]
        if glbs:
            glbs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            mesh_path = str(glbs[0])
        else:
            raise HTTPException(status_code=400, detail="Nessuna mesh trovata da sottoporre a retopology.")

    out_name = req.output_name or f"{Path(mesh_path).stem}_{req.mode}_{req.target_count}"

    await state_mgr.broadcast_progress(
        step=1, total=2,
        message=f"Retopology {req.mode.upper()} in corso (Target: {req.target_count:,})...",
        percent=40
    )

    try:
        res = BlenderPipeline.retopologize(
            input_mesh_path=mesh_path,
            output_name=out_name,
            mode=req.mode,
            target_count=req.target_count
        )
        stl_name = Path(res["stl_path"]).name
        glb_name = Path(res["glb_path"]).name
        threemf_name = Path(res["3mf_path"]).name if res.get("3mf_path") else None

        state_mgr.current_stl_path = res["stl_path"]
        state_mgr.current_glb_path = res["glb_path"]
        if res.get("3mf_path"):
            state_mgr.current_3mf_path = res["3mf_path"]
        state_mgr.current_triangles = res.get("telemetry", {}).get("triangles", req.target_count)

        res["stl_download_url"] = f"/api/v1/files/{stl_name}"
        res["glb_download_url"] = f"/api/v1/files/{glb_name}"
        res["viewer_url"] = f"/viewer?model={glb_name}"
        if threemf_name:
            res["3mf_download_url"] = f"/api/v1/files/{threemf_name}"

        await state_mgr.broadcast_progress(
            step=2, total=2,
            message=f"Retopology {req.mode.upper()} completata! ({state_mgr.current_triangles:,} tris / {res.get('telemetry',{}).get('quads',0):,} quads)",
            percent=100,
            extra={
                "stl_url": res["stl_download_url"],
                "glb_url": res["glb_download_url"],
                "viewer_url": res["viewer_url"],
                "triangles": state_mgr.current_triangles
            }
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/bake-textures")
async def api_bake_textures(req: BakeRequest):
    """
    PBR Texture Baking endpoint:
    Bakes normal maps and ambient occlusion maps in Blender Cycles and embeds them in the exported GLB.
    """
    mesh_path = req.input_mesh_path or state_mgr.current_glb_path or state_mgr.current_stl_path
    if not mesh_path or not os.path.exists(mesh_path):
        glbs = [p for p in OUTPUT_DIR.glob("*.glb") if not p.name.endswith("_raw.glb")]
        if glbs:
            glbs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            mesh_path = str(glbs[0])
        else:
            raise HTTPException(status_code=400, detail="Nessuna mesh trovata per il baking delle texture.")

    out_name = req.output_name or f"{Path(mesh_path).stem}_baked"

    await state_mgr.broadcast_progress(
        step=1, total=2,
        message=f"Baking texture PBR in Blender Cycles ({req.texture_resolution}x{req.texture_resolution})...",
        percent=45
    )

    try:
        res = BlenderPipeline.bake_pbr_textures(
            input_mesh_path=mesh_path,
            output_name=out_name,
            texture_resolution=req.texture_resolution,
            bake_normal=req.bake_normal,
            bake_ao=req.bake_ao
        )
        glb_name = Path(res["glb_path"]).name
        state_mgr.current_glb_path = res["glb_path"]

        res["glb_download_url"] = f"/api/v1/files/{glb_name}"
        res["viewer_url"] = f"/viewer?model={glb_name}"
        if res.get("normal_map_path"):
            res["normal_map_url"] = f"/api/v1/files/{Path(res['normal_map_path']).name}"
        if res.get("ao_map_path"):
            res["ao_map_url"] = f"/api/v1/files/{Path(res['ao_map_path']).name}"

        await state_mgr.broadcast_progress(
            step=2, total=2,
            message=f"PBR Texture Baking completato! Mappe generate a {req.texture_resolution}px.",
            percent=100,
            extra={
                "glb_url": res["glb_download_url"],
                "viewer_url": res["viewer_url"]
            }
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# ----------------------------------------------------------------------------
# Web Studio Three.js Viewers (/ and /viewer)
# ----------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
@app.get("/viewer", response_class=HTMLResponse)
def serve_viewer(model: Optional[str] = None):
    target_glb = None
    if model:
        safe_model = Path(model).name
        candidate = (OUTPUT_DIR / safe_model).resolve()
        if candidate.is_relative_to(OUTPUT_DIR.resolve()) and candidate.exists() and candidate.suffix.lower() in [".glb", ".gltf"]:
            target_glb = str(candidate)

    if not target_glb:
        if state_mgr.current_glb_path and os.path.exists(state_mgr.current_glb_path):
            target_glb = state_mgr.current_glb_path
        else:
            glbs = list(OUTPUT_DIR.glob("*.glb"))
            if not glbs:
                from core.config import PROJECT_ROOT
                assets_dir = PROJECT_ROOT / "assets"
                if assets_dir.exists():
                    glbs = list(assets_dir.glob("*.glb"))
            if glbs:
                glbs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                target_glb = str(glbs[0])

    if not target_glb or not os.path.exists(target_glb):
        return HTMLResponse(content="""
        <html><body style="background:#090d16;color:#38bdf8;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;">
        <h2>Local3D Studio: Nessun modello .glb generato ancora. Avvia una pipeline dal server MCP o carica un'immagine!</h2>
        </body></html>
        """)

    base_name = Path(target_glb).stem
    res = generate_interactive_viewer(
        glb_path=target_glb,
        output_html_path=None,
        title=base_name.replace("_", " ").upper(),
        stl_path=state_mgr.current_stl_path,
        threemf_path=state_mgr.current_3mf_path,
        mode_used=state_mgr.current_mode_used,
        image_path=state_mgr.current_image_path,
        art_style=state_mgr.art_style,
        embed_base64=False
    )
    return HTMLResponse(content=res["html_content"])


# ----------------------------------------------------------------------------
# Standard Engine Endpoints (Individual Steps)
# ----------------------------------------------------------------------------

@app.post("/api/v1/enhance-prompt")
def api_enhance_prompt(req: PromptRequest):
    style = req.art_style or state_mgr.art_style
    enhanced = enhance_prompt_for_3d(
        user_prompt=req.prompt,
        mode=req.mode,
        art_style=style,
        multiview=req.multiview,
        add_pedestal_base=req.add_pedestal_base
    )
    return {
        "original_prompt": req.prompt,
        "enhanced_prompt": enhanced,
        "mode": req.mode,
        "art_style": style,
        "multiview": req.multiview,
        "add_pedestal_base": req.add_pedestal_base
    }


@app.post("/api/v1/generate-concept")
def api_generate_concept(req: ConceptRequest):
    return {
        "status": "info",
        "message": "Local 2D concept generation has been decoupled to the AI client visual generator or direct image upload, dedicating 100% of system RAM/VRAM to 3D neural reconstruction and manufacturing.",
        "recommended_flow": "Use compile_3d_master_prompt -> Native 2D concept -> direct_image_to_3d"
    }


@app.post("/api/v1/upload-image")
async def api_upload_image(file: UploadFile = File(...)):
    try:
        safe_name = Path(file.filename).name
        dest_path = str(OUTPUT_DIR / safe_name)
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        state_mgr.current_image_path = dest_path
        return {"status": "success", "file_path": dest_path, "filename": safe_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/remove-background")
def api_remove_background(image_path: str = Form(...)):
    try:
        clean_path = BackgroundRemovalEngine.remove_background(image_path, replace_with_white=True)
        filename = Path(clean_path).name
        return {
            "status": "success",
            "clean_image_path": clean_path,
            "filename": filename,
            "download_url": f"/api/v1/files/{filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/image-to-3d")
def api_image_to_3d(req: ImageTo3DRequest):
    try:
        out_glb = str(OUTPUT_DIR / f"{req.output_name}.glb")
        glb_result = Neural3DEngine.generate_glb(
            image_path=req.image_path,
            output_glb_path=out_glb,
            tier=req.tier,
            octree_resolution=req.octree_resolution,
            num_inference_steps=req.steps,
            caption=req.caption,
            seed=req.seed
        )
        state_mgr.current_glb_path = glb_result
        filename = Path(glb_result).name
        return {
            "status": "success",
            "glb_path": glb_result,
            "filename": filename,
            "download_url": f"/api/v1/files/{filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/postprocess")
def api_postprocess(req: PostprocessRequest):
    try:
        res = BlenderPipeline.process_and_export(
            input_glb_path=req.input_glb_path,
            target_height_mm=req.target_height_mm,
            target_triangles=req.target_triangles,
            voxel_size=req.voxel_size,
            smooth_iterations=req.smooth_iterations,
            smooth_factor=req.smooth_factor,
            add_pedestal=req.add_pedestal,
            output_name=req.output_name
        )
        stl_name = Path(res["stl_path"]).name
        glb_name = Path(res["glb_path"]).name
        sheet_name = Path(res["lookdev_sheet_path"]).name

        state_mgr.current_stl_path = res["stl_path"]
        state_mgr.current_glb_path = res["glb_path"]
        state_mgr.current_sheet_path = res["lookdev_sheet_path"]

        res["stl_download_url"] = f"/api/v1/files/{stl_name}"
        res["glb_download_url"] = f"/api/v1/files/{glb_name}"
        res["lookdev_download_url"] = f"/api/v1/files/{sheet_name}"
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/files/{filename}")
def api_download_file(filename: str):
    safe_name = Path(filename).name
    file_path = (OUTPUT_DIR / safe_name).resolve()
    if not file_path.is_relative_to(OUTPUT_DIR.resolve()) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=str(file_path), filename=safe_name)


def start_worker(host: str = WORKER_HOST, port: int = WORKER_PORT):
    """Entry point to launch worker with uvicorn."""
    import uvicorn
    hw = HardwareManager.get_instance()
    print("=" * 80)
    print(hw.get_hardware_badge())
    print(f"Memory Strategy: {hw.tier_config.memory_strategy}")
    print(f"3D Model: {hw.tier_config.model_3d_id} @ {hw.tier_config.octree_resolution}p (steps={hw.tier_config.inference_steps})")
    print(f"Blender Remesh: voxel={hw.tier_config.blender_voxel_size}, triangles={hw.tier_config.target_triangles:,}")
    print(f"Web Studio UI: http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}/")
    print("=" * 80)
    print(f"[Worker] Starting Local3D Studio 3D Compute Worker on {host}:{port}...")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_worker()
