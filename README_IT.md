# 🚀 Local3D Studio — Suite di Manifattura 3D AI & Server MCP Universale a 16GB

[![Licenza: MIT](https://img.shields.io/badge/Licenza-MIT-blue.svg)](LICENSE)
[![Compatibile MCP](https://img.shields.io/badge/MCP-Compatibile-brightgreen.svg)](docs/MCP_GUIDE.md)
[![Sicurezza Memoria](https://img.shields.io/badge/RAM%2FVRAM-16GB%20Sicuro-orange.svg)](docs/ARCHITECTURE.md)
[![Hardware](https://img.shields.io/badge/Hardware-Apple%20Silicon%20|%20AMD%20ROCm%20|%20NVIDIA%20CUDA-purple.svg)](core/hardware_backend.py)
[![Documentazione](https://img.shields.io/badge/Docs-English-blue.svg)](README.md)

<p align="center">
  <img src="assets/pipeline_showcase.png" alt="Local3D Studio - Manifattura Locale Image-to-3MF/STL & Taglio con Perni per Stampa 3D" width="100%">
</p>

<p align="center">
  <strong>Local Image-to-3MF/STL Manufacturing & Auto-Keyed Splitting for 3D Printing</strong><br>
  <em>100% Locale • Sicuro su 16GB RAM/VRAM Consumer • Zero Abbonamenti Cloud • Server MCP stdio Nativo</em>
</p>

---

**Local3D Studio** è una suite di manifattura generativa 3D open-source e server Model Context Protocol (MCP) di livello industriale. Converte prompt testuali e fotografie 2D in figurine 3D a tenuta stagna pronte per la stampa (`.stl`), assemblaggi modulari con perni e giunti di montaggio (`.3mf`) e modelli digitali per videogiochi e animazione (`.glb`).

Progettato come **alternativa 100% locale, aperta e senza abbonamenti a piattaforme cloud come Meshy AI e Tripo3D**, Local3D Studio gira interamente su hardware consumer all'interno di un budget rigido di **16 GB di RAM/VRAM unificata**—senza richiedere flag di compilazione CUDA proprietari o server daemon in background. Sfruttando la potenza visiva nativa del client AI (o foto dell'utente) per il 2D, **il 100% dei 16 GB di RAM/VRAM viene dedicato interamente alla ricostruzione neurale 3D (Hunyuan3D-2) e alla manifattura headless in Blender**.

> 🇬🇧 **Read in English**: [README.md](README.md)  
> 🏛️ **Architettura Tecnica Dettagliata**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)  
> 🔌 **Guida alla Configurazione dei Client MCP**: [docs/MCP_GUIDE.md](docs/MCP_GUIDE.md)  
> 🌐 **Directory MCP & Community**: [docs/SUBMISSIONS.md](docs/SUBMISSIONS.md)

---

## 🌟 Funzionalità Principali

### 1. Suite Completa Open-Source Alternativa a Meshy AI (15 Tool MCP Nativi)
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

### 5. Protocollo di Produzione a 3 Fasi & Hard Approval Gate
- **Compilatore Prompt (`compile_3d_master_prompt`)**: Genera prompt ultra-dettagliati in stile **Meshy AI Single-Master 3/4** con direttive ferree di anti-occlusione (A-pose, arti staccati, zero fumo, zero auree, zero basette).
- **Client AI 2D Nativo / Foto Utente (100% RAM Dedicata al 3D)**: Delega interamente la generazione del concept 2D all'assistente AI (es. generatore nativo multimodale Antigravity) o a una foto fornita dall'utente. Eliminando i modelli locali di diffusione 2D, **il 100% dei 16 GB di RAM/VRAM unificata viene dedicato alla ricostruzione 3D (Hunyuan3D-2) e alla manifattura headless Blender**, azzerando i freeze di sistema e massimizzando la densità poligonale.
- **Hard Approval Gate**: L'esecuzione si arresta tassativamente dopo il salvataggio in `output/<nome>_concept.png`. L'agente mostra l'immagine all'utente e attende esplicita conferma prima di procedere.
- **Ricostruzione 3D Diretta (`direct_image_to_3d`)**: Pre-elabora l'immagine approvata con rimozione sfondo (`rembg_engine.py`), contrasto locale CLAHE e ancoraggio a $Z=0$, seguiti da ricostruzione neurale isolata e manifattura headless Blender.
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
├── server.json                      # Manifesto Ufficiale Catalogo Specifiche MCP
├── run_mcp.sh / .bat                # Launcher server MCP stdio in-process
├── update.sh / .bat                 # Script di aggiornamento automatico con un clic
├── start_worker.sh / .bat           # Launcher opzionale Web Studio GUI
├── server.py                        # Server MCP Principale & CLI Unificata (15 Tool Nativi)
├── worker_api.py                    # Server opzionale FastAPI Web Studio & Three.js
│
├── core/                            # Livello di astrazione hardware, diagnostica e client
│   ├── __init__.py
│   ├── config.py                    # Variabili d'ambiente e percorsi globali
│   ├── hardware_backend.py          # HardwareManager (MPS / ROCm / CUDA / 4 Tier)
│   ├── diagnostics.py               # Local3D Doctor e diagnostica profonda di sistema
│   ├── client_setup.py              # Installatore automatico client MCP & deploy skill
│   ├── updater.py                   # Sincronizzazione automatica release GitHub & pip
│   ├── response_envelope.py         # Contratti standardizzati di risposta ed errore MCP
│   ├── memory.py                    # Garbage collector e svuotamento cache VRAM/RAM
│   └── client.py                    # Client REST unificato (per offloading LAN)
│
├── skills/                          # Skill Integrate per Agenti AI
│   └── local3d-studio/
│       ├── SKILL.md                 # Protocollo a 3 Fasi per Google Antigravity
│       └── references/              # Guide di riferimento slicing e profili hardware
│
├── tools/                           # Motori Generativi e di Manifattura Modulari
│   ├── __init__.py
│   ├── prompt_enhancer.py           # Router dinamico di stili e compilatore prompt Meshy AI
│   ├── pose_canonicalizer.py        # Guida Pose Umanoidi (overlay A-Pose/T-Pose)
│   ├── concept_engine.py            # Motore concept e generatore di fallback
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
git clone https://github.com/Jaco2308/Local3D_Studio.git
cd Local3D_Studio

# Esegui l'installer universale (rileva Apple Silicon, AMD ROCm, NVIDIA CUDA)
python3 setup_env.py
```

`setup_env.py` esegue in automatico:
1. Rileva il sistema operativo e l'acceleratore GPU.
2. Installa la corretta versione di PyTorch (`mps`, `rocm`, `cuda` o `cpu`).
3. Installa le librerie necessarie (`mcp`, `trimesh`, `rembg`, `scipy`, `psutil`, `fastapi`, `transformers`).
4. Individua autonomamente l'eseguibile di Blender.
5. Inizializza il file `.env`.

---

### 2. Suite CLI Universale `local3d`

Ispirata all'architettura di REA, Local3D Studio include un comando CLI unificato disponibile a livello di sistema (`local3d`):

```bash
# 1. Diagnostica di Sistema Approfondita (Blender, PyTorch, RAM, Drift Client MCP)
local3d doctor

# 2. Aggiornamento Automatico con 1 Clic (Release GitHub, pip, refresh skill)
local3d update
# (oppure doppio clic su update.bat su Windows / ./update.sh su macOS/Linux)

# 3. Registrazione Automatica Client MCP & Deploy Skill in 1 Comando
local3d setup --client antigravity
local3d setup --client claude_desktop
local3d setup --client cursor

# 4. Visualizza Telemetria Hardware e Profilo di Performance Attivo
local3d status

# 5. Avvia il Server Nativo Stdio MCP
local3d mcp
```

---

### 3. Connessione al Client MCP

Il server MCP di Local3D Studio gira **100% in locale in-process su stdio**.

Puoi configurare il tuo client automaticamente in un comando:
```bash
local3d setup --client antigravity
# Client supportati: antigravity, claude_desktop, cursor, vscode, gemini_cli
```

Oppure aggiungere manualmente Local3D Studio al file di configurazione del tuo client:

```json
{
  "mcpServers": {
    "local3d": {
      "command": "/percorso/assoluto/a/Local3D-Studio/.venv/bin/python",
      "args": [
        "/percorso/assoluto/a/Local3D-Studio/server.py"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8"
      }
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

## 🛠️ Riferimento Completo dei 15 Tool MCP

| Nome Tool | Argomenti | Descrizione |
|:---|:---|:---|
| `get_hardware_status` | *(nessuno)* | Restituisce CPU, GPU (CUDA/ROCm/MPS), RAM/VRAM, Profilo di Prestazioni attivo (1-4) e percorso di Blender. |
| `set_quality_preset` | `preset` | Imposta la modalità qualitativa (`fast_draft`, `auto`, `ultra_production`). |
| `enhance_prompt_for_3d` | `prompt`, `mode`, `art_style`, `multiview`, `add_pedestal_base`, `humanoid_pose` | Espande prompt testuali in specifiche ottimali per la modellazione 3D attraverso 5 stili artistici. |
| `compile_3d_master_prompt` | `subject`, `art_style`, `key_details`, `add_pedestal_base`, `humanoid_pose`, `generation_strategy` | Compila il prompt chirurgico Meshy AI Single-Master 3/4 per la generazione nativa Antigravity con anti-occlusione e zero-effetti. |
| `align_multiview_concept` | `concept_path` | Calibra le viste ortografiche, isola il soggetto via connected components, fissa l'altezza Y a 400px e applica CLAHE. |
| `confirm_concept_and_build_3d` | `concept_path`, `output_filename`, `quality_preset`, `target_height_mm`, `add_pedestal`, `art_style`, `target_triangles`, `voxel_size`, `auto_split` | **Hard Approval Gate**: Invocabile dopo approvazione utente per avviare la ricostruzione 3D e Blender. |
| `direct_image_to_3d` | `image_path`, `output_filename`, `quality_preset`, `generation_strategy`, `add_pedestal`, `target_height_mm`, `art_style`, `target_triangles`, `voxel_size`, `auto_split` | **Punto di Ingresso 3D Primario**: Converte il concept 2D o un'immagine utente in modello 3D con rembg, CLAHE, Hunyuan3D-2 e manifattura Blender. |
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

## 🌐 Directory MCP & Ecosistema

Local3D Studio è progettato per integrarsi istantaneamente con qualunque client Model Context Protocol standard:

### Installazione in 1-Click via Smithery.ai
```bash
npx -y @smithery/cli install @Jaco2308/Local3D_Studio --client claude
```

### Registri Ufficiali & Community
- **Model Context Protocol Servers**: Inviato all'elenco community di [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers).
- **Elenco Ufficiale mcpservers.org**: Indicizzato su [mcpservers.org](https://mcpservers.org).
- **Registro Smithery**: Disponibile su [smithery.ai](https://smithery.ai).
- **Community Reddit**: Partecipa alle discussioni su [r/mcp](https://reddit.com/r/mcp), [r/BambuLab](https://reddit.com/r/BambuLab) e [r/3Dprinting](https://reddit.com/r/3Dprinting).
- Modelli e guide di invio dettagliate: [docs/SUBMISSIONS.md](docs/SUBMISSIONS.md).

---

## 🤝 Come Contribuire

Contributi, segnalazioni di bug e pull request sono i benvenuti! Ti invitiamo a leggere le nostre linee guida in [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📄 Licenza

Local3D Studio è rilasciato sotto la licenza open source **MIT License**. Consulta il file [LICENSE](LICENSE) per tutti i dettagli. Libero per uso personale, commerciale e di ricerca.
