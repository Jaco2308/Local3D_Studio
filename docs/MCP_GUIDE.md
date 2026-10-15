# 🔌 Local3D Studio MCP Client Configuration & User Guide

This guide explains how to connect **Local3D Studio** to any Model Context Protocol (MCP) compatible AI environment—including **Google Antigravity**, **Claude Desktop**, **Cursor**, **Continue.dev**, and **Windsurf**.

Local3D Studio's MCP server executes **100% locally in-process over standard I/O (`stdio`)**. You do **not** need to run any HTTP server, open any ports, or maintain a localhost background daemon.

---

## 🚀 Quick Setup Overview

The MCP server entrypoint is:
- **Server Name**: `Local3D-Studio`
- **Recommended MCP Key**: `local3d`
- **Executable**: `python server.py` (or `./run_mcp.sh` on macOS/Linux, `run_mcp.bat` on Windows)
- **Transport**: `stdio`
- **Environment**: Your Python virtual environment (`.venv`) where dependencies were installed via `setup_env.py`.

---

## 💻 Client Configuration Snippets

### 1. Google Antigravity / Gemini CLI

In your Antigravity MCP configuration (e.g. `~/.gemini/antigravity/mcp/local3d/` or global MCP settings):

```json
{
  "mcpServers": {
    "local3d": {
      "command": "/absolute/path/to/Local3D-Studio/.venv/bin/python",
      "args": [
        "/absolute/path/to/Local3D-Studio/server.py"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

*Or simply point `command` to `/absolute/path/to/Local3D-Studio/run_mcp.sh`.*

---

### 2. Claude Desktop

#### macOS Configuration
File location: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "local3d": {
      "command": "/Users/<your-username>/path/to/Local3D-Studio/.venv/bin/python",
      "args": [
        "/Users/<your-username>/path/to/Local3D-Studio/server.py"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

#### Windows Configuration
File location: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "local3d": {
      "command": "C:\\path\\to\\Local3D-Studio\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\path\\to\\Local3D-Studio\\server.py"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

---

### 3. Cursor IDE

Add Local3D Studio under **Cursor Settings** > **Features** > **MCP** > **Add New MCP Server**, or configure `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "local3d": {
      "command": "/absolute/path/to/Local3D-Studio/.venv/bin/python",
      "args": [
        "/absolute/path/to/Local3D-Studio/server.py"
      ]
    }
  }
}
```

---

### 4. Continue.dev (VS Code & JetBrains)

In `~/.continue/config.json`:

```json
{
  "experimental": {
    "modelContextProtocolServers": [
      {
        "transport": {
          "type": "stdio",
          "command": "/absolute/path/to/Local3D-Studio/.venv/bin/python",
          "args": [
            "/absolute/path/to/Local3D-Studio/server.py"
          ]
        }
      }
    ]
  }
}
```

---

### 5. Windsurf

In `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "local3d": {
      "command": "/absolute/path/to/Local3D-Studio/.venv/bin/python",
      "args": [
        "/absolute/path/to/Local3D-Studio/server.py"
      ]
    }
  }
}
```

---

## 🛠️ Complete MCP Tool Suite (16 Native Tools)

| # | Tool Name | Arguments | Purpose & Highlights |
|---|:---|:---|:---|
| 1 | `get_hardware_status` | *(none)* | Returns CPU, GPU backend (CUDA/ROCm/MPS), system RAM/VRAM, active Performance Tier (1 to 4), and Blender binary location. |
| 2 | `set_quality_preset` | `preset` (`'fast_draft'`, `'auto'`, `'ultra_production'`) | Configures mesh density and neural reconstruction steps across the platform. |
| 3 | `enhance_prompt_for_3d` | `prompt`, `mode`, `art_style`, `multiview`, `add_pedestal_base`, `humanoid_pose` | Expands raw prompts into photogrammetry-grade 3D prompts across 5 styles and standard pose angles. |
| 4 | `compile_3d_master_prompt` | `subject`, `art_style`, `key_details`, `add_pedestal_base`, `humanoid_pose` | Compiles a 3-Panel Turnaround prompt with wide margins and Anatomical De-Occlusion guarantees. |
| 5 | `generate_concept_image` | `prompt`, `output_filename`, `mode`, `art_style`, `multiview`, `add_pedestal_base`, `seed` | Generates 2D concept illustration using SDXL-Lightning (4-step float16) and arms the Hard Approval Gate. |
| 6 | `align_multiview_concept` | `concept_path` | Crops quadrants, isolates main subject via connected components, locks Y-bounding-box, and enhances albedo. |
| 7 | `confirm_concept_and_build_3d` | `concept_path`, `output_filename`, `quality_preset`, `target_height_mm`, `add_pedestal`, `art_style`, `target_triangles`, `voxel_size`, `auto_split` | **Hard Approval Gate**: Invocable ONLY after user confirmation to execute 3D neural reconstruction and Blender pipeline. |
| 8 | `direct_image_to_3d` | `image_path`, `output_filename`, `quality_preset`, `generation_strategy`, `add_pedestal`, `target_height_mm`, `art_style`, `target_triangles`, `voxel_size`, `auto_split` | **Meshy AI Alternative**: Direct 1-step conversion from any 2D photo to 3D mesh (`single_hero_34` or `multiview_turnaround`). |
| 9 | `retopologize_mesh` | `input_mesh_path`, `output_filename`, `mode` (`'quad'` / `'tri'`), `target_count` | **AI Retopology**: Converts dense sculpts into clean topology: Quadriflow all-quads (animation/rigging) or fixed tri budget (games). |
| 10 | `bake_pbr_textures` | `input_mesh_path`, `output_filename`, `texture_resolution`, `bake_normal`, `bake_ao` | **PBR Texture Baker**: Computes tangent-space Normal maps and Ambient Occlusion (AO) via Blender Cycles, exporting PBR GLB. |
| 11 | `auto_split_model` | `input_mesh_path`, `output_filename`, `subject_category`, `add_connectors`, `connector_size_mm`, `exploded_distance_mm` | **Auto Split & Keying**: Bisects models into watertight parts with 0.25mm connector pegs/sockets, exploded GLB, and multi-color 3MF. |
| 12 | `canonicalize_humanoid_pose` | `image_path`, `target_pose` (`'a_pose'`, `'t_pose'`, `'natural'`, `'action_pose'`), `output_filename`, `art_style` | **Pose Guidance**: Eliminates armpit/crotch webbing by standardizing character inputs with visual vector angle overlay. |
| 13 | `image_to_high_detail_stl` | `image_path`, `output_filename`, `quality_preset`, `target_height_mm`, `target_triangles`, `voxel_size`, `add_pedestal`, `art_style` | Full end-to-end manufacturing pipeline with automatic Approval Gate validation and 3D print preparation. |
| 14 | `recalculate_in_ultra_production` | `output_filename` | 1-Click recalculation: Re-runs 3D generation on the latest concept using 100k polygon budget and dense remeshing. |
| 15 | `prepare_for_3d_print` | `input_mesh_path`, `output_filename`, `target_height_mm`, `target_triangles`, `voxel_size`, `smooth_iterations`, `add_pedestal` | Repairs existing meshes, normalizes scale to millimeters, forces Z=0 bed grounding, and guarantees watertightness. |
| 16 | `capture_multiview_sheet` | `mesh_path`, `output_filename` | Renders a 4-view studio LookDev sheet (Isometric 3/4 Hero, Front Close-Up, Profile, Rear View). |

---

## 🎯 Example Client Prompts

Here are examples of how to query your AI assistant once Local3D Studio is connected:

### 1. Generating a New 3D Printable Character from Prompt
> *"Create a 3D-printable warrior dwarf in A-Pose with full beard and battle hammer. Follow the Local3D Studio approval gate workflow."*
- The AI will call `compile_3d_master_prompt` and `generate_concept_image`.
- The AI presents the 2D concept image and pauses for your approval.
- Once you say *"Approved"*, the AI calls `confirm_concept_and_build_3d` to output `.stl`, `.glb`, and LookDev render.

### 2. Auto-Splitting a Model for 3D Printing / Bambu Studio AMS
> *"Take the Santa Claus STL and auto-split it into keyed parts for multi-color printing on my Bambu Lab printer."*
- The AI invokes `auto_split_model(input_mesh_path="output/Santa_Claus.stl", subject_category="humanoid")`.
- Generates 6 watertight parts in `output/Santa_Claus_parts/`, an exploded `.glb`, and `output/Santa_Claus_split.3mf` with pastel vertex colors ready for slicing.

### 3. Direct Image-to-3D with Retopology & PBR Baking
> *"Convert my weapon sketch at `assets/samples/sword.png` into a game-ready asset with quad retopology and baked normal maps."*
- The AI executes:
  1. `direct_image_to_3d(image_path="assets/samples/sword.png", generation_strategy="single_hero_34")`
  2. `retopologize_mesh(..., mode="quad", target_count=10000)`
  3. `bake_pbr_textures(..., texture_resolution=2048)`

---

## ⚙️ Environment Variables Reference (`.env`)

You can customize Local3D Studio's behavior by editing the `.env` file in the project root:

| Variable | Default | Options | Description |
|:---|:---|:---|:---|
| `FORCE_TIER` | `AUTO` | `AUTO`, `TIER_1`, `TIER_2`, `TIER_3`, `TIER_4` | Overrides automatic hardware detection tiering. |
| `QUALITY_MODE` | `auto` | `fast_draft`, `auto`, `ultra_production` | Default quality preset for neural generation. |
| `BLENDER_PATH` | *(auto-detected)* | File path to Blender executable | Explicit path to Blender if installed in a custom location. |
| `OUTPUT_DIR` | `./output` | File path | Directory where production deliverables are saved. |
| `WORKER_URL` | `http://127.0.0.1:8000` | URL string | Target URL if offloading compute to a remote desktop worker over LAN. |

---

## ❓ Troubleshooting & FAQs

### 1. Blender is not found automatically
If `get_hardware_status` reports `"blender_path": "NOT_FOUND"`, install Blender 4.x or 5.x and set its path in `.env`:
- **macOS**: `BLENDER_PATH=/Applications/Blender.app/Contents/MacOS/Blender`
- **Windows**: `BLENDER_PATH=C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`
- **Linux**: `BLENDER_PATH=/usr/bin/blender`

### 2. MCP client cannot connect or times out
- Ensure you point to the Python executable **inside the virtual environment** (`.venv/bin/python` or `.venv\Scripts\python.exe`), not the global system Python.
- Test the server directly from your terminal:
  ```bash
  source .venv/bin/activate
  python server.py
  ```
  The server should initialize cleanly and await stdio input without crashing.

### 3. Working within strict 16 GB unified RAM
- Keep `QUALITY_MODE=auto` or `FORCE_TIER=TIER_1`.
- Local3D Studio automatically flushes PyTorch VRAM and runs Python garbage collection between stages (`core/memory.py`), guaranteeing zero system freezes.
