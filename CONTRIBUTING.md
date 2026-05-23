# BertFlow — Contributor Guide

> **Two contributors:** Brahim (Linux) and Windows collaborator.  
> Read this before touching anything related to the Rust extension, the Python venv, or the backend.



### notes: for how the SKIPPED status is handling propagating errors:
Here's what the logic does now, and why each decision is sound:
The skip_queue drains transitively. After each wave, any node that just became "failed" (under skip mode) is seeded into skip_queue. Then we drain it in a loop — a node marked "skipped" is itself pushed back into the queue as a skip source, so the skip signal cascades through the whole downstream subtree without needing an extra wave.
required is the single decision point. For each downstream edge from a failed/skipped node:

required=True → the target is marked "skipped" immediately, error message tells you exactly which upstream caused it and whether it failed or was skipped. pending is decremented so the outer loop can terminate cleanly.
required=False → in_deg is decremented, nothing is injected into node_inputs, and if all other deps are satisfied the node runs normally with its own default for that port.

in_deg is always decremented regardless of required. This is important — it's an edge being resolved either way, just without a value. Skipping the decrement would leave the node stranded at "pending" again.
The final status vocabulary you end up with is unambiguous: completed, failed, skipped, running (only transiently), pending (only transiently). Every terminal state has a clear cause.



---

## Table of Contents

