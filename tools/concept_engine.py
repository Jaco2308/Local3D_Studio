"""
Local3D Studio Concept Engine (Antigravity Native Mode)
2D concept generation is now delegated directly to Antigravity's native multimodal
image generator or user-provided reference photos, eliminating local SDXL diffusion
memory overhead on Apple Silicon unified RAM.
"""

from typing import Optional
from pathlib import Path


class ConceptEngine:
    @classmethod
    def generate_concept(
        cls,
        user_prompt: str,
        output_path: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Stub informing that 2D concept generation is handled natively by Antigravity
        or user-provided reference images.
        """
        raise NotImplementedError(
            "2D image generation with SDXL-Lightning has been disabled to eliminate Mac freeze. "
            "Use 'compile_3d_master_prompt' to obtain the master prompt, generate the image using "
            "Antigravity's native image generator or provide your own reference image, then call 'direct_image_to_3d'."
        )
