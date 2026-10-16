"""
Local3D Studio Background Removal Engine
Uses rembg (u2net) in pure Python/ONNX to strip backgrounds and replace them
with pure solid white (#ffffff) or transparent alpha.
"""

import os
import sys
from pathlib import Path
from PIL import Image


class BackgroundRemovalEngine:
    _session = None
    _rembg_checked = False
    _rembg_module = None

    @classmethod
    def _get_rembg(cls):
        if not cls._rembg_checked:
            cls._rembg_checked = True
            try:
                import rembg
                cls._rembg_module = rembg
            except ImportError:
                cls._rembg_module = None
        return cls._rembg_module

    @classmethod
    def get_session(cls):
        rembg_mod = cls._get_rembg()
        if cls._session is None and rembg_mod is not None:
            try:
                cls._session = rembg_mod.new_session("u2net")
            except Exception as e:
                print(f"[RembgEngine] Warning: Could not initialize u2net session: {e}", file=sys.stderr)
        return cls._session

    @classmethod
    def remove_background(
        cls,
        image_path: str,
        output_path: str = None,
        replace_with_white: bool = True
    ) -> str:
        """
        Removes background from image. If replace_with_white is True, composites
        the foreground subject on a solid #ffffff canvas, which is mandatory
        for neural 3D reconstruction networks to avoid dark ambient halos.
        """
        image_path = os.path.abspath(image_path)
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Input image not found: {image_path}")

        if output_path is None:
            p = Path(image_path)
            output_path = str(p.parent / f"{p.stem}_rembg.png")

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        input_img = Image.open(image_path).convert("RGBA")
        rembg_mod = cls._get_rembg()

        if rembg_mod is not None:
            session = cls.get_session()
            if session is not None:
                cutout = rembg_mod.remove(input_img, session=session)
            else:
                cutout = rembg_mod.remove(input_img)
        else:
            print("[RembgEngine] rembg not available, using raw image.", file=sys.stderr)
            cutout = input_img

        if replace_with_white:
            # Create pure solid white background
            white_bg = Image.new("RGBA", cutout.size, (255, 255, 255, 255))
            white_bg.paste(cutout, mask=cutout.split()[3])  # use alpha channel as mask
            final_img = white_bg.convert("RGB")
            final_img.save(output_path, "PNG")
        else:
            cutout.save(output_path, "PNG")

        print(f"[RembgEngine] Processed image saved to: {output_path}", file=sys.stderr)
        return output_path