1. [Project Architecture](#1-project-architecture)
2. [Running the Project — Linux (Brahim)](#2-running-the-project--linux-brahim)
3. [Running the Project — Windows (Collaborator)](#3-running-the-project--windows-collaborator)
4. [The `rag_rust` Binary — Critical Rules](#4-the-rag_rust-binary--critical-rules)
5. [GitHub Collaboration Rules](#5-github-collaboration-rules)
6. [What Changed (May 2026)](#6-what-changed-may-2026)

---

## 1. Project Architecture

```
bertflow/
├── src/                    # React/Vite frontend (JSX)
├── backend/                # Python WebSocket backend
│   ├── core/               # Executor, registry, models, validator
│   ├── nodes/              # Node definitions (each file = one node type)
│   ├── infrastructure/
│   │   └── rust_bridge.py  # Thin Python wrapper over rag_rust
│   ├── ws_server.py        # WebSocket server (websockets library)
│   ├── __main__.py         # Entry point: python -m backend
│   └── backend-env/        # Python 3.13 venv — DO NOT DELETE
│
├── rag_rust_src/           # Rust/PyO3 source (compile → .so)
│   └── src/
│       ├── lib.rs           # PyO3 bindings
│       ├── embeddings.rs    # fastembed + ZeroEntropy API
│       ├── vector_store.rs  # LanceDB read/write
│       ├── chunking.rs
│       ├── pdf_ops.rs       # PDFium PDF extraction
│       └── runtime.rs       # Shared Tokio runtime
│
├── libpdfium.so            # Required at runtime (Linux)
├── pdfium.dll              # Required at runtime (Windows)
├── pyproject.toml          # Project metadata (uv-compatible)
├── run-backend.sh          # Linux: start backend via uv
├── run-backend.ps1         # Windows: start backend via venv Python
└── run-dev.ps1             # Windows: start Vite frontend
```

**How the pieces talk:**

```
Browser (React + React Flow)
        │ WebSocket ws://localhost:8765
        ▼
backend/ws_server.py  ──imports──▶  backend/nodes/*.py
                                          │ imports
                                          ▼
                              backend/infrastructure/rust_bridge.py
                                          │ imports
                                          ▼
                              rag_rust  (compiled .so / .pyd)
                              ├─ fastembed (local embeddings)
                              ├─ LanceDB  (vector store)
                              └─ pdfium-render (PDF extraction)
```

---

## 2. Running the Project — Linux (Brahim)

### Prerequisites

| Tool | Install |
|------|---------|
| `uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `bun` | `curl -fsSL https://bun.sh/install \| bash` |
| Python 3.13 | already in `backend/backend-env` |

### Start the backend

```bash
# From the project root:
./run-backend.sh --host localhost --port 8765

# Or directly with uv (same thing):
UV_PROJECT_ENVIRONMENT=backend/backend-env \
  uv run --no-sync -- python -m backend --host localhost --port 8765
```

> **Why `uv run --no-sync`?**  
> `backend/backend-env` is a Python 3.13 venv that has `rag_rust` installed.  
> `--no-sync` tells uv not to recreate the venv — it just uses it as-is.  
> The system Python is 3.14 and **cannot** load `rag_rust.so` (wrong ABI).

### Start the frontend

```bash
bun run dev
```

Then open: **http://localhost:5173**

### Installing / updating Python deps

```bash
# Add a new package to backend-env:
UV_PROJECT_ENVIRONMENT=backend/backend-env uv pip install <package>

# Or activate the venv manually:
source backend/backend-env/bin/activate
pip install <package>
deactivate
```

---

## 3. Running the Project — Windows (Collaborator)

### Prerequisites

| Tool | Where to get it |
|------|-----------------|
| Python **3.13.x** | https://www.python.org/downloads/ — pick **3.13**, NOT 3.14+ |
| `uv` | `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| Bun | https://bun.sh — click "Install" |
| Rust + cargo | https://rustup.rs (only if recompiling `rag_rust`) |
| Maturin | `pip install maturin` (only if recompiling `rag_rust`) |

> ⚠️ **Python version is not optional.** The compiled `rag_rust.pyd` targets CPython 3.13.  
> Installing Python 3.14 and using it will cause an immediate **crash** when the backend starts.

### First-time setup

```powershell
# 1. Clone the repo
git clone <repo-url>
cd bertflow

# 2. Create the backend venv with Python 3.13 specifically
uv venv backend/backend-env --python 3.13

# 3. Install Python deps into it
uv pip install --python backend/backend-env websockets httpx

# 4. Install rag_rust into the venv
#    The pre-built wheel is checked in under backend/backend-env — you need to
#    rebuild it for Windows. See Section 4.
```

### Start the backend (Windows)

```powershell
# Option A — with uv (recommended):
$env:UV_PROJECT_ENVIRONMENT = "backend\backend-env"
uv run --no-sync -- python -m backend --host localhost --port 8765

# Option B — activate venv manually:
backend\backend-env\Scripts\Activate.ps1
python -m backend --host localhost --port 8765

# Option C — original convenience script (pass -Python if needed):
.\run-backend.ps1 -Python "backend\backend-env\Scripts\python.exe"
```

### Start the frontend (Windows)

```powershell
bun install   # first time only
.\run-dev.ps1
# or: bun run dev
```

Then open: **http://localhost:5173**

---

## 4. The `rag_rust` Binary — Critical Rules

This is the most important section. Violating these rules will crash the backend.

### What it is

`rag_rust` is a compiled Rust extension (`rag_rust.cpython-313-*.so` on Linux,  
`rag_rust.cp313-win_amd64.pyd` on Windows). It is built with [Maturin](https://maturin.rs/) from source in `rag_rust_src/`.

It provides:
- `load_pdf_pages_pdfium_many` — PDF text extraction (requires `libpdfium.so` / `pdfium.dll`)
- `embed_texts_rust_local` / `embed_texts_rust_zembed` — text embeddings
- `lancedb_create_or_open`, `lancedb_search` — vector store operations
- `dartboard_rerank` — result reranking

### Rules everyone must follow

**1. Never commit compiled binaries to git.**

The `.so` and `.pyd` files are platform-specific. One person's compiled binary will **segfault** on a different machine or Python version.

Add this to `.gitignore` and keep it there:
```
backend/backend-env/lib/*/site-packages/rag_rust/*.so
backend/backend-env/lib/*/site-packages/rag_rust/*.pyd
backend/backend-env/Scripts/
backend/backend-env/Lib/
```

**2. Never change `rag_rust_src/` source without telling the other person.**

If you edit any `.rs` file, you must:
- Announce it in a GitHub Issue or PR description
- Bump `version` in `rag_rust_src/Cargo.toml`
- Include a note in the PR saying "needs recompile" so the other person knows to rebuild

**3. How to recompile after a Rust source change**

```bash
# Linux (Brahim):
cd rag_rust_src
source ../backend/backend-env/bin/activate
maturin develop --release
deactivate

# Windows (Collaborator):
cd rag_rust_src
..\backend\backend-env\Scripts\Activate.ps1
maturin develop --release
deactivate
```

> After recompiling, **test** with: `python -c "import rag_rust; print(dir(rag_rust))"`  
> If you get a segfault or ImportError, the build is broken — do NOT push.

**4. `BGESmallENV15` is the default embedding model**

The local embedding model (used when `embed_backend = "local"` in `LanceDBIndexer`)  
defaults to `BGESmallENV15`. This is now correctly handled in `embeddings.rs`.  
If you change the model name anywhere, update **both** the Python side (`lancedb_indexer.py`) and the Rust match arm in `embeddings.rs`.

**5. `pdfium.dll` / `libpdfium.so` must stay in the project root**

Both files are already committed and must not be deleted. They are loaded at runtime by `rust_bridge.py` using `ctypes` before the Rust extension is imported.

---

## 5. GitHub Collaboration Rules

### Branch strategy

```
main           ← stable, always runnable
dev            ← integration branch — both of you merge here first
feature/xxx    ← your feature branches
```

- **Never push directly to `main`**
- All PRs go through `dev` first, get tested on both platforms, then merge to `main`

### What to put in `.gitignore`

Make sure these are ignored (add if missing):

```gitignore
# Python environments — NEVER commit these
backend/backend-env/
bertenv/

# Compiled Rust binaries — platform-specific, always rebuild locally
rag_rust_src/target/
*.so
*.pyd

# Python caches
__pycache__/
*.pyc
.ruff_cache/

# Editor / OS
.vscode/
.idea/
*.kate-swp
.DS_Store
Thumbs.db

# Data / outputs
lancedb_store/
files/
graphify-out/
```

### PR checklist before merging

- [ ] Backend starts without crash (`python -m backend`)
- [ ] "Fetch from Backend" button in the UI returns node types
- [ ] If `rag_rust_src/` changed: compiled and tested on your platform
- [ ] No `backend-env/`, `bertenv/`, or `*.so` files accidentally staged (`git status` before committing)
- [ ] Describe in the PR what Rust changes were made (if any) so the other person knows to recompile

### What NOT to push

| Thing | Why |
|-------|-----|
| `backend/backend-env/` | Platform-specific venv + compiled `.so` |
| `bertenv/` | Same — different venv |
| `rag_rust_src/target/` | Build artifacts, huge, platform-specific |
| `lancedb_store/` | Runtime data, not source |
| `files/` | Uploaded user files |

---

## 6. What Changed (May 2026)

### Problem: backend crashed immediately on "Fetch from Backend"

**Root cause:** The `rag_rust.so` that was recompiled from `rag_rust_src/` on May 17 caused a **segfault** (exit 139) the moment Python tried to `import rag_rust`. This crashed the entire Python process — no error message, no traceback.

**Why it happened:** The newly compiled binary had a bad link or initialization bug. The older binary from `~/Documents/Agentic-RAG-Rust-Core-PFE-26/rustvenv/` (compiled from the same source, slightly earlier) worked fine.

**Fix:** Replaced the broken `.so` with the working one from the Agentic-RAG project.

**Secondary bug fixed:** In `rag_rust_src/src/embeddings.rs`, the default embedding model `"BGESmallENV15"` was missing from the `match` arm — it would hit the error branch and fail every time local embedding was used. Fixed by adding the missing arm.

### How to run the backend changed

| Before | After |
|--------|-------|
| `python -m backend --host localhost --port 8765` | `./run-backend.sh --host localhost --port 8765` |
| Used system Python 3.14 (wrong — rag_rust.so is for 3.13) | Uses `backend/backend-env` Python 3.13 via `uv run --no-sync` |

The `run-backend.ps1` on Windows is still valid **if** you pass the correct Python:
```powershell
.\run-backend.ps1 -Python "backend\backend-env\Scripts\python.exe"
```

### `pyproject.toml` updated

- Added `requires-python = ">=3.13,<3.14"` — enforces the correct Python version
- Added `websockets` and `httpx` as declared dependencies
- Fixed `target-version` for ruff to `py313`
