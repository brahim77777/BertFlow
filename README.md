# BertFlow

A Bun + Vite + React Flow app for building and executing Agentic RAG pipelines visually,
backed by a Python WebSocket server and a Rust (PyO3) extension for embeddings, PDF
extraction, and vector search.

## Quick Start

### Frontend

```bash
bun install   # first time only
bun run dev
```

Open: **http://localhost:5173**

### Backend (Linux)

```bash
./run-backend.sh --host localhost --port 8765
```

### Backend (Windows)

```powershell
.\run-backend.ps1 -Python "backend\backend-env\Scripts\python.exe"
```

> The backend requires **Python 3.13** — the `rag_rust` extension is compiled for CPython 3.13.
> Using any other Python version will crash the server.

## Collaborating / Setup from Scratch

See **[CONTRIBUTING.md](./CONTRIBUTING.md)** for:
- Full project architecture
- First-time setup on Linux and Windows
- Rules for handling the compiled `rag_rust` binary
- GitHub workflow and `.gitignore` requirements
- What changed in May 2026 and why

## What It Does

- Drag-and-drop pipeline builder (React Flow)
- Live backend node types fetched over WebSocket
- Nodes execute as an async graph — parallel where possible
- Node types: PDF extraction, chunking, embeddings, LanceDB indexing/search, LLM (Ollama / OpenRouter), web search, calculator, and more
- Per-node output preview in the UI
