# 🚀 Local3D Studio — Suite di Manifattura 3D AI & Server MCP Universale a 16GB

[![Licenza: MIT](https://img.shields.io/badge/Licenza-MIT-blue.svg)](LICENSE)
[![Compatibile MCP](https://img.shields.io/badge/MCP-Compatibile-brightgreen.svg)](docs/MCP_GUIDE.md)
[![Sicurezza Memoria](https://img.shields.io/badge/RAM%2FVRAM-16GB%20Sicuro-orange.svg)](docs/ARCHITECTURE.md)
[![Hardware](https://img.shields.io/badge/Hardware-Apple%20Silicon%20|%20AMD%20ROCm%20|%20NVIDIA%20CUDA-purple.svg)](core/hardware_backend.py)
[![Documentazione](https://img.shields.io/badge/Docs-English-blue.svg)](README.md)

**Local3D Studio** è una suite di manifattura generativa 3D open-source e server Model Context Protocol (MCP) di livello industriale. Converte prompt testuali e fotografie 2D in figurine 3D a tenuta stagna pronte per la stampa (`.stl`), assemblaggi modulari con perni e giunti di montaggio (`.3mf`) e modelli digitali per videogiochi e animazione (`.glb`).

Progettato come **alternativa 100% locale, aperta e senza abbonamenti a piattaforme cloud come Meshy AI e Tripo3D**, Local3D Studio gira interamente su hardware consumer all'interno di un budget rigido di **16 GB di RAM/VRAM unificata**—senza richiedere flag di compilazione CUDA proprietari o server daemon in background.

> 🇬🇧 **Read in English**: [README.md](README.md)  
> 🏛️ **Architettura Tecnica Dettagliata**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)  
> 🔌 **Guida alla Configurazione dei Client MCP**: [docs/MCP_GUIDE.md](docs/MCP_GUIDE.md)

---

## 🌟 Funzionalità Principali

### 1. Suite Completa Open-Source Alternativa a Meshy AI (16 Tool MCP Nativi)
Local3D Studio fornisce una sostituzione locale e gratuita delle funzionalità delle piattaforme cloud commerciali:
- **Direct Image-to-3D (`direct_image_to_3d`)**: Conversione in 1 click di qualsiasi immagine o foto 2D in mesh solida 3D, con strategie `single_hero_34` (armi, veicoli, prop isometrici) o `multiview_turnaround` (personaggi e creature a 360°).
- **Auto Split & Assembly Keying (`auto_split_model`)**: Suddivide automaticamente mesh complesse in parti anatomiche (Testa, Torso, Braccia, Gambe) con tolleranza di incastro di 0.25mm, chiusura stagna dei tagli, vista esplosa `.glb` e pacchetto multi-colore `.3mf` pronto per Bambu Studio e OrcaSlicer AMS.
- **Humanoid Pose Guidance (`canonicalize_humanoid_pose`)**: Elimina la fusione indesiderata degli arti (*webbing*) standardizzando i personaggi in **A-Pose (35°-45°)**, **T-Pose (90°)**, **Action Pose** o **Natural Pose** con overlay vettoriale di verifica degli angoli.
- **AI Retopology Engine (`retopologize_mesh`)**: Genera topologia pulita tramite **Quadriflow 100% All-Quad** (ottimale per animazione e rigging) o **Decimate Triangle Collapse** a budget poligonale fisso (per motori di gioco).
- **PBR Texture Baking (`bake_pbr_textures`)**: Calcola mappe di Normali tangent-space e Ambient Occlusion (AO) fino a 4096px tramite Blender Cycles headless, esportando un `.glb` PBR completo.

### 2. Esecuzione MCP Pura In-Process (Zero Demoni o Porte Aperte)
A differenza di sistemi che richiedono server FastAPI sempre attivi su `localhost:8000`, il server MCP di Local3D Studio (`server.py`) comunica direttamente tramite lo standard **`stdio`**. Si connette a **Google Antigravity**, **Claude Desktop**, **Cursor** o **Continue.dev** semplicemente indicando il comando `server.py` o `run_mcp.sh`.

### 3. Rilevamento Hardware Automatico e 4 Profili di Prestazione Dinamici
Rileva autonomamente le risorse hardware del sistema (`psutil` + analisi PyTorch) e seleziona automaticamente il profilo ottimale:
- **macOS Apple Silicon**: Backend nativo `mps` con `torch.float16`.
- **AMD Radeon (Windows / Linux)**: Backend nativo AMD ROCm/HIP (`torch.version.hip`) o DirectML (`torch-directml`), libero da dipendenze CUDA proprietarie.
- **NVIDIA GeForce / RTX**: Backend nativo `cuda` con SDPA attention.
- **Blender Discovery**: Rileva autonomamente l'eseguibile di Blender su macOS, Windows e Linux.

| Livello | Hardware di Riferimento | Configurazione Motore 3D | Risoluzione Remesh & Triangoli |
|:---|:---|:---|:---|
| **`TIER 1 ECO`** | Mac 16GB / PC VRAM $\le 8$GB o RAM $\le 16$GB | Mini 320p (25 step) | `0.0025m` (80.000 triangoli) |
| **`TIER 2 BALANCED`** | Mac 24-36GB / PC 10-12GB VRAM | Mini 320p (25 step) | `0.0060m` (65.000 triangoli) |
| **`TIER 3 PRO 64GB`** | Mac $\ge 48$GB / PC $\ge 15$GB VRAM | **Full 1.1B** 384p (25 step) | `0.0025m` (90.000 triangoli) |
| **`TIER 4 ULTRA`** | PC $\ge 22$GB VRAM / Mac $\ge 64$GB | **Full 1.1B** 512p (35 step) | `0.0035m` (120.000 triangoli) |

### 4. Calibrazione Turnaround Multi-Vista (`tools/multiview_aligner.py`)
Elimina le allucinazioni sul retro e le occlusioni tipiche dei modelli a vista singola:
- **Isolamento Componenti Connesse**: Rimuove il bleed-over tra pannelli adiacenti tramite segmentazione delle maschere alpha (`scipy.ndimage`).
- **Y-Bounding-Box Lock**: Normalizza l'altezza della figura a 400px su canvas 512x512 trasparente, ancorando i piedi a $Z=0$ ($Y=456$) e la sommità della testa a $Y=56$.
- **CLAHE Normal Enhancement**: Esalta i micro-rilievi della superficie nell'albedo prima della ricostruzione neurale.

### 5. Hard Approval Gate e Igiene dei File Temporanei
- **Approval Gate**: Salva risorse di calcolo bloccando l'esecuzione dopo la generazione del concept 2D, attendendo la conferma esplicita dell'utente prima della generazione 3D.
- **Igiene File Temporanei**: Tutti i ritagli intermedi e le mesh grezze risiedono in `tempfile.TemporaryDirectory()`. Solo gli asset finali (`.stl`, `.glb`, `.3mf`, `lookdev_sheet.png`) vengono salvati in `output/`.

---

## 📂 Struttura del Repository

```text
Local3D-Studio/
├── .env.example                     # Configurazione di riferimento dell'ambiente
├── .gitignore                       # File e cartelle ignorati da git
├── LICENSE                          # Licenza Open Source MIT
├── CONTRIBUTING.md                  # Linee guida per i contributori
├── README.md                        # Documentazione Master in Inglese
├── README_IT.md                     # Documentazione Master in Italiano
├── requirements.txt                 # Dipendenze universali (zero dipendenze C++ proprietarie)
├── setup_env.py                     # Installer universale e bootstrapper hardware
├── run_mcp.sh / .bat                # Launcher server MCP stdio in-process
├── start_worker.sh / .bat           # Launcher opzionale Web Studio GUI
├── server.py                        # Server MCP Principale (16 Tool Nativi)
├── worker_api.py                    # Server opzionale FastAPI Web Studio & Three.js
│
├── core/                            # Livello di astrazione hardware e memoria
│   ├── __init__.py
│   ├── config.py                    # Variabili d'ambiente e percorsi globali
│   ├── hardware_backend.py          # HardwareManager (MPS / ROCm / CUDA / 4 Tier)
│   ├── memory.py                    # Garbage collector e svuotamento cache VRAM/RAM
│   └── client.py                    # Client REST unificato (per offloading LAN)
│
├── tools/                           # Motori Generativi e di Manifattura Modulari
│   ├── __init__.py
│   ├── prompt_enhancer.py           # Router dinamico di stili e pose (5 profili)
│   ├── pose_canonicalizer.py        # Guida Pose Umanoidi (overlay A-Pose/T-Pose)
│   ├── concept_engine.py            # Generatore concept 2D SDXL-Lightning (4-step)
│   ├── rembg_engine.py              # Rimozione sfondo in puro Python (u2net/ONNX)
│   ├── multiview_aligner.py         # Calibrazione anti-bleed e lock Y a Z=0
│   ├── neural_3d_engine.py          # Ricostruzione 3D Hunyuan3D-2 (Mini & Full)
│   ├── blender_pipeline.py          # Remesh headless Blender, LookDev, retopo, PBR
│   ├── model_splitter.py            # Auto Split, chiusura stagna e 3MF AMS
│   └── pipeline_engine.py           # Pipeline master di esecuzione e approval gate
│
├── frontend/                        # Web Studio Three.js GUI (Opzionale)
│   ├── __init__.py
│   └── web_viewer.py                # Viewport 3D Three.js, ispezione wireframe, telemetria
│
├── docs/                            # Guide tecniche di approfondimento
│   ├── ARCHITECTURE.md              # Deep-dive tecnico e diagrammi dei sottosistemi
│   └── MCP_GUIDE.md                 # Guida client MCP (Antigravity, Claude, Cursor)
│
└── output/                          # File di produzione generati (.stl, .glb, .3mf)
    └── .gitkeep
```

---

## ⚡ Guida Rapida

### 1. Installazione

```bash
git clone https://github.com/your-username/Local3D-Studio.git
cd Local3D-Studio

# Esegui l'installer universale (rileva Apple Silicon, AMD ROCm, NVIDIA CUDA)
python3 setup_env.py
```

`setup_env.py` esegue in automatico:
1. Rileva il sistema operativo e l'acceleratore GPU.
2. Installa la corretta versione di PyTorch (`mps`, `rocm`, `cuda` o `cpu`).
3. Installa le librerie necessarie (`mcp`, `diffusers`, `trimesh`, `rembg`, `scipy`, `psutil`, `fastapi`).
4. Individua autonomamente l'eseguibile di Blender.
5. Inizializza il file `.env`.

---

### 2. Connessione al Client MCP

Il server MCP di Local3D Studio gira **100% in locale in-process su stdio**.

Aggiungi Local3D Studio al file di configurazione del tuo client (es. `claude_desktop_config.json` o `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "local3d": {
      "command": "/percorso/assoluto/a/Local3D-Studio/.venv/bin/python",
      "args": [
        "/percorso/assoluto/a/Local3D-Studio/server.py"
      ]
    }
  }
}
```

*Per esempi completi per Google Antigravity, Claude Desktop, Cursor, Continue.dev e Windsurf, consulta [docs/MCP_GUIDE.md](docs/MCP_GUIDE.md).*

---

### 3. Opzionale: Web Studio GUI Interattivo Three.js

Se desideri visualizzare i modelli nel browser con drag & drop di foto, ispezione wireframe e telemetria hardware in tempo reale:

```bash
# macOS / Linux:
./start_worker.sh

# Windows:
start_worker.bat
```
Poi apri `http://localhost:8000` nel browser.

---

## 🛠️ Riferimento Completo dei 16 Tool MCP

| Nome Tool | Argomenti | Descrizione |
|:---|:---|:---|
| `get_hardware_status` | *(nessuno)* | Restituisce CPU, GPU (CUDA/ROCm/MPS), RAM/VRAM, Profilo di Prestazioni attivo (1-4) e percorso di Blender. |
| `set_quality_preset` | `preset` | Imposta la modalità qualitativa (`fast_draft`, `auto`, `ultra_production`). |
| `enhance_prompt_for_3d` | `prompt`, `mode`, `art_style`, `multiview`, `add_pedestal_base`, `humanoid_pose` | Espande prompt testuali in specifiche ottimali per la modellazione 3D attraverso 5 stili artistici. |
| `compile_3d_master_prompt` | `subject`, `art_style`, `key_details`, `add_pedestal_base`, `humanoid_pose` | Compila un prompt a 3 viste ortografiche con ampi margini vuoti e de-occlusione anatomica. |
| `generate_concept_image` | `prompt`, `output_filename`, `mode`, `art_style`, `multiview`, `add_pedestal_base`, `seed` | Genera il concept 2D con SDXL-Lightning (4-step float16) e attiva l'Hard Approval Gate. |
| `align_multiview_concept` | `concept_path` | Calibra le viste ortografiche, isola il soggetto via connected components, fissa l'altezza Y a 400px e applica CLAHE. |
| `confirm_concept_and_build_3d` | `concept_path`, `output_filename`, `quality_preset`, `target_height_mm`, `add_pedestal`, `art_style`, `target_triangles`, `voxel_size`, `auto_split` | **Hard Approval Gate**: Invocabile SOLO dopo approvazione utente per avviare la ricostruzione 3D e Blender. |
| `direct_image_to_3d` | `image_path`, `output_filename`, `quality_preset`, `generation_strategy`, `add_pedestal`, `target_height_mm`, `art_style`, `target_triangles`, `voxel_size`, `auto_split` | **Alternativa Meshy AI**: Trasformazione diretta in 1 step da qualsiasi foto a modello 3D (`single_hero_34` o `multiview_turnaround`). |
| `retopologize_mesh` | `input_mesh_path`, `output_filename`, `mode`, `target_count` | **Retopology AI**: Converte mesh dense in topologia pulita: Quadriflow all-quads (rigging) o Decimate triangoli (giochi). |
| `bake_pbr_textures` | `input_mesh_path`, `output_filename`, `texture_resolution`, `bake_normal`, `bake_ao` | **Baking PBR**: Calcola mappe di Normali tangent-space e AO tramite Blender Cycles ed esporta un GLB PBR. |
| `auto_split_model` | `input_mesh_path`, `output_filename`, `subject_category`, `add_connectors`, `connector_size_mm`, `exploded_distance_mm` | **Auto Split & Incastri**: Suddivide la mesh in parti stagne con perni da 0.25mm, vista esplosa GLB e 3MF multi-colore. |
| `canonicalize_humanoid_pose` | `image_path`, `target_pose`, `output_filename`, `art_style` | **Guida Postura**: Elimina il webbing ascellare e inguinale standardizzando i personaggi in posture canoniche. |
| `image_to_high_detail_stl` | `image_path`, `output_filename`, `quality_preset`, `target_height_mm`, `target_triangles`, `voxel_size`, `add_pedestal`, `art_style` | Pipeline di manifattura completa con verifica automatica dell'Approval Gate e preparazione stampa 3D. |
| `recalculate_in_ultra_production` | `output_filename` | Ricalcolo in 1 Click: Riesegue la ricostruzione 3D sull'ultimo concept a 100.000 triangoli in Ultra Production. |
| `prepare_for_3d_print` | `input_mesh_path`, `output_filename`, `target_height_mm`, `target_triangles`, `voxel_size`, `smooth_iterations`, `add_pedestal` | Ripara mesh esistenti, scala in millimetri, assicura il contatto a Z=0 e garantisce la tenuta stagna. |
| `capture_multiview_sheet` | `mesh_path`, `output_filename` | Esegue il rendering di una scheda LookDev a 4 viste (Prospettiva 3/4, Fronte, Profilo, Retro). |

---

## 🖨️ Flusso di Stampa Multi-Colore Bambu Lab / OrcaSlicer AMS

Quando utilizzi `auto_split_model`:
1. Local3D Studio suddivide la tua mesh in componenti anatomici (Testa, Torso, Braccia, Gambe).
2. Genera singoli file `.stl` a tenuta stagna in `output/<nome>_parts/` con perni maschio/femmina calibrati a 0.25mm.
3. Compila automaticamente un file `.3mf` unificato con assegnazione colore per vertice.
4. **Trascina e rilascia** il file `<nome>_split.3mf` direttamente in **Bambu Studio** o **OrcaSlicer**:
   - Lo slicer chiederà: *"Caricare questi oggetti come un singolo oggetto con parti multiple?"* -> Clicca **Sì**.
   - Assegna gli slot filamento (AMS Slot 1, 2, 3, 4) a ciascuna parte con un solo click.
   - Esegui lo slicing e stampa senza colla di montaggio e senza colorazione a mano!

---

## 🤝 Come Contribuire

Contributi, segnalazioni di bug e pull request sono i benvenuti! Ti invitiamo a leggere le nostre linee guida in [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📄 Licenza

Local3D Studio è rilasciato sotto la licenza open source **MIT License**. Consulta il file [LICENSE](LICENSE) per tutti i dettagli. Libero per uso personale, commerciale e di ricerca.
