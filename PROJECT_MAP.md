# BertFlow — Project Map

## TECH_STACK

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend | Python + asyncio | **3.13.x** (CPython — required by `rag_rust.so`) |
| WebSocket | websockets | 16.0 |
| Frontend (React) | React + Vite + @xyflow/react | 18.x / 7.x / 12.x |
| Runtime | Bun | 1.3.13 |
| Linter | ruff | 0.15.x |

## SYSTEM_FLOW

```
User actions → React UI → WebSocket → Python Backend
                                        │
                                ┌───────┴───────┐
                           Validator       Executor
                                │               │
                           GraphPlan    InMemoryStore
                                │               │
                                └───────┬───────┘
                                        │
                                Result stream (WebSocket)
```

### JSON Contracts
1. **node_type_definitions** (backend → frontend): Auto-sent on connect, also via `get_node_types` request. Ports now include `mode` field (`"data"` or `"extension"`)
2. **RunRequest** (frontend → backend): Graph execution payload using `node_type` from backend schema. Edges now include `mode` field
3. **execution_state** (backend → frontend): `run_accepted`, `run_finished` with per-node state
4. **stream_chunk** (backend → frontend): `{type, run_id, node_id, port, data}` — incremental output from streaming nodes

## ARCHITECTURE

```
backend/
├── __init__.py
├── __main__.py              # python3 -m backend --host 0.0.0.0 --port 8765
├── ws_server.py             # WebSocket lifecycle, message dispatch, build_registry()
├── core/
│   ├── __init__.py
│   ├── errors.py             # BackendError ← {RunRequestError, GraphValidationError, NodeExecutionError}
│   ├── types.py              # normalize_type(), are_types_compatible()
│   ├── models.py             # RunRequest, NodeInstance, Edge, ExecutionState, NodeTypeSchema
│   ├── registry.py           # NodeRegistry, @register_node decorator, auto-discovery
│   ├── validator.py          # 6-stage validation → GraphPlan
│   ├── executor.py           # AsyncGraphExecutor, Kahn's algorithm, wave-based parallel execution
│   ├── result_store.py       # InMemoryResultStore, InMemoryExecutionCache (SHA-256)
│   └── logging.py            # bertflow logger
└── nodes/
    ├── __init__.py
    ├── builtin.py            # 3 nodes: PromptBuilder, BrahimYoucefDemo, OutputNode
    ├── openrouter.py         # OpenRouterLLM — streaming LLM node with SSE + tool support
    ├── calculator.py         # CalculatorTool — safe AST-based math evaluator (extension)
    └── web_search.py         # WebSearchTool — SerpAPI integration (extension)

src/
├── main.jsx                  # App entry, Builder view, mode-switch with hash+localStorage persistence
├── flow.jsx                  # Flow canvas: WebSocket lifecycle, node_types palette, run execution
├── styles.css
├── lib/
│   └── server-utils.mjs     # Shared: multipart parsing, component rendering, JSON helpers
└── components/generated/     # Auto-generated JSX component files
```

## FRONTEND-BACKEND COMMUNICATION

