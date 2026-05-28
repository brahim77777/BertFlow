# BertFlow

A visual, drag-and-drop pipeline builder for **Agentic RAG** workflows. Built with React Flow on the frontend, Python WebSocket backend, and a Rust (PyO3) extension for high-performance embeddings, PDF extraction, and vector search.

![Architecture](https://img.shields.io/badge/architecture-React%20%2B%20Python%20%2B%20Rust-blue)
![Python](https://img.shields.io/badge/python-3.13-green)
![Rust](https://img.shields.io/badge/rust-PyO3-orange)

---

## Demo

[![Demo Video](https://img.shields.io/badge/▶-Watch%20Demo-red)](https://drive.google.com/file/d/1e7yTFdkF4GHo83xEV9I7_t893WzW4tIV/view?usp=drive_link)

This video shows how to run BertFlow (after installation and compilation), create a simple flow, and execute it.

---

## Table of Contents

- [Features](#features)
- [Project Architecture](#project-architecture)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
  - [Linux](#linux)
  - [Windows](#windows)
- [Compiling the Rust Extension](#compiling-the-rust-extension-rag_rust)
- [Running BertFlow](#running-bertflow)
- [Creating & Running a Flow](#creating--running-a-flow)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Features

- **Visual flow builder** — drag & drop nodes to build Agentic RAG pipelines
- **Live node discovery** — backend node types are fetched over WebSocket
- **Async graph execution** — nodes run in parallel where possible
- **Node types** — PDF extraction, text chunking, embeddings (local + API), LanceDB indexing/search, LLM (Ollama / OpenRouter), web search, calculator, and more
- **Per-node output preview** — inspect intermediate results in the UI
- **Persistent execution cache** — cached results survive server restarts (diskcache-backed, 2 GiB LRU)

---

## Project Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       Browser (React + React Flow)               │
│                           localhost:5173                          │
└──────────────────────────┬───────────────────────────────────────┘
                           │ WebSocket
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│               Python Backend (websockets library)                 │
│                    localhost:8765                                  │
│                                                                   │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────────────┐    │
│  │ ws_server │→ │   nodes/*    │→ │ infrastructure/          │    │
│  │   .py     │  │  (defs)      │  │ rust_bridge.py           │    │
│  └──────────┘  └──────────────┘  └──────────┬───────────────┘    │
│                                              │                     │
│  ┌──────────┐  ┌──────────────┐              │                     │
│  │ core/    │  │ core/        │              │                     │
│  │ executor │  │ registry     │              │                     │
│  └──────────┘  └──────────────┘              │                     │
└──────────────────────────────────────────────┼─────────────────────┘
                                               │
                                               ▼
┌──────────────────────────────────────────────────────────────────┐
│          rag_rust (compiled .so / .pyd via PyO3 + Maturin)       │
│                                                                   │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────────────┐   │
│  │ embeddings │→ │ vector_store │→ │ pdf_ops (PDFium)       │   │
│  │ .rs        │  │ .rs (LanceDB) │  │ .rs                   │   │
│  └────────────┘  └──────────────┘  └────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### How the pieces talk

1. **Browser** connects to the **Python backend** via WebSocket (`ws://localhost:8765`)
2. **Backend** discovers node types and executes the flow graph
3. Node implementations import `rust_bridge.py`, which loads the compiled **Rust extension**
4. **rag_rust** handles PDF extraction (via PDFium), local embeddings (via fastembed), vector search (via LanceDB), and reranking

---

## Prerequisites

### Required for all platforms

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | **3.13.x** (exactly) | The `rag_rust` binary is compiled for CPython 3.13. **Python 3.14 will crash.** |
| **uv** | latest | Fast Python package manager (by Astral) |
| **Bun** | latest | JavaScript runtime + frontend dev server |
| **Rust + cargo** | stable (edition 2021) | Only needed to recompile `rag_rust` |

### Linux additional

| Package | Install |
|---------|---------|
| `libpdfium.so` | Already included in project root, or download from [pdfium-binaries](https://github.com/bblanchon/pdfium-binaries/releases) |
| Build essentials | `sudo apt install build-essential pkg-config libssl-dev` |

### Windows additional

| Package | Install |
|---------|---------|
| `pdfium.dll` | Already included in project root, or download from [pdfium-binaries](https://github.com/bblanchon/pdfium-binaries/releases) |
| Visual Studio Build Tools | [Download](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022) (for compiling Rust) |
| Maturin | `pip install maturin` |

---

## Setup & Installation

### Linux

#### 1. Install system dependencies

```bash
sudo apt update
sudo apt install build-essential pkg-config libssl-dev python3.13 python3.13-venv -y
```

> If Python 3.13 is not available via apt, use [deadsnakes](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa) or [pyenv](https://github.com/pyenv/pyenv).

#### 2. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# restart your shell or run: source ~/.bashrc
```

#### 3. Install Bun

```bash
curl -fsSL https://bun.sh/install | bash
# restart your shell or run: source ~/.bashrc
```

#### 4. Install Rust

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
# restart your shell or run: source ~/.bashrc
```

#### 5. Clone and set up the project

```bash
git clone <repo-url>
cd BertFlow
```

#### 6. Create the Python venv (Python 3.13 specifically)

```bash
uv venv backend/backend-env --python 3.13
```

#### 7. Install Python dependencies

```bash
uv pip install --python backend/backend-env websockets httpx diskcache
```

> Or if the venv is already created in the repo, just use it.

#### 8. Install frontend dependencies

```bash
bun install
```

#### 9. Compile the Rust extension

```bash
cd rag_rust_src
source ../backend/backend-env/bin/activate
maturin develop --release
deactivate
cd ..
```

> See [Compiling the Rust Extension](#compiling-the-rust-extension-rag_rust) for details.

#### 10. Verify the Rust extension loads

```bash
source backend/backend-env/bin/activate
python -c "import rag_rust; print(dir(rag_rust))"
deactivate
```

You should see a list of functions (no ImportError or segfault).

---

### Windows

#### 1. Install Python 3.13.x

Download from [python.org](https://www.python.org/downloads/). **Pick 3.13.x**, NOT 3.14+.

During installation, check **"Add Python to PATH"**.

#### 2. Install uv

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### 3. Install Bun

Go to https://bun.sh and click **Install**, or run:

```powershell
powershell -c "irm bun.sh/install.ps1 | iex"
```

#### 4. Install Rust

Download and run [rustup-init.exe](https://rustup.rs/).

#### 5. Install Maturin

```powershell
pip install maturin
```

#### 6. Clone and set up the project

```powershell
git clone <repo-url>
cd BertFlow
```

#### 7. Create the Python venv (Python 3.13 specifically)

```powershell
uv venv backend/backend-env --python 3.13
```

> Make sure Python 3.13 is the default Python on your PATH. If uv picks the wrong version, specify the full path:
> ```powershell
> uv venv backend/backend-env --python "C:\Users\<You>\AppData\Local\Programs\Python\Python313\python.exe"
> ```

#### 8. Install Python dependencies

```powershell
uv pip install --python backend/backend-env websockets httpx diskcache
```

#### 9. Install frontend dependencies

```powershell
bun install
```

#### 10. Compile the Rust extension

```powershell
cd rag_rust_src
..\backend\backend-env\Scripts\Activate.ps1
maturin develop --release
deactivate
cd ..
```

#### 11. Verify the Rust extension loads

```powershell
backend\backend-env\Scripts\Activate.ps1
python -c "import rag_rust; print(dir(rag_rust))"
deactivate
```

---

## Compiling the Rust Extension (rag_rust)

`rag_rust` is a **compiled Rust extension** that provides:

- `load_pdf_pages_pdfium_many` — PDF text extraction (via PDFium)
- `embed_texts_rust_local` / `embed_texts_rust_zembed` — text embeddings (fastembed / ZeroEntropy API)
- `lancedb_create_or_open`, `lancedb_search` — vector store operations (LanceDB)
- `dartboard_rerank` — result reranking

### Build command

```bash
# Linux
cd rag_rust_src
source ../backend/backend-env/bin/activate
maturin develop --release
deactivate
```

```powershell
# Windows
cd rag_rust_src
..\backend\backend-env\Scripts\Activate.ps1
maturin develop --release
deactivate
```

> **Important:** The `.so` / `.pyd` binary is platform-specific and **must not be committed to git**. Each developer must compile it for their own machine.

### After recompiling

Always test that the extension loads correctly:

```bash
python -c "import rag_rust; print(dir(rag_rust))"
```

If you get an `ImportError` or segfault, something is wrong with the build.

### Important files

| File | Purpose |
|------|---------|
| `rag_rust_src/src/lib.rs` | PyO3 bindings — entry point for all exported functions |
| `rag_rust_src/src/embeddings.rs` | fastembed local + ZeroEntropy API embedding |
| `rag_rust_src/src/vector_store.rs` | LanceDB read/write |
| `rag_rust_src/src/chunking.rs` | Text chunking |
| `rag_rust_src/src/pdf_ops.rs` | PDFium-based PDF extraction |
| `rag_rust_src/src/runtime.rs` | Shared Tokio runtime |

### Build dependencies

- **Maturin** (`pip install maturin`) — builds the Rust extension into a Python wheel
- **Rust edition 2021** — stable toolchain
- **Python 3.13 development headers** — `python3-dev` on Linux, included in Windows installer

### Pre-built libraries

These DLLs/SOs are required at runtime and **are** committed to the repo:

| File | Platform |
|------|----------|
| `libpdfium.so` | Linux — download from [pdfium-binaries](https://github.com/bblanchon/pdfium-binaries/releases) |
| `pdfium.dll` | Windows — download from [pdfium-binaries](https://github.com/bblanchon/pdfium-binaries/releases) |

---

## Running BertFlow

You need **two terminal windows**: one for the backend, one for the frontend.

### 1. Start the backend

```bash
# Linux
./run-backend.sh --host localhost --port 8765
```

```powershell
# Windows (Option A — with uv)
$env:UV_PROJECT_ENVIRONMENT = "backend\backend-env"
uv run --no-sync -- python -m backend --host localhost --port 8765

# Windows (Option B — activate venv manually)
backend\backend-env\Scripts\Activate.ps1
python -m backend --host localhost --port 8765

# Windows (Option C — convenience script)
.\run-backend.ps1 -Python "backend\backend-env\Scripts\python.exe"
```

You should see output like:
```
WebSocket server started on ws://localhost:8765
```

> **Why `uv run --no-sync`?** `backend/backend-env` is a Python 3.13 venv with `rag_rust` installed. `--no-sync` tells uv not to recreate the venv — it just uses it as-is. The system Python might be 3.14 which cannot load `rag_rust.so`.

### 2. Start the frontend

```bash
# Linux / Mac
bun run dev

# Windows
.\run-dev.ps1
# or: bun run dev
```

You should see output like:
```
VITE v7.x.x  ready in XXX ms
➜  Local:   http://localhost:5173/
```

### 3. Open the app

Open your browser to **http://localhost:5173**

Click the **"Fetch from Backend"** button — if the backend is running, it will populate the node palette with available node types.

---

## Creating & Running a Flow

A quick walkthrough after both servers are running:

1. **Open** http://localhost:5173 in your browser
2. **Click "Fetch from Backend"** — available node types appear in the palette
3. **Drag nodes** from the palette onto the canvas to build your pipeline
4. **Connect nodes** by dragging from one node's output handle to another's input handle
5. **Configure node parameters** (e.g., select a PDF file for extraction, set chunk size, choose embedding model, etc.)
6. **Click "Run"** to execute the flow — results propagate through the graph
7. **Inspect outputs** — click on a node to see its execution result in the preview panel

> Watch the [demo video](https://drive.google.com/file/d/1e7yTFdkF4GHo83xEV9I7_t893WzW4tIV/view?usp=drive_link) for a visual walkthrough.

### Example flow

A typical RAG pipeline looks like:

```
PDF Upload → PDF Extraction → Text Chunking → Embedding (local) → LanceDB Index
                                                                           ↓
User Query → Embedding (local) → LanceDB Search → LLM (Ollama) → Answer
```

---

## Project Structure

```
BertFlow/
├── src/                          # React/Vite frontend (JSX)
│   ├── components/               # React components (nodes, panels, etc.)
│   ├── lib/                      # Utility functions
│   ├── flow.jsx                  # Main flow component
│   ├── main.jsx                  # Entry point
│   └── styles.css                # Global styles
│
├── backend/                      # Python WebSocket backend
│   ├── __main__.py               # Entry point — `python -m backend`
│   ├── ws_server.py              # WebSocket server (websockets library)
│   ├── core/                     # Executor, registry, models, validator
│   │   ├── executor.py           # Async graph executor
│   │   ├── registry.py           # Node type discovery
│   │   ├── models.py             # Data models
│   │   └── validator.py          # Input validation
│   ├── nodes/                    # Node definitions (one file per node type)
│   ├── infrastructure/
│   │   └── rust_bridge.py        # Thin Python wrapper over rag_rust
│   └── backend-env/              # Python 3.13 venv (with rag_rust installed)
│
├── rag_rust_src/                 # Rust/PyO3 source
│   └── src/
│       ├── lib.rs                # PyO3 bindings
│       ├── embeddings.rs         # fastembed + ZeroEntropy API
│       ├── vector_store.rs       # LanceDB read/write
│       ├── chunking.rs           # Text chunking
│       ├── pdf_ops.rs            # PDFium PDF extraction
│       └── runtime.rs            # Shared Tokio runtime
│
├── libpdfium.so                  # Required at runtime (Linux)
├── pdfium.dll                    # Required at runtime (Windows)
├── run-backend.sh                # Linux backend launcher
├── run-backend.ps1               # Windows backend launcher
├── run-dev.ps1                   # Windows frontend launcher
├── package.json                  # Node.js / Bun dependencies
├── pyproject.toml                # Python project config
├── requirements.txt              # Python dependencies
├── vite.config.js                # Vite configuration
├── CONTRIBUTING.md               # Contributor guide
└── LICENSE                       # MIT license
```

---

## Troubleshooting

### Backend crashes on startup (segfault / ImportError)

The `rag_rust` extension is the most common source of crashes.

**Check Python version:**
```bash
python --version
# Must be 3.13.x — if it's 3.14, the extension will not load.
```

**Verify the extension loads:**
```bash
source backend/backend-env/bin/activate
python -c "import rag_rust; print('OK:', dir(rag_rust))"
deactivate
```

**Recompile rag_rust:**
```bash
cd rag_rust_src && source ../backend/backend-env/bin/activate && maturin develop --release && deactivate && cd ..
```

### Frontend can't connect to backend

- Make sure the backend is running (check terminal output)
- Ensure the backend port matches: default is `8765`
- The frontend attempts to connect via WebSocket to `ws://localhost:8765`
- Check for firewall rules blocking the connection

### "Fetch from Backend" returns no node types

- The backend must be running and reachable
- Check the backend terminal for errors
- Verify all node Python files are in `backend/nodes/`

### Python version mismatch

```
RuntimeError: Python version mismatch — the rag_rust extension requires CPython 3.13
```

The solution is to create the venv with Python 3.13 specifically:
```bash
uv venv backend/backend-env --python 3.13
```

### PDFium not found

Ensure `libpdfium.so` (Linux) or `pdfium.dll` (Windows) exists in the project root directory. Download from [pdfium-binaries/releases](https://github.com/bblanchon/pdfium-binaries/releases) if missing.

### uv can't find Python 3.13

```bash
uv python list          # see available Python versions
uv python install 3.13  # install 3.13 via uv
```

---

## License

MIT License — see [LICENSE](./LICENSE) for details.

---

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for:
- Full project architecture
- Collaboration rules (branch strategy, PR checklist)
- Rules for handling the compiled `rag_rust` binary
- Detailed contributor workflow for both Linux and Windows
