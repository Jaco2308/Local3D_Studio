"""
Local3D Studio Worker Client
Communicates with the 3D Compute Worker via HTTP/REST.
Supports seamless execution across localhost and remote Wi-Fi LAN nodes,
with state synchronization, quality mode selection, and pipeline triggering.
"""

import os
import requests
from pathlib import Path
from typing import Dict, Any, Optional

from core.config import WORKER_URL, OUTPUT_DIR
from core.hardware_backend import HardwareManager


class WorkerClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or WORKER_URL).rstrip("/")
        self.is_local = "127.0.0.1" in self.base_url or "localhost" in self.base_url

    def is_alive(self) -> bool:
        """Checks if the compute worker is reachable."""
        try:
            r = requests.get(f"{self.base_url}/health", timeout=3.0)
            return r.status_code == 200
        except Exception:
            return False

    def get_hardware_info(self) -> Dict[str, Any]:
        """Fetches hardware status from worker or local system."""
        try:
            r = requests.get(f"{self.base_url}/api/v1/hardware", timeout=5.0)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        if self.is_local:
            return HardwareManager.get_instance().get_summary()
        return {"status": "unavailable", "worker_url": self.base_url}

    def get_quality_mode(self) -> str:
        """Fetches active quality mode from worker state."""
        try:
            r = requests.get(f"{self.base_url}/api/v1/quality-mode", timeout=3.0)
            if r.status_code == 200:
                return r.json().get("quality_mode", "auto")
        except Exception:
            pass
        return "auto"

    def set_quality_mode(self, mode: str) -> bool:
        """Sets quality mode on worker state."""
        try:
            r = requests.post(f"{self.base_url}/api/set-quality-mode", json={"quality_mode": mode}, timeout=5.0)
            return r.status_code == 200
        except Exception:
            return False

    def get_art_style(self) -> str:
        """Gets current art style from worker state."""
        try:
            r = requests.get(f"{self.base_url}/api/v1/art-style", timeout=5.0)
            if r.status_code == 200:
                return r.json().get("art_style", "faithful_anatomical")
        except Exception:
            pass
        return "faithful_anatomical"

    def set_art_style(self, style: str) -> bool:
        """Sets art style on worker state."""
        try:
            r = requests.post(f"{self.base_url}/api/set-art-style", json={"art_style": style}, timeout=5.0)
            return r.status_code == 200
        except Exception:
            return False

    def enhance_prompt(
        self,
        prompt: str,
        mode: str = "3d_print",
        art_style: str = "faithful_anatomical",
        multiview: bool = True,
        add_pedestal_base: bool = False
    ) -> str:
        """Requests prompt enhancement from worker or local module."""
        try:
            r = requests.post(
                f"{self.base_url}/api/v1/enhance-prompt",
                json={
                    "prompt": prompt,
                    "mode": mode,
                    "art_style": art_style,
                    "multiview": multiview,
                    "add_pedestal_base": add_pedestal_base
                },
                timeout=10.0
            )
            if r.status_code == 200:
                return r.json().get("enhanced_prompt", prompt)
        except Exception:
            pass
        from tools.prompt_enhancer import enhance_prompt_for_3d
        return enhance_prompt_for_3d(
            prompt,
            mode=mode,
            art_style=art_style,
            multiview=multiview,
            add_pedestal_base=add_pedestal_base
        )

    def generate_concept(
        self,
        prompt: str,
        mode: str = "3d_print",
        art_style: str = "faithful_anatomical",
        multiview: bool = True,
        add_pedestal_base: bool = False,
        output_name: str = "concept_latest",
        seed: Optional[int] = None
    ) -> str:
        """Requests 2D concept generation."""
        try:
            r = requests.post(
                f"{self.base_url}/api/v1/generate-concept",
                json={
                    "prompt": prompt,
                    "mode": mode,
                    "art_style": art_style,
                    "multiview": multiview,
                    "add_pedestal_base": add_pedestal_base,
                    "output_name": output_name,
                    "seed": seed
                },
                timeout=180.0
            )
            if r.status_code == 200:
                data = r.json()
                if not self.is_local and "download_url" in data:
                    local_dest = str(OUTPUT_DIR / f"{output_name}.png")
                    self._download_file(data["download_url"], local_dest)
                    return local_dest
                return data.get("concept_path")
        except Exception as e:
            if not self.is_local:
                raise e

        from tools.concept_engine import ConceptEngine
        return ConceptEngine.generate_concept(
            user_prompt=prompt,
            output_path=str(OUTPUT_DIR / f"{output_name}.png"),
            mode=mode,
            art_style=art_style,
            multiview=multiview,
            add_pedestal_base=add_pedestal_base,
            seed=seed
        )

    def image_to_3d(
        self,
        image_path: str,
        output_name: str = "neural_raw",
        tier: Optional[str] = None,
        octree_resolution: Optional[int] = None,
        steps: Optional[int] = None
    ) -> str:
        """Sends image to worker for Image-to-3D neural reconstruction."""
        image_path = os.path.abspath(image_path)
        try:
            if not self.is_local:
                with open(image_path, "rb") as f:
                    up_r = requests.post(f"{self.base_url}/api/v1/upload-image", files={"file": f}, timeout=60.0)
                remote_image_path = up_r.json().get("file_path")
            else:
                remote_image_path = image_path

            payload = {
                "image_path": remote_image_path,
                "output_name": output_name,
                "tier": tier,
                "octree_resolution": octree_resolution,
                "steps": steps
            }
            r = requests.post(
                f"{self.base_url}/api/v1/image-to-3d",
                json=payload,
                timeout=300.0
            )
            if r.status_code == 200:
                data = r.json()
                if not self.is_local and "download_url" in data:
                    local_glb = str(OUTPUT_DIR / f"{output_name}.glb")
                    self._download_file(data["download_url"], local_glb)
                    return local_glb
                return data.get("glb_path")
        except Exception as e:
            if not self.is_local:
                raise e

        from tools.neural_3d_engine import Neural3DEngine
        return Neural3DEngine.generate_glb(
            image_path=image_path,
            output_glb_path=str(OUTPUT_DIR / f"{output_name}.glb"),
            tier=tier,
            octree_resolution=octree_resolution,
            num_inference_steps=steps
        )

    def postprocess(
        self,
        input_glb_path: str,
        target_height_mm: float = 100.0,
        target_triangles: Optional[int] = None,
        voxel_size: Optional[float] = None,
        smooth_iterations: int = 5,
        smooth_factor: float = 0.35,
        add_pedestal: bool = False,
        output_name: str = "production_model"
    ) -> Dict[str, Any]:
        """Runs the standardized Blender post-processing pipeline."""
        input_glb_path = os.path.abspath(input_glb_path)
        try:
            if not self.is_local:
                with open(input_glb_path, "rb") as f:
                    up_r = requests.post(f"{self.base_url}/api/v1/upload-image", files={"file": f}, timeout=120.0)
                remote_glb_path = up_r.json().get("file_path")
            else:
                remote_glb_path = input_glb_path

            payload = {
                "input_glb_path": remote_glb_path,
                "target_height_mm": target_height_mm,
                "target_triangles": target_triangles,
                "voxel_size": voxel_size,
                "smooth_iterations": smooth_iterations,
                "smooth_factor": smooth_factor,
                "add_pedestal": add_pedestal,
                "output_name": output_name
            }
            r = requests.post(f"{self.base_url}/api/v1/postprocess", json=payload, timeout=300.0)
            if r.status_code == 200:
                data = r.json()
                if not self.is_local:
                    local_stl = str(OUTPUT_DIR / f"{output_name}.stl")
                    local_glb = str(OUTPUT_DIR / f"{output_name}.glb")
                    local_sheet = str(OUTPUT_DIR / f"{output_name}_lookdev_sheet.png")

                    if "stl_download_url" in data:
                        self._download_file(data["stl_download_url"], local_stl)
                        data["stl_path"] = local_stl
                    if "glb_download_url" in data:
                        self._download_file(data["glb_download_url"], local_glb)
                        data["glb_path"] = local_glb
                    if "lookdev_download_url" in data:
                        self._download_file(data["lookdev_download_url"], local_sheet)
                        data["lookdev_sheet_path"] = local_sheet

                return data
        except Exception as e:
            if not self.is_local:
                raise e

        from tools.blender_pipeline import BlenderPipeline
        return BlenderPipeline.process_and_export(
            input_glb_path=input_glb_path,
            target_height_mm=target_height_mm,
            target_triangles=target_triangles,
            voxel_size=voxel_size,
            smooth_iterations=smooth_iterations,
            smooth_factor=smooth_factor,
            add_pedestal=add_pedestal,
            output_name=output_name
        )

    def run_pipeline(
        self,
        image_path: str,
        output_name: str = "production_model",
        quality_preset: Optional[str] = None,
        target_height_mm: float = 100.0,
        add_pedestal: bool = False,
        art_style: str = "faithful_anatomical"
    ) -> Dict[str, Any]:
        """Invokes the end-to-end 3D production pipeline via worker."""
        image_path = os.path.abspath(image_path)
        try:
            if not self.is_local:
                with open(image_path, "rb") as f:
                    up_r = requests.post(f"{self.base_url}/api/v1/upload-image", files={"file": f}, timeout=60.0)
                remote_img = up_r.json().get("file_path")
            else:
                remote_img = image_path

            payload = {
                "image_path": remote_img,
                "output_name": output_name,
                "quality_preset": quality_preset,
                "target_height_mm": target_height_mm,
                "add_pedestal": add_pedestal,
                "art_style": art_style
            }
            r = requests.post(f"{self.base_url}/api/v1/pipeline", json=payload, timeout=600.0)
            if r.status_code == 200:
                data = r.json()
                if not self.is_local:
                    local_stl = str(OUTPUT_DIR / f"{output_name}.stl")
                    local_glb = str(OUTPUT_DIR / f"{output_name}.glb")
                    local_sheet = str(OUTPUT_DIR / f"{output_name}_lookdev_sheet.png")

                    if "stl_download_url" in data:
                        self._download_file(data["stl_download_url"], local_stl)
                        data["stl_path"] = local_stl
                    if "glb_download_url" in data:
                        self._download_file(data["glb_download_url"], local_glb)
                        data["glb_path"] = local_glb
                    if "lookdev_sheet_path" in data and "files" in data.get("lookdev_sheet_path", ""):
                        self._download_file(f"/api/v1/files/{Path(data['lookdev_sheet_path']).name}", local_sheet)
                        data["lookdev_sheet_path"] = local_sheet

                return data
        except Exception as e:
            if not self.is_local:
                raise e

        # Local in-process fallback
        raw_glb = self.image_to_3d(image_path=image_path, output_name=f"{output_name}_raw")
        return self.postprocess(
            input_glb_path=raw_glb,
            target_height_mm=target_height_mm,
            add_pedestal=add_pedestal,
            output_name=output_name
        )

    def recalculate(self, quality_preset: str = "ultra_production", output_name: Optional[str] = None) -> Dict[str, Any]:
        """Calls recalculate endpoint on worker."""
        payload = {"quality_preset": quality_preset}
        if output_name:
            payload["output_name"] = output_name
        r = requests.post(f"{self.base_url}/api/recalculate", json=payload, timeout=600.0)
        r.raise_for_status()
        return r.json()

    def direct_image_to_3d(
        self,
        image_path: str,
        output_name: str = "direct_model",
        quality_preset: Optional[str] = "auto",
        generation_strategy: Optional[str] = "single_hero_34",
        add_pedestal: bool = False,
        target_height_mm: float = 100.0,
        art_style: str = "faithful_anatomical"
    ) -> Dict[str, Any]:
        """Calls direct image-to-3d endpoint bypassing 2D text generation."""
        image_path = os.path.abspath(image_path)
        payload = {
            "image_path": image_path,
            "output_name": output_name,
            "quality_preset": quality_preset or "auto",
            "generation_strategy": generation_strategy or "single_hero_34",
            "add_pedestal": str(add_pedestal).lower(),
            "target_height_mm": str(target_height_mm),
            "art_style": art_style
        }
        r = requests.post(f"{self.base_url}/api/v1/direct-image-to-3d", data=payload, timeout=600.0)
        r.raise_for_status()
        return r.json()

    def retopologize(
        self,
        input_mesh_path: Optional[str] = None,
        output_name: str = "retopo_model",
        mode: str = "quad",
        target_count: int = 10000
    ) -> Dict[str, Any]:
        """Calls retopology endpoint on worker."""
        payload = {
            "input_mesh_path": os.path.abspath(input_mesh_path) if input_mesh_path else None,
            "output_name": output_name,
            "mode": mode,
            "target_count": target_count
        }
        r = requests.post(f"{self.base_url}/api/v1/retopologize", json=payload, timeout=300.0)
        r.raise_for_status()
        return r.json()

    def bake_textures(
        self,
        input_mesh_path: Optional[str] = None,
        output_name: str = "pbr_model",
        texture_resolution: int = 2048,
        bake_normal: bool = True,
        bake_ao: bool = True
    ) -> Dict[str, Any]:
        """Calls PBR texture baking endpoint on worker."""
        payload = {
            "input_mesh_path": os.path.abspath(input_mesh_path) if input_mesh_path else None,
            "output_name": output_name,
            "texture_resolution": texture_resolution,
            "bake_normal": bake_normal,
            "bake_ao": bake_ao
        }
        r = requests.post(f"{self.base_url}/api/v1/bake-textures", json=payload, timeout=300.0)
        r.raise_for_status()
        return r.json()


    def _download_file(self, relative_url: str, local_destination: str):
        url = f"{self.base_url}/{relative_url.lstrip('/')}"
        r = requests.get(url, stream=True, timeout=120.0)
        r.raise_for_status()
        with open(local_destination, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
