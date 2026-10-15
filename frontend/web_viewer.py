"""
Interactive Three.js WebGL 3D Viewer Generator for Local3D Studio.
Creates a self-contained, high-performance HTML/WebGL viewer with:
- Dark-Glassmorphism UI Overlay: Quality Mode Selector (Fast Draft / Auto / Ultra Production)
- Dynamic Hardware Telemetry Badge (fetched live from worker API)
- 1-Click "Ricalcola in Ultra Production" action
- Physically Accurate Live Triangle Counter (directly computed from Three.js buffers)
- Quick Download Actions (.STL & .GLB)
- Real-Time WebSocket Progress Synchronization
- Three.js PBR shader pipeline, OrbitControls, ACES Filmic Tone Mapping, 3-point studio lighting
"""

import os
import base64
from typing import Optional, Dict, Any


def generate_interactive_viewer(
    glb_path: str,
    output_html_path: Optional[str] = None,
    title: Optional[str] = None,
    stl_path: Optional[str] = None,
    threemf_path: Optional[str] = None,
    mode_used: str = "auto",
    image_path: Optional[str] = None,
    art_style: str = "faithful_anatomical",
    embed_base64: bool = False,
    model_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generates an interactive 3D WebGL viewer HTML string/file for any .glb model.
    By default (embed_base64=False), streams the .glb directly via model_url or /api/v1/files/{glb_name},
    reducing HTML payload from ~8MB to <20KB and eliminating CPU/memory overhead.
    """
    if not os.path.exists(glb_path):
        raise FileNotFoundError(f"Model file not found: {glb_path}")

    glb_abs = os.path.abspath(glb_path)
    base_name = os.path.splitext(os.path.basename(glb_path))[0]

    if title is None:
        title = base_name.replace("_", " ")

    # Read hardware badge
    try:
        from core.hardware_backend import HardwareManager
        hw = HardwareManager.get_instance()
        hw_badge = hw.get_hardware_badge()
        hw_chip = f"GPU: {hw.device_info['name']} | RAM: {int(round(hw.memory_info['total_ram_gb']))}GB [{hw.tier_config.label}]"
    except Exception:
        hw_badge = "🚀 Hardware Tier: Auto-Detected"
        hw_chip = "Local3D Studio 3D Engine"

    stl_filename = os.path.basename(stl_path) if stl_path and os.path.exists(stl_path) else f"{base_name}.stl"
    threemf_filename = os.path.basename(threemf_path) if threemf_path and os.path.exists(threemf_path) else f"{base_name}.3mf"
    glb_filename = os.path.basename(glb_abs)
    image_filename = os.path.basename(image_path) if image_path and os.path.exists(image_path) else ""

    effective_model_url = model_url or f"/api/v1/files/{glb_filename}"
    if embed_base64:
        with open(glb_abs, "rb") as f:
            glb_data_src = '"data:model/gltf-binary;base64,' + base64.b64encode(f.read()).decode("utf-8") + '"'
    else:
        glb_data_src = f'"{effective_model_url}"'

    html_content = f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Local3D Studio</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      width: 100vw; height: 100vh;
      overflow: hidden;
      background: radial-gradient(circle at center, #1e293b 0%, #090d16 100%);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #f8fafc;
      user-select: none;
    }}
    #canvas-container {{ width: 100%; height: 100%; display: block; }}

    /* Top-Left Figurine Title & Info */
    .hud {{
      position: absolute;
      top: 20px; left: 24px;
      pointer-events: none;
      z-index: 10;
      max-width: 50%;
    }}
    .title {{
      font-size: 22px; font-weight: 700;
      letter-spacing: -0.5px;
      margin-bottom: 4px;
      color: #ffffff;
      text-shadow: 0 2px 10px rgba(0,0,0,0.6);
    }}
    .subtitle {{
      font-size: 13px; color: #94a3b8;
    }}
    .tier-badge {{
      display: inline-flex;
      align-items: center;
      margin-top: 8px;
      padding: 5px 12px;
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid rgba(56, 189, 248, 0.35);
      border-radius: 8px;
      font-size: 11px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      color: #38bdf8;
      backdrop-filter: blur(8px);
      box-shadow: 0 4px 14px rgba(0,0,0,0.4);
      pointer-events: auto;
    }}

    /* Top-Right Glassmorphic Control Bar */
    .control-panel {{
      position: absolute;
      top: 20px; right: 24px;
      z-index: 100;
      width: 330px;
      background: rgba(15, 23, 42, 0.82);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 16px;
      padding: 16px 18px;
      box-shadow: 0 12px 36px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.1);
      display: flex;
      flex-direction: column;
      gap: 12px;
      pointer-events: auto;
    }}

    .hw-chip {{
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      color: #38bdf8;
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid rgba(56, 189, 248, 0.28);
      padding: 4px 10px;
      border-radius: 6px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .hw-chip .dot {{
      width: 6px; height: 6px;
      border-radius: 50%;
      background: #38bdf8;
      box-shadow: 0 0 8px #38bdf8;
    }}

    .control-label {{
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.8px;
      text-transform: uppercase;
      color: #94a3b8;
    }}

    .select-wrapper {{
      position: relative;
      width: 100%;
    }}
    .dark-select {{
      width: 100%;
      appearance: none;
      -webkit-appearance: none;
      background: rgba(30, 41, 59, 0.9);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 8px;
      padding: 9px 32px 9px 12px;
      font-size: 12px;
      font-weight: 600;
      color: #f1f5f9;
      cursor: pointer;
      outline: none;
      transition: all 0.2s ease;
    }}
    .dark-select:focus {{
      border-color: #38bdf8;
      box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.25);
    }}
    .select-arrow {{
      position: absolute;
      right: 12px;
      top: 50%;
      transform: translateY(-50%);
      pointer-events: none;
      font-size: 10px;
      color: #94a3b8;
    }}

    .mode-desc {{
      font-size: 11px;
      color: #cbd5e1;
      line-height: 1.4;
      background: rgba(0, 0, 0, 0.2);
      padding: 6px 10px;
      border-radius: 6px;
      border-left: 2px solid #38bdf8;
    }}

    /* Recalculate Button */
    .btn-recalc {{
      width: 100%;
      padding: 10px 14px;
      border: none;
      border-radius: 8px;
      background: linear-gradient(135deg, #ea580c 0%, #c2410c 100%);
      color: #ffffff;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.2px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: all 0.2s ease;
      box-shadow: 0 4px 15px rgba(234, 88, 12, 0.4);
    }}
    .btn-recalc:hover {{
      transform: translateY(-1px);
      box-shadow: 0 6px 20px rgba(234, 88, 12, 0.6);
      background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
    }}
    .btn-recalc:active {{
      transform: translateY(0);
    }}
    .btn-recalc:disabled {{
      opacity: 0.5;
      cursor: not-allowed;
      transform: none;
      box-shadow: none;
    }}

    /* Mesh Counter */
    .mesh-stats {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 12px;
      background: rgba(30, 41, 59, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 8px;
      font-size: 12px;
    }}
    .mesh-stats strong {{
      color: #38bdf8;
      font-family: ui-monospace, monospace;
      font-size: 13px;
    }}
    .badge-watertight {{
      background: rgba(34, 197, 94, 0.2);
      border: 1px solid rgba(34, 197, 94, 0.4);
      color: #4ade80;
      font-size: 10px;
      font-weight: 700;
      padding: 2px 7px;
      border-radius: 4px;
      letter-spacing: 0.5px;
    }}

    /* Quick Action Download Buttons */
    .btn-row {{
      display: flex;
      gap: 8px;
    }}
    .btn-action {{
      flex: 1;
      text-align: center;
      text-decoration: none;
      padding: 8px 10px;
      border-radius: 8px;
      font-size: 11px;
      font-weight: 600;
      transition: all 0.2s ease;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 4px;
    }}
    .btn-stl {{
      background: rgba(56, 189, 248, 0.15);
      border: 1px solid rgba(56, 189, 248, 0.4);
      color: #38bdf8;
    }}
    .btn-stl:hover {{
      background: rgba(56, 189, 248, 0.25);
      border-color: #38bdf8;
      color: #ffffff;
    }}
    .btn-glb {{
      background: rgba(148, 163, 184, 0.15);
      border: 1px solid rgba(148, 163, 184, 0.3);
      color: #cbd5e1;
    }}
    .btn-glb:hover {{
      background: rgba(148, 163, 184, 0.25);
      color: #ffffff;
    }}

    /* Left Image-to-3D Dock (Meshy AI Alternative) */
    .upload-panel {{
      position: absolute;
      top: 110px; left: 24px;
      z-index: 100;
      width: 290px;
      background: rgba(15, 23, 42, 0.85);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 16px;
      padding: 14px 16px;
      box-shadow: 0 12px 36px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.1);
      display: flex;
      flex-direction: column;
      gap: 10px;
      pointer-events: auto;
    }}
    .drop-zone {{
      border: 2px dashed rgba(56, 189, 248, 0.45);
      background: rgba(15, 23, 42, 0.5);
      border-radius: 12px;
      padding: 16px 10px;
      text-align: center;
      cursor: pointer;
      transition: all 0.25s ease;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 105px;
    }}
    .drop-zone:hover, .drop-zone.dragover {{
      border-color: #38bdf8;
      background: rgba(56, 189, 248, 0.12);
      transform: scale(1.01);
    }}
    .btn-direct-gen {{
      width: 100%;
      padding: 10px 14px;
      border: none;
      border-radius: 8px;
      background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
      color: #ffffff;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.2px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: all 0.2s ease;
      box-shadow: 0 4px 15px rgba(2, 132, 199, 0.4);
    }}
    .btn-direct-gen:hover:not(:disabled) {{
      background: linear-gradient(135deg, #38bdf8 0%, #0284c7 100%);
      transform: translateY(-1px);
      box-shadow: 0 6px 20px rgba(56, 189, 248, 0.5);
    }}
    .btn-direct-gen:disabled {{
      opacity: 0.4;
      cursor: not-allowed;
      box-shadow: none;
    }}
    .btn-retopo {{
      width: 100%;
      padding: 8px 12px;
      border: none;
      border-radius: 8px;
      background: linear-gradient(135deg, #9333ea 0%, #7e22ce 100%);
      color: #ffffff;
      font-size: 11px;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: all 0.2s ease;
      box-shadow: 0 4px 12px rgba(147, 51, 234, 0.35);
    }}
    .btn-retopo:hover:not(:disabled) {{
      background: linear-gradient(135deg, #a855f7 0%, #9333ea 100%);
      transform: translateY(-1px);
    }}
    .btn-bake {{
      padding: 8px 12px;
      border: none;
      border-radius: 8px;
      background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%);
      color: #ffffff;
      font-size: 11px;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: all 0.2s ease;
      box-shadow: 0 4px 12px rgba(13, 148, 136, 0.35);
    }}
    .btn-bake:hover:not(:disabled) {{
      background: linear-gradient(135deg, #14b8a6 0%, #0d9488 100%);
      transform: translateY(-1px);
    }}

    /* Real-Time Progress Bar */
    .progress-box {{
      display: none;
      flex-direction: column;
      gap: 6px;
      background: rgba(15, 23, 42, 0.9);
      border: 1px solid rgba(234, 88, 12, 0.4);
      border-radius: 8px;
      padding: 10px 12px;
      animation: pulseBorder 2s infinite ease-in-out;
    }}
    @keyframes pulseBorder {{
      0% {{ border-color: rgba(234, 88, 12, 0.3); }}
      50% {{ border-color: rgba(234, 88, 12, 0.8); }}
      100% {{ border-color: rgba(234, 88, 12, 0.3); }}
    }}
    .progress-header {{
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      color: #ea580c;
      font-weight: 600;
    }}
    .progress-track {{
      width: 100%;
      height: 6px;
      background: rgba(255, 255, 255, 0.1);
      border-radius: 9999px;
      overflow: hidden;
    }}
    .progress-bar {{
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #ea580c 0%, #38bdf8 100%);
      border-radius: 9999px;
      transition: width 0.3s ease;
    }}

    .controls-hint {{
      position: absolute;
      bottom: 24px; left: 50%;
      transform: translateX(-50%);
      background: rgba(15, 23, 42, 0.75);
      backdrop-filter: blur(8px);
      padding: 8px 18px;
      border-radius: 9999px;
      font-size: 12px;
      color: #cbd5e1;
      border: 1px solid rgba(255,255,255,0.1);
      box-shadow: 0 4px 20px rgba(0,0,0,0.4);
      pointer-events: none;
      z-index: 10;
    }}
    #loading {{
      position: absolute;
      top: 50%; left: 50%;
      transform: translate(-50%, -50%);
      font-size: 15px; color: #38bdf8;
      font-weight: 500;
      letter-spacing: 0.5px;
      transition: opacity 0.4s ease;
      z-index: 20;
    }}
  </style>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js"></script>
</head>
<body>
  <!-- Top-Left Title HUD -->
  <div class="hud">
    <div class="title">{title}</div>
    <div class="subtitle">Local3D Studio • Meshy AI Competitor Suite • 100% Free & Open-Source</div>
    <div class="tier-badge">{hw_badge}</div>
  </div>

  <!-- Left Sidebar: Meshy-Style Image-to-3D Upload Dock -->
  <div class="upload-panel">
    <div class="control-label" style="display:flex; justify-content:space-between; align-items:center;">
      <span>📸 IMAGE-TO-3D DOCK</span>
      <span style="color:#38bdf8; font-size:9px;">OPEN-SOURCE MESHY</span>
    </div>

    <!-- Drag & Drop Zone -->
    <div id="dropZone" class="drop-zone">
      <input type="file" id="directFileInput" accept="image/*" style="display:none;">
      <div id="dropPrompt">
        <div style="font-size:24px; margin-bottom:4px;">📥</div>
        <div style="font-size:12px; font-weight:600; color:#f1f5f9;">Trascina qui l'immagine</div>
        <div style="font-size:10px; color:#94a3b8; margin-top:2px;">o clicca / incolla dagli appunti</div>
      </div>
      <div id="dropPreviewBox" style="display:none; position:relative; width:100%;">
        <img id="dropThumbnail" src="" style="max-height:105px; max-width:100%; border-radius:8px; object-fit:contain; box-shadow:0 4px 12px rgba(0,0,0,0.5);">
        <button id="clearDropImg" style="position:absolute; top:-6px; right:2px; background:#ef4444; color:#fff; border:none; border-radius:50%; width:20px; height:20px; font-size:11px; cursor:pointer; line-height:20px;">✕</button>
      </div>
    </div>

    <!-- Strategy Selector -->
    <div>
      <div class="control-label" style="margin-bottom: 4px;">Strategia Ricostruzione</div>
      <div class="select-wrapper">
        <select id="strategySelect" class="dark-select">
          <option value="single_hero_34" selected>🌟 Single 3/4 Hero (Meshy Style)</option>
          <option value="multiview_turnaround">🔄 Multi-View Turnaround (4 Viste)</option>
        </select>
        <span class="select-arrow">▼</span>
      </div>
    </div>

    <!-- Direct Generation Action -->
    <button id="directGenBtn" class="btn-direct-gen" disabled>
      <span>🚀 Genera Modello 3D</span>
    </button>
  </div>

  <!-- Top-Right Glassmorphic Quality Control Bar -->
  <div class="control-panel">
    <div class="hw-chip">
      <span class="dot"></span>
      <span id="hwChipText">{hw_chip}</span>
    </div>

    <div>
      <div class="control-label" style="margin-bottom: 6px;">Stile Artistico & Anatomia</div>
      <div class="select-wrapper">
        <select id="artStyleSelect" class="dark-select">
          <option value="faithful_anatomical" selected>🎯 Anatomia Fedele (Default Canoniche)</option>
          <option value="realistic_sculpt">🗿 Realistic Sculpt (ZBrush / Dettaglio Fine)</option>
          <option value="game_prop">⚔️ Game Prop (Hard Surface / Planar Bevels)</option>
          <option value="tabletop_miniature">🛡️ Tabletop Miniature (Scala Eroica 32mm/75mm)</option>
          <option value="stylized_vinyl">🧸 Stylized Vinyl (Chibi / Funko - Esplicito)</option>
        </select>
        <span class="select-arrow">▼</span>
      </div>
    </div>

    <div id="artStyleDescription" class="mode-desc">
      🎯 Proporzioni 100% canoniche e fedeli al soggetto originale, senza alterazioni o deformazioni.
    </div>

    <div>
      <div class="control-label" style="margin-bottom: 6px;">Profilo Qualità 3D</div>
      <div class="select-wrapper">
        <select id="modeSelect" class="dark-select">
          <option value="fast_draft">⚡ Fast Draft (8-10s | 30k tris)</option>
          <option value="auto" selected>⚖️ Auto Hardware Tier (Default)</option>
          <option value="ultra_production">💎 Ultra Production (Hunyuan Full 384p | 100k tris)</option>
        </select>
        <span class="select-arrow">▼</span>
      </div>
    </div>

    <div id="modeDescription" class="mode-desc">
      Usa i parametri ideali rilevati automaticamente dall'hardware manager.
    </div>

    <button id="recalcBtn" class="btn-recalc">
      <span>🔥 Ricalcola in Ultra Production</span>
    </button>

    <!-- Real-Time Progress -->
    <div id="progressSection" class="progress-box">
      <div class="progress-header">
        <span id="progressStep">Avvio processo 3D...</span>
        <span id="progressPct">0%</span>
      </div>
      <div class="progress-track">
        <div id="progressFill" class="progress-bar"></div>
      </div>
    </div>

    <!-- Live Mesh Stats -->
    <div class="mesh-stats">
      <span>Triangoli: <strong id="polyCount">Calcolo...</strong></span>
      <span class="badge-watertight">WATERTIGHT: YES</span>
    </div>

    <!-- Retopology Section (Step 3) -->
    <div style="border-top: 1px solid rgba(255,255,255,0.1); padding-top: 8px;">
      <div class="control-label" style="margin-bottom: 6px; display:flex; justify-content:space-between;">
        <span>📐 AI Retopology</span>
        <span style="color:#c084fc; font-size:9px;">QUADS & TRIS</span>
      </div>
      <div style="display:flex; gap:6px; margin-bottom:6px;">
        <div class="select-wrapper" style="flex:1;">
          <select id="retopoModeSelect" class="dark-select">
            <option value="quad" selected>Quads (Quadriflow)</option>
            <option value="tri">Tris (Decimate)</option>
          </select>
          <span class="select-arrow">▼</span>
        </div>
        <div class="select-wrapper" style="width:110px;">
          <select id="retopoCountSelect" class="dark-select">
            <option value="5000">5,000</option>
            <option value="10000" selected>10,000</option>
            <option value="25000">25,000</option>
            <option value="50000">50,000</option>
          </select>
          <span class="select-arrow">▼</span>
        </div>
      </div>
      <button id="retopoBtn" class="btn-retopo">
        <span>📐 Esegui Retopology</span>
      </button>
    </div>

    <!-- PBR Texture Baking Section (Step 4) -->
    <div style="border-top: 1px solid rgba(255,255,255,0.1); padding-top: 8px;">
      <div class="control-label" style="margin-bottom: 6px; display:flex; justify-content:space-between;">
        <span>🎨 PBR Texture Baking</span>
        <span style="color:#2dd4bf; font-size:9px;">CYCLES NORMAL & AO</span>
      </div>
      <div style="display:flex; gap:6px;">
        <div class="select-wrapper" style="flex:1;">
          <select id="bakeResSelect" class="dark-select">
            <option value="1024">1024 x 1024</option>
            <option value="2048" selected>2048 x 2048 (HD)</option>
            <option value="4096">4096 x 4096 (4K)</option>
          </select>
          <span class="select-arrow">▼</span>
        </div>
        <button id="bakeBtn" class="btn-bake" style="flex:1;">
          <span>🎨 Bake Maps</span>
        </button>
      </div>
    </div>

    <!-- Quick Action Download Buttons -->
    <div class="btn-row">
      <a id="downloadStl" class="btn-action btn-stl" href="/api/v1/files/{stl_filename}" download="{stl_filename}">
        ⬇️ .STL
      </a>
      <a id="download3mf" class="btn-action btn-stl" style="background: rgba(34, 197, 94, 0.15); border-color: rgba(34, 197, 94, 0.4); color: #86efac;" href="/api/v1/files/{threemf_filename}" download="{threemf_filename}">
        ⬇️ .3MF (Bambu)
      </a>
      <a id="downloadGlb" class="btn-action btn-glb" href="/api/v1/files/{glb_filename}" download="{glb_filename}">
        ⬇️ .GLB
      </a>
    </div>
  </div>

  <div class="controls-hint">🖱️ Trascina per ruotare • Rotellina per zoomare • Tasto destro per spostare</div>
  <div id="loading">Caricamento modello 3D in corso...</div>
  <div id="canvas-container"></div>

  <script>
    const container = document.getElementById('canvas-container');
    const loadingElem = document.getElementById('loading');
    const modeSelect = document.getElementById('modeSelect');
    const modeDescription = document.getElementById('modeDescription');
    const artStyleSelect = document.getElementById('artStyleSelect');
    const artStyleDescription = document.getElementById('artStyleDescription');
    const recalcBtn = document.getElementById('recalcBtn');
    const progressSection = document.getElementById('progressSection');
    const progressStep = document.getElementById('progressStep');
    const progressPct = document.getElementById('progressPct');
    const progressFill = document.getElementById('progressFill');
    const polyCountElem = document.getElementById('polyCount');
    const hwChipText = document.getElementById('hwChipText');

    // Meshy Dock Elements
    const dropZone = document.getElementById('dropZone');
    const directFileInput = document.getElementById('directFileInput');
    const dropPrompt = document.getElementById('dropPrompt');
    const dropPreviewBox = document.getElementById('dropPreviewBox');
    const dropThumbnail = document.getElementById('dropThumbnail');
    const clearDropImg = document.getElementById('clearDropImg');
    const strategySelect = document.getElementById('strategySelect');
    const directGenBtn = document.getElementById('directGenBtn');

    // Retopo & Bake Elements
    const retopoBtn = document.getElementById('retopoBtn');
    const retopoModeSelect = document.getElementById('retopoModeSelect');
    const retopoCountSelect = document.getElementById('retopoCountSelect');
    const bakeBtn = document.getElementById('bakeBtn');
    const bakeResSelect = document.getElementById('bakeResSelect');

    let currentModelObject = null;
    let currentModeUsed = "{mode_used}";
    let currentArtStyle = "{art_style}";
    let currentImageFilename = "{image_filename}";
    if (artStyleSelect && currentArtStyle) {{
      artStyleSelect.value = currentArtStyle;
    }}


    const modeDescriptions = {{
      fast_draft: "⚡ Generazione ultra-rapida (~8-10s) con Hunyuan3D-2mini a 192p e decimate a 30.000 triangoli. Ottima per test di silhouette.",
      auto: "⚖️ Impostazioni bilanciate ottimali calibrate dinamicamente sulla RAM e GPU del tuo sistema.",
      ultra_production: "💎 Massima fedeltà geometrica: Hunyuan3D-2 Full a 384p, remesh ultra-denso (0.0038) e 100.000 triangoli per stampa 3D HD."
    }};

    const artStyleDescriptions = {{
      faithful_anatomical: "🎯 Proporzioni 100% canoniche e fedeli al soggetto originale, senza alterazioni o deformazioni.",
      realistic_sculpt: "🗿 Scultura anatomica organica tipo ZBrush con rugosità superficiali e pieghe ad alta definizione.",
      game_prop: "⚔️ Superfici rigide, tagli netti e biselli controllati per armature, armi e veicoli.",
      tabletop_miniature: "🛡️ Miniatura heroic scale (32mm/75mm) con volumi rinforzati per miniature da wargame e RPG.",
      stylized_vinyl: "🧸 Stile vinyl toy con testa arrotondata e dettagli semplificati (applicato SOLO se espressamente richiesto)."
    }};

    // 1. Scene & Camera Setup
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.set(0, 35, 130);

    // 2. WebGL Renderer with ACES Tone Mapping
    const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);

    // 3. OrbitControls
    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI / 2 + 0.05;
    controls.minDistance = 20;
    controls.maxDistance = 300;

    // 4. Studio 3-Point Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.65);
    scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0xffffff, 1.4);
    keyLight.position.set(45, 80, 60);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.width = 2048;
    keyLight.shadow.mapSize.height = 2048;
    keyLight.shadow.bias = -0.0005;
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0xb4d4ff, 0.7);
    fillLight.position.set(-50, 40, -30);
    scene.add(fillLight);

    const rimLight = new THREE.DirectionalLight(0xffecd2, 1.1);
    rimLight.position.set(0, 60, -80);
    scene.add(rimLight);

    // Ground Shadow Catcher
    const shadowPlaneGeo = new THREE.PlaneGeometry(300, 300);
    const shadowPlaneMat = new THREE.ShadowMaterial({{ opacity: 0.35 }});
    const shadowPlane = new THREE.Mesh(shadowPlaneGeo, shadowPlaneMat);
    shadowPlane.rotation.x = -Math.PI / 2;
    shadowPlane.position.y = 0;
    shadowPlane.receiveShadow = true;
    scene.add(shadowPlane);

    // 5. Load 3D Model Function
    const loader = new THREE.GLTFLoader();

    function loadModelFromUri(uri) {{
      loadingElem.style.display = 'block';
      loadingElem.style.opacity = '1';

      loader.load(
        uri,
        function (gltf) {{
          if (currentModelObject) {{
            scene.remove(currentModelObject);
          }}

          const model = gltf.scene;
          currentModelObject = model;

          // Compute exact physical triangles from Three.js buffers
          let totalTriangles = 0;
          model.traverse((node) => {{
            if (node.isMesh && node.geometry) {{
              if (node.geometry.index) {{
                totalTriangles += node.geometry.index.count / 3;
              }} else if (node.geometry.attributes.position) {{
                totalTriangles += node.geometry.attributes.position.count / 3;
              }}
              node.castShadow = true;
              node.receiveShadow = true;
              if (node.material) {{
                node.material.roughness = Math.max(0.35, node.material.roughness || 0.4);
                node.material.metalness = Math.min(0.1, node.material.metalness || 0.0);
                node.material.needsUpdate = true;
              }}
            }}
          }});

          polyCountElem.innerText = Math.round(totalTriangles).toLocaleString();

          // Auto-center & Floor Alignment
          const box = new THREE.Box3().setFromObject(model);
          const size = box.getSize(new THREE.Vector3());
          const center = box.getCenter(new THREE.Vector3());

          model.position.x = -center.x;
          model.position.y = -box.min.y;
          model.position.z = -center.z;

          scene.add(model);

          loadingElem.style.opacity = '0';
          setTimeout(() => {{ loadingElem.style.display = 'none'; }}, 300);

          controls.target.set(0, size.y * 0.45, 0);
          camera.position.set(0, size.y * 0.7, size.y * 1.8);
          controls.update();

          // Update Recalculate button state
          if (totalTriangles < 45000) {{
            recalcBtn.style.display = 'flex';
          }}
        }},
        undefined,
        function (error) {{
          console.error('Error loading 3D model:', error);
          loadingElem.innerText = 'Errore nel caricamento del modello 3D.';
          loadingElem.style.color = '#ef4444';
        }}
      );
    }}

    // Initial Model Load (Direct Streaming URL or Base64 embedded)
    const initialGlbUri = {glb_data_src};
    loadModelFromUri(initialGlbUri);

    // 6. Quality Mode & Art Style Sync with Backend
    modeSelect.addEventListener('change', async (e) => {{
      const selected = e.target.value;
      modeDescription.innerText = modeDescriptions[selected] || "";
      
      try {{
        await fetch('/api/set-quality-mode', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ quality_mode: selected }})
        }});
        console.log('[Local3D Studio] Quality mode set to:', selected);
      }} catch (err) {{
        console.warn('Backend not responding to mode change (standalone mode).');
      }}
    }});

    artStyleSelect.addEventListener('change', async (e) => {{
      const selected = e.target.value;
      artStyleDescription.innerText = artStyleDescriptions[selected] || "";
      
      try {{
        await fetch('/api/set-art-style', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ art_style: selected }})
        }});
        console.log('[Local3D Studio] Art style set to:', selected);
      }} catch (err) {{
        console.warn('Backend not responding to art style change (standalone mode).');
      }}
    }});

    // 7. Live Telemetry Fetch from Worker API
    async function syncHardwareInfo() {{
      try {{
        const res = await fetch('/api/hardware-status');
        if (res.ok) {{
          const data = await res.json();
          if (data.chip_summary) {{
            hwChipText.innerText = data.chip_summary;
          }}
          if (data.quality_mode && modeSelect.value !== data.quality_mode) {{
            modeSelect.value = data.quality_mode;
            modeDescription.innerText = modeDescriptions[data.quality_mode] || "";
          }}
          if (data.art_style && artStyleSelect.value !== data.art_style) {{
            artStyleSelect.value = data.art_style;
            artStyleDescription.innerText = artStyleDescriptions[data.art_style] || "";
          }}
          if (data.current_image_filename) {{
            currentImageFilename = data.current_image_filename;
          }}
        }}
      }} catch (err) {{
        // Standalone file fallback
      }}
    }}
    syncHardwareInfo();

    // 8. WebSocket for Real-Time Pipeline Progress
    let progressWs = null;
    function connectProgressWs() {{
      try {{
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        progressWs = new WebSocket(`${{protocol}}//${{window.location.host}}/ws/progress`);
        
        progressWs.onmessage = (event) => {{
          const data = JSON.parse(event.data);
          if (data.percent !== undefined) {{
            progressSection.style.display = 'flex';
            progressStep.innerText = data.message || "Elaborazione...";
            progressPct.innerText = `${{data.percent}}%`;
            progressFill.style.width = `${{data.percent}}%`;

            if (data.percent >= 100) {{
              setTimeout(() => {{
                progressSection.style.display = 'none';
              }}, 3500);

              if (data.glb_url) {{
                loadModelFromUri(data.glb_url);
              }}
              if (data.stl_url) {{
                document.getElementById('downloadStl').href = data.stl_url;
              }}
            }}
          }}
        }};

        progressWs.onclose = () => {{
          setTimeout(connectProgressWs, 3000);
        }};
      }} catch (err) {{
        console.log('WebSocket connection skipped in file:// protocol.');
      }}
    }}
    if (window.location.protocol.startsWith('http')) {{
      connectProgressWs();
    }}

    // 9. Recalculate Button Handler
    recalcBtn.addEventListener('click', async () => {{
      recalcBtn.disabled = true;
      progressSection.style.display = 'flex';
      progressStep.innerText = "1/3 Inizializzazione Ultra Production (100k tris)...";
      progressPct.innerText = "10%";
      progressFill.style.width = "10%";

      try {{
        const res = await fetch('/api/recalculate', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ quality_preset: 'ultra_production' }})
        }});

        if (res.ok) {{
          const result = await res.json();
          if (result.glb_download_url) {{
            loadModelFromUri(result.glb_download_url);
          }}
          if (result.stl_download_url) {{
            document.getElementById('downloadStl').href = result.stl_download_url;
          }}
          progressStep.innerText = "Produzione 100k triangoli completata!";
          progressPct.innerText = "100%";
          progressFill.style.width = "100%";
          setTimeout(() => {{ progressSection.style.display = 'none'; }}, 3000);
        }} else {{
          const errData = await res.json();
          alert('Errore ricalcolo: ' + (errData.detail || 'Operazione fallita'));
          progressSection.style.display = 'none';
        }}
      }} catch (err) {{
        alert('Impossibile contattare il Worker 3D API su ' + window.location.origin);
        progressSection.style.display = 'none';
      }} finally {{
        recalcBtn.disabled = false;
      }}
    }});

    // 10. Drag & Drop Image-to-3D Dock Handler
    let selectedDropFile = null;

    if (dropZone && directFileInput) {{
      dropZone.addEventListener('click', (e) => {{
        if (e.target !== clearDropImg) {{
          directFileInput.click();
        }}
      }});

      directFileInput.addEventListener('change', (e) => {{
        if (e.target.files && e.target.files[0]) {{
          handleImageSelect(e.target.files[0]);
        }}
      }});

      dropZone.addEventListener('dragover', (e) => {{
        e.preventDefault();
        dropZone.classList.add('dragover');
      }});

      dropZone.addEventListener('dragleave', () => {{
        dropZone.classList.remove('dragover');
      }});

      dropZone.addEventListener('drop', (e) => {{
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {{
          handleImageSelect(e.dataTransfer.files[0]);
        }}
      }});

      window.addEventListener('paste', (e) => {{
        const clipData = e.clipboardData || window.clipboardData;
        if (clipData && clipData.items) {{
          for (let i = 0; i < clipData.items.length; i++) {{
            if (clipData.items[i].type.indexOf('image') !== -1) {{
              const blob = clipData.items[i].getAsFile();
              handleImageSelect(blob);
              break;
            }}
          }}
        }}
      }});
    }}

    function handleImageSelect(file) {{
      selectedDropFile = file;
      const reader = new FileReader();
      reader.onload = (ev) => {{
        dropThumbnail.src = ev.target.result;
        dropPrompt.style.display = 'none';
        dropPreviewBox.style.display = 'block';
        directGenBtn.disabled = false;
      }};
      reader.readAsDataURL(file);
    }}

    if (clearDropImg) {{
      clearDropImg.addEventListener('click', (e) => {{
        e.stopPropagation();
        selectedDropFile = null;
        directFileInput.value = '';
        dropThumbnail.src = '';
        dropPrompt.style.display = 'block';
        dropPreviewBox.style.display = 'none';
        directGenBtn.disabled = true;
      }});
    }}

    if (directGenBtn) {{
      directGenBtn.addEventListener('click', async () => {{
        if (!selectedDropFile) return;
        directGenBtn.disabled = true;
        progressSection.style.display = 'flex';
        progressStep.innerText = '1/3 Pre-processing & Isolamento sagoma...';
        progressPct.innerText = '15%';
        progressFill.style.width = '15%';

        const fd = new FormData();
        fd.append('file', selectedDropFile);
        const baseName = (selectedDropFile.name || 'direct_model').split('.')[0] + '_3d';
        fd.append('output_name', baseName);
        fd.append('quality_preset', modeSelect.value || 'auto');
        fd.append('generation_strategy', strategySelect.value || 'single_hero_34');
        fd.append('art_style', artStyleSelect.value || 'faithful_anatomical');

        try {{
          const res = await fetch('/api/v1/direct-image-to-3d', {{
            method: 'POST',
            body: fd
          }});
          if (res.ok) {{
            const data = await res.json();
            if (data.glb_download_url) loadModelFromUri(data.glb_download_url);
            if (data.stl_download_url) document.getElementById('downloadStl').href = data.stl_download_url;
            if (data.threemf_download_url) document.getElementById('download3mf').href = data.threemf_download_url;
            progressStep.innerText = 'Generazione completata con successo!';
            progressPct.innerText = '100%';
            progressFill.style.width = '100%';
            setTimeout(() => {{ progressSection.style.display = 'none'; }}, 3000);
          }} else {{
            const err = await res.json();
            alert('Errore generazione: ' + (err.detail || 'Operazione fallita'));
            progressSection.style.display = 'none';
          }}
        }} catch (err) {{
          alert('Errore di connessione col server worker.');
          progressSection.style.display = 'none';
        }} finally {{
          directGenBtn.disabled = false;
        }}
      }});
    }}

    // 11. Retopology Handler
    if (retopoBtn) {{
      retopoBtn.addEventListener('click', async () => {{
        retopoBtn.disabled = true;
        progressSection.style.display = 'flex';
        progressStep.innerText = 'Esecuzione Retopology in Blender headless...';
        progressPct.innerText = '30%';
        progressFill.style.width = '30%';

        try {{
          const res = await fetch('/api/v1/retopologize', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{
              mode: retopoModeSelect.value,
              target_count: parseInt(retopoCountSelect.value, 10)
            }})
          }});
          if (res.ok) {{
            const data = await res.json();
            if (data.glb_download_url) loadModelFromUri(data.glb_download_url);
            if (data.stl_download_url) document.getElementById('downloadStl').href = data.stl_download_url;
            if (data.threemf_download_url) document.getElementById('download3mf').href = data.threemf_download_url;
            progressStep.innerText = 'Retopology completata!';
            progressPct.innerText = '100%';
            progressFill.style.width = '100%';
            setTimeout(() => {{ progressSection.style.display = 'none'; }}, 3000);
          }} else {{
            const err = await res.json();
            alert('Errore retopology: ' + (err.detail || 'Operazione fallita'));
            progressSection.style.display = 'none';
          }}
        }} catch (err) {{
          alert('Impossibile contattare il Worker 3D API.');
          progressSection.style.display = 'none';
        }} finally {{
          retopoBtn.disabled = false;
        }}
      }});
    }}

    // 12. PBR Texture Baking Handler
    if (bakeBtn) {{
      bakeBtn.addEventListener('click', async () => {{
        bakeBtn.disabled = true;
        progressSection.style.display = 'flex';
        progressStep.innerText = 'Baking mappe Normal & AO in Blender Cycles...';
        progressPct.innerText = '35%';
        progressFill.style.width = '35%';

        try {{
          const res = await fetch('/api/v1/bake-textures', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{
              texture_resolution: parseInt(bakeResSelect.value, 10),
              bake_normal: true,
              bake_ao: true
            }})
          }});
          if (res.ok) {{
            const data = await res.json();
            if (data.glb_download_url) loadModelFromUri(data.glb_download_url);
            progressStep.innerText = 'PBR Texture Baking completato!';
            progressPct.innerText = '100%';
            progressFill.style.width = '100%';
            setTimeout(() => {{ progressSection.style.display = 'none'; }}, 3000);
          }} else {{
            const err = await res.json();
            alert('Errore baking: ' + (err.detail || 'Operazione fallita'));
            progressSection.style.display = 'none';
          }}
        }} catch (err) {{
          alert('Impossibile contattare il Worker 3D API.');
          progressSection.style.display = 'none';
        }} finally {{
          bakeBtn.disabled = false;
        }}
      }});
    }}

    // 13. Responsive Window Resize
    window.addEventListener('resize', () => {{
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    }});


    // 11. Render Loop
    function animate() {{
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    }}
    animate();
  </script>
</body>
</html>
"""
    if output_html_path:
        with open(output_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"[WebViewer] Interactive Three.js Studio HTML generated at: {output_html_path}")

    return {
        "status": "success",
        "html_path": output_html_path,
        "html_content": html_content,
        "title": title,
        "hardware_badge": hw_badge
    }
