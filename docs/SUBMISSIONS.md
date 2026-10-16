# 🚀 Local3D Studio — MCP Directory Submissions & Community Launch Guide

**Slogan**: *"Local Image-to-3MF/STL Manufacturing & Auto-Keyed Splitting for 3D Printing"*  
**Repository**: [https://github.com/Jaco2308/Local3D_Studio](https://github.com/Jaco2308/Local3D_Studio)

---

## 1. Official Model Context Protocol Registry (`modelcontextprotocol/servers`)

- **Repository**: [https://github.com/modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers)
- **Action**: Fork, edit `README.md` under **Community Servers**, and open a Pull Request.

### Pull Request Title
```text
Add Local3D Studio: Local Image-to-3MF/STL Manufacturing & Auto-Keyed Splitting
```

### Table Entry for `modelcontextprotocol/servers/README.md`
```markdown
| [Local3D Studio](https://github.com/Jaco2308/Local3D_Studio) | 100% local image-to-3MF/STL generative manufacturing server with auto-keyed anatomical splitting (0.25mm pins), multi-color AMS export, and headless Blender integration on 16GB consumer hardware. | [Python](https://github.com/Jaco2308/Local3D_Studio) |
```

### Pull Request Description
```markdown
### Summary
Adds **Local3D Studio** to the Community Servers list.

**Local3D Studio** is an open-source, production-grade 3D generative manufacturing suite and MCP server running locally over standard `stdio`.

- **Key Capabilities**: 
  - Direct 2D-to-3D neural mesh synthesis (`direct_image_to_3d`).
  - Automated anatomical model splitting with 0.25mm keyed male/female pins (`auto_split_model`).
  - Multi-part `.3mf` export ready for Bambu Studio & OrcaSlicer AMS multi-color printing.
  - Headless Blender mesh repair, Quadriflow retopology, and tangent-space normal/AO baking.
  - 16GB Unified RAM/VRAM safety with dynamic hardware auto-detection (Apple Silicon MPS, AMD ROCm, NVIDIA CUDA).
```

---

## 2. Smithery.ai Directory

- **Website**: [https://smithery.ai](https://smithery.ai)
- **Configuration**: Local3D Studio includes a native [`smithery.yaml`](../smithery.yaml).

### Automated CLI Publishing
```bash
npx -y @smithery/cli publish
```

### 1-Click User Installation Command
```bash
npx -y @smithery/cli install @Jaco2308/Local3D_Studio --client claude
```

---

## 3. mcpservers.org Listing

- **Submission Page**: [https://mcpservers.org/submit](https://mcpservers.org/submit)
- **Name**: `Local3D Studio`
- **GitHub URL**: `https://github.com/Jaco2308/Local3D_Studio`
- **Short Description**: `Local Image-to-3MF/STL Manufacturing & Auto-Keyed Splitting for 3D Printing`
- **Category**: `Development / 3D & Graphics / AI Agents`
- **Transport**: `stdio`

---

## 4. Reddit Launch Posts

### A. Post for `r/mcp` (Model Context Protocol Community)

**Title**:
```text
[Release] Local3D Studio: 100% Local Image-to-3MF/STL Manufacturing MCP Server (16GB Safe, Zero Cloud)
```

**Body**:
```markdown
Hey everyone! 👋

I'm excited to share **Local3D Studio**, an open-source Model Context Protocol server designed to give LLMs direct generative manufacturing capabilities on consumer hardware.

🔗 **GitHub**: https://github.com/Jaco2308/Local3D_Studio  
📸 **Showcase Banner**: [assets/pipeline_showcase.png](https://raw.githubusercontent.com/Jaco2308/Local3D_Studio/main/assets/pipeline_showcase.png)

### Why I built it:
Cloud 3D generators (like Meshy or Tripo) are expensive, locked behind monthly subscriptions, and return single-shell meshes that are impossible to print in multi-color without hours of manual slicing work.

Local3D Studio solves this entirely locally:
1. **Zero-Daemon stdio Execution**: Genuinely connects in-process to Google Antigravity, Claude Desktop, Cursor, or Continue.dev over `stdio`.
2. **16GB Unified RAM/VRAM Safe**: 2D generation is offloaded to the client AI's native vision generator or user photos, dedicating 100% of the 16 GB unified RAM/VRAM to Hunyuan3D-2 neural reconstruction and headless Blender.
3. **Auto-Keyed Model Splitting (`auto_split_model`)**: Automatically bisects models into Head, Torso, Arms, and Legs, adds 0.25mm keyed male pins and female sockets, manifold watertight caps, and exports a unified `.3mf` package.
4. **Bambu Studio / OrcaSlicer Multi-Color Ready**: Drag and drop the generated `.3mf` directly into your slicer, assign AMS filament slots, and slice.

### Quick Start via Claude Desktop / Cursor:
```json
{
  "mcpServers": {
    "local3d": {
      "command": "/path/to/Local3D_Studio/.venv/bin/python",
      "args": ["/path/to/Local3D_Studio/server.py"]
    }
  }
}
```

Or install with 1 click via Smithery:
```bash
npx -y @smithery/cli install @Jaco2308/Local3D_Studio --client claude
```

Would love to hear your feedback and feature requests!
```

---

### B. Post for `r/BambuLab` & `r/3Dprinting`

**Title**:
```text
I built an open-source, 100% local Image-to-3MF generator with Auto-Keyed Splitting (0.25mm pins) for Bambu Studio & OrcaSlicer AMS
```

**Body**:
```markdown
Hi Bambu Lab & 3D printing community! 🖨️✨

Like many of you, I've wanted a way to turn concept art or reference photos into physical, multi-color figurines without spending hours manually cutting meshes, creating boolean pins, or paying \$30/month for cloud AI tools.

I built **Local3D Studio**, a 100% local-first generative manufacturing pipeline that runs entirely on your own PC or Mac (16GB RAM/VRAM safe):

🔗 **GitHub**: https://github.com/Jaco2308/Local3D_Studio  
📸 **Showcase Workflow**: [Check out the pipeline render](https://raw.githubusercontent.com/Jaco2308/Local3D_Studio/main/assets/pipeline_showcase.png)

### What makes it special for Bambu Studio / OrcaSlicer users:
- **Auto-Keyed Splitting (`auto_split_model`)**: It automatically cuts characters into Head, Torso, Arms, and Legs with manifold watertight capping and automatically adds **0.25mm clearance male connector pegs and female sockets** so parts snap together securely after printing.
- **Native Multi-Color `.3mf` Export**: Generates a single `.3mf` assembly file. When you drag & drop it into Bambu Studio or OrcaSlicer, it prompts: *"Load these objects as a single object with multiple parts?"* -> Click **Yes**, and each part is pre-assigned to separate AMS slots!
- **100% Local (Zero Cloud Subscriptions)**: Uses Hunyuan3D-2 and Blender headless locally.
- **Strict 16GB Memory Budget**: By using your AI client or your own photo for 2D, 100% of your RAM is reserved for dense 3D reconstruction without freezing your system.

### Formats Output:
- `.stl`: Individual watertight parts in `output/<name>_parts/` with pins.
- `.3mf`: Multi-part assembly ready for Bambu Studio AMS.
- `.glb`: Exploded assembly view and textured digital asset.
- `_lookdev_sheet.png`: 4-view studio render (Hero, Front, Profile, Rear).

It's completely free and open-source under the MIT license. Hope this is helpful for the community!
```
