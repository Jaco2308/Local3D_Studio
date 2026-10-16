"""
Local3D Studio Model Splitter Engine (Multi-Part Assembly & Keyed 3D Printing)
Implements:
1. Intelligent Hierarchical Anatomical Model Segmentation (Humanoids, Quadrupeds, Props, Generic).
2. Watertight Manifold Capping on all cut boundaries (bpy.ops.mesh.bisect + fill_holes).
3. Registration Keying (Male Pegs & Female Sockets with 0.25mm 3D printing clearance).
4. Multi-Part STL Export, Multi-Object 3MF for Bambu Studio / OrcaSlicer (AMS Multi-Color).
5. Exploded View LookDev Sheet Rendering & GLB Assembly Export.
"""

import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import OUTPUT_DIR
from core.hardware_backend import HardwareManager
from tools.prompt_enhancer import detect_subject_category


_SPLITTER_BLENDER_SCRIPT = r"""
import bpy
import bmesh
from mathutils import Vector
import os
import sys
import json
import math
import shutil

def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def setup_studio_lighting():
    world = bpy.data.worlds.new(name="World")
    bpy.context.scene.world = world

    # Key light
    key_data = bpy.data.lights.new(name="KeyLight", type='SUN')
    key_data.energy = 3.5
    key_obj = bpy.data.objects.new(name="KeyLight", object_data=key_data)
    bpy.context.collection.objects.link(key_obj)
    key_obj.rotation_euler = (math.radians(45), math.radians(20), math.radians(35))

    # Fill light
    fill_data = bpy.data.lights.new(name="FillLight", type='SUN')
    fill_data.energy = 2.2
    fill_obj = bpy.data.objects.new(name="FillLight", object_data=fill_data)
    bpy.context.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(30), math.radians(-40), math.radians(-120))

    # Rim light
    rim_data = bpy.data.lights.new(name="RimLight", type='SUN')
    rim_data.energy = 2.5
    rim_obj = bpy.data.objects.new(name="RimLight", object_data=rim_data)
    bpy.context.collection.objects.link(rim_obj)
    rim_obj.rotation_euler = (math.radians(40), 0, math.radians(150))

def create_pastel_material(name, rgba):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = 0.40
    return mat

def get_bbox(obj):
    coords = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)

def slice_and_cap(obj, plane_co, plane_no, keep_outer=True):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.005)
    bpy.ops.mesh.bisect(
        plane_co=plane_co,
        plane_no=plane_no,
        clear_inner=keep_outer,
        clear_outer=not keep_outer
    )
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.fill_holes(sides=0)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

def add_peg_connector(obj, location, normal, radius=0.15, length=0.45):
    cyl = None
    try:
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.mesh.primitive_cylinder_add(
            radius=radius,
            depth=length,
            location=location
        )
        cyl = bpy.context.active_object
        up = Vector((0, 0, 1))
        norm = normal.normalized()
        if norm.length > 0.01:
            rot_axis = up.cross(norm)
            if rot_axis.length > 0.001:
                rot_axis.normalize()
                rot_angle = up.angle(norm)
                cyl.rotation_mode = 'AXIS_ANGLE'
                cyl.rotation_axis_angle = (rot_angle, rot_axis.x, rot_axis.y, rot_axis.z)
            elif up.dot(norm) < -0.9:
                cyl.rotation_mode = 'AXIS_ANGLE'
                cyl.rotation_axis_angle = (3.14159, 1, 0, 0)
        
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new(name="PegUnion", type='BOOLEAN')
        mod.object = cyl
        mod.operation = 'UNION'
        bpy.ops.object.modifier_apply(modifier="PegUnion")
    except Exception as ex:
        print(f"[ModelSplitter] Note adding peg: {ex}")
    finally:
        if cyl and cyl.name in bpy.data.objects:
            bpy.data.objects.remove(cyl, do_unlink=True)

def add_socket_connector(obj, location, normal, radius=0.18, length=0.50):
    cyl = None
    try:
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.mesh.primitive_cylinder_add(
            radius=radius,
            depth=length,
            location=location
        )
        cyl = bpy.context.active_object
        up = Vector((0, 0, 1))
        norm = normal.normalized()
        if norm.length > 0.01:
            rot_axis = up.cross(norm)
            if rot_axis.length > 0.001:
                rot_axis.normalize()
                rot_angle = up.angle(norm)
                cyl.rotation_mode = 'AXIS_ANGLE'
                cyl.rotation_axis_angle = (rot_angle, rot_axis.x, rot_axis.y, rot_axis.z)
            elif up.dot(norm) < -0.9:
                cyl.rotation_mode = 'AXIS_ANGLE'
                cyl.rotation_axis_angle = (3.14159, 1, 0, 0)
        
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new(name="SocketDiff", type='BOOLEAN')
        mod.object = cyl
        mod.operation = 'DIFFERENCE'
        bpy.ops.object.modifier_apply(modifier="SocketDiff")
    except Exception as ex:
        print(f"[ModelSplitter] Note adding socket: {ex}")
    finally:
        if cyl and cyl.name in bpy.data.objects:
            bpy.data.objects.remove(cyl, do_unlink=True)

def main():
    config_path = os.environ.get("LOCAL3D_SPLIT_CONFIG")
    if not config_path or not os.path.exists(config_path):
        print("ERROR: LOCAL3D_SPLIT_CONFIG not found", file=sys.stderr)
        sys.exit(1)

    with open(config_path, "r") as f:
        cfg = json.load(f)

    input_mesh = cfg["input_mesh"]
    output_dir = cfg["output_dir"]
    output_name = cfg["output_name"]
    category = cfg.get("category", "generic")
    add_connectors = cfg.get("add_connectors", True)

    clean_scene()
    os.makedirs(output_dir, exist_ok=True)
    parts_dir = os.path.join(output_dir, f"{output_name}_parts")
    if os.path.exists(parts_dir):
        shutil.rmtree(parts_dir, ignore_errors=True)
    os.makedirs(parts_dir, exist_ok=True)

    # Import base model
    ext = input_mesh.lower().split('.')[-1]
    if ext == 'stl':
        bpy.ops.wm.stl_import(filepath=input_mesh)
    elif ext in ['glb', 'gltf']:
        bpy.ops.import_scene.gltf(filepath=input_mesh)
    else:
        print(f"ERROR: Unsupported format {ext}", file=sys.stderr)
        sys.exit(1)

    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not meshes:
        print("ERROR: No mesh found after import", file=sys.stderr)
        sys.exit(1)

    bpy.ops.object.select_all(action='DESELECT')
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()

    main_obj = bpy.context.active_object
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    min_x, max_x, min_y, max_y, min_z, max_z = get_bbox(main_obj)
    dx = max_x - min_x
    dy = max_y - min_y
    dz = max_z - min_z
    mid_x = (min_x + max_x) / 2.0
    mid_y = (min_y + max_y) / 2.0
    mid_z = (min_z + max_z) / 2.0

    unit_per_mm = 0.1 if dz <= 25.0 else 1.0
    connector_r = (cfg.get("connector_radius", 1.5) * 2.0 * unit_per_mm) / 2.0
    connector_len = cfg.get("connector_radius", 1.5) * 2.0 * unit_per_mm * 1.5
    socket_r = connector_r + (0.25 * unit_per_mm)
    exploded_dist = cfg.get("exploded_distance", 15.0) * unit_per_mm

    print(f"[ModelSplitter] Model dimensions: dx={dx:.2f}, dy={dy:.2f}, dz={dz:.2f}, category={category}, unit_per_mm={unit_per_mm}")

    # Meshy-style pastel color palette
    palette = [
        ("Red", (0.92, 0.35, 0.35, 1.0)),
        ("LightGreen", (0.65, 0.88, 0.58, 1.0)),
        ("Beige", (0.90, 0.88, 0.72, 1.0)),
        ("Violet", (0.80, 0.60, 0.85, 1.0)),
        ("Green", (0.45, 0.75, 0.45, 1.0)),
        ("Purple", (0.70, 0.45, 0.80, 1.0)),
        ("Cyan", (0.40, 0.75, 0.85, 1.0)),
        ("Blue", (0.35, 0.55, 0.88, 1.0)),
    ]

    pieces = []

    # Helper function to duplicate and slice cleanly
    def extract_slice(parent_obj, name, plane_co, plane_no, keep_outer, expl_vec, custom_conn_pos=None):
        bpy.ops.object.select_all(action='DESELECT')
        parent_obj.select_set(True)
        bpy.context.view_layer.objects.active = parent_obj
        bpy.ops.object.duplicate()
        piece = bpy.context.active_object
        piece.name = f"{output_name}_{name}"
        
        slice_and_cap(piece, plane_co, plane_no, keep_outer=keep_outer)
        slice_and_cap(parent_obj, plane_co, plane_no, keep_outer=not keep_outer)
        
        if len(piece.data.vertices) >= 50:
            if add_connectors and len(parent_obj.data.vertices) > 100:
                conn_dir = plane_no if keep_outer else -plane_no
                c_pos = custom_conn_pos if custom_conn_pos is not None else plane_co
                add_peg_connector(piece, c_pos, -conn_dir, radius=connector_r, length=connector_len)
                add_socket_connector(parent_obj, c_pos, conn_dir, radius=socket_r, length=connector_len * 1.15)
            
            c_name, rgba = palette[len(pieces) % len(palette)]
            mat = create_pastel_material(f"Mat_{name}_{c_name}", rgba)
            piece.data.materials.clear()
            piece.data.materials.append(mat)
            pieces.append((name, piece, expl_vec, rgba))
            return piece
        else:
            bpy.data.objects.remove(piece, do_unlink=True)
            return None

    # HIERARCHICAL SEGMENTATION
    if category in ["humanoid_biped", "humanoid"]:
        neck_z = min_z + 0.74 * dz
        waist_z = min_z + 0.46 * dz
        shoulder_z = min_z + 0.62 * dz

        # 1. Head
        extract_slice(main_obj, "Head", Vector((mid_x, mid_y, neck_z)), Vector((0, 0, 1)), keep_outer=True, expl_vec=Vector((0, 0, exploded_dist * 1.2)))

        # 2. Duplicate lower body for legs
        bpy.ops.object.select_all(action='DESELECT')
        main_obj.select_set(True)
        bpy.context.view_layer.objects.active = main_obj
        bpy.ops.object.duplicate()
        lower_body = bpy.context.active_object
        lower_body.name = f"{output_name}_LowerBody"

        # Cut main_obj to keep Upper Torso & Arms
        slice_and_cap(main_obj, Vector((mid_x, mid_y, waist_z)), Vector((0, 0, 1)), keep_outer=True)
        # Cut lower_body to keep Legs
        slice_and_cap(lower_body, Vector((mid_x, mid_y, waist_z)), Vector((0, 0, 1)), keep_outer=False)

        # Waist connector between Torso and Lower Body
        if add_connectors:
            add_peg_connector(lower_body, Vector((mid_x, mid_y, waist_z)), Vector((0, 0, 1)), radius=connector_r * 1.3, length=connector_len)
            add_socket_connector(main_obj, Vector((mid_x, mid_y, waist_z)), Vector((0, 0, -1)), radius=socket_r * 1.3, length=connector_len * 1.15)

        # 3. Arms from Upper Body
        arm_left_x = min_x + 0.28 * dx
        arm_right_x = max_x - 0.28 * dx
        extract_slice(main_obj, "Arm_Left", Vector((arm_left_x, mid_y, waist_z)), Vector((-1, 0, 0)), keep_outer=True, expl_vec=Vector((-exploded_dist * 1.2, 0, 0)), custom_conn_pos=Vector((arm_left_x, mid_y, shoulder_z)))
        extract_slice(main_obj, "Arm_Right", Vector((arm_right_x, mid_y, waist_z)), Vector((1, 0, 0)), keep_outer=True, expl_vec=Vector((exploded_dist * 1.2, 0, 0)), custom_conn_pos=Vector((arm_right_x, mid_y, shoulder_z)))

        # 4. Legs from Lower Body
        leg_split_z = min_z + 0.25 * dz
        extract_slice(lower_body, "Leg_Right", Vector((mid_x, mid_y, leg_split_z)), Vector((1, 0, 0)), keep_outer=True, expl_vec=Vector((exploded_dist * 0.6, 0, -exploded_dist * 0.7)))
        if len(lower_body.data.vertices) >= 50:
            c_name, rgba = palette[len(pieces) % len(palette)]
            mat = create_pastel_material(f"Mat_Leg_Left_{c_name}", rgba)
            lower_body.name = f"{output_name}_Leg_Left"
            lower_body.data.materials.clear()
            lower_body.data.materials.append(mat)
            pieces.append(("Leg_Left", lower_body, Vector((-exploded_dist * 0.6, 0, -exploded_dist * 0.7)), rgba))

        # 5. Remaining main_obj is Torso_Core
        if len(main_obj.data.vertices) >= 50:
            c_name, rgba = palette[len(pieces) % len(palette)]
            mat = create_pastel_material(f"Mat_Torso_Core_{c_name}", rgba)
            main_obj.name = f"{output_name}_Torso_Core"
            main_obj.data.materials.clear()
            main_obj.data.materials.append(mat)
            pieces.append(("Torso_Core", main_obj, Vector((0, 0, 0)), rgba))

    elif category in ["quadruped_creature", "quadruped"]:
        # Quadruped / Beast Decomposition (like wolf reference)
        if dy >= dx:
            head_cut_y = min_y + 0.72 * dy
            mane_cut_y = min_y + 0.55 * dy
            tail_cut_y = min_y + 0.22 * dy
            leg_cut_z = min_z + 0.42 * dz

            extract_slice(main_obj, "Head_Skull", Vector((mid_x, head_cut_y, mid_z)), Vector((0, 1, 0.3)), keep_outer=True, expl_vec=Vector((0, exploded_dist * 1.3, exploded_dist * 0.4)))
            extract_slice(main_obj, "Mane_Neck", Vector((mid_x, mane_cut_y, mid_z)), Vector((0, 1, 0.4)), keep_outer=True, expl_vec=Vector((0, exploded_dist * 0.8, exploded_dist * 0.5)))
            extract_slice(main_obj, "Tail", Vector((mid_x, tail_cut_y, mid_z)), Vector((0, -1, 0.3)), keep_outer=True, expl_vec=Vector((0, -exploded_dist * 1.2, exploded_dist * 0.3)))
            
            # Legs
            extract_slice(main_obj, "Leg_Front_Left", Vector((min_x + 0.32 * dx, mid_y + 0.20 * dy, leg_cut_z)), Vector((-1, 0.3, -0.8)), keep_outer=True, expl_vec=Vector((-exploded_dist, exploded_dist * 0.6, -exploded_dist * 0.5)))
            extract_slice(main_obj, "Leg_Front_Right", Vector((max_x - 0.32 * dx, mid_y + 0.20 * dy, leg_cut_z)), Vector((1, 0.3, -0.8)), keep_outer=True, expl_vec=Vector((exploded_dist, exploded_dist * 0.6, -exploded_dist * 0.5)))
            extract_slice(main_obj, "Leg_Hind_Left", Vector((min_x + 0.32 * dx, mid_y - 0.20 * dy, leg_cut_z)), Vector((-1, -0.3, -0.8)), keep_outer=True, expl_vec=Vector((-exploded_dist, -exploded_dist * 0.6, -exploded_dist * 0.5)))
            extract_slice(main_obj, "Leg_Hind_Right", Vector((max_x - 0.32 * dx, mid_y - 0.20 * dy, leg_cut_z)), Vector((1, -0.3, -0.8)), keep_outer=True, expl_vec=Vector((exploded_dist, -exploded_dist * 0.6, -exploded_dist * 0.5)))
        else:
            head_cut_x = max_x - 0.28 * dx
            extract_slice(main_obj, "Head_Skull", Vector((head_cut_x, mid_y, mid_z)), Vector((1, 0, 0.3)), keep_outer=True, expl_vec=Vector((exploded_dist * 1.3, 0, exploded_dist * 0.4)))
            extract_slice(main_obj, "Tail", Vector((min_x + 0.22 * dx, mid_y, mid_z)), Vector((-1, 0, 0.3)), keep_outer=True, expl_vec=Vector((-exploded_dist * 1.2, 0, exploded_dist * 0.3)))

        if len(main_obj.data.vertices) >= 50:
            c_name, rgba = palette[len(pieces) % len(palette)]
            mat = create_pastel_material(f"Mat_Ribcage_Torso_{c_name}", rgba)
            main_obj.name = f"{output_name}_Ribcage_Torso"
            main_obj.data.materials.clear()
            main_obj.data.materials.append(mat)
            pieces.append(("Ribcage_Torso", main_obj, Vector((0, 0, 0)), rgba))

    elif category in ["prop_weapon", "weapon"]:
        extract_slice(main_obj, "Blade_Tip", Vector((mid_x, mid_y, min_z + 0.72 * dz)), Vector((0, 0, 1)), keep_outer=True, expl_vec=Vector((0, 0, exploded_dist * 1.3)))
        extract_slice(main_obj, "Pommel", Vector((mid_x, mid_y, min_z + 0.12 * dz)), Vector((0, 0, -1)), keep_outer=True, expl_vec=Vector((0, 0, -exploded_dist * 1.3)))
        extract_slice(main_obj, "Hilt_Grip", Vector((mid_x, mid_y, min_z + 0.26 * dz)), Vector((0, 0, -1)), keep_outer=True, expl_vec=Vector((0, 0, -exploded_dist * 0.6)))
        if len(main_obj.data.vertices) >= 50:
            c_name, rgba = palette[len(pieces) % len(palette)]
            mat = create_pastel_material(f"Mat_Crossguard_{c_name}", rgba)
            main_obj.name = f"{output_name}_Crossguard"
            main_obj.data.materials.clear()
            main_obj.data.materials.append(mat)
            pieces.append(("Crossguard", main_obj, Vector((0, 0, 0)), rgba))

    else:
        # Generic modular cut
        extract_slice(main_obj, "Top_Section", Vector((mid_x, mid_y, mid_z)), Vector((0, 0, 1)), keep_outer=True, expl_vec=Vector((0, 0, exploded_dist)))
        if len(main_obj.data.vertices) >= 50:
            c_name, rgba = palette[len(pieces) % len(palette)]
            mat = create_pastel_material(f"Mat_Bottom_Section_{c_name}", rgba)
            main_obj.name = f"{output_name}_Bottom_Section"
            main_obj.data.materials.clear()
            main_obj.data.materials.append(mat)
            pieces.append(("Bottom_Section", main_obj, Vector((0, 0, -exploded_dist)), rgba))

    print(f"[ModelSplitter] Successfully decomposed into {len(pieces)} watertight parts!")

    # 1. Export individual STL parts
    exported_stl_paths = []
    for part_name, p_obj, _, _ in pieces:
        stl_filename = f"{part_name}.stl"
        stl_filepath = os.path.join(parts_dir, stl_filename)
        
        bpy.ops.object.select_all(action='DESELECT')
        p_obj.select_set(True)
        bpy.context.view_layer.objects.active = p_obj
        
        bpy.ops.wm.stl_export(
            filepath=stl_filepath,
            export_selected_objects=True,
            apply_modifiers=True
        )
        exported_stl_paths.append(stl_filepath)

    # 2. Render LookDev Exploded Sheet
    setup_studio_lighting()
    
    # Offset pieces outward along their exploded vectors
    for _, p_obj, expl_vec, _ in pieces:
        p_obj.location += expl_vec

    all_meshes = [p_obj for _, p_obj, _, _ in pieces]
    min_x = min(get_bbox(o)[0] for o in all_meshes)
    max_x = max(get_bbox(o)[1] for o in all_meshes)
    min_y = min(get_bbox(o)[2] for o in all_meshes)
    max_y = max(get_bbox(o)[3] for o in all_meshes)
    min_z = min(get_bbox(o)[4] for o in all_meshes)
    max_z = max(get_bbox(o)[5] for o in all_meshes)
    
    max_dim = max(max_x - min_x, max_y - min_y, max_z - min_z)
    center = Vector(((min_x + max_x)/2.0, (min_y + max_y)/2.0, (min_z + max_z)/2.0))

    # Camera setup (Hero Isometric View)
    cam_data = bpy.data.cameras.new(name="ExplodedCam")
    cam_data.type = 'PERSP'
    cam_data.lens = 45.0
    cam_dist = max_dim * 2.35
    cam_data.clip_start = 0.05
    cam_data.clip_end = max_dim * 20.0

    cam_obj = bpy.data.objects.new(name="ExplodedCam", object_data=cam_data)
    bpy.context.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj

    cam_obj.location = center + Vector((-cam_dist * 0.65, -cam_dist * 0.85, cam_dist * 0.55))
    
    direction = center - cam_obj.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam_obj.rotation_euler = rot_quat.to_euler()

    render_sheet_path = os.path.join(output_dir, f"{output_name}_split_sheet.png")
    bpy.context.scene.render.resolution_x = 1920
    bpy.context.scene.render.resolution_y = 1080
    bpy.context.scene.render.filepath = render_sheet_path
    bpy.context.scene.render.image_settings.file_format = 'PNG'
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'

    bpy.ops.render.render(write_still=True)

    # 3. Export Exploded GLB
    exploded_glb_path = os.path.join(output_dir, f"{output_name}_exploded.glb")
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(
        filepath=exploded_glb_path,
        use_selection=False,
        export_format='GLB',
        export_materials='EXPORT',
        export_apply=True
    )

    out_summary = {
        "status": "success",
        "num_parts": len(pieces),
        "parts_names": [p[0] for p in pieces],
        "parts_dir": parts_dir,
        "stl_files": exported_stl_paths,
        "exploded_glb": exploded_glb_path,
        "render_sheet": render_sheet_path,
        "connectors_added": add_connectors
    }

    results_file = cfg["results_file"]
    with open(results_file, "w") as f:
        json.dump(out_summary, f, indent=2)

    print(f"[ModelSplitter] Completed successfully. Summary written to {results_file}")

if __name__ == "__main__":
    main()
"""


