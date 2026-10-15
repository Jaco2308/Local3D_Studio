"""
Local3D Studio 2D Concept Engine (16GB-Safe)
Generates high-resolution 2D concepts using SDXL-Lightning (4-step, float16)
with immediate deallocation under the 16GB_SAFE memory profile.
"""

import os
from pathlib import Path
from typing import Optional
from PIL import Image

from core.hardware_backend import HardwareManager
from core.memory import cleanup_memory, offload_or_cleanup
from core.config import SDXL_MODEL_ID, SDXL_LIGHTNING_REPO, SDXL_LIGHTNING_CKPT, OUTPUT_DIR
from tools.prompt_enhancer import enhance_prompt_for_3d

try:
    import torch
    from diffusers import StableDiffusionXLPipeline, UNet2DConditionModel, EulerDiscreteScheduler
    from huggingface_hub import hf_hub_download
    from safetensors.torch import load_file
    _DIFFUSERS_AVAILABLE = True
except ImportError:
    _DIFFUSERS_AVAILABLE = False


class ConceptEngine:
    _pipeline = None

    @classmethod
    def get_pipeline(cls):
        """Loads SDXL-Lightning 4-step pipeline with memory-mapped zero-duplication loading."""
        if cls._pipeline is not None:
            return cls._pipeline

        if not _DIFFUSERS_AVAILABLE:
            raise RuntimeError("diffusers and transformers must be installed for local concept generation.")

        import gc
        hw = HardwareManager.get_instance()
        device = hw.get_torch_device()
        dtype = hw.get_torch_dtype()

        print(f"[ConceptEngine] Loading SDXL-Lightning 4-step on {hw.device_info['name']} ({dtype})...")

        local_cached_unet = Path("models/sdxl_lightning_4step_unet")

        try:
            if not (local_cached_unet / "config.json").exists() or not (local_cached_unet / "diffusion_pytorch_model.safetensors").exists():
                local_cached_unet.mkdir(parents=True, exist_ok=True)
                ckpt_path = hf_hub_download(SDXL_LIGHTNING_REPO, SDXL_LIGHTNING_CKPT)
                unet_config = UNet2DConditionModel.load_config(SDXL_MODEL_ID, subfolder="unet")
                unet = UNet2DConditionModel.from_config(unet_config).to(dtype=dtype)
                state_dict = load_file(ckpt_path)
                unet.load_state_dict(state_dict)
                del state_dict
                gc.collect()
                unet.save_pretrained(local_cached_unet)
                del unet
                gc.collect()

            # Single-pass direct memory-mapped safetensors loading (zero memory duplication)
            unet = UNet2DConditionModel.from_pretrained(
                str(local_cached_unet),
                torch_dtype=dtype
            )

            pipe = StableDiffusionXLPipeline.from_pretrained(
                SDXL_MODEL_ID,
                unet=unet,
                torch_dtype=dtype,
                variant="fp16" if dtype == torch.float16 else None
            )
            del unet
            gc.collect()

        except Exception as e:
            print(f"[ConceptEngine] Note: Direct UNet load fallback ({e}), falling back to standard SDXL pipeline...")
            pipe = StableDiffusionXLPipeline.from_pretrained(
                SDXL_MODEL_ID,
                torch_dtype=dtype,
                variant="fp16" if dtype == torch.float16 else None
            )

        # Set 4-step scheduler
        pipe.scheduler = EulerDiscreteScheduler.from_config(pipe.scheduler.config, timestep_spacing="trailing")
        pipe.enable_attention_slicing()
        pipe.to(device)

        cls._pipeline = pipe
        return cls._pipeline

    @classmethod
    def generate_concept(
        cls,
        user_prompt: str,
        output_path: Optional[str] = None,
        mode: str = "3d_print",
        art_style: str = "faithful_anatomical",
        multiview: bool = True,
        add_pedestal_base: bool = False,
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None
    ) -> str:
        """
        Generates a 2D concept PNG from a user prompt using the 3D-Aware Prompt Enhancer.
        Runs in strict inference_mode with attention slicing and immediate deallocation under 16GB_SAFE.
        """
        import random
        if seed is None:
            seed = random.randint(1, 99999999)

        if multiview:
            if width == 1024 and height == 1024:
                width, height = 1536, 512
        else:
            if width == 1536 and height == 512:
                width, height = 1024, 1024

        enhanced_prompt = enhance_prompt_for_3d(
            user_prompt=user_prompt,
            mode=mode,
            art_style=art_style,
            multiview=multiview,
            add_pedestal_base=add_pedestal_base
        )
        print(f"[ConceptEngine] Enhanced Prompt ({art_style}, seed={seed}, res={width}x{height}): {enhanced_prompt}")

        if output_path is None:
            output_path = str(OUTPUT_DIR / "concept_latest.png")
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        hw = HardwareManager.get_instance()
        pipe = cls.get_pipeline()

        generator = None
        if seed is not None and torch is not None:
            generator = torch.Generator(device="cpu").manual_seed(seed)

        print(f"[ConceptEngine] Running 4-step SDXL-Lightning inference in torch.inference_mode (seed={seed})...")
        with torch.inference_mode():
            image = pipe(
                prompt=enhanced_prompt,
                num_inference_steps=4,
                guidance_scale=0.0,
                width=width,
                height=height,
                generator=generator
            ).images[0]

        image.save(output_path, "PNG")
        print(f"[ConceptEngine] Concept saved to: {output_path}")

        # Immediate clean deallocation under 16GB_SAFE
        cls._pipeline = offload_or_cleanup(cls._pipeline, label="SDXL-Lightning")

        return output_path
