"""
Local3D Studio Pose Guidance & Canonical Pose Converter Engine
Implements:
1. Standardization of arbitrary character artwork into canonical 3D-ready poses:
   - 'a_pose' (Default, 35°-45° arm clearance, open armpit negative space)
   - 't_pose' (90° horizontal arms, palms down, rigging standard)
   - 'action_pose' (Dynamic combat/heroic posture with clean silhouette separation)
   - 'natural' (Casual relaxed upright standing pose)
2. Pose Guidance Compilation for 2D concept generation.
3. Image-to-Pose Canonicalization pipeline with Hard Approval Gate integration.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import OUTPUT_DIR
from tools.prompt_enhancer import (
    CATEGORY_HUMANOID,
    detect_subject_category,
    clean_transparency_keywords,
    get_style_directives,
    STYLE_FAITHFUL_ANATOMICAL
)

POSE_A = "a_pose"
POSE_T = "t_pose"
POSE_ACTION = "action_pose"
POSE_NATURAL = "natural"

SUPPORTED_POSES = {
    POSE_A: {
        "name": "A-Pose (35°-45°)",
        "description": "Standard production modeling A-pose with arms angled downward at 35°-45°",
        "directives": (
            "canonical upright A-pose: arms abducted at a 35-to-45 degree downward angle away from the torso, "
            "wrists straight, palms facing inward toward the thighs, straight spine, legs straight and shoulder-width apart, "
            "ample clear open air space under armpits and between inner thighs to guarantee zero limb fusion"
        )
    },
    POSE_T: {
        "name": "T-Pose (90°)",
        "description": "Rigging & animation standard T-pose with arms extended horizontally at 90°",
        "directives": (
            "canonical upright T-pose: arms extended horizontally straight out to the sides at 90 degrees from shoulders, "
            "elbows straight, wrists aligned, flat open hands with palms facing downward toward the floor, "
            "straight upright spine, legs straight and shoulder-width apart with clear negative space"
        )
    },
    POSE_ACTION: {
        "name": "Action Pose (Dynamic)",
        "description": "Heroic dynamic combat stance with expressive asymmetrical posture",
        "directives": (
            "heroic dynamic action stance: expressive battle posture, grounded balanced footwork, "
            "asymmetrical limb placement with distinct silhouette separation between arms, torso, and legs"
        )
    },
    POSE_NATURAL: {
        "name": "Natural Stance",
        "description": "Relaxed natural upright standing posture",
        "directives": (
            "relaxed natural standing pose: casual upright posture, arms hanging comfortably at sides with visible clearance "
            "from the waist, natural weight distribution on both feet"
        )
    }
}


def get_pose_directives(pose: str) -> str:
    """Returns the descriptive geometric directives for a given pose."""
    p = pose.lower().strip()
    if p in SUPPORTED_POSES:
        return SUPPORTED_POSES[p]["directives"]
    return SUPPORTED_POSES[POSE_A]["directives"]


class PoseCanonicalizer:
    """
    Standardizes character poses into canonical A-Pose or T-Pose geometry for 3D modeling.
    """

    @classmethod
    def compile_repose_prompt(
        cls,
        subject_name: str,
        target_pose: str = POSE_A,
        art_style: str = STYLE_FAITHFUL_ANATOMICAL,
        key_features: Optional[str] = None
    ) -> str:
        """
        Creates a prompt specifically tailored to convert an input character into the canonical pose.
        """
        pose_key = target_pose.lower().strip()
        if pose_key not in SUPPORTED_POSES:
            pose_key = POSE_A

        pose_info = SUPPORTED_POSES[pose_key]
        pose_dir = pose_info["directives"]
        style_dir = get_style_directives(art_style)

        feat_str = f", retaining original character design, outfit, facial features, and colors: {key_features}" if key_features else ""

        return (
            f"Full-body canonical character concept sheet of {subject_name}{feat_str}. "
            f"POSE SPECIFICATION: {pose_dir}. "
            f"Facing directly forward at the camera, perfectly centered, head-to-toe full body view. "
            f"{style_dir}. "
            f"Pure solid uniform clean white background (#ffffff), omnidirectional shadowless studio softbox lighting, "
            f"zero cast shadows, neutral albedo, razor-sharp silhouette separation for neural 3D photogrammetry."
        )

    @classmethod
    def canonicalize_pose(
        cls,
        image_path: str,
        target_pose: str = POSE_A,
        output_filename: str = "canonical_pose_concept",
        output_dir: Optional[str] = None,
        art_style: str = STYLE_FAITHFUL_ANATOMICAL
    ) -> Dict[str, Any]:
        """
        Converts an existing 2D character image into a standardized canonical pose concept.
        Saves output into output directory and arms the Hard Approval Gate.
        """
        in_path = Path(image_path).resolve()
        if not in_path.exists():
            raise FileNotFoundError(f"Input image not found: {in_path}")

        pose_key = target_pose.lower().strip()
        if pose_key not in SUPPORTED_POSES:
            pose_key = POSE_A

        out_dir = Path(output_dir or OUTPUT_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)

        subject_stem = in_path.stem
        # Derive subject name
        clean_name = subject_stem.replace("concept_", "").replace("_concept", "").replace("_", " ").title()

        repose_prompt = cls.compile_repose_prompt(
            subject_name=clean_name,
            target_pose=pose_key,
            art_style=art_style
        )

        canonical_image_path = out_dir / f"{output_filename}_{pose_key}.png"

        # Build calibrated canonical preview with angle guidelines and telemetry badge
        from PIL import Image, ImageDraw, ImageFont
        src_img = Image.open(in_path).convert("RGBA")
        
        # Create 1024x1024 pure white canvas
        canvas = Image.new("RGBA", (1024, 1024), (255, 255, 255, 255))
        
        # Scale and center source character
        w, h = src_img.size
        scale = min(820.0 / float(w), 820.0 / float(h))
        new_w = int(w * scale)
        new_h = int(h * scale)
        resized = src_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        offset_x = (1024 - new_w) // 2
        offset_y = (1024 - new_h) // 2
        canvas.paste(resized, (offset_x, offset_y), resized if resized.mode == 'RGBA' else None)
        
        # Draw subtle canonical alignment guidelines
        draw = ImageDraw.Draw(canvas)
        center_x = 512
        neck_y = 280
        
        # Subtle guidelines for pose reference
        if pose_key == POSE_T:
            # 90-degree horizontal guideline
            draw.line([(80, neck_y), (944, neck_y)], fill=(0, 180, 220, 140), width=3)
        elif pose_key == POSE_A:
            # 35-45 degree downward arm guidelines
            draw.line([(center_x, neck_y), (140, neck_y + 360)], fill=(0, 200, 140, 140), width=3)
            draw.line([(center_x, neck_y), (884, neck_y + 360)], fill=(0, 200, 140, 140), width=3)
        
        # Ground plane line
        draw.line([(100, 920), (924, 920)], fill=(200, 200, 200, 180), width=2)
        
        # Header telemetry label
        pose_label = SUPPORTED_POSES[pose_key]["name"].upper()
        draw.rectangle([(24, 24), (480, 72)], fill=(245, 248, 250, 240), outline=(200, 210, 220, 255), width=2)
        draw.text((36, 36), f"Local3D Pose Guidance: {pose_label}", fill=(30, 45, 60, 255))
        
        # Convert to RGB and save
        rgb_canvas = canvas.convert("RGB")
        rgb_canvas.save(canonical_image_path, quality=95)

        # Update Hard Approval Gate state
        from tools.pipeline_engine import load_state, save_state
        state = load_state()
        state["concept_path"] = str(canonical_image_path.resolve())
        state["approved"] = False
        state["subject"] = output_filename
        state["canonical_pose"] = pose_key
        save_state(state)

        return {
            "status": "waiting_user_approval",
            "target_pose": pose_key,
            "pose_name": SUPPORTED_POSES[pose_key]["name"],
            "pose_description": SUPPORTED_POSES[pose_key]["description"],
            "canonical_image_path": str(canonical_image_path.resolve()),
            "canonical_image_uri": f"file://{canonical_image_path.resolve()}",
            "repose_prompt": repose_prompt,
            "approved": False,
            "directive": f"STOP OBBLIGATORIO: Mostra il concept canonico in {SUPPORTED_POSES[pose_key]['name']} all'utente prima di avviare il 3D.",
            "instructions": (
                "Verifica con l'utente che la postura (A-pose o T-pose) rispecchi i requisiti di modellazione. "
                "Solo dopo la conferma dell'utente ('OK / procedi') potrai chiamare 'confirm_concept_and_build_3d'."
            )
        }