class ModelSplitter:
    """
    Executes automated anatomical and structural mesh decomposition for multi-part 3D printing.
    """

    @classmethod
    def split_model(
        cls,
        input_mesh_path: str,
        output_filename: str = "model_split",
        output_dir: Optional[str] = None,
        subject_category: str = "auto",
        add_connectors: bool = True,
        connector_size_mm: float = 3.0,
        exploded_distance_mm: float = 16.0
    ) -> Dict[str, Any]:
        """
        Decomposes a 3D model into watertight anatomical parts with registration connectors.
        """
        input_path = os.path.abspath(input_mesh_path)
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input mesh not found: {input_path}")

        out_dir = Path(output_dir or OUTPUT_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)

        blender_bin = HardwareManager.get_instance().blender_path
        if not blender_bin:
            raise RuntimeError("Blender not found on this system. Required for Auto Split.")

        cat = subject_category.lower().strip()
        if cat in ["auto", "default", ""]:
            cat = detect_subject_category(output_filename)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            script_path = tmp_path / "blender_splitter.py"
            config_path = tmp_path / "splitter_config.json"
            results_path = tmp_path / "splitter_results.json"

            script_path.write_text(_SPLITTER_BLENDER_SCRIPT, encoding="utf-8")

            config_data = {
                "input_mesh": input_path,
                "output_dir": str(out_dir),
                "output_name": output_filename,
                "category": cat,
                "add_connectors": add_connectors,
                "connector_radius": float(connector_size_mm) / 2.0,
                "exploded_distance": float(exploded_distance_mm),
                "results_file": str(results_path)
            }
            config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

            env = os.environ.copy()
            env["LOCAL3D_SPLIT_CONFIG"] = str(config_path)

            cmd = [
                blender_bin,
                "--background",
                "--factory-startup",
                "-noaudio",
                "--python", str(script_path)
            ]

            print(
                f"[ModelSplitter] Running automated hierarchical split in Blender on {input_path} (category: {cat})...",
                file=sys.stderr
            )
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=180)

            if proc.returncode != 0 or not results_path.exists():
                print(f"[ModelSplitter] Blender stderr:\n{proc.stderr}", file=sys.stderr)
                raise RuntimeError(f"Blender splitting failed (code {proc.returncode}): {proc.stderr[:400]}")

            with open(results_path, "r") as f:
                res = json.load(f)

            # Assembling multi-object 3MF for Bambu Studio / OrcaSlicer via trimesh
            threemf_path = out_dir / f"{output_filename}_split.3mf"
            try:
                import trimesh
                import numpy as np
                scene_dict = {}
                palette_colors = [
                    [235, 90, 90, 255],    # Red
                    [165, 225, 145, 255],  # Light Green
                    [230, 225, 180, 255],  # Beige
                    [205, 150, 215, 255],  # Violet
                    [115, 190, 115, 255],  # Green
                    [180, 115, 205, 255],  # Purple
                    [100, 190, 215, 255],  # Cyan
                    [90, 140, 225, 255],   # Blue
                ]
                for i, stl_f in enumerate(res.get("stl_files", [])):
                    if os.path.exists(stl_f) and os.path.getsize(stl_f) > 100:
                        loaded = trimesh.load(stl_f)
                        if isinstance(loaded, trimesh.Scene):
                            if len(loaded.geometry) == 0:
                                continue
                            p_mesh = list(loaded.geometry.values())[0]
                        else:
                            p_mesh = loaded
                        
                        if len(p_mesh.faces) > 0:
                            # Filter out disconnected degenerate micro-slivers from bisecting
                            subs = [s for s in p_mesh.split(only_watertight=False) if len(s.faces) >= 20]
                            if subs:
                                p_mesh = trimesh.util.concatenate(subs)
                                p_mesh.export(stl_f)

                            p_name = Path(stl_f).stem
                            color = palette_colors[i % len(palette_colors)]
                            p_mesh.visual = trimesh.visual.ColorVisuals(
                                mesh=p_mesh,
                                vertex_colors=np.full((len(p_mesh.vertices), 4), color, dtype=np.uint8)
                            )
                            scene_dict[p_name] = p_mesh
                
                if scene_dict:
                    multi_scene = trimesh.Scene(scene_dict)
                    data_3mf = multi_scene.export(file_type="3mf")
                    with open(threemf_path, "wb") as f_3mf:
                        f_3mf.write(data_3mf)
                    res["multi_color_3mf"] = str(threemf_path)
                    res["multi_color_3mf_uri"] = f"file://{threemf_path}"
            except Exception as e:
                print(f"[ModelSplitter] Note exporting multi-color 3MF: {e}", file=sys.stderr)

            res["parts_dir_uri"] = f"file://{res['parts_dir']}"
            res["exploded_glb_uri"] = f"file://{res['exploded_glb']}"
            res["render_sheet_uri"] = f"file://{res['render_sheet']}"
            return res
