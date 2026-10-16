"""
Local3D Studio Tools & Engines Package
Exposes 3D AI generation, background removal, prompt enhancement, and Blender pipeline.
"""

__all__ = [
    "enhance_prompt_for_3d",
    "BackgroundRemovalEngine",
    "ConceptEngine",
    "Neural3DEngine",
    "BlenderPipeline"
]


def __getattr__(name: str):
    if name == "enhance_prompt_for_3d":
        from tools.prompt_enhancer import enhance_prompt_for_3d
        return enhance_prompt_for_3d
    if name == "BackgroundRemovalEngine":
        from tools.rembg_engine import BackgroundRemovalEngine
        return BackgroundRemovalEngine
    if name == "ConceptEngine":
        from tools.concept_engine import ConceptEngine
        return ConceptEngine
    if name == "Neural3DEngine":
        from tools.neural_3d_engine import Neural3DEngine
        return Neural3DEngine
    if name == "BlenderPipeline":
        from tools.blender_pipeline import BlenderPipeline
        return BlenderPipeline
    raise AttributeError(f"module 'tools' has no attribute {name!r}")

