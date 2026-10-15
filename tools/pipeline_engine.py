"""
Local3D Studio Local Pipeline Engine (Pure In-Process Execution)
Executes end-to-end 3D generation, retopology, and PBR baking locally in Python
with ZERO reliance on external HTTP servers, localhost ports, or background daemons.
"""

import os
import json
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from PIL import Image

from core.config import OUTPUT_DIR, get_effective_3d_settings
from core.hardware_backend import HardwareManager
from tools.neural_3d_engine import Neural3DEngine
from tools.blender_pipeline import BlenderPipeline
from tools.rembg_engine import BackgroundRemovalEngine
from tools.multiview_aligner import MultiviewAligner

STATE_FILE = OUTPUT_DIR / ".state_gate.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {
        "concept_path": None,
        "approved": False,
        "subject": None,
        "quality_mode": "auto",
        "latest_model": None
    }


def save_state(state: dict):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"[PipelineEngine] Warning saving state: {e}")


def resolve_quality_preset_settings(preset: str = "auto") -> Dict[str, Any]:
    hw = HardwareManager.get_instance()
    p = preset.lower().strip()
    tier_cfg = hw.tier_config

    if p == "fast_draft":
        return {
            "preset": "fast_draft",
            "model_tier": "mini",
            "octree_resolution": 192,
            "inference_steps": 12,
            "voxel_size": 0.0075,
            "target_triangles": 30000,
            "smooth_iterations": 1,
            "smooth_factor": 0.15,
            "warning": None
        }
    elif p == "ultra_production":
        return {
            "preset": "ultra_production",
            "model_tier": "full",
            "octree_resolution": 384,
            "inference_steps": 30,
            "voxel_size": 0.0038,
            "target_triangles": 100000,
            "smooth_iterations": 2,
            "smooth_factor": 0.20,
            "warning": None
        }
    else:  # auto
        eff = get_effective_3d_settings()
        return {
            "preset": "auto",
            "model_tier": eff.get("model_tier", tier_cfg.model_tier),
            "octree_resolution": eff.get("octree_resolution", tier_cfg.octree_resolution),
            "inference_steps": eff.get("inference_steps", tier_cfg.inference_steps),
            "voxel_size": eff.get("blender_voxel_size", tier_cfg.blender_voxel_size),
            "target_triangles": eff.get("target_triangles", tier_cfg.target_triangles),
            "smooth_iterations": 2,
            "smooth_factor": 0.20,
            "warning": None
        }


