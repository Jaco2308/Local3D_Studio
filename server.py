"""
Local3D Studio Universal MCP Server (Pure In-Process Local Execution)
Model Context Protocol server for AI 3D Generation & Blender Manufacturing.
Executes 100% locally in Python without any external HTTP server, localhost:8000 daemon, or network ports,
featuring Dynamic Hardware Tiering (Auto-Scaling) and Quality Mode Presets (Fast Draft / Auto / Ultra Production).
"""

import os
import sys
import json
import re
import contextlib
from pathlib import Path
from typing import Optional

# Ensure UTF-8 output encoding on Windows consoles
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure") and sys.stdout is not None:
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure") and sys.stderr is not None:
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# Ensure project root is in python path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp.server.mcpserver import MCPServer
from core.config import OUTPUT_DIR
from core.response_envelope import format_success, format_error
from tools.pipeline_engine import PipelineEngine, load_state, save_state

# Initialize MCP Server immediately (<50ms boot time for instant MCP stdio handshake)
server = MCPServer("Local3D-Studio")


def _get_hw():
    from core.hardware_backend import HardwareManager
    return HardwareManager.get_instance()


APPROVAL_STATE_FILE = OUTPUT_DIR / ".state_gate.json"


def _load_approval_state() -> dict:
    return load_state()


def _save_approval_state(state: dict):
    save_state(state)