1. **On connect**: Backend auto-sends `{type: "node_types", node_types: [...]}`
2. **Fetch palette**: User clicks "Fetch from Backend" — opens WebSocket, requests `get_node_types`, builds component list
3. **Add node**: Canvas nodes store `_nodeType` (the backend's `node_type` string) for correct RunRequest mapping
4. **Run**: `RunRequest.nodes[nid].node_type` uses the stored `_nodeType` instead of deriving from display name
5. **Component dropdown**: Backend components marked with "⚡", localStorage components shown alongside

## TESTS

```
tests/test_backend_core.py — 5 tests, all passing:
  ✓ executor runs topological waves and stores refs
  ✓ disconnected components run without manual selection
  ✓ cache boundary marks reused node outputs
  ✓ cycles are rejected before execution
  ✓ duplicate target input is rejected

E2E (manual): WebSocket server verified with full cycle:
  ✓ node_types on connect
  ✓ get_node_types request
  ✓ run_accepted + run_finished with correct node outputs
```

## RUNNING

> ⚠️ The `rag_rust` extension is compiled for **CPython 3.13 only**. Using any other Python version will cause an immediate segfault or ImportError.

### Linux (Brahim)

```bash
# Terminal 1 — backend (uses uv + backend/backend-env which has Python 3.13 + rag_rust)
./run-backend.sh --host localhost --port 8765

# Terminal 2 — frontend
bun run dev
```

### Windows (Collaborator)

```powershell
# Terminal 1 — backend (must point at the 3.13 venv explicitly)
.\run-backend.ps1 -Python "backend\backend-env\Scripts\python.exe"

# Terminal 2 — frontend
bun run dev        # or: .\run-dev.ps1
```

**First-time Windows setup:**
```powershell
# 1. Install Python 3.13 from python.org (not 3.14+)
# 2. Create the venv
uv venv backend/backend-env --python 3.13
# 3. Install Python deps
uv pip install --python backend/backend-env websockets httpx
# 4. Rebuild rag_rust for Windows (see CONTRIBUTING.md § 4)
cd rag_rust_src
..\backend\backend-env\Scripts\Activate.ps1
maturin develop --release
deactivate
# 5. Install frontend deps
bun install
```

## ADDING A NODE

Create one file in `backend/nodes/`:

```python
from backend.core.registry import register_node

@register_node
class MyNode:
    node_type = "my_node"
    label = "My Node"
    category = "general"
    inputs = {"in": {"type": "string", "required": True}}
    outputs = {"out": {"type": "string"}}
    args_schema = {"param": {"type": "string", "default": "val"}}

    @staticmethod
    async def run(args, inputs, context):
        return {"out": f"processed {inputs.get('in', '')}"}
```

**Streaming node** (emits chunks while running):

```python
@register_node
class MyStreamer:
    node_type = "my_streamer"
    inputs = {"prompt": {"type": "string", "required": True}}
    outputs = {"response": {"type": "string"}}
    args_schema = {}

    @staticmethod
    async def run(args, inputs, context, emit):
        for chunk in some_stream():
            emit("response", chunk)   # pushes to frontend + accumulates
        return {"response": full_text}
```

Then click "Fetch from Backend" in the Flow view to see it appear.


## CURRENT PROGRESS & SUMMARY

### What the app does right now

BertFlow is a **visual Agentic RAG pipeline builder**. You drag backend-registered node types onto a canvas, wire them together, and hit **Run Flow** — the Python backend executes the graph in topological waves (parallel where possible) and streams results back in real time.

**Working end-to-end today:**

| Feature | Status |
|---------|--------|
| Visual node canvas (React Flow) | ✅ Working |
| Backend node discovery via WebSocket | ✅ Working |
| Graph execution (topological + parallel) | ✅ Working |
| Streaming output (chunk-by-chunk to UI) | ✅ Working |
| Per-node status badges + duration | ✅ Working |
| Output preview modal (first 15 lines) | ✅ Working |
| Extension / tool injection system | ✅ Working |
| PDF extraction (PDFium, Rust) | ✅ Working |
| Semantic chunking (Rust) | ✅ Working |
| Local embeddings via fastembed (Rust) | ✅ Working |
| ZeroEntropy API embeddings (Rust) | ✅ Working |
| LanceDB vector store (Rust) | ✅ Working |
| Dartboard reranking (Rust) | ✅ Working |
| OpenRouter LLM node (streaming) | ✅ Working |
| Ollama LLM node | ✅ Working |
| Calculator tool node (extension) | ✅ Working |
| Web search tool (SerpAPI, extension) | ✅ Working |
| Shared result store across connections | ✅ Working |
| SHA-256 node output cache | ✅ Working |
| File upload → `files/` folder | ✅ Working |

### May 2026 — Critical bug fixed

**Problem:** Clicking "Fetch from Backend" immediately crashed the Python process (exit 139, segfault).  
**Root cause:** The `rag_rust.so` compiled that day from `rag_rust_src/` had a fatal initialization bug. Python loaded it and died instantly — no traceback.  
**Fix:** Replaced with the stable `.so` from `~/Documents/Agentic-RAG-Rust-Core-PFE-26/rustvenv/` (same PyO3 version, same API surface, no crash).  
**Secondary bug fixed:** `BGESmallENV15` was the default embedding model but was missing from the match arm in `embeddings.rs` — local embedding always errored. Fixed in source.

### Architecture decisions locked in

- **Rust extension is pre-compiled** — do not commit `.so`/`.pyd` to git; rebuild locally when source changes (see CONTRIBUTING.md)
- **Python must be exactly 3.13** — the ABI is baked into the `.so` filename (`cpython-313`)
- **Backend launched via `uv run --no-sync`** on Linux, pointing at `backend/backend-env`
- **`build_registry()` runs per WebSocket connection** — modules are cached by Python after first import so this is cheap; if Rust init fails on first connection it will fail on all subsequent ones too

---

## COMPLETED FIXES

- [x] **Shared cache & result store across connections** — `ws_server.py`: moved `InMemoryResultStore` and `InMemoryExecutionCache` to module-level `_shared_store` / `_shared_cache` so all WebSocket connections share the same cache and result store. Previously each connection got its own empty cache, meaning no cross-client cache hits.
- [x] **O(E) → O(degree) edge scanning in executor** — `executor.py:98-107`: replaced the post-wave loop that iterated over all edges with a direct adjacency list lookup (`adj[src]`). For a graph with N nodes and E edges across W waves, this reduces edge scanning from O(W × E) to O(E) total.
- [x] **Streaming node support** — Added `emit(port, data)` callback pattern. Nodes with `emit` parameter in `run()` signature stream chunks to frontend via `stream_chunk` WS message. Executor accumulates chunks into final output. Frontend shows "streaming…" status with live preview. Example: `openrouter.py` streams OpenRouter SSE responses.
- [x] **Frontend type coercion for args** — `flow.jsx:675-693`: field values are now coerced to their backend-declared types (`integer`/`number` → `Number()`, `boolean` → `Boolean()`) before sending in the run payload. Prevents 400 errors from APIs that reject string-typed numbers.
- [x] **Inline streaming preview in nodes** — `flow.jsx:343-352` + `styles.css`: live preview area appears directly in the node body during streaming (no click needed). Shows full text with scroll, purple pulsing border on the node. Removed `previewLines()` truncation from the inline preview.
- [x] **OpenRouter node: sync → async HTTP** — `openrouter.py`: replaced `requests` + `asyncio.to_thread` with `httpx.AsyncClient.stream()`. The `emit` callback was silently failing because it was called from a blocking thread where coroutines were never awaited. Now everything runs in the event loop and `await emit()` actually sends WS messages. Added `httpx` dependency.

## ORPHANS & PENDING

- [ ] force types in the frontend ( string != List[str] ) and the types should be a dropdown list precollected from the backend at first start
- [ ] add a sync of arg fields from the backend and the frontend ( edge cases like fileuploads)
- [ X ] adding a colored border on the nodes indicating their run status , (green is done, yellow is still running, red it gave an error)
- [ x ] adding a small section in the button right of the components that opens a modal(preview of some sort) that lists the output( first 15 lines).
- [ x ] adding a logo placeholder in the front-end through the ui-config from the backend
- [ ] adding a document upload component, and using "ref" to get it's value.
- [ ] implement the reference instead of actual value in fileUpload + change saved files folder + adding multiple compatible formats
- [ ] add a Ctrl+Z functionality
- [ ] update the requirements.txt

- [ ] adding reference resolve logic when getting huge file sizes -----> to verify

## KNOWN BUGS & RESOLUTIONS

### Bug: Connecting tool nodes broke the prompt input ("Prompt input is empty")

**Cause:** The initial design used a separate `_resolve_extensions()` phase that ran before the main execution graph. Both phases operated on the same `node_states` dict and shared the same `pending` counter. When extension nodes (Calculator, WebSearch) completed in the pre-phase, their status was set to `"completed"`, but the main phase's topological sort still counted them in `pending` and `in_deg` calculations. This created a mismatch:
1. Extension phase runs Calculator → marks it `"completed"`
2. Main phase builds `in_deg` including the tool → OpenRouter edge
3. OpenRouter's `in_deg` becomes 2 (prompt + tool)
4. Calculator is already `"completed"` so its edge never fires in the main phase's wave propagation
5. OpenRouter's `in_deg` never drops to 0, it never runs
6. The remaining pending nodes get marked as failed with "Dependency not satisfied"

Even when mode detection worked correctly for server-fetched components, the two-phase design created this state corruption.

**Fix:** Removed the separate extension resolution phase entirely. Now:
- All edges (data + extension) share the same adjacency graph
- Extension nodes run first naturally (they're leaf nodes with in_degree = 0)
- In `_run_node`, extension port values are collected from `node_inputs` and wrapped into `context["extensions"][port_name]` as lists
- Single topological sort, single `pending` counter, no state corruption
- The frontend fallback checks `tgt.data._backendDef.ports.inputs` directly when the port ID lookup fails

### Bug: Adding a second tool overwrote the first ("calculator gets replaced by web_search")

**Cause:** In the executor's wave propagation loop, `node_inputs[tgt][tgt_port] = inp` used direct assignment. When multiple extension edges targeted the same port (e.g., both Calculator and WebSearch → OpenRouter's `tools` port), the second tool's output overwrote the first. The port received only the last-connected tool.

**Fix:** Changed to `node_inputs[tgt].setdefault(tgt_port, []).append(inp)` — all connections to the same port accumulate in a list. In `_run_node`:
- Data ports: single-element lists are unwrapped (`inputs[k] = v[0]` if `len(v) == 1`) for backward compatibility
- Extension ports: receive the full list of all connected tool outputs

### Bug: "Fetch from Backend" instantly crashes Python (segfault, exit 139) — May 2026

**Cause:** The `rag_rust.so` recompiled from `rag_rust_src/` had a fatal initialization bug. The moment Python executed `import rag_rust` the process died — no traceback, no error message, just exit 139.

**Fix:** Replaced the broken `.so` with the stable build from `Agentic-RAG-Rust-Core-PFE-26/rustvenv/`. Both share the same PyO3 0.28.3 + Python 3.13 ABI and identical API surface.
