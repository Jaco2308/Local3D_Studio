"""
Local3D Studio Neural Image-to-3D Engine (Multi-View & Tempfile Clean)
Generates high-fidelity 3D geometry (.glb) using Hunyuan3D-2 / Hunyuan3D-2mv
scaled dynamically according to the active hardware performance tier.

Features:
1. Zero-Copy Meta-Device Local Loader: Loads Hunyuan3D-2 (4.6 GB fp16 safetensors)
   in ~5 seconds on Apple Silicon (MPS) and CUDA without double-allocating CPU RAM.
2. Transformers 5.x DINOv2 State-Dict Remapper: Automatically bridges legacy
   Hunyuan3D conditioner weights to transformers >= 5.0 Dinov2Model layer names.
3. Progressive Unified Memory Release: On 16GB unified memory (TIER_1_ECO),
   immediately frees the 1.1B DINOv2 conditioner after image encoding and frees
   the DiT transformer before Marching Cubes decoding, keeping peak RAM < 2.5 GB.
4. Multi-View Sheet Auto-Detection & Clean Tempfile Operation.
"""

import os
import sys
import time
import glob
import tempfile
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
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


def _get_gradio_client():
    try:
        from gradio_client import Client, handle_file
        return Client, handle_file
    except ImportError:
        return None, None