class PipelineEngine:
    """
    Central local execution engine for Local3D Studio MCP Server.
    Provides direct in-process calls for 3D reconstruction, retopology, and PBR baking.
    """

    @classmethod
    def get_quality_mode(cls) -> str:
        state = load_state()
        return state.get("quality_mode", "auto")

    @classmethod
    def set_quality_mode(cls, mode: str) -> bool:
        mode = mode.lower().strip()
        if mode in ["fast_draft", "auto", "ultra_production"]:
            state = load_state()
            state["quality_mode"] = mode
            save_state(state)
            return True
        return False

    @classmethod
    def run_pipeline(
        cls,
        image_path: str,
        output_name: str = "production_model",
        quality_preset: str = "auto",
        generation_strategy: str = "auto",
        target_height_mm: float = 100.0,
        add_pedestal: bool = False,
        art_style: str = "faithful_anatomical",
        target_triangles: Optional[int] = None,
        voxel_size: Optional[float] = None,
        auto_split: bool = False
    ) -> Dict[str, Any]:
        """
        Executes end-to-end 3D reconstruction locally:
        1. Multi-view or single-view background isolation.
        2. Neural 3D generation (Hunyuan3D-2 / Hunyuan3D-2mv).
        3. Blender high-detail decimation, watertight enforcement & LookDev render.
        4. Native 3MF generation for Bambu / OrcaSlicer.
        """
        image_path = os.path.abspath(image_path)
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Source image not found: {image_path}")

        active_mode = quality_preset or cls.get_quality_mode()
        params = resolve_quality_preset_settings(active_mode)
        if target_triangles is not None:
            params["target_triangles"] = int(target_triangles)
            if target_triangles > 100000 and voxel_size is None:
                params["voxel_size"] = min(params["voxel_size"], 0.0018)
        if voxel_size is not None:
            params["voxel_size"] = float(voxel_size)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            clean_path = str(tmp_path / "clean_isolated.png")
            raw_glb = str(tmp_path / f"{output_name}_neural_raw.glb")

            # Strategy detection
            strategy = (generation_strategy or "auto").lower().strip()
            is_multiview = False
            front_path = None
            side_path = None
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
                    print(f"[PipelineEngine] Note inspecting image: {e}")

            if is_multiview:
                print(f"[PipelineEngine] Multi-View turnaround active. Running MultiviewAligner (4 views + CLAHE)...")
                align_res = MultiviewAligner.split_and_align_multiview(
                    concept_image_path=image_path,
                    output_dir=tmp_dir,
                    save_preview=False
                )
                front_path = align_res["front_path"]
                side_path = align_res["left_path"]
                right_path = align_res["right_path"]
                back_path = align_res["back_path"]
                clean_path = front_path
            else:
                print(f"[PipelineEngine] Single hero 3/4 view active. Running clean_and_calibrate_hero_image (rembg + CLAHE + Z=0 ground lock)...")
                MultiviewAligner.clean_and_calibrate_hero_image(
                    image_path=image_path,
                    output_path=clean_path
                )

            # Neural 3D generation
            clean_title = output_name.replace("_", " ")
            print(f"[PipelineEngine] Generating neural mesh (octree={params['octree_resolution']}, steps={params['inference_steps']})...")
            Neural3DEngine.generate_glb(
                image_path=clean_path,
                output_glb_path=raw_glb,
                tier=params["model_tier"],
                octree_resolution=params["octree_resolution"],
                num_inference_steps=params["inference_steps"],
                caption=f"A highly detailed 3D sculpt of {clean_title}, watertight solid",
                front_view_path=front_path,
                left_view_path=side_path,
                right_view_path=right_path,
                back_view_path=back_path,
                generation_strategy=strategy
            )

            # Blender high-fidelity manufacturing
            print(f"[PipelineEngine] Blender post-processing ({params['target_triangles']:,} triangles)...")
            blender_res = BlenderPipeline.process_and_export(
                input_glb_path=raw_glb,
                target_height_mm=target_height_mm,
                target_triangles=params["target_triangles"],
                voxel_size=params["voxel_size"],
                smooth_iterations=params.get("smooth_iterations", 2),
                smooth_factor=params.get("smooth_factor", 0.20),
                add_pedestal=add_pedestal,
                output_name=output_name
            )

            stl_path = blender_res["stl_path"]
            glb_path = blender_res["glb_path"]
            threemf_path = blender_res.get("3mf_path")
            sheet_path = blender_res["lookdev_sheet_path"]

            # Save state
            st = load_state()
            st["latest_model"] = {
                "stl_path": stl_path,
                "glb_path": glb_path,
                "3mf_path": threemf_path,
                "lookdev_sheet_path": sheet_path
            }
            save_state(st)

            res = {
                "status": "success",
                "execution_mode": "pure_local",
                "quality_preset": params["preset"],
                "stl_path": stl_path,
                "stl_uri": f"file://{stl_path}",
                "glb_path": glb_path,
                "glb_uri": f"file://{glb_path}",
                "3mf_path": threemf_path,
                "3mf_uri": f"file://{threemf_path}" if threemf_path else None,
                "lookdev_sheet_path": sheet_path,
                "lookdev_sheet_uri": f"file://{sheet_path}",
                "telemetry": blender_res.get("telemetry", {}),
                "warning": params.get("warning")
            }

            if auto_split:
                print(f"[PipelineEngine] Auto-Split enabled. Decomposing model into keyed watertight parts...")
                from tools.model_splitter import ModelSplitter
                split_res = ModelSplitter.split_model(
                    input_mesh_path=stl_path,
                    output_filename=output_name,
                    output_dir=str(OUTPUT_DIR),
                    subject_category="auto",
                    add_connectors=True
                )
                res["auto_split"] = split_res

            return res

    @classmethod
    def recalculate(
        cls,
        quality_preset: str = "ultra_production",
        output_name: str = "recalculated_ultra_100k"
    ) -> Dict[str, Any]:
        """Reruns 3D generation on the latest concept image in ultra production mode."""
        st = load_state()
        concept_path = st.get("concept_path")
        if not concept_path or not os.path.exists(concept_path):
            candidates = [p for p in OUTPUT_DIR.glob("*concept*.png")] + [p for p in OUTPUT_DIR.glob("*concept*.jpg")]
            if candidates:
                candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                concept_path = str(candidates[0])
            else:
                raise FileNotFoundError("No approved concept image found for recalculation.")

        return cls.run_pipeline(
            image_path=concept_path,
            output_name=output_name,
            quality_preset=quality_preset
        )

    @classmethod
    def retopologize(
        cls,
        input_mesh_path: Optional[str] = None,
        output_name: str = "retopo_model",
        mode: str = "quad",
        target_count: int = 10000
    ) -> Dict[str, Any]:
        """Runs Quadriflow (All-Quad) or Decimate (Triangles) locally in Blender."""
        target_path = input_mesh_path
        if not target_path or not os.path.exists(target_path):
            st = load_state()
            latest = st.get("latest_model", {})
            target_path = latest.get("glb_path") or latest.get("stl_path")
            if not target_path or not os.path.exists(target_path):
                glbs = [p for p in OUTPUT_DIR.glob("*.glb") if not p.name.endswith("_raw.glb")]
                if glbs:
                    glbs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    target_path = str(glbs[0])
                else:
                    raise FileNotFoundError("No 3D mesh found to retopologize.")

        res = BlenderPipeline.retopologize(
            input_mesh_path=target_path,
            output_name=output_name,
            mode=mode,
            target_count=target_count
        )

        res["execution_mode"] = "pure_local"
        res["stl_uri"] = f"file://{res['stl_path']}"
        res["glb_uri"] = f"file://{res['glb_path']}"
        if res.get("3mf_path"):
            res["3mf_uri"] = f"file://{res['3mf_path']}"
        return res

    @classmethod
    def bake_textures(
        cls,
        input_mesh_path: Optional[str] = None,
        output_name: str = "pbr_model",
        texture_resolution: int = 2048,
        bake_normal: bool = True,
        bake_ao: bool = True
    ) -> Dict[str, Any]:
        """Bakes Normal and AO maps locally in Blender Cycles and exports textured GLB."""
        target_path = input_mesh_path
        if not target_path or not os.path.exists(target_path):
            st = load_state()
            latest = st.get("latest_model", {})
            target_path = latest.get("glb_path") or latest.get("stl_path")
            if not target_path or not os.path.exists(target_path):
                glbs = [p for p in OUTPUT_DIR.glob("*.glb") if not p.name.endswith("_raw.glb")]
                if glbs:
                    glbs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    target_path = str(glbs[0])
                else:
                    raise FileNotFoundError("No 3D mesh found for PBR texture baking.")

        res = BlenderPipeline.bake_pbr_textures(
            input_mesh_path=target_path,
            output_name=output_name,
            texture_resolution=texture_resolution,
            bake_normal=bake_normal,
            bake_ao=bake_ao
        )

        res["execution_mode"] = "pure_local"
        res["glb_uri"] = f"file://{res['glb_path']}"
        if res.get("normal_map_path"):
            res["normal_map_uri"] = f"file://{res['normal_map_path']}"
        if res.get("ao_map_path"):
            res["ao_map_uri"] = f"file://{res['ao_map_path']}"
        return res

    @classmethod
    def split_model(
        cls,
        input_mesh_path: Optional[str] = None,
        output_name: str = "model_split",
        subject_category: str = "auto",
        add_connectors: bool = True,
        connector_size_mm: float = 3.0,
        exploded_distance_mm: float = 16.0
    ) -> Dict[str, Any]:
        """Decomposes a 3D model into watertight parts with assembly keying and multi-color 3MF."""
        target_path = input_mesh_path
        if not target_path or not os.path.exists(target_path):
            st = load_state()
            latest = st.get("latest_model", {})
            target_path = latest.get("stl_path") or latest.get("glb_path")
            if not target_path or not os.path.exists(target_path):
                stls = [p for p in OUTPUT_DIR.glob("*.stl") if not p.name.endswith("_split.stl") and not "_parts" in str(p)]
                if stls:
                    stls.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    target_path = str(stls[0])
                else:
                    raise FileNotFoundError("No 3D mesh found to split.")

        from tools.model_splitter import ModelSplitter
        res = ModelSplitter.split_model(
            input_mesh_path=target_path,
            output_filename=output_name,
            output_dir=str(OUTPUT_DIR),
            subject_category=subject_category,
            add_connectors=add_connectors,
            connector_size_mm=connector_size_mm,
            exploded_distance_mm=exploded_distance_mm
        )
        res["execution_mode"] = "pure_local"
        return res

    @classmethod
    def canonicalize_pose(
        cls,
        image_path: str,
        target_pose: str = "a_pose",
        output_name: str = "canonical_pose_concept",
        art_style: str = "faithful_anatomical"
    ) -> Dict[str, Any]:
        """Converts an input 2D image/character into a canonical A-Pose or T-Pose concept."""
        from tools.pose_canonicalizer import PoseCanonicalizer
        return PoseCanonicalizer.canonicalize_pose(
            image_path=image_path,
            target_pose=target_pose,
            output_filename=output_name,
            output_dir=str(OUTPUT_DIR),
            art_style=art_style
        )

