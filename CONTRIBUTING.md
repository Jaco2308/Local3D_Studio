# Contributing to Local3D Studio

Thank you for your interest in contributing to **Local3D Studio**! 
Local3D Studio is dedicated to providing a 100% local, high-fidelity AI-to-3D generative and manufacturing pipeline adhering to a strict 16GB memory footprint.

---

## 🧭 Code of Conduct & Development Principles

1. **Zero Localhost/Daemon Dependencies for MCP**:
   - The MCP Server (`server.py`) must remain pure in-process. Never introduce mandatory `http://localhost:8000` requirements for standard MCP tools.
2. **Watertight Manifold Geometry Guaranteed**:
   - Every mesh emitted for 3D printing (`.stl`, `.3mf`) must be 100% manifold (`is_watertight = True`).
   - Slicing and booleans must include normal consistency recalculation and micro-sliver filtering.
3. **Cross-Platform Zero-CUDA-Exclusivity**:
   - The codebase runs on macOS (Apple Silicon MPS), Windows/Linux AMD GPUs (ROCm/DirectML), NVIDIA GPUs (CUDA), and CPU fallback.
   - Never write code that assumes CUDA is always present or fails when CUDA is absent.
4. **Temporary File Hygiene**:
   - All intermediate slices, temporary GLBs, and background masks must use `tempfile.TemporaryDirectory()`. The `output/` directory is reserved strictly for user-facing production deliverables.

---

## 🛠️ Development Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/your-username/Local3D-Studio.git
   cd Local3D-Studio
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   python setup_env.py
   ```

3. Verify tool registration and tests:
   ```bash
   python -c "import server; print(len(server.server._tool_manager.list_tools()), 'tools loaded!')"
   ```

---

## 🧪 Testing Your Changes

Before submitting a Pull Request, verify:
1. **MCP Tool Suite Validation**:
   Ensure all 16 MCP tools register and respond without runtime exceptions.
2. **Mesh Manifoldness**:
   If modifying `blender_pipeline.py` or `model_splitter.py`, run a test cut with `trimesh` to confirm `mesh.is_watertight == True`.
3. **Clean Diffs**:
   Ensure `.env`, virtualenvs, and test outputs are not committed.

---

## 🚀 Submitting a Pull Request

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Commit your changes with clear, descriptive commit messages:
   ```bash
   git commit -m "feat(splitter): enhance quadruped tail bisection"
   ```
3. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
4. Open a Pull Request against the `main` branch. Provide a concise summary of the changes and any test artifacts (e.g. LookDev sheets or part metrics).

---

## 📄 License
By contributing to Local3D Studio, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
