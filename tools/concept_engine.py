"""
Local3D Studio Concept Engine (Client AI Native Mode)
2D concept generation is delegated directly to the client AI assistant's native
multimodal visual generator or user-provided reference photos. This dedicates
100% of the 16 GB RAM/VRAM budget to 3D neural reconstruction (Hunyuan3D-2)
and headless Blender manufacturing, eliminating local memory bottlenecks.
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
        Stub informing that 2D concept generation is handled natively by the AI client
        or user-provided reference images.
        """
        raise NotImplementedError(
            "2D image generation is handled directly by your client AI assistant (e.g. Antigravity native generator) "
            "or user-provided reference images, dedicating 100% of the 16 GB RAM/VRAM budget to Hunyuan3D-2 3D reconstruction. "
            "Use 'compile_3d_master_prompt' to obtain the photogrammetry-grade prompt, generate or supply your image, "
            "then call 'direct_image_to_3d'."
        )
