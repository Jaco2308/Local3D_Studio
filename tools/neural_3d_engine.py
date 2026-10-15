"""
Local3D Studio Neural Image-to-3D Engine (Multi-View & Tempfile Clean)
Generates high-fidelity 3D geometry (.glb) using Hunyuan3D-2 / Hunyuan3D-2mv
scaled dynamically according to the active hardware performance tier.

Features:
1. Multi-View Sheet Auto-Detection: Automatically crops 3-view model sheets
   (Front, Side, Back) and supplies them to Hunyuan3D Multi-View inputs.
2. Clean Tempfile Operation: Intermediate clean PNGs and temporary raw GLBs
   are stored in temporary locations and never clutter output/.
3. High-Fidelity Parameters: octree=320/384, steps=25, guidance_scale=5.5.
"""

import os
import time
import tempfile
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image

from core.hardware_backend import HardwareManager
from core.memory import cleanup_memory, offload_or_cleanup
from core.config import (
    OUTPUT_DIR,
    HF_TOKEN,
    get_effective_3d_settings
)
from tools.rembg_engine import BackgroundRemovalEngine
from tools.multiview_aligner import MultiviewAligner

try:
    from gradio_client import Client, handle_file
    _GRADIO_AVAILABLE = True
except ImportError:
    _GRADIO_AVAILABLE = False