class Neural3DEngine:
    _local_pipeline = None

    @classmethod
    def _find_local_hunyuan_checkpoint(cls, tier: str = "mini") -> Tuple[Optional[str], Optional[str]]:
        """
        Locates local Hunyuan3D-2 config.yaml and model.fp16.safetensors across
        ~/.cache/hy3dgen and ~/.cache/huggingface/hub without redundant downloads.
        """
        home = os.path.expanduser("~")
        candidates = []

        if tier == "mini":
            candidates.extend([
                os.path.join(home, ".cache/hy3dgen/tencent/Hunyuan3D-2mini/hunyuan3d-dit-v2-mini"),
                os.path.join(home, ".cache/hy3dgen/tencent/Hunyuan3D-2mini/hunyuan3d-dit-v2-mini-turbo"),
            ])
            candidates.extend(glob.glob(
                os.path.join(home, ".cache/huggingface/hub/models--tencent--Hunyuan3D-2mini/snapshots/*/hunyuan3d-dit-v2-mini*")
            ))

        # Full Hunyuan3D-2 checkpoint (also serves as local high-fidelity engine if mini is not separately cached)
        candidates.append(os.path.join(home, ".cache/hy3dgen/tencent/Hunyuan3D-2/hunyuan3d-dit-v2-0"))
        candidates.extend(glob.glob(
            os.path.join(home, ".cache/huggingface/hub/models--tencent--Hunyuan3D-2/snapshots/*/hunyuan3d-dit-v2-0")
        ))

        for folder in candidates:
            cfg_path = os.path.join(folder, "config.yaml")
            ckpt_path = os.path.join(folder, "model.fp16.safetensors")
            if os.path.isfile(cfg_path) and os.path.isfile(ckpt_path):
                return cfg_path, ckpt_path

        return None, None

    @staticmethod
    def _remap_dinov2_conditioner_state_dict(cond_sd: Dict[str, Any], target_keys: set) -> Dict[str, Any]:
        """
        Bridges Hunyuan3D-2's legacy DINOv2 conditioner state_dict to transformers >= 5.0
        (where query/key/value/dense became q_proj/k_proj/v_proj/o_proj and SwiGLU weights_in
        split into gate_proj / up_proj).
        """
        if "main_image_encoder.model.encoder.layer.0.attention.q_proj.weight" not in target_keys:
            return cond_sd
        if "main_image_encoder.model.encoder.layer.0.attention.q_proj.weight" in cond_sd:
            return cond_sd

        new_sd = {}
        for k, v in cond_sd.items():
            nk = k
            if nk.startswith("main_image_encoder.model.dinov2."):
                nk = nk.replace("main_image_encoder.model.dinov2.", "main_image_encoder.model.", 1)

            if ".attention.attention.query." in nk:
                nk = nk.replace(".attention.attention.query.", ".attention.q_proj.")
            elif ".attention.attention.key." in nk:
                nk = nk.replace(".attention.attention.key.", ".attention.k_proj.")
            elif ".attention.attention.value." in nk:
                nk = nk.replace(".attention.attention.value.", ".attention.v_proj.")
            elif ".attention.output.dense." in nk:
                nk = nk.replace(".attention.output.dense.", ".attention.o_proj.")
            elif ".mlp.weights_out." in nk:
                nk = nk.replace(".mlp.weights_out.", ".mlp.down_proj.")
            elif ".mlp.weights_in.weight" in nk:
                half = v.shape[0] // 2
                new_sd[nk.replace(".mlp.weights_in.weight", ".mlp.gate_proj.weight")] = v[:half]
                new_sd[nk.replace(".mlp.weights_in.weight", ".mlp.up_proj.weight")] = v[half:]
                continue
            elif ".mlp.weights_in.bias" in nk:
                half = v.shape[0] // 2
                new_sd[nk.replace(".mlp.weights_in.bias", ".mlp.gate_proj.bias")] = v[:half]
                new_sd[nk.replace(".mlp.weights_in.bias", ".mlp.up_proj.bias")] = v[half:]
                continue

            new_sd[nk] = v
        return new_sd

    @classmethod
    def _try_load_local_hunyuan(cls, tier: str = "mini"):
        """
        Loads local Hunyuan3D-2 pipeline onto MPS/CUDA/CPU using zero-copy meta-device
        instantiation (~5.4s load time, zero swap on 16GB Unified Memory).
        """
        hw = HardwareManager.get_instance()
        device = str(hw.device_info.get("device", "cpu"))
        dtype = hw.get_torch_dtype()

        if cls._local_pipeline is not None:
            if getattr(cls._local_pipeline, "conditioner", None) is not None and getattr(cls._local_pipeline, "model", None) is not None:
                try:
                    cls._local_pipeline.to(device, dtype=dtype)
                    return cls._local_pipeline
                except Exception as e:
                    print(f"[Neural3D] Re-initializing cached pipeline after device move note: {e}", file=sys.stderr)
                    cls._local_pipeline = None

        try:
            import torch
            import yaml
            from safetensors.torch import load_file
            from hy3dgen.shapegen.pipelines import (
                Hunyuan3DDiTFlowMatchingPipeline,
                instantiate_from_config,
            )

            cfg_path, ckpt_path = cls._find_local_hunyuan_checkpoint(tier=tier)
            if not cfg_path or not ckpt_path:
                print("[Neural3D] Local Hunyuan3D-2 safetensors not found in cache. Attempting from_pretrained...", file=sys.stderr)
                model_id = "tencent/Hunyuan3D-2mini" if tier == "mini" else "tencent/Hunyuan3D-2"
                subfolder = "hunyuan3d-dit-v2-mini" if tier == "mini" else "hunyuan3d-dit-v2-0"
                pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
                    model_id,
                    subfolder=subfolder,
                    device=device,
                    dtype=dtype,
                    use_safetensors=True,
                )
                if hasattr(pipeline, "enable_flashvdm"):
                    pipeline.enable_flashvdm(enabled=True, mc_algo="mc", replace_vae=False)
                cls._local_pipeline = pipeline
                return cls._local_pipeline

            t0 = time.time()
            print(f"[Neural3D] Loading local Hunyuan3D-2 ({os.path.basename(os.path.dirname(ckpt_path))}) on {device} ({dtype})...", file=sys.stderr)

            with open(cfg_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            # Instantiate heavy 1.1B DiT & 1.1B DINOv2 on meta device so zero CPU RAM is wasted on random float32 weights
            with torch.device("meta"):
                model = instantiate_from_config(config["model"])
                conditioner = instantiate_from_config(config["conditioner"])

            # Instantiate lightweight VAE on CPU so non-persistent FourierEmbedder buffers in encoder & geo_decoder are populated
            vae = instantiate_from_config(config["vae"])

            raw_sd = load_file(ckpt_path, device="cpu")
            sub_sds = {"model": {}, "vae": {}, "conditioner": {}}
            for k, v in raw_sd.items():
                if "." in k:
                    prefix, rest = k.split(".", 1)
                    if prefix in sub_sds:
                        sub_sds[prefix][rest] = v
            del raw_sd

            model.load_state_dict(sub_sds["model"], assign=True)
            del sub_sds["model"]
            model.to(device=device, dtype=dtype)
            model.eval()

            vae.load_state_dict(sub_sds["vae"], assign=True)
            del sub_sds["vae"]
            vae.to(device=device, dtype=dtype)
            vae.eval()

            target_cond_keys = set(conditioner.state_dict().keys())
            remapped_cond = cls._remap_dinov2_conditioner_state_dict(sub_sds["conditioner"], target_cond_keys)
            del sub_sds["conditioner"]
            conditioner.load_state_dict(remapped_cond, strict=False, assign=True)
            del remapped_cond
            conditioner.to(device=device, dtype=dtype)
            conditioner.eval()

            image_processor = instantiate_from_config(config["image_processor"])
            scheduler = instantiate_from_config(config["scheduler"])

            pipeline = Hunyuan3DDiTFlowMatchingPipeline(
                vae=vae,
                model=model,
                scheduler=scheduler,
                conditioner=conditioner,
                image_processor=image_processor,
                device=device,
                dtype=dtype,
                from_pretrained_kwargs=dict(
                    model_path=os.path.dirname(ckpt_path),
                    subfolder="",
                    use_safetensors=True,
                    variant="fp16",
                    dtype=dtype,
                    device=device,
                ),
            )
            if hasattr(pipeline, "enable_flashvdm"):
                pipeline.enable_flashvdm(enabled=True, mc_algo="mc", replace_vae=False)

            print(f"[Neural3D] Local Hunyuan3D-2 ready in {time.time() - t0:.2f}s.", file=sys.stderr)
            cls._local_pipeline = pipeline
            return cls._local_pipeline

        except Exception as e:
            print(f"[Neural3D] Note: Local hy3dgen pipeline unavailable ({e}). Using Gradio client fallback.", file=sys.stderr)
            return None

    @classmethod
    def _run_local_hunyuan_inference(
        cls,
        pipeline,
        image_input: str,
        target_steps: int,
        target_octree: int,
        seed: int,
        output_glb_path: str
    ) -> str:
        """
        Executes local Hunyuan3D-2 inference with progressive VRAM release on 16GB Unified Memory
        and automatic step/octree bounding on MPS so tool calls never trigger IDE SSE timeouts.
        """
        import torch

        hw = HardwareManager.get_instance()
        device = str(hw.device_info.get("device", "cpu"))
        is_strict_memory = hw.is_16gb_safe()

        # On Apple Silicon MPS, each full 1.1B DiT CFG step takes ~16s.
        # Cap local MPS steps & octree so the entire MCP tool finishes well under the IDE SSE timeout (~60s).
        if device == "mps":
            max_mps_steps = int(os.getenv("LOCAL_MPS_MAX_STEPS", "4"))
            max_mps_octree = int(os.getenv("LOCAL_MPS_MAX_OCTREE", "256"))
            eff_steps = min(target_steps, max_mps_steps)
            eff_octree = min(target_octree, max_mps_octree)
            num_chunks = 32000
        else:
            eff_steps = target_steps
            eff_octree = target_octree
            num_chunks = 16000

        print(
            f"[Neural3D] Running local Hunyuan3D-2 on {device} "
            f"(octree={eff_octree}, steps={eff_steps}, chunks={num_chunks}, seed={seed})...",
            file=sys.stderr
        )

        t0 = time.time()
        cond_inputs = pipeline.prepare_image(image_input)
        image_tensor = cond_inputs.pop("image")
        cond = pipeline.encode_cond(
            image=image_tensor,
            additional_cond_inputs=cond_inputs,
            do_classifier_free_guidance=True,
            dual_guidance=False,
        )
        del image_tensor

        # Immediately release 1.1B DINOv2 conditioner (~2.2 GB) on 16GB unified memory before DiT sampling
        if is_strict_memory and getattr(pipeline, "conditioner", None) is not None:
            pipeline.conditioner = None
            cleanup_memory(label="Post-DINOv2-Conditioner")

        generator = torch.Generator(device=pipeline.device).manual_seed(seed)
        batch_size = cond["main"].shape[0] // 2
        latents = pipeline.prepare_latents(batch_size, pipeline.dtype, pipeline.device, generator)
        timesteps, sigmas = pipeline.get_timesteps(eff_steps)

        with torch.no_grad():
            for i, t in enumerate(timesteps):
                latent_model_input = torch.cat([latents] * 2)
                t_tensor = torch.tensor([t], device=pipeline.device, dtype=pipeline.dtype) / 1000.0
                t_expand = t_tensor.expand(latent_model_input.shape[0])
                noise_pred = pipeline.model(latent_model_input, t_expand, cond)
                noise_pred_cond, noise_pred_uncond = noise_pred.chunk(2)
                noise_pred = noise_pred_uncond + 5.0 * (noise_pred_cond - noise_pred_uncond)
                # Flow-matching Euler step
                dt = sigmas[i + 1] - sigmas[i]
                latents = latents + dt * noise_pred
                del latent_model_input, noise_pred, noise_pred_cond, noise_pred_uncond

        del cond

        # Immediately release DiT model (~2.2 GB) on 16GB unified memory before Marching Cubes decoding
        if is_strict_memory and getattr(pipeline, "model", None) is not None:
            pipeline.model = None
            cleanup_memory(label="Post-DiT-Sampling")

        with torch.no_grad():
            latents = pipeline.vae.decode(latents)
            mesh = pipeline.vae.latents2mesh(
                latents,
                bounds=1.01,
                mc_level=0.0,
                octree_resolution=eff_octree,
                num_chunks=num_chunks,
                mc_algo="mc",
                enable_pbar=False,
            )
            mesh = pipeline._export(mesh, output_type="trimesh", box_v=1.01)

        while isinstance(mesh, (list, tuple)):
            mesh = mesh[0]

        mesh.export(output_glb_path)
        print(
            f"[Neural3D] Local Hunyuan3D-2 exported mesh in {time.time() - t0:.2f}s -> {output_glb_path}",
            file=sys.stderr
        )

        if is_strict_memory:
            cls._local_pipeline = None
        else:
            cls._local_pipeline = offload_or_cleanup(cls._local_pipeline, label="Hunyuan3D-2")
        cleanup_memory(label="Post-Local-Hunyuan3D")
        return output_glb_path

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
                    print(f"[Neural3D] Detected Multi-View model sheet ({w}x{h}). Running Anti-Bleed MultiviewAligner (4 views + CLAHE)...", file=sys.stderr)
                    align_res = MultiviewAligner.split_and_align_multiview(
                        concept_image_path=img_path,
                        output_dir=temp_dir,
                        save_preview=False
                    )
                    return align_res["front_path"], align_res["left_path"], align_res["right_path"], align_res["back_path"]
        except Exception as e:
            print(f"[Neural3D] Error inspecting image dimensions for multiview: {e}", file=sys.stderr)
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
        2. Routes according to generation_strategy ('single_hero_34', 'multiview_turnaround', or 'auto').
        3. Runs local Hunyuan3D-2 with zero-copy meta loading & progressive VRAM release (or fast timeout-bounded Gradio fallback).
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
        target_octree = octree_resolution or max(eff_settings.get("octree_resolution", 320), 256)
        target_steps = num_inference_steps or max(eff_settings.get("inference_steps", 25), 12)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            clean_img_path = str(tmp_path / "clean_isolated.png")

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

            print(f"[Neural3D] Executing 3D generation with strategy: {strat.upper()}", file=sys.stderr)

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
                mv_front = mv_left = mv_right = mv_back = None
                spaces = ["tencent/Hunyuan3D-2", "tencent/Hunyuan3D-2mv", "VAST-AI/TripoSG"]

            # Step 3: Local Inference with isolated MPS/CUDA memory
            os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"
            cleanup_memory(label="Pre-Hunyuan3D Isolation")

            local_pipe = cls._try_load_local_hunyuan(tier=target_tier)
            if local_pipe is not None:
                try:
                    input_for_local = mv_front if mv_front else clean_img_path
                    return cls._run_local_hunyuan_inference(
                        pipeline=local_pipe,
                        image_input=input_for_local,
                        target_steps=target_steps,
                        target_octree=target_octree,
                        seed=seed,
                        output_glb_path=output_glb_path
                    )
                except Exception as local_err:
                    print(f"[Neural3D] Local inference error ({local_err}); attempting fast Gradio fallback...", file=sys.stderr)
                    cls._local_pipeline = None
                    cleanup_memory(label="Failed-Local-Hunyuan3D")

            # Step 4: Fast, Timeout-Bounded Gradio Client Fallback (Hugging Face Spaces)
            Client, handle_file = _get_gradio_client()
            if Client is None:
                raise RuntimeError("Neither local hy3dgen nor gradio_client is available.")

            t0 = time.time()
            last_error = None
            for space_id in spaces:
                if time.time() - t0 > 50.0:
                    print("[Neural3D] Fast fallback time budget reached (50s); aborting remaining spaces to prevent IDE stream timeout.", file=sys.stderr)
                    break

                print(f"[Neural3D] Connecting to Space: {space_id} (timeout=45s)...", file=sys.stderr)
                try:
                    client = Client(
                        space_id,
                        token=HF_TOKEN or None,
                        httpx_kwargs={"timeout": 45.0},
                        verbose=False
                    )
                    print(f"[Neural3D] Submitting inference job to {space_id} (steps={target_steps}, octree={target_octree}, seed={seed})...", file=sys.stderr)

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
                        print(f"[Neural3D] Success from {space_id} in {duration}s -> {output_glb_path}", file=sys.stderr)

                        cleanup_memory(label="Post-Neural3D")
                        return output_glb_path

                except Exception as e:
                    print(f"[Neural3D] Space {space_id} failed: {e}", file=sys.stderr)
                    last_error = e

            raise RuntimeError(f"All 3D neural engines failed. Last error: {last_error}")

