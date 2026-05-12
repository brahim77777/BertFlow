# BertFlow — Project Map

## TECH_STACK

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend | Python + asyncio | 3.14.3 |
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
1. **node_type_definitions** (backend → frontend): Auto-sent on connect, also via `get_node_types` request
2. **RunRequest** (frontend → backend): Graph execution payload using `node_type` from backend schema
3. **execution_state** (backend → frontend): `run_accepted`, `run_finished` with per-node state

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
    └── builtin.py            # 3 nodes: PromptBuilder, BrahimYoucefDemo, OutputNode

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

```bash
# Terminal 1: Start backend
python3 -m backend --host 127.0.0.1 --port 8765

# Terminal 2: Start frontend
source ~/.bash_profile && bun run dev
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

Then click "Fetch from Backend" in the Flow view to see it appear.

## ORPHANS & PENDING

- [ ] force types in the frontend ( string != List[str] ) and string != 100, and the types should be a dropdown list precollected from the backend at first start
- [ ] add a sync of arg fields from the backend and the frontend ( edge cases like fileuploads)
- [ ] adding a colored border on the nodes indicating their run status , (green is done, yellow is still running, red it gave an error)
- [ ] adding a small section in the button right of the components that opens a modal(preview of some sort) that lists the output( first 15 lines).