class Neural3DEngine:
    _local_pipeline = None

    @classmethod
    def _try_load_local_hunyuan(cls, tier: str = "mini"):
        """Attempts to load local Hunyuan3D-2mini / full pipeline without C++ compilation."""
        hw = HardwareManager.get_instance()
        device = hw.get_torch_device()
        model_id = "tencent/Hunyuan3D-2mini" if tier == "mini" else "tencent/Hunyuan3D-2"

        if cls._local_pipeline is not None:
            try:
                if hasattr(cls._local_pipeline, "to"):
                    cls._local_pipeline.to(device)
            except Exception as e:
                print(f"[Neural3D] Note moving cached pipeline to {device}: {e}")
            return cls._local_pipeline

        try:
            import hy3dgen
            from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

            print(f"[Neural3D] Initializing local {model_id} on {hw.device_info['name']}...")
            pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(model_id)
            if hasattr(pipeline, "enable_flashvdm"):
                pipeline.enable_flashvdm()
            pipeline.to(device)

            cls._local_pipeline = pipeline
            return cls._local_pipeline
        except Exception as e:
            print(f"[Neural3D] Note: Local hy3dgen pipeline unavailable ({e}). Using Gradio client fallback.")
            return None

    @classmethod
    def _slice_multiview_sheet(cls, img_path: str, temp_dir: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        If the image is a turnaround character sheet (width > 1.25 * height),
        applies MultiviewAligner (anti-bleed, connected components, 400px height lock, CLAHE, 4 views).
        """
        try:
            with Image.open(img_path) as im:
                w, h = im.size
                if w >= 1.25 * h:
                    print(f"[Neural3D] Detected Multi-View model sheet ({w}x{h}). Running Anti-Bleed MultiviewAligner (4 views + CLAHE)...")
                    align_res = MultiviewAligner.split_and_align_multiview(
                        concept_image_path=img_path,
                        output_dir=temp_dir,
                        save_preview=False
                    )
                    return align_res["front_path"], align_res["left_path"], align_res["right_path"], align_res["back_path"]
        except Exception as e:
            print(f"[Neural3D] Error inspecting image dimensions for multiview: {e}")
        return None, None, None, None

    @classmethod
    def generate_glb(
        cls,
        image_path: str,
        output_glb_path: Optional[str] = None,
        tier: Optional[str] = None,
        octree_resolution: Optional[int] = None,
        num_inference_steps: Optional[int] = None,
        caption: str = "A highly detailed 3D model, watertight solid",
        seed: Optional[int] = None,
        front_view_path: Optional[str] = None,
        left_view_path: Optional[str] = None,
        right_view_path: Optional[str] = None,
        back_view_path: Optional[str] = None,
        generation_strategy: str = "auto"
    ) -> str:
        """
        Executes Image-to-3D neural generation cleanly:
        1. Strips background using rembg into a temporary directory.
        2. Routes according to generation_strategy ('single_hero_34', 'multiview_turnaround', or 'auto'):
           - 'single_hero_34': Meshy-style single 3/4 view. Vision encoder uses rich RGB contrast to distinguish
             foreground from background limbs and DiT generates complete 360° geometry without cross-view conflict.
           - 'multiview_turnaround': Slices turnaround sheet into 4 calibrated views (Y-lock + CLAHE) and calls Hunyuan3D-2mv.
           - 'auto': Turnaround if width >= 1.25 * height, otherwise single_hero_34.
        3. Invokes Hunyuan3D-2 / Hunyuan3D-2mv with guidance_scale=5.5, octree=320/384, steps=25.
        4. Writes output GLB directly without leaving temporary clutter in output/.
        """
        import random
        if seed is None:
            seed = random.randint(1, 99999999)

        image_path = os.path.abspath(image_path)
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Input image not found: {image_path}")

        eff_settings = get_effective_3d_settings()
        target_tier = tier or eff_settings.get("model_tier", "mini")
        target_octree = octree_resolution or max(eff_settings.get("octree_resolution", 320), 320)
        target_steps = num_inference_steps or max(eff_settings.get("inference_steps", 25), 25)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            clean_img_path = str(tmp_path / "clean_isolated.png")
            temp_raw_glb = str(tmp_path / "raw_neural.glb")

            # Final destination
            if output_glb_path is None:
                output_glb_path = str(OUTPUT_DIR / f"{Path(image_path).stem}_raw.glb")
            os.makedirs(os.path.dirname(os.path.abspath(output_glb_path)), exist_ok=True)

            # Step 1: Pre-process image into temporary file if not already pre-cleaned
            if "clean_isolated" in Path(image_path).name or front_view_path is not None:
                clean_img_path = image_path
            else:
                BackgroundRemovalEngine.remove_background(image_path, clean_img_path, replace_with_white=True)

            # Step 2: Determine Strategy & Multiview Views
            strat = generation_strategy.lower().strip()
            if strat == "auto":
                try:
                    with Image.open(image_path) as im:
                        w, h = im.size
                        strat = "multiview_turnaround" if w >= 1.25 * h else "single_hero_34"
                except Exception:
                    strat = "single_hero_34"

            print(f"[Neural3D] Executing 3D generation with strategy: {strat.upper()}")

            if strat == "multiview_turnaround":
                if front_view_path and os.path.exists(front_view_path):
                    mv_front = front_view_path
                    mv_left = left_view_path if left_view_path and os.path.exists(left_view_path) else None
                    mv_right = right_view_path if right_view_path and os.path.exists(right_view_path) else None
                    mv_back = back_view_path if back_view_path and os.path.exists(back_view_path) else None
                else:
                    mv_front, mv_left, mv_right, mv_back = cls._slice_multiview_sheet(image_path, tmp_dir)
                spaces = ["tencent/Hunyuan3D-2mv", "tencent/Hunyuan3D-2", "VAST-AI/TripoSG"]
            else:
                # single_hero_34 (Meshy AI style): Do not slice, feed single high-contrast hero image
                mv_front = mv_left = mv_right = mv_back = None
                spaces = ["tencent/Hunyuan3D-2", "tencent/Hunyuan3D-2mv", "VAST-AI/TripoSG"]

            # Step 3: Try Local Inference with isolated MPS memory
            os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"
            cleanup_memory(label="Pre-Hunyuan3D Isolation")

            local_pipe = cls._try_load_local_hunyuan(tier=target_tier)
            if local_pipe is not None:
                print(f"[Neural3D] Running local Hunyuan3D-{target_tier} inference (octree={target_octree}, steps={target_steps}, seed={seed})...")
                input_for_local = mv_front if mv_front else clean_img_path
                mesh = local_pipe(
                    image=input_for_local,
                    num_inference_steps=target_steps,
                    octree_resolution=target_octree
                )
                mesh.export(output_glb_path)
                print(f"[Neural3D] Successfully exported local mesh: {output_glb_path}")

                cls._local_pipeline = offload_or_cleanup(cls._local_pipeline, label=f"Hunyuan3D-{target_tier}")
                cleanup_memory(label="Post-Local-Hunyuan3D")
                return output_glb_path

            # Step 4: Resilient Gradio Client Fallback (Hugging Face Spaces)
            if not _GRADIO_AVAILABLE:
                raise RuntimeError("Neither local hy3dgen nor gradio_client is available.")

            t0 = time.time()
            last_error = None
            for space_id in spaces:
                print(f"[Neural3D] Connecting to Space: {space_id}...")
                try:
                    client = Client(space_id, token=HF_TOKEN or None, httpx_kwargs={"timeout": 300.0})
                    print(f"[Neural3D] Connected to {space_id}. Submitting inference job (steps={target_steps}, octree={target_octree}, seed={seed}, guidance=5.5)...")

                    f_main = handle_file(mv_front if mv_front else clean_img_path)
                    f_left = handle_file(mv_left) if mv_left else None
                    f_right = handle_file(mv_right) if mv_right else None
                    f_back = handle_file(mv_back) if mv_back else None

                    if space_id in ["tencent/Hunyuan3D-2mv", "tencent/Hunyuan3D-2"]:
                        result = client.predict(
                            caption=caption,
                            image=f_main,
                            mv_image_front=f_main if mv_front else None,
                            mv_image_back=f_back,
                            mv_image_left=f_left,
                            mv_image_right=f_right,
                            steps=target_steps,
                            guidance_scale=5.5,
                            seed=seed,
                            octree_resolution=target_octree,
                            check_box_rembg=False,
                            num_chunks=8000,
                            randomize_seed=True,
                            api_name="/shape_generation"
                        )
                    else:  # TripoSG
                        result = client.predict(
                            image=f_main,
                            api_name="/image_to_3d"
                        )

                    downloaded_file = None
                    if isinstance(result, str) and os.path.exists(result):
                        downloaded_file = result
                    elif isinstance(result, (list, tuple)):
                        for item in result:
                            if isinstance(item, str) and item.endswith((".glb", ".obj")):
                                downloaded_file = item
                                break
                            if isinstance(item, dict) and "value" in item and isinstance(item["value"], str):
                                downloaded_file = item["value"]
                                break

                    if downloaded_file and os.path.exists(downloaded_file):
                        import shutil
                        shutil.copyfile(downloaded_file, output_glb_path)
                        duration = round(time.time() - t0, 2)
                        print(f"[Neural3D] Success from {space_id} in {duration}s -> {output_glb_path}")

                        cleanup_memory(label="Post-Neural3D")
                        return output_glb_path

                except Exception as e:
                    print(f"[Neural3D] Space {space_id} failed: {e}")
                    last_error = e

            raise RuntimeError(f"All 3D neural spaces failed. Last error: {last_error}")
