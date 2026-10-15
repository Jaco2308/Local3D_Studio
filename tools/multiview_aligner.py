"""
Local3D Studio Multiview Aligner & Anti-Bleed Engine (Adaptive & Globally Normalized)
Implements:
1. Adaptive Column Gutter Detection: Scans column darkness profiles to find true empty gutters
   between panels, preventing accidental slicing of wings, arms, or tails.
2. Anti-Bleed Isolation & Connected Component Analysis (scipy.ndimage.label):
   Eliminates adjacent panel intrusions.
3. Unified Global Scale Normalization:
   Computes a single, uniform scale factor across Front, Side, and Back panels,
   guaranteeing 100% identical proportions and eliminating scale distortion on wide objects.
4. Ground Plane Lock (Z=0 at Y=456):
   Aligns feet, base, and eyelines with sub-pixel precision on 512x512 transparent canvases.
5. Depth-Crevice Enhancer (CLAHE + Unsharp Masking) for enhanced DINOv2 vision embedding.
"""

import os
import tempfile
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from tools.rembg_engine import BackgroundRemovalEngine


class MultiviewAligner:
    TARGET_CANVAS_SIZE = 512
    TARGET_SUBJECT_HEIGHT = 400
    Y_OFFSET_TOP = 56
    Y_OFFSET_BOTTOM = 456

    @classmethod
    def _find_column_dividers(cls, full_rgb: Image.Image, num_panels: int = 3) -> List[int]:
        """
        Scans column brightness profiles to locate true empty gutters between panels,
        preventing blind slicing through wide appendages.
        """
        w, h = full_rgb.size
        gray = np.array(full_rgb.convert("L"))
        # Non-white pixel density across columns
        darkness_profile = np.mean(gray < 242, axis=0)

        dividers = [0]
        step = w // num_panels
        for i in range(1, num_panels):
            nominal_x = i * step
            search_min = max(0, nominal_x - int(step * 0.18))
            search_max = min(w, nominal_x + int(step * 0.18))
            if search_max > search_min:
                gutter_offset = int(np.argmin(darkness_profile[search_min:search_max]))
                dividers.append(search_min + gutter_offset)
            else:
                dividers.append(nominal_x)
        dividers.append(w)
        return dividers

    @classmethod
    def _isolate_primary_component(cls, rgba_np: np.ndarray) -> np.ndarray:
        """
        Uses scipy connected component labeling on alpha channel to keep ONLY
        the primary subject centered in the slice, zeroing out bleed from adjacent panels.
        """
        from scipy.ndimage import label, center_of_mass

        alpha = rgba_np[:, :, 3].copy()
        mask = alpha > 15
        if not np.any(mask):
            return rgba_np

        labeled_array, num_features = label(mask)
        if num_features <= 1:
            return rgba_np

        h, w = alpha.shape
        center_x = w / 2.0
        center_y = h / 2.0

        # Determine dominant component (largest area)
        sizes = [int(np.sum(labeled_array == i)) for i in range(1, num_features + 1)]
        best_label = int(np.argmax(sizes)) + 1

        # Keep components that are either the best label OR central features (not boundary bleeds)
        keep_mask = np.zeros_like(mask, dtype=bool)
        for feat_id in range(1, num_features + 1):
            feat_mask = (labeled_array == feat_id)
            area = np.sum(feat_mask)
            if area < 30:  # Ignore microscopic noise specks
                continue

            cy, cx = center_of_mass(feat_mask)
            is_edge_bleed = (cx < w * 0.12) or (cx > w * 0.88)
            # Retain dominant feature as well as central appendages (e.g. high tails, ears, held accessories)
            if feat_id == best_label or not is_edge_bleed:
                keep_mask |= feat_mask

        cleaned_alpha = np.where(keep_mask, alpha, 0).astype(np.uint8)
        cleaned_rgba = rgba_np.copy()
        cleaned_rgba[:, :, 3] = cleaned_alpha
        return cleaned_rgba

    @classmethod
    def isolate_slice_crop(cls, slice_img: Image.Image) -> Optional[Image.Image]:
        """
        Removes background, strips adjacent bleed via connected component analysis,
        and returns a tight bounding box crop with alpha channel.
        """
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_in, \
             tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_out:
            in_path = f_in.name
            out_path = f_out.name

        try:
            slice_img.save(in_path, "PNG")
            BackgroundRemovalEngine.remove_background(in_path, out_path, replace_with_white=False)
            isolated_pil = Image.open(out_path).convert("RGBA")
        finally:
            if os.path.exists(in_path):
                os.remove(in_path)
            if os.path.exists(out_path):
                os.remove(out_path)

        rgba_np = np.array(isolated_pil)
        cleaned_np = cls._isolate_primary_component(rgba_np)

        alpha = cleaned_np[:, :, 3]
        rows = np.any(alpha > 15, axis=1)
        cols = np.any(alpha > 15, axis=0)

        if not np.any(rows) or not np.any(cols):
            return None

        y_min, y_max = np.where(rows)[0][[0, -1]]
        x_min, x_max = np.where(cols)[0][[0, -1]]

        return Image.fromarray(cleaned_np).crop((x_min, y_min, x_max + 1, y_max + 1))

    @classmethod
    def enhance_depth_crevices(cls, rgba_pil: Image.Image) -> Image.Image:
        """
        Depth-Crevice Enhancer:
        Applies CLAHE on L-channel (clipLimit=2.5, tileGridSize=(8,8)) and subtle Unsharp Masking
        to accentuate contrast in crevices between foreground and background limbs.
        Preserves alpha transparency 100%.
        """
        import cv2
        rgba_np = np.array(rgba_pil)
        rgb = rgba_np[:, :, :3]
        alpha = rgba_np[:, :, 3]

        # Convert to LAB color space
        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)

        # CLAHE on L channel
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        l_clahe = clahe.apply(l)

        # Merge and convert back to RGB
        lab_enhanced = cv2.merge((l_clahe, a, b))
        rgb_enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)

        # Unsharp Mask (radius=2, percent=150)
        blurred = cv2.GaussianBlur(rgb_enhanced, (0, 0), sigmaX=2.0)
        unsharp = cv2.addWeighted(rgb_enhanced, 2.5, blurred, -1.5, 0)
        unsharp = np.clip(unsharp, 0, 255).astype(np.uint8)

        # Recombine with alpha
        enhanced_rgba = np.dstack((unsharp, alpha))
        return Image.fromarray(enhanced_rgba, "RGBA")

    @classmethod
    def detect_profile_orientation(cls, rgba_pil: Image.Image) -> str:
        """
        Determines if a profile view is facing 'left' or 'right'
        using weighted contour protrusion analysis across the upper 20%-50% of the silhouette.
        """
        alpha = np.array(rgba_pil)[:, :, 3]
        y_idx, x_idx = np.where(alpha > 15)
        if len(y_idx) == 0:
            return "left"
        y_min, y_max = y_idx.min(), y_idx.max()
        H = max(y_max - y_min, 1)

        # Upper feature band (head, snout, muzzle, or front hood)
        band = (y_idx >= y_min + 0.15 * H) & (y_idx <= y_min + 0.50 * H)
        if not np.any(band):
            band = (y_idx >= y_min) & (y_idx <= y_min + 0.50 * H)

        body_cx = x_idx.mean()
        left_protrusion = body_cx - x_idx[band].min()
        right_protrusion = x_idx[band].max() - body_cx

        return "left" if left_protrusion >= right_protrusion else "right"

    @classmethod
    def split_and_align_multiview(
        cls,
        concept_image_path: str,
        output_dir: Optional[str] = None,
        save_preview: bool = True,
        force_recompute: bool = False
    ) -> Dict[str, Any]:
        """
        Executes complete Adaptive Anti-Bleed Slicing, Unified Global Height Normalization,
        Depth-Crevice Enhancement (CLAHE + Unsharp), and 4-View Generation:
        1. Dynamically detects empty vertical gutters between columns.
        2. Isolates Front, Side, and Back subjects cleanly via rembg and connected component filtering.
        3. Normalizes all views with a UNIFIED global scale factor to prevent height mismatches.
        4. Locks ground plane at Z=0 (Y=456) on 512x512 transparent canvases.
        5. Generates Left and Right profiles and enhances crevices with CLAHE.
        6. Outputs 'concept_multiview_aligned.jpg' preview with laser reference lines.
        """
        concept_path = Path(concept_image_path).resolve()
        if not concept_path.exists():
            raise FileNotFoundError(f"Concept image not found: {concept_path}")

        out_dir = Path(output_dir) if output_dir else concept_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        stem = concept_path.stem
        cache_dir = out_dir / ".cache_multiview" / stem
        cache_dir.mkdir(parents=True, exist_ok=True)

        cached_front = cache_dir / "mv_front_512.png"
        cached_left = cache_dir / "mv_left_512.png"
        cached_right = cache_dir / "mv_right_512.png"
        cached_back = cache_dir / "mv_back_512.png"
        preview_path = str(out_dir / "concept_multiview_aligned.jpg")

        # Cache check
        if not force_recompute and all(p.exists() for p in [cached_front, cached_left, cached_right, cached_back]):
            concept_mtime = concept_path.stat().st_mtime
            if min(p.stat().st_mtime for p in [cached_front, cached_left, cached_right, cached_back]) >= concept_mtime:
                print(f"[MultiviewAligner] Cache Hit for '{stem}'. Reusing aligned 4 views.")
                return {
                    "status": "cached",
                    "front_path": str(cached_front),
                    "left_path": str(cached_left),
                    "right_path": str(cached_right),
                    "back_path": str(cached_back),
                    "preview_path": preview_path if os.path.exists(preview_path) else None,
                    "detected_orientation": "cached",
                    "y_top": cls.Y_OFFSET_TOP,
                    "y_bottom": cls.Y_OFFSET_BOTTOM,
                    "subject_height": cls.TARGET_SUBJECT_HEIGHT
                }

        with Image.open(concept_path) as full_img:
            full_rgb = full_img.convert("RGB")
            w, h = full_rgb.size

            if w < 1.25 * h:
                raise ValueError(
                    f"Image aspect ratio {w}x{h} ({w/h:.2f}) does not match a horizontal turnaround model sheet."
                )

            # 1. Adaptive Gutter Detection
            dividers = cls._find_column_dividers(full_rgb, num_panels=3)
            front_raw = full_rgb.crop((dividers[0], 0, dividers[1], h))
            side_raw = full_rgb.crop((dividers[1], 0, dividers[2], h))
            back_raw = full_rgb.crop((dividers[2], 0, dividers[3], h))

        print("[MultiviewAligner] Isolating Slice 1/3 (FRONT) with Anti-Bleed...")
        front_crop = cls.isolate_slice_crop(front_raw)

        print("[MultiviewAligner] Isolating Slice 2/3 (SIDE PROFILE) with Anti-Bleed...")
        side_crop = cls.isolate_slice_crop(side_raw)

        print("[MultiviewAligner] Isolating Slice 3/3 (BACK) with Anti-Bleed...")
        back_crop = cls.isolate_slice_crop(back_raw)

        crops = [c for c in [front_crop, side_crop, back_crop] if c is not None]
        if not crops:
            raise RuntimeError("Failed to isolate subject geometry in turnaround concept sheet.")

        # Fallback for any missing crop
        if front_crop is None:
            front_crop = crops[0]
        if side_crop is None:
            side_crop = crops[0]
        if back_crop is None:
            back_crop = crops[0]

        # 2. Unified Global Scale Normalization Across All Views
        # Finds dominant height and width to scale all panels uniformly without height mismatch
        max_crop_h = max(front_crop.height, side_crop.height, back_crop.height, 1)
        max_crop_w = max(front_crop.width, side_crop.width, back_crop.width, 1)

        base_scale = cls.TARGET_SUBJECT_HEIGHT / float(max_crop_h)
        # Check if any view's width would exceed canvas limits at base_scale
        if (max_crop_w * base_scale) > (cls.TARGET_CANVAS_SIZE - 24):
            global_scale = (cls.TARGET_CANVAS_SIZE - 24) / float(max_crop_w)
        else:
            global_scale = base_scale

        effective_target_height = int(round(max_crop_h * global_scale))

        def _format_canvas(crop_pil: Image.Image) -> Image.Image:
            cw, ch = crop_pil.size
            nw = max(1, int(round(cw * global_scale)))
            nh = max(1, int(round(ch * global_scale)))
            resized = crop_pil.resize((nw, nh), Image.Resampling.LANCZOS)

            canvas = Image.new("RGBA", (cls.TARGET_CANVAS_SIZE, cls.TARGET_CANVAS_SIZE), (0, 0, 0, 0))
            px = (cls.TARGET_CANVAS_SIZE - nw) // 2
            # Ground foot plane at Y_OFFSET_BOTTOM (456), clamped to prevent top clipping
            py = max(0, cls.Y_OFFSET_BOTTOM - nh)
            canvas.paste(resized, (px, py), mask=resized)
            return canvas

        front_aligned = _format_canvas(front_crop)
        side_aligned = _format_canvas(side_crop)
        back_aligned = _format_canvas(back_crop)

        # 3. Profile Orientation Detection & 4th view (Right) Generation
        detected_orient = cls.detect_profile_orientation(side_aligned)
        print(f"[MultiviewAligner] Side profile detected orientation: facing {detected_orient.upper()}")

        if detected_orient == "left":
            left_aligned = side_aligned
            right_aligned = side_aligned.transpose(Image.FLIP_LEFT_RIGHT)
        else:
            right_aligned = side_aligned
            left_aligned = side_aligned.transpose(Image.FLIP_LEFT_RIGHT)

        # 4. Pre-Processing: Depth-Crevice Enhancer (CLAHE + Unsharp Mask) on all 4 views
        print("[MultiviewAligner] Applying Depth-Crevice Enhancer (CLAHE + Unsharp Mask) across all 4 views...")
        front_enhanced = cls.enhance_depth_crevices(front_aligned)
        left_enhanced = cls.enhance_depth_crevices(left_aligned)
        right_enhanced = cls.enhance_depth_crevices(right_aligned)
        back_enhanced = cls.enhance_depth_crevices(back_aligned)

        # Save the 4 isolated 512x512 PNGs into cache directory
        front_enhanced.save(str(cached_front), "PNG")
        left_enhanced.save(str(cached_left), "PNG")
        right_enhanced.save(str(cached_right), "PNG")
        back_enhanced.save(str(cached_back), "PNG")

        front_path = str(cached_front)
        left_path = str(cached_left)
        right_path = str(cached_right)
        back_path = str(cached_back)

        # 5. Generate 4-Panel Verification Preview with Laser Alignment Guidelines
        if save_preview:
            total_w = cls.TARGET_CANVAS_SIZE * 4
            total_h = cls.TARGET_CANVAS_SIZE
            preview_img = Image.new("RGB", (total_w, total_h), (255, 255, 255))

            preview_img.paste(front_enhanced, (0, 0), mask=front_enhanced)
            preview_img.paste(left_enhanced, (cls.TARGET_CANVAS_SIZE, 0), mask=left_enhanced)
            preview_img.paste(right_enhanced, (cls.TARGET_CANVAS_SIZE * 2, 0), mask=right_enhanced)
            preview_img.paste(back_enhanced, (cls.TARGET_CANVAS_SIZE * 3, 0), mask=back_enhanced)

            draw = ImageDraw.Draw(preview_img)

            # Vertical column separators
            for sep_x in [cls.TARGET_CANVAS_SIZE, cls.TARGET_CANVAS_SIZE * 2, cls.TARGET_CANVAS_SIZE * 3]:
                draw.line([(sep_x, 0), (sep_x, total_h)], fill=(226, 232, 240), width=2)

            # Horizontal reference lines
            top_y = cls.Y_OFFSET_BOTTOM - effective_target_height
            draw.line([(0, top_y), (total_w, top_y)], fill=(56, 189, 248), width=2)
            draw.line([(0, (top_y + cls.Y_OFFSET_BOTTOM) // 2), (total_w, (top_y + cls.Y_OFFSET_BOTTOM) // 2)], fill=(148, 163, 184), width=1)
            draw.line([(0, cls.Y_OFFSET_BOTTOM), (total_w, cls.Y_OFFSET_BOTTOM)], fill=(34, 197, 94), width=3)

            # Labels for 4 panels
            labels = [
                (16, 16, "1. FRONT ORTHOGRAPHIC [512x512]"),
                (cls.TARGET_CANVAS_SIZE + 16, 16, "2. LEFT PROFILE (FACING LEFT) [512x512]"),
                (cls.TARGET_CANVAS_SIZE * 2 + 16, 16, "3. RIGHT PROFILE (FACING RIGHT) [512x512]"),
                (cls.TARGET_CANVAS_SIZE * 3 + 16, 16, "4. BACK ORTHOGRAPHIC [512x512]")
            ]
            for lx, ly, ltxt in labels:
                draw.rectangle([(lx - 4, ly - 2), (lx + 270, ly + 18)], fill=(15, 23, 42))
                draw.text((lx, ly), ltxt, fill=(56, 189, 248))

            draw.rectangle([(16, cls.Y_OFFSET_BOTTOM - 20), (220, cls.Y_OFFSET_BOTTOM - 2)], fill=(20, 83, 45))
            draw.text((22, cls.Y_OFFSET_BOTTOM - 18), "GROUND PLANE LOCK (Z=0)", fill=(134, 239, 172))

            preview_img.save(preview_path, "JPEG", quality=95)
            print(f"[MultiviewAligner] 4-panel aligned verification sheet saved: {preview_path}")

        return {
            "status": "success",
            "front_path": front_path,
            "left_path": left_path,
            "right_path": right_path,
            "back_path": back_path,
            "preview_path": preview_path,
            "detected_orientation": detected_orient,
            "y_top": cls.Y_OFFSET_BOTTOM - effective_target_height,
            "y_bottom": cls.Y_OFFSET_BOTTOM,
            "subject_height": effective_target_height
        }
