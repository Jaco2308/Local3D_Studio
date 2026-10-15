"""
Local3D Studio Background Removal Engine
Uses rembg (u2net) in pure Python/ONNX to strip backgrounds and replace them
with pure solid white (#ffffff) or transparent alpha.
"""

import os
from pathlib import Path
from PIL import Image

try:
    import rembg
    _REMBG_AVAILABLE = True
except ImportError:
    _REMBG_AVAILABLE = False


class BackgroundRemovalEngine:
    _session = None

    @classmethod
    def get_session(cls):
        if cls._session is None and _REMBG_AVAILABLE:
            try:
                cls._session = rembg.new_session("u2net")
            except Exception as e:
                print(f"[RembgEngine] Warning: Could not initialize u2net session: {e}")
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

        if _REMBG_AVAILABLE:
            session = cls.get_session()
            if session is not None:
                cutout = rembg.remove(input_img, session=session)
            else:
                cutout = rembg.remove(input_img)
        else:
            print("[RembgEngine] rembg not available, using raw image.")
            cutout = input_img

        if replace_with_white:
            # Create pure solid white background
            white_bg = Image.new("RGBA", cutout.size, (255, 255, 255, 255))
            white_bg.paste(cutout, mask=cutout.split()[3])  # use alpha channel as mask
            final_img = white_bg.convert("RGB")
            final_img.save(output_path, "PNG")
        else:
            cutout.save(output_path, "PNG")

        print(f"[RembgEngine] Processed image saved to: {output_path}")
        return output_path