@server.tool()
def get_hardware_status() -> str:
    """
    Returns complete auto-detected hardware diagnostic summary:
    operating system, CPU model, GPU accelerator, system RAM & VRAM,
    active Performance Tier (Tier 1 Eco, Tier 2 Balanced, Tier 3 Pro, Tier 4 Ultra),
    currently selected Quality Mode (Fast Draft / Auto / Ultra Production),
    and local execution status.
    """
    try:
        with contextlib.redirect_stdout(sys.stderr):
            hw = _get_hw()
            hw_summary = hw.get_summary()
            active_mode = PipelineEngine.get_quality_mode()
            res = {
                "telemetry_badge": hw.get_hardware_badge(),
                "execution_mode": "pure_local_in_process",
                "localhost_required": False,
                "selected_quality_mode": active_mode,
                "active_tier": hw.tier_config.to_dict(),
                "hardware": hw_summary,
                "blender_path": hw.blender_path or "NOT_FOUND"
            }
        return json.dumps(res, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@server.tool()
def set_quality_preset(preset: str = "auto") -> str:
    """
    Sets the active 3D Generation Quality Mode across the entire platform:
    - 'fast_draft': 8-10s neural generation (192p octree, 12 steps, 30,000 triangles)
    - 'auto': Uses optimal settings detected by HardwareManager
    - 'ultra_production': Hunyuan3D-2 Full 384p, dense 0.0038 remesh, 100,000 triangles
    
    Args:
        preset: 'fast_draft', 'auto', or 'ultra_production'.
    """
    preset = preset.lower().strip()
    if preset not in ["fast_draft", "auto", "ultra_production"]:
        return json.dumps({"status": "error", "message": f"Invalid preset: '{preset}'. Must be 'fast_draft', 'auto', or 'ultra_production'."}, indent=2)
    
    with contextlib.redirect_stdout(sys.stderr):
        success = PipelineEngine.set_quality_mode(preset)
    return json.dumps({
        "status": "success" if success else "warning",
        "quality_preset": preset,
        "message": f"Quality preset successfully updated to: {preset}"
    }, indent=2)


@server.tool()
def enhance_prompt_for_3d(
    prompt: str,
    mode: str = "3d_print",
    art_style: str = "faithful_anatomical",
    multiview: bool = True,
    add_pedestal_base: bool = False,
    humanoid_pose: str = "a_pose"
) -> str:
    """
    Dynamic Style & Anatomy Router:
    Expands a user text prompt into a 3D-optimized sculpt specification:
    1. Level A (Style-Agnostic): Lighting, albedo, silhouette isolation, watertight solid volume.
    2. Level B (Dynamic Art Style):
       - 'faithful_anatomical' (DEFAULT): 100% canonical proportions and authentic anatomy.
       - 'realistic_sculpt': ZBrush anatomical sculpture with fine surface fidelity.
       - 'game_prop': Hard-surface planar bevels for props/weapons/vehicles.
       - 'tabletop_miniature': 32mm/75mm heroic scale for wargames.
       - 'stylized_vinyl': ONLY applied if user explicitly mentions 'funko', 'chibi', or 'vinyl'.
    3. Multiview 3-view sheet (Front, Side, Back) to eliminate 360° blind spots.
    4. Humanoid Pose Guidance: 'a_pose' (default 35°-45°), 't_pose' (90°), 'action_pose', 'natural'.
    5. Optional pedestal (add_pedestal_base defaults to False).
    
    Args:
        prompt: Raw user description (e.g. 'Pikachu Pokemon character').
        mode: Target production profile ('3d_print' or 'game_asset').
        art_style: Artistic style profile (default: 'faithful_anatomical').
        multiview: If True (default), structures the prompt for a 3-view model sheet.
        add_pedestal_base: Whether to add a round display disc (default: False).
        humanoid_pose: Pose guidance for humanoid characters ('a_pose', 't_pose', 'action_pose', 'natural').
    """
    try:
        with contextlib.redirect_stdout(sys.stderr):
            from tools.prompt_enhancer import enhance_prompt_for_3d as _enhance
            enhanced = _enhance(
                user_prompt=prompt,
                mode=mode,
                art_style=art_style,
                multiview=multiview,
                add_pedestal_base=add_pedestal_base,
                humanoid_pose=humanoid_pose
            )
        return json.dumps({
            "original_prompt": prompt,
            "enhanced_prompt": enhanced,
            "mode": mode,
            "art_style": art_style,
            "multiview": multiview,
            "add_pedestal_base": add_pedestal_base,
            "humanoid_pose": humanoid_pose
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@server.tool()
def compile_3d_master_prompt(
    subject: str,
    art_style: str = "faithful_anatomical",
    key_details: Optional[list] = None,
    add_pedestal_base: bool = False,
    humanoid_pose: str = "a_pose",
    generation_strategy: str = "single_hero_34"
) -> str:
    """
    Prompt Compiler for Antigravity Native Image Generator (Meshy AI Single-Master 3/4 Style):
    Compiles an ultra-detailed, unconstrained 3D master prompt tailored for 3D reconstruction:
    - 35° elevated isometric three-quarter hero view
    - Total anti-occlusion & limb separation (open A-pose, clear air under armpits/wings/legs/tail)
    - Strictly zero aura, zero ki blasts, zero smoke, zero flames, zero pedestal (unless add_pedestal_base=True)
    - Deep ambient occlusion in crevices and vivid chromatic albedo separation on pure solid white (#ffffff).
    
    Returns the compiled prompt with the mandatory directive for the agent to generate natively and halt.
    """
    try:
        with contextlib.redirect_stdout(sys.stderr):
            strat = generation_strategy.lower().strip()
            from tools.prompt_enhancer import compile_3d_master_prompt as _compile
            compiled = _compile(
                subject=subject,
                art_style=art_style,
                key_details=key_details or [],
                add_pedestal_base=add_pedestal_base,
                humanoid_pose=humanoid_pose,
                generation_strategy=strat
            )
            clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', subject.lower().strip())
            clean_name = re.sub(r'_+', '_', clean_name).strip('_') or "concept"
        return json.dumps({
            "subject": subject,
            "art_style": art_style,
            "humanoid_pose": humanoid_pose,
            "generation_strategy": strat,
            "compiled_prompt": compiled,
            "compiled_master_prompt": compiled,
            "recommended_output_path": f"output/{clean_name}_concept.png",
            "instruction": (
                "ISTRUZIONE OBBLIGATORIA PER L'AGENTE: Usa ora il tuo tool nativo di generazione immagini con 'compiled_prompt', "
                f"salva l'immagine in output/{clean_name}_concept.png, mostrala all'utente e FERMATI ad attendere il suo OK prima di chiamare direct_image_to_3d!"
            )
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@server.tool()
def align_multiview_concept(
    concept_path: Optional[str] = None
) -> str:
    """
    Anti-Bleed & Y-Bounding-Box Lock calibration engine:
    1. Splits 3-view sheet into Front, Left Profile, and Back quadrants in tempfile.
    2. Runs rembg + connected component analysis (scipy.ndimage.label) to isolate central subjects and zero out neighboring bleed.
    3. Locks vertical height to exactly 400px on 512x512 transparent canvases (feet at Y=456, head at Y=56).
    4. Saves 'concept_multiview_aligned.jpg' preview with laser reference guidelines.
    5. Sets the Hard Approval Gate waiting for user confirmation.
    
    Args:
        concept_path: Path to the 3-view concept image (defaults to latest generated concept).
    """
    gate_state = _load_approval_state()
    target = concept_path or gate_state.get("concept_path")
    if not target or not os.path.exists(target):
        candidates = [p for p in OUTPUT_DIR.glob("*concept*.jpg")] + [p for p in OUTPUT_DIR.glob("*concept*.png")]
        if candidates:
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            target = str(candidates[0])
        else:
            return json.dumps({"status": "error", "message": "No concept image found to align."}, indent=2)

    try:
        with contextlib.redirect_stdout(sys.stderr):
            from tools.multiview_aligner import MultiviewAligner
            res = MultiviewAligner.split_and_align_multiview(
                concept_image_path=target,
                output_dir=str(OUTPUT_DIR),
                save_preview=True
            )
            gate_state["concept_path"] = os.path.abspath(target)
            gate_state["approved"] = False
            _save_approval_state(gate_state)
        return json.dumps({
            "status": "waiting_user_approval",
            "preview_path": res["preview_path"],
            "preview_uri": f"file://{res['preview_path']}",
            "front_path": res["front_path"],
            "left_path": res["left_path"],
            "right_path": res["right_path"],
            "back_path": res["back_path"],
            "detected_orientation": res.get("detected_orientation"),
            "approved": False,
            "directive": "STOP OBBLIGATORIO: Mostra 'concept_multiview_aligned.jpg' a 4 viste all'utente e attendi la sua conferma prima di avviare il 3D.",
            "instructions": "Non chiamare confirm_concept_and_build_3d finché l'utente non ha esplicitamente confermato l'allineamento."
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@server.tool()
def confirm_concept_and_build_3d(
    concept_path: Optional[str] = None,
    output_filename: str = "production_model",
    quality_preset: str = "auto",
    target_height_mm: float = 100.0,
    add_pedestal: bool = False,
    art_style: str = "faithful_anatomical",
    target_triangles: Optional[int] = None,
    voxel_size: Optional[float] = None,
    auto_split: bool = False,
    generation_strategy: Optional[str] = None
) -> str:
    """
    CONFIRMATION GATE: Invocabile SOLO in un turno successivo, DOPO che l'utente ha esplicitamente confermato il concept 2D generato.
    Sblocca ed esegue la ricostruzione neurale 3D in locale, il post-processing in Blender (preservazione micro-dettagli)
    e l'esportazione di STL, GLB e 3MF.
    
    Args:
        concept_path: Percorso del concept 2D confermato dall'utente (se omesso usa l'ultimo generato).
        output_filename: Nome base per i file STL e GLB finali.
        quality_preset: 'fast_draft', 'auto', o 'ultra_production'.
        target_height_mm: Altezza in millimetri (default 100.0 mm).
        add_pedestal: Se includere il basamento per adesione al piatto di stampa (default: False).
        art_style: Profilo stilistico (default: 'faithful_anatomical').
        target_triangles: Numero desiderato esplicito di triangoli (es. 50000, 100000, 200000, 500000).
        voxel_size: Risoluzione voxel remesh in metri (es. 0.0025, 0.0015).
        auto_split: Se suddividere automaticamente il modello in parti con connettori (default: False).
        generation_strategy: 'auto', 'multiview_turnaround', o 'single_hero_34'.
    """
    gate_state = _load_approval_state()
    target_image = concept_path or gate_state.get("concept_path")
    if not target_image or not os.path.exists(target_image):
        return json.dumps({
            "status": "error",
            "message": f"Nessun concept 2D valido trovato da confermare a percorso: {target_image}"
        }, indent=2)

    gate_state["approved"] = True
    gate_state["concept_path"] = os.path.abspath(target_image)
    _save_approval_state(gate_state)

    try:
        with contextlib.redirect_stdout(sys.stderr):
            effective_preset = quality_preset.lower().strip()
            if effective_preset == "auto":
                local_mode = PipelineEngine.get_quality_mode()
                if local_mode in ["fast_draft", "ultra_production"]:
                    effective_preset = local_mode

            effective_strategy = generation_strategy or gate_state.get("generation_strategy", "auto")

            result = PipelineEngine.run_pipeline(
                image_path=target_image,
                output_name=output_filename,
                quality_preset=effective_preset,
                generation_strategy=effective_strategy,
                target_height_mm=target_height_mm,
                add_pedestal=add_pedestal,
                art_style=art_style,
                target_triangles=target_triangles,
                voxel_size=voxel_size,
                auto_split=auto_split
            )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@server.tool()
def image_to_high_detail_stl(
    image_path: str,
    output_filename: str = "production_model",
    quality_preset: str = "auto",
    target_height_mm: float = 100.0,
    target_triangles: Optional[int] = None,
    voxel_size: Optional[float] = None,
    add_pedestal: bool = False,
    art_style: str = "faithful_anatomical"
) -> str:
    """
    Complete Production Pipeline from Approved 2D Image to Production 3D STL & Three.js Viewer.
    Enforces the Hard Approval Gate: if called on an unapproved concept, blocks execution.
    
    Args:
        image_path: Absolute path to the approved 2D PNG concept.
        output_filename: Base filename for generated STL, GLB, and LookDev sheet.
        quality_preset: 'fast_draft', 'auto', or 'ultra_production' (defaults to 'auto').
        target_height_mm: Physical height in millimeters (default: 100.0 mm).
        target_triangles: Polygon budget (optional override).
        voxel_size: Voxel remesh size (optional override).
        add_pedestal: Whether to fuse a solid flat circular base at Z=0 for print bed adhesion (default: False).
        art_style: Profilo stilistico (default: 'faithful_anatomical').
    """
    img_abs = os.path.abspath(image_path)
    gate_state = _load_approval_state()
    if gate_state.get("concept_path") == img_abs and not gate_state.get("approved"):
        return json.dumps({
            "status": "error",
            "error_type": "HARD_APPROVAL_GATE_BLOCKED",
            "message": (
                "BLOCCO FISICO: Il concept 2D non è ancora stato approvato dall'utente! "
                "L'agente non può procedere alla generazione 3D nello stesso turno della generazione 2D. "
                "Mostra prima l'immagine all'utente e attendi la sua conferma esplicita ('OK / confermo / procedi'). "
                "Solo dopo la risposta dell'utente potrai chiamare 'confirm_concept_and_build_3d'."
            )
        }, indent=2)

    try:
        with contextlib.redirect_stdout(sys.stderr):
            effective_preset = quality_preset.lower().strip()
            if effective_preset == "auto":
                local_mode = PipelineEngine.get_quality_mode()
                if local_mode in ["fast_draft", "ultra_production"]:
                    effective_preset = local_mode

            result = PipelineEngine.run_pipeline(
                image_path=image_path,
                output_name=output_filename,
                quality_preset=effective_preset,
                target_height_mm=target_height_mm,
                add_pedestal=add_pedestal,
                art_style=art_style,
                target_triangles=target_triangles,
                voxel_size=voxel_size
            )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@server.tool()
def recalculate_in_ultra_production(output_filename: str = "recalculated_ultra_100k") -> str:
    """
    1-Click Recalculation: Reruns 3D generation on the latest approved 2D concept image
    in Ultra Production mode (Hunyuan Full 384p, dense 0.0038 remesh, 100,000 triangles).
    Ideal when the previous model was generated in Fast Draft mode.
    
    Args:
        output_filename: Base filename for the upgraded 100k triangle model.
    """
    try:
        with contextlib.redirect_stdout(sys.stderr):
            res = PipelineEngine.recalculate(quality_preset="ultra_production", output_name=output_filename)
        return json.dumps(res, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@server.tool()
def prepare_for_3d_print(
    input_mesh_path: str,
    output_filename: str = "print_ready",
    target_height_mm: float = 100.0,
    target_triangles: Optional[int] = None,
    voxel_size: Optional[float] = None,
    smooth_iterations: int = 5,
    add_pedestal: bool = True
) -> str:
    """
    Post-processes an existing .glb or .stl file with the standardized Blender manufacturing pipeline:
    Voxel Remesh, Corrective Smooth, Decimation to tier polygon budget, scaling in mm, and flat base alignment on Z=0.
    
    Args:
        input_mesh_path: Path to existing 3D file (.glb, .stl, .obj).
        output_filename: Base output name.
        target_height_mm: Height in millimeters (e.g. 100.0).
        target_triangles: Polygon count (optional, auto-scaled from hardware tier).
        voxel_size: Voxel remesh resolution (optional, auto-scaled from hardware tier).
        smooth_iterations: Smooth passes (default: 5).
        add_pedestal: Whether to add a flat circular base.
    """
    try:
        with contextlib.redirect_stdout(sys.stderr):
            from tools.blender_pipeline import BlenderPipeline
            res = BlenderPipeline.process_and_export(
                input_glb_path=input_mesh_path,
                target_height_mm=target_height_mm,
                target_triangles=target_triangles or 80000,
                voxel_size=voxel_size or 0.005,
                smooth_iterations=smooth_iterations,
                add_pedestal=add_pedestal,
                output_name=output_filename
            )
            res["execution_mode"] = "pure_local"
            res["stl_uri"] = f"file://{res['stl_path']}"
            res["glb_uri"] = f"file://{res['glb_path']}"
            if res.get("3mf_path"):
                res["3mf_uri"] = f"file://{res['3mf_path']}"
        return json.dumps(res, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@server.tool()
def capture_multiview_sheet(mesh_path: str, output_filename: str = "lookdev_multiview") -> str:
    """
    Renders a 4-view studio LookDev sheet (Perspective 3/4 Hero, Front Close-Up, Side Profile, Rear View)
    for a given 3D mesh (.glb, .stl, or .obj) in ~2.5s without re-running mesh decimation or remeshing.
    """
    try:
        with contextlib.redirect_stdout(sys.stderr):
            from tools.blender_pipeline import BlenderPipeline
            res = BlenderPipeline.render_lookdev_only(
                input_mesh_path=mesh_path,
                output_name=output_filename
            )
            sheet_path = res.get("lookdev_sheet_path")
        return json.dumps({
            "status": "success",
            "execution_mode": "pure_local",
            "lookdev_sheet": sheet_path,
            "lookdev_sheet_uri": f"file://{sheet_path}" if sheet_path else None
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@server.tool()
def direct_image_to_3d(
    image_path: str,
    output_filename: str = "direct_model",
    quality_preset: str = "auto",
    generation_strategy: str = "single_hero_34",
    add_pedestal: bool = False,
    target_height_mm: float = 100.0,
    art_style: str = "faithful_anatomical",
    target_triangles: Optional[int] = None,
    voxel_size: Optional[float] = None,
    auto_split: bool = False
) -> str:
    """
    Direct Image-to-3D Tool (Meshy AI Alternative):
    Converts any 2D reference image directly into a production-grade 3D model (.stl, .glb, .3mf)
    without needing a text-to-image concept stage.
    
    Args:
        image_path: Absolute path to the 2D image file (PNG, JPG, WebP).
        output_filename: Base name for generated 3D files.
        quality_preset: 'fast_draft', 'auto', or 'ultra_production'.
        generation_strategy: 'single_hero_34' (Meshy Style single view) or 'multiview_turnaround'.
        add_pedestal: Whether to add a solid flat circular base at Z=0.
        target_height_mm: Desired height in millimeters (default: 100.0).
        art_style: Artistic style profile (default: 'faithful_anatomical').
        target_triangles: Numero desiderato esplicito di triangoli (es. 50000, 100000, 200000, 500000).
        voxel_size: Risoluzione voxel remesh in metri (es. 0.0025, 0.0015).
        auto_split: Se suddividere automaticamente il modello in parti con connettori (default: False).
    """
    try:
        with contextlib.redirect_stdout(sys.stderr):
            res = PipelineEngine.run_pipeline(
                image_path=image_path,
                output_name=output_filename,
                quality_preset=quality_preset,
                generation_strategy=generation_strategy,
                add_pedestal=add_pedestal,
                target_height_mm=target_height_mm,
                art_style=art_style,
                target_triangles=target_triangles,
                voxel_size=voxel_size,
                auto_split=auto_split
            )
        return json.dumps(res, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@server.tool()
def retopologize_mesh(
    input_mesh_path: Optional[str] = None,
    output_filename: str = "retopo_model",
    mode: str = "quad",
    target_count: int = 10000
) -> str:
    """
    Retopology Tool (Meshy AI Alternative):
    Converts heavy or triangulated 3D meshes into clean, production-ready topology:
    - 'quad': All-quad manifold mesh using Quadriflow (ideal for rigging, animation, and subdivision).
    - 'tri': Decimate collapse to an exact polygon count budget for real-time game engines or 3D printing.
    
    Args:
        input_mesh_path: Path to .glb or .stl (defaults to latest generated model).
        output_filename: Base name for the retopologized output files.
        mode: 'quad' for quads, or 'tri' for triangles.
        target_count: Target number of faces/triangles (e.g. 5000, 10000, 50000).
    """
    try:
        with contextlib.redirect_stdout(sys.stderr):
            res = PipelineEngine.retopologize(
                input_mesh_path=input_mesh_path,
                output_name=output_filename,
                mode=mode,
                target_count=target_count
            )
        return json.dumps(res, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@server.tool()
def bake_pbr_textures(
    input_mesh_path: Optional[str] = None,
    output_filename: str = "pbr_model",
    texture_resolution: int = 2048,
    bake_normal: bool = True,
    bake_ao: bool = True
) -> str:
    """
    PBR Texture Baking Tool (Meshy AI Alternative):
    Performs smart UV unwrap and bakes high-fidelity tangent-space Normal and Ambient Occlusion maps
    in Blender Cycles, exporting a textured GLB with embedded PBR materials.
    
    Args:
        input_mesh_path: Path to input 3D mesh (defaults to latest generated model).
        output_filename: Base output name for textured GLB and texture maps.
        texture_resolution: Resolution in pixels (e.g. 1024, 2048, 4096).
        bake_normal: Bake tangent normal map (default: True).
        bake_ao: Bake ambient occlusion map (default: True).
    """
    try:
        with contextlib.redirect_stdout(sys.stderr):
            res = PipelineEngine.bake_textures(
                input_mesh_path=input_mesh_path,
                output_name=output_filename,
                texture_resolution=texture_resolution,
                bake_normal=bake_normal,
                bake_ao=bake_ao
            )
        return json.dumps(res, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@server.tool()
def auto_split_model(
    input_mesh_path: Optional[str] = None,
    output_filename: str = "model_split",
    subject_category: str = "auto",
    add_connectors: bool = True,
    connector_size_mm: float = 3.0,
    exploded_distance_mm: float = 16.0
) -> str:
    """
    Auto Split Tool (Meshy AI Alternative):
    Automatically subdivides a 3D model into watertight, 3D-printable parts
    (e.g., Head, Limbs, Torso, Tail, Base) with assembly registration peg & socket keying (0.25mm clearance),
    multi-color AMS 3MF export, exploded GLB assembly, and studio LookDev exploded sheet.
    
    Args:
        input_mesh_path: Path to .stl or .glb (defaults to latest generated model).
        output_filename: Base name for split parts directory and assembly files.
        subject_category: 'auto' (detects humanoid, quadruped, weapon, generic), or specify explicitly.
        add_connectors: Whether to generate male pegs and female sockets with 0.25mm 3D printing clearance (default: True).
        connector_size_mm: Diameter of the connector pegs in mm (default: 3.0 mm).
        exploded_distance_mm: Distance in mm to separate parts in exploded view render (default: 16.0 mm).
    """
    try:
        with contextlib.redirect_stdout(sys.stderr):
            res = PipelineEngine.split_model(
                input_mesh_path=input_mesh_path,
                output_name=output_filename,
                subject_category=subject_category,
                add_connectors=add_connectors,
                connector_size_mm=connector_size_mm,
                exploded_distance_mm=exploded_distance_mm
            )
        return json.dumps(res, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@server.tool()
def canonicalize_humanoid_pose(
    image_path: str,
    target_pose: str = "a_pose",
    output_filename: str = "canonical_pose_concept",
    art_style: str = "faithful_anatomical"
) -> str:
    """
    Humanoid Pose Guidance & Canonical Pose Converter (Meshy AI Alternative):
    Converts arbitrary character artwork (e.g. sitting, action, crouching, self-occluded)
    into a standardized canonical pose concept optimized for 3D reconstruction and rigging:
    - 'a_pose' (Default): Arms held 35°-45° downward angle, open armpit and inner-thigh negative space.
    - 't_pose': Rigging & animation standard with arms extended horizontally at 90°, palms down.
    - 'action_pose': Heroic dynamic battle stance with balanced footing.
    - 'natural': Relaxed natural standing posture.
    
    Enforces the Hard Approval Gate: saves state as approved=False and obligates the agent to halt
    and show the canonical concept to the user before calling any 3D tool.
    
    Args:
        image_path: Absolute path to the source 2D character image.
        target_pose: 'a_pose' (default), 't_pose', 'action_pose', or 'natural'.
        output_filename: Base filename for the canonical concept image.
        art_style: Artistic style profile (default: 'faithful_anatomical').
    """
    try:
        with contextlib.redirect_stdout(sys.stderr):
            res = PipelineEngine.canonicalize_pose(
                image_path=image_path,
                target_pose=target_pose,
                output_name=output_filename,
                art_style=art_style
            )
        return json.dumps(res, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


def main():
    args = sys.argv[1:]
    if not args or args[0] == "mcp":
        print("[Local3D Studio] Starting Universal MCP Server over stdio (Lazy Hardware Init enabled)...", file=sys.stderr)
        server.run(transport="stdio")
    elif args[0] == "doctor":
        from core.diagnostics import run_doctor, print_doctor_report
        doc = run_doctor()
        if "--json" in args:
            print(json.dumps(doc, indent=2))
        else:
            print_doctor_report(doc)
    elif args[0] == "setup":
        from core.client_setup import run_setup
        dry_run = "--dry-run" in args
        target_client = "antigravity"
        for i, a in enumerate(args):
            if a == "--client" and i + 1 < len(args):
                target_client = args[i + 1]
        res = run_setup(clients=[target_client], dry_run=dry_run)
        print(json.dumps(res, indent=2))
    elif args[0] == "update":
        from core.updater import run_update, check_updates, print_update_report
        if "--check" in args:
            chk = check_updates()
            if "--json" in args:
                print(json.dumps(chk, indent=2))
            else:
                if chk.get("has_update"):
                    print(f"Update available: local {chk['local_commit']} is {chk['behind_by']} commits behind remote {chk['remote_commit']}.")
                else:
                    print(f"Local3D Studio is up to date at commit {chk.get('local_commit', 'HEAD')}.")
        else:
            up_res = run_update()
            if "--json" in args:
                print(json.dumps(up_res, indent=2))
            else:
                print_update_report(up_res)
    elif args[0] in ["status", "hardware"]:
        hw = _get_hw()
        print(hw.get_hardware_badge())
    else:
        print(f"Unknown command: '{args[0]}'. Available commands: mcp, doctor, setup, update, status", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

