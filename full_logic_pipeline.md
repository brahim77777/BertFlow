# BertLike Backend — Full Logic Pipeline

> This document traces every code path in the Python WebSocket backend, from process startup through WebSocket handshake, graph validation, wave-based Kahn execution, result storage, cache boundary, and final state emission.

---

## 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                       BertLike Platform                              │
├──────────────────┬────────────────────────┬─────────────────────────┤
│  React Frontend  │  Node.js Helper Server │  Python WebSocket Backend│
│  src/main.jsx    │  server.mjs            │  backend/               │
│  src/flow.jsx    │                        │                         │
│                  │  POST /api/files       │  ws://127.0.0.1:8765/ws │
│  localStorage    │  POST /api/components  │                         │
│  components      │  POST /api/run (legacy)│  NodeRegistry            │
└──────────────────┴────────────────────────┴─────────────────────────┘
```

**Three runtime pieces:**

| Piece | Language | Entry Point | Role |
|-------|----------|-------------|------|
| React Frontend | JavaScript/JSX | `src/main.jsx` | Visual graph builder & flow runner |
| JS Helper Server | Node.js | `server.mjs` | File uploads, JSX generation, legacy run logging |
| Python Backend | Python 3.12+ | `backend/__main__.py` | Graph validation, execution, result storage |

**Core contract — 3 JSON messages:**

| Contract | Name | Direction | Contents |
|----------|------|-----------|----------|
| JSON #1 | `NodeTypeSchema` | Backend → Frontend | What node types exist, their ports, args, types |
| JSON #2 | `RunRequest` | Frontend → Backend | What graph to execute (nodes, edges, config) |
| JSON #3 | `ExecutionState` | Backend → Frontend | What is happening (streamed per-event) |

---

## 2. Backend Package Structure

```
backend/
├── __init__.py              # Package marker
├── __main__.py              # Entry point: calls ws_server.main()
├── ws_server.py             # WebSocket server, message dispatch
├── README.md                # Backend usage docs
├── core/
│   ├── __init__.py          # Package marker
│   ├── models.py            # All data models (241 lines)
│   ├── registry.py          # Node registry (56 lines)
│   ├── validator.py         # Graph validation (164 lines)
│   ├── executor.py          # Async graph executor (204 lines)
│   ├── errors.py            # Exception hierarchy (22 lines)
│   ├── result_store.py      # In-memory result store & cache (52 lines)
│   └── types.py             # Type system & compatibility (62 lines)
└── nodes/
    ├── __init__.py          # Package marker
    └── builtin.py           # 3 built-in node implementations (98 lines)
```

**Module dependencies:**

```
__main__.py → ws_server.py
ws_server.py → core/executor, core/models, core/registry, core/result_store, nodes/builtin
core/executor → core/validator, core/models, core/registry, core/result_store, core/types
core/validator → core/errors, core/models, core/registry, core/types
core/models → core/errors
core/registry → core/models
core/result_store → (stdlib: hashlib, json)
core/types → (stdlib: collections.abc, typing)
nodes/builtin → core/models, core/registry
```

---

## 3. Startup Phase

### 3.1 Process Entry (`backend/__main__.py`)

```
python -m backend --host 127.0.0.1 --port 8765
```

```
__main__.py:4  main()
  ↓
ws_server.py:97  main()
  ├── argparse: --host (default 127.0.0.1), --port (default 8765)
  ├── logging.basicConfig(level=INFO)
  └── asyncio.run(run_server(host, port))
        ↓
ws_server.py:90  run_server()
  ├── WorkflowWebSocketServer()  ← constructor creates all shared state
  │     ├── build_registry() → NodeRegistry (register 3 built-in nodes)
  │     ├── InMemoryResultStore()
  │     └── InMemoryExecutionCache()
  └── websockets.asyncio.server.serve(server.handle, host, port)
        └── await asyncio.Future()   ← runs forever
```

### 3.2 Shared State Created at Startup

All three objects are **singleton instances** created once per server process:

```python
# ws_server.py:29-32
class WorkflowWebSocketServer:
    def __init__(self, registry=None):
        self.registry = registry or build_registry()
        self.result_store = InMemoryResultStore()
        self.cache = InMemoryExecutionCache()
```

| Object | Class | File | Purpose |
|--------|-------|------|---------|
| `registry` | `NodeRegistry` | `registry.py:29` | Maps `node_type` → `RegisteredNode(schema, callable)` |
| `result_store` | `InMemoryResultStore` | `result_store.py:8` | Stores outputs by `[run_id][node_id][port]` |
| `cache` | `InMemoryExecutionCache` | `result_store.py:31` | SHA-256 keyed cache for repeatable node calls |

### 3.3 Built-in Node Registration (`backend/nodes/builtin.py`)

```python
# builtin.py:10-13
def register_builtin_nodes(registry):
    registry.register(_prompt_builder_schema(), prompt_builder)
    registry.register(_demo_schema(), brahim_youcef_demo)
    registry.register(_output_schema(), output_node)
```

Three node types are registered:

| `node_type` | Label | Category | Inputs | Outputs | Args |
|-------------|-------|----------|--------|---------|------|
| `prompt_builder` | Prompt Builder | Text | `context` (string, optional) | `result` (string) | `model_name` (string), `temperature` (number) |
| `brahim_&_youcef_demo` | Brahim & Youcef Demo | Documents | `input_2` (string), `input_2_2` (any) | `text` (string), `output_2` (any), `output_3` (any), `output_4` (any) | `file` (string), `cach_results` (boolean), `number_field` (number), `checkbox_field` (boolean) |
| `output` | Output | IO | `text` (string) | *(none)* | *(none)* |

Each `RegisteredNode` holds two things:
1. `schema: NodeTypeSchema` — the JSON #1 metadata
2. `callable: NodeCallable` — the Python function to execute

---

## 4. WebSocket Protocol

### 4.1 Connection Lifecycle

```
Client connects → Server sends "hello" with JSON #1
Client sends messages → Server dispatches per type
Client disconnects → Loop exits via async for
```

### 4.2 Message Dispatch (`ws_server.py:63-87`)

```python
async def _handle_message(self, message, send):
    message_type = message.get("type")

    if message_type == "ping":
        → send({"type": "pong"})

    if message_type == "get_node_types":
        → send({"type": "node_types", "node_types": registry.to_json()})

    if message_type == "run":
        → parse RunRequest from message["payload"]
        → send({"type": "run_accepted", "run_id": ...})
        → create AsyncGraphExecutor(registry, result_store, cache, event_sink=send)
        → final_state = await executor.execute(request)
        → send({"type": "run_finished", "run_id": ..., "state": final_state.to_json()})

    else
        → send({"type": "error", "message": f"unknown message type: {message_type!r}"})
```

### 4.3 Error Boundaries (`ws_server.py:49-62`)

The handler wraps every message in a try/except chain:

| Exception | Response | Status |
|-----------|----------|--------|
| `GraphValidationError` | `{"type": "run_rejected", "errors": [...]}` | Run rejected, socket stays open |
| `BackendError` | `{"type": "error", "message": ...}` | General backend error |
| `json.JSONDecodeError` | `{"type": "error", "message": "message must be JSON"}` | Malformed message |
| `Exception` (bare) | `{"type": "error", "message": ...}` | Unexpected failure, logged via `LOGGER.exception` |

### 4.4 Send Lock

All outgoing messages acquire `asyncio.Lock()` to prevent concurrent writes corrupting the WebSocket stream.

---

## 5. JSON #2 — Run Request Parsing

### 5.1 Entry Point

```python
# ws_server.py:75
request = RunRequest.from_dict(message.get("payload"))
```

### 5.2 `RunRequest.from_dict()` (`models.py:164-187`)

Parsing steps in order:

```
1. Validate top-level is a dict               → RunRequestError if not
2. Parse nodes must be a dict                 → RunRequestError if not
3. Parse edges must be a list                 → RunRequestError if not
4. For each (node_id, node_data) pair:
   a. NodeInstance.from_dict(node_id, data)
      → validate node_data is a dict
      → extract node_type (must be non-empty string)
      → extract args (must be dict, default {})
      → extract config (NodeConfig.from_dict)
5. For each edge at index:
   a. Edge.from_dict(data, index)
      → validate data is a dict
      → extract id, from, from_port, to, to_port
      → KeyError if any missing
6. Build RunRequest:
   run_id        = payload.run_id or "run-<iso now>"
   flow_id       = payload.flow_id or "flow"
   schema_version = payload.schema_version or 1
   flow_revision  = payload.flow_revision or 1
   created_at    = payload.created_at or now_iso()
   execution_config = ExecutionConfig.from_dict(payload.execution_config or {})
   nodes         = {node_id: NodeInstance, ...}
   edges         = [Edge, ...]
```

### 5.3 `ExecutionConfig.from_dict()` (`models.py:140-150`)

```
timeout_seconds  = float(raw.get("timeout_seconds", 120))
on_node_failure  = str(raw.get("on_node_failure", "halt"))
  → validated: must be "halt", "skip", or "retry"
max_retries      = max(0, int(raw.get("max_retries", 0)))
```

### 5.4 What Happens After Parsing

The server immediately sends:

```json
{"type": "run_accepted", "run_id": "run-..."}
```

This means **JSON shape parsed successfully**. It does NOT mean graph validation passed.

### 5.5 Executor Creation

```python
executor = AsyncGraphExecutor(
    registry=self.registry,          # shared singleton
    result_store=self.result_store,  # shared singleton
    cache=self.cache,                # shared singleton
    event_sink=send,                  # bound to this WebSocket session
)
```

The executor borrows the same three singletons from the server. Every run on this server process shares one `result_store` and one `cache`.

---

## 6. Validation Pipeline (`core/validator.py`)

### 6.1 Entry

```python
# executor.py:35
plan = validate_run_request(request, self.registry)
```

### 6.2 Node Validation (lines 22-45)

For every `(node_id, node_instance)` in the request:

| Check | Error Message |
|-------|---------------|
| `registry.has(node.node_type)` | `"node X uses unknown node_type Y"` |
| Required args exist in `schema.args_schema` | `"node X is missing required arg Y"` |
| Arg values match declared types via `value_matches_type()` | `"node X arg Y expected Z, got W"` |
| No unknown args in payload | `"node X includes unknown arg Y"` |

### 6.3 Edge Validation (lines 46-103)

For every edge in the request:

| Check | Error Message |
|-------|---------------|
| Edge id is unique | `"edge id X is duplicated"` |
| `from_node` exists in request.nodes | `"edge X references missing from node Y"` |
| `to_node` exists in request.nodes | `"edge X references missing to node Y"` |
| `from_node != to_node` | `"edge X creates a self dependency on node Y"` |
| Source output port exists in source schema | `"edge X references missing output port Y on Z"` |
| Target input port exists in target schema | `"edge X references missing input port Y on Z"` |
| Port types are compatible via `are_types_compatible()` | `"edge X type mismatch: A.Y (type1) -> B.Z (type2)"` |
| No duplicate target port | `"input port X.Y has more than one incoming edge"` |

### 6.4 Type Compatibility (`core/types.py:27-41`)

```python
def are_types_compatible(source_type, target_type):
```

Rules after normalization via `TYPE_ALIASES`:

| Source | Target | Compatible? |
|--------|--------|-------------|
| `any` | anything | Yes |
| anything | `any` | Yes |
| exact match | exact match | Yes |
| `int`, `float` | `number` | Yes |
| `int`, `number` | `float` | Yes |
| `file` | `string` | Yes |
| everything else | everything else | No |

### 6.5 Graph Structure Building (lines 46-103)

After all edge checks pass, four maps are built:

```python
incoming_edges[to_node]    = [Edge, ...]  # edges feeding into this node
outgoing_edges[from_node]  = [Edge, ...]  # edges leaving this node
dependencies[node_id]      = {upstream_node_ids}  # nodes this node depends on
dependents[node_id]        = {downstream_node_ids}  # nodes that depend on this node
```

### 6.6 Topological Order (Kahn's Algorithm) (`_topological_order`, lines 122-135)

```
1. remaining_deps = copy of dependencies dict
2. ready = sorted queue of nodes with empty dependency sets
3. while ready:
     a. pop leftmost node
     b. append to order
     c. for each child in sorted(dependents[node]):
          - remove node from child's remaining_deps
          - if child's remaining_deps is now empty: add to ready
4. return order
```

If `len(order) != len(request.nodes)`, the graph contains at least one cycle. The run is rejected.

### 6.7 Connected Components (`_connected_components`, lines 138-163)

Treats `dependencies` and `dependents` as undirected adjacency, runs BFS to find all connected subgraphs.

```
unseen = set(all_node_ids)
while unseen:
    start = min(unseen)  # deterministic
    BFS from start using (dependencies ∪ dependents) as neighbors
    component = visited nodes
    components.append(component)
return components
```

### 6.8 Return: `GraphPlan` Dataclass

```python
@dataclass(frozen=True)
class GraphPlan:
    dependencies: dict[str, set[str]]
    dependents: dict[str, set[str]]
    incoming_edges: dict[str, list[Edge]]
    outgoing_edges: dict[str, list[Edge]]
    connected_components: list[list[str]]
    topo_order: list[str]
```

If validation succeeds, `GraphPlan` is returned. If it fails, `GraphValidationError(issues)` is raised.

---

## 7. Execution Pipeline (`core/executor.py`)

### 7.1 Entry: `AsyncGraphExecutor.execute()` (lines 31-78)

```
1. Parse dict → RunRequest (if needed)
2. plan = validate_run_request(request, registry)
3. state = ExecutionState.for_request(request)
4. state.status = "running"
5. state.started_at = now_iso()
6. Emit "run_started" with connected_components
7. Execute waves (Kahn's algorithm, async)
8. Determine final status:
   - halted         → "failed"
   - any failed     → "failed" (halt mode) or "partial" (skip mode)
   - any skipped    → "partial"
   - all completed  → "completed"
9. state.completed_at = now_iso()
10. Emit "run_completed"
11. Return state
```

### 7.2 Wave Execution Algorithm (lines 41-78)

```python
remaining_deps = copy of plan.dependencies
ready = sorted(node_ids with empty deps)
halted = False

while ready and not halted:
    wave = ready
    ready = []
    emit("wave_started", nodes=wave)

    # Run all nodes in this wave concurrently
    await asyncio.gather(
        *(self._run_or_skip_node(request, plan, state, node_id) for node_id in wave)
    )

    # Check for failures
    if any failed in wave AND on_node_failure == "halt":
        halted = True
        break

    # Schedule next wave
    for node_id in wave:
        remaining_deps.pop(node_id, None)
        for child_id in sorted(plan.dependents[node_id]):
            if child_id in remaining_deps:
                remaining_deps[child_id].discard(node_id)
                if not remaining_deps[child_id] and child_id not in ready:
                    ready.append(child_id)
    ready.sort()
```

Key properties:
- **Nodes in the same wave run in parallel** via `asyncio.gather()`
- **Waves run sequentially** (wave N+1 waits for all wave N nodes to complete)
- **Deterministic ordering**: `sorted()` ensures same order across runs
- **Graph with disconnected components** still works: source nodes of all components appear in wave 1

Example execution:

```
Graph: A→C, B→C, D→E, F

Wave 1: [A, B, D, F]    (all have empty deps)
Wave 2: [C, E]           (C waits for A,B; E waits for D)
Wave 3: []               (done — but the loop condition fails before this)
```

### 7.3 Per-Node Execution: `_run_or_skip_node()` (lines 80-101)

```python
failed_deps = [dep for dep in plan.dependencies[node_id]
               if state.node_states[dep].status in {"failed", "skipped"}]

if failed_deps:
    → Skip this node:
      status = "skipped"
      error = "upstream dependency did not complete: ..."
      emit("node_skipped")
else:
    → Execute normally:
      await _execute_node(request, plan, state, node_id)
```

### 7.4 `_execute_node()` (lines 103-145)

Step-by-step:

#### Step 1: Gather inputs from Result Store

```python
inputs = {}
for edge in plan.incoming_edges[node_id]:
    inputs[edge.to_port] = self.result_store.get(
        request.run_id, edge.from_node, edge.from_port
    )
```

This reads the output values of upstream nodes that were already written to the result store.

#### Step 2: Attempt loop (with retries)

```python
attempts_allowed = max_retries + 1  (only if on_node_failure == "retry", else 1)
```

For each attempt:

#### Step 3: Cache check (`_execute_with_cache`, lines 147-184)

```python
cache_key = make_key(node.node_type, node.args, inputs)
if node.config.cache:
    cached = cache.get(cache_key)
    if cached is not None:
        return cached, True, cache_key
```

The cache key is a SHA-256 hash of `{"node_type": ..., "args": ..., "inputs": ...}`.

#### Step 4: Call the node's Python function

```python
context = NodeContext(run_id, node_id, node_type, args, inputs)
registered = registry.get(node.node_type)

if inspect.iscoroutinefunction(registered.callable):
    outputs = await asyncio.wait_for(
        registered.callable(context),
        timeout=timeout_seconds
    )
else:
    outputs = await asyncio.wait_for(
        asyncio.to_thread(registered.callable, context),
        timeout=timeout_seconds
    )
```

Sync functions are offloaded to a thread via `asyncio.to_thread()`.

#### Step 5: Validate outputs

```python
# executor.py:186-198
for port_name, port_def in output_schema.items():
    if port_def.required and port_name not in outputs:
        raise NodeExecutionError(...)
    if port_name in outputs and not value_matches_type(outputs[port_name], port_def.type):
        raise NodeExecutionError(...)

for port_name in outputs:
    if port_name not in output_schema:
        raise NodeExecutionError(...)
```

#### Step 6: Store outputs

```python
if node.config.cache and not cached:
    cache.set(cache_key, outputs)

result_store.set_node_outputs(run_id, node_id, outputs)
node_state.outputs = result_store.output_refs(run_id, node_id, outputs)
node_state.cached = cached
node_state.status = "completed"
```

The `NodeState` stores **store refs** (like `"store://run-123/demo-a/text"`) rather than actual values.

#### Step 7: Retry or fail

```python
except Exception as exc:
    node_state.error = str(exc)
    if attempt < attempts_allowed:
        emit("node_retrying")
        continue  # retry
    node_state.status = "failed"
    emit("node_failed")
```

### 7.5 Event Emission (`_emit`, lines 200-204)

```python
async def _emit(self, event, state, **extra):
    if self.event_sink is None:
        return
    payload = {
        "type": "execution_state",
        "event": event,
        "state": state.to_json(),
        **extra
    }
    await self.event_sink(payload)
```

All events that can fire:

| Event | Extra fields |
|-------|-------------|
| `run_started` | `connected_components: [...]` |
| `wave_started` | `nodes: [...]` |
| `node_started` | `node_id: "..."` |
| `node_retrying` | `node_id: "..."` |
| `node_completed` | `node_id: "..."` |
| `node_failed` | `node_id: "..."` |
| `node_skipped` | `node_id: "..."` |
| `run_completed` | *(none)* |

---

## 8. Result Store & Cache (`core/result_store.py`)

### 8.1 `InMemoryResultStore`

```
Store structure:
  _values[run_id][node_id][port_name] = actual_value
```

| Method | Signature | Behavior |
|--------|-----------|----------|
| `set_node_outputs` | `(run_id, node_id, outputs)` | Writes all port→value pairs for a node |
| `get` | `(run_id, node_id, port)` | Reads a specific port value (raises KeyError if missing) |
| `ref` | `(run_id, node_id, port)` | Returns `"store://{run_id}/{node_id}/{port}"` |
| `output_refs` | `(run_id, node_id, outputs)` | Returns `{port: ref(...) for port in outputs}` |
| `value_hash` | `(value)` | SHA-256 of `json.dumps(value, sort_keys=True)` |

### 8.2 `InMemoryExecutionCache`

```
Cache structure:
  _values[sha256_key] = outputs_dict
```

| Method | Signature | Behavior |
|--------|-----------|----------|
| `make_key` | `(node_type, args, inputs)` | SHA-256 of `{"node_type":..., "args":..., "inputs":...}` |
| `get` | `(key)` | Returns cached outputs or `None` |
| `set` | `(key, outputs)` | Stores outputs under key |

### 8.3 Store-Ref Pattern

Output values are written to the result store as actual Python objects. But `NodeState.outputs` contains **string references** only:

```json
{
  "outputs": {
    "text": "store://run-123/demo-a/text",
    "output_2": "store://run-123/demo-a/output_2"
  }
}
```

This keeps JSON #3 lightweight. Downstream nodes resolve references by calling `result_store.get()` to fetch the actual value from the upstream node's outputs.

---

## 9. Node System & Registry (`core/registry.py`)

### 9.1 Key Types

```python
NodeContext:  # What every node callable receives
    run_id: str
    node_id: str
    node_type: str
    args: JsonMap       # static instance configuration
    inputs: JsonMap      # upstream outputs keyed by input port name

NodeResult = dict[str, Any]  # What every node callable must return

NodeCallable = Callable[[NodeContext], NodeResult | Awaitable[NodeResult]]
```

### 9.2 `NodeRegistry` Methods

| Method | Signature | Behavior |
|--------|-----------|----------|
| `register` | `(schema, func)` | Binds `node_type` to `RegisteredNode`. Raises `ValueError` if already registered. |
| `decorator` | `(schema)` | Returns a decorator that calls `register()` |
| `get` | `(node_type)` | Returns `RegisteredNode` or raises `KeyError` |
| `has` | `(node_type)` | Returns `bool` |
| `schemas` | `()` | Returns list of all `NodeTypeSchema` objects |
| `to_json` | `()` | Returns JSON-serializable list for JSON #1 |

### 9.3 Built-in Node Implementations

#### `prompt_builder` (lines 34-40)
```python
async def prompt_builder(context):
    model_name = context.args.get("model_name", "bert-base")
    temperature = context.args.get("temperature", 0.7)
    upstream = context.inputs.get("context", "")
    result = f"model={model_name}; temperature={temperature}; context={upstream}"
    return {"result": result}
```

#### `brahim_&_youcef_demo` (lines 67-78)
```python
async def brahim_youcef_demo(context):
    source_text = context.inputs.get("input_2") or context.inputs.get("input_2_2") or context.args.get("file") or "empty"
    number = context.args.get("number_field", 0)
    checked = context.args.get("checkbox_field", False)
    text = f"{source_text} | number={number} | checked={checked}"
    return {
        "text": text,
        "output_2": {"args": context.args, "inputs": context.inputs},
        "output_3": checked,
        "output_4": number,
    }
```

#### `output_node` (lines 94-97)
```python
async def output_node(context):
    print(f"[{context.run_id}] output:{context.node_id}: {context.inputs.get('text', '')}")
    return {}
```

---

## 10. Failure Modes

The `execution_config.on_node_failure` setting controls behavior:

### 10.1 `halt` (default)

```
1. Node fails → node_state.status = "failed"
2. Current wave finishes
3. halted = True → while loop breaks
4. No downstream nodes run
5. Final status: "failed"
```

### 10.2 `skip`

```
1. Node fails → node_state.status = "failed"
2. Wave finishes normally
3. Remaining nodes with completed deps still run
4. Any node depending on the failed node → "skipped"
5. Final status: "partial"
```

### 10.3 `retry`

```
1. Node fails on attempt N where N < (max_retries + 1)
2. node_state.attempts increments
3. Node retries
4. If all attempts fail → node_state.status = "failed"
5. Behavior then follows "halt" or "skip" for any nodes that depend on it
```

---

## 11. Error Hierarchy (`core/errors.py`)

```
BackendError (Exception)
├── RunRequestError       # Malformed JSON #2 payload
├── GraphValidationError  # Graph fails validation (cycle, type mismatch, etc.)
│   .issues: list[str]    # Human-readable error messages
└── NodeExecutionError    # Node callable failure or invalid outputs
```

| Exception | Raised Where | Handled Where |
|-----------|-------------|---------------|
| `RunRequestError` | `models.py` (from_dict methods) | `ws_server.py` as `BackendError` |
| `GraphValidationError` | `validator.py:110` | `ws_server.py` → sends `run_rejected` |
| `NodeExecutionError` | `executor.py:183, 189, 192, 198` | `executor.py:138` → caught as `Exception`, node marked `failed` |

---

## 12. The Node.js Helper Server (`server.mjs`)

Runs alongside the Python backend (started via `run-dev.ps1` or `bun run dev`).

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/files` | File upload: parses multipart form, writes to `files/<name>`, returns `{name, path}` |
| `POST` | `/api/components` | Component JSX generation: creates a React Flow node component at `src/components/generated/<ComponentName>.jsx` |
| `POST` | `/api/run` | Legacy run logger: just logs the payload and returns 200 (the real execution is in the Python WebSocket backend) |
| `GET` | `/*` | Static file server: serves `index.html`, JS, CSS, etc. |

### Component Name Transformation

```
"Brahim & youcef demo" → "BrahimYoucefDemo"
"output"               → "Output"
"file upload"          → "FileUpload"
```

The `toComponentName()` function removes non-alphanumeric characters, splits on whitespace, capitalizes each word, and joins.

### Generated Component Template

Each generated `.jsx` file:
- Defines `fields`, `inputs`, `outputs` as JSON constants
- Exports a `memo()`-wrapped React component
- Renders `Handle` components (type=target/source) with the port's UUID as handle id
- Renders field values with type-aware `FieldValue` (toggle/checkbox → switch span, others → value span)

---

## 13. Vite Configuration (`vite.config.js`)

The Vite dev server includes a custom middleware `localApiPlugin()` that proxies API endpoints during development:

- `/api/files` → handled by the plugin (simulates the JS server's file upload)
- `/api/components` → handled by the plugin (simulates JSX generation)
- `/api/run` → handled by the plugin (simulates run logging)

The actual WebSocket connections go directly from the browser to `ws://127.0.0.1:8765/ws`.

---

## 14. Complete End-to-End Flow

### Phase 1: Startup
```
[Terminal 1] python -m backend --host 127.0.0.1 --port 8765
  → create NodeRegistry
  → register prompt_builder, brahim_&_youcef_demo, output
  → create InMemoryResultStore
  → create InMemoryExecutionCache
  → listen on ws://127.0.0.1:8765

[Terminal 2] bun run dev
  → Vite dev server on http://localhost:5173
  → server.mjs on same port (or different port via PORT env)
```

### Phase 2: Frontend connects
```
1. Browser opens http://localhost:5173
2. src/main.jsx mounts React app
3. Components loaded from localStorage
4. User builds component graph in React Flow canvas
```

### Phase 3: Run Flow
```
1. User clicks "Run Flow"
2. src/flow.jsx runFlow() constructs JSON #2:
   {
     type: "run",
     payload: { run_id, flow_id, nodes, edges, execution_config }
   }
3. WebSocket opens to ws://127.0.0.1:8765/ws
4. Backend sends JSON #1 (hello + node_types)
5. Frontend sends JSON #2 (run)
6. Backend sends run_accepted
```

### Phase 4: Backend execution
```
7. validate_run_request():
   a. Validate all nodes (types, args)
   b. Validate all edges (ports, types, uniqueness)
   c. Run Kahn's topological sort (reject cycles)
   d. Find connected components
   e. Build GraphPlan (deps, dependents, edge maps)

8. Initialize ExecutionState:
   a. status = "running"
   b. All nodes → "pending"
   c. Emit "run_started"

9. Wave execution loop:
   Wave 1: all source nodes
     a. For each node:
        - Gather inputs from result_store
        - Check cache
        - Execute callable (async or thread-pooled)
        - Validate outputs against schema
        - Store outputs in result_store
        - Emit "node_completed" (or "node_failed"/"node_skipped")
     b. Check for halting condition
     c. Schedule next wave

10. Set final status (completed/failed/partial)
11. Emit "run_completed"
12. Send run_finished with final ExecutionState
```

### Phase 5: Frontend displays results
```
13. Frontend receives run_finished
14. Sets isRunning = false
15. Updates runStatus text
16. (Future: visual node state indicators)
```

---

## 15. Testing (`tests/test_backend_core.py`)

Four test cases:

| Test | What it validates |
|------|-------------------|
| `test_executor_runs_topological_waves_and_stores_refs` | 3-node DAG: `demo-a → demo-b → out`. Asserts final status "completed", node outputs use store ref format, output node has empty outputs dict. |
| `test_disconnected_components_run_without_manual_selection` | 2 disconnected nodes (no edges). Asserts `GraphPlan` finds 2 connected components, both nodes complete. |
| `test_cache_boundary_marks_reused_node_outputs` | Same node with same args in 2 separate runs. First run: `cached=false`. Second run: `cached=true`. Asserts cache boundary works across runs. |
| `test_cycles_are_rejected_before_execution` | 2-node cycle `a → b → a`. Asserts `GraphValidationError` raised with "cycle" in message. |
| `test_duplicate_target_input_is_rejected` | 2 nodes feeding into same input port of output node. Asserts `GraphValidationError` raised with "more than one incoming edge". |

Run with:
```powershell
python -m pytest tests/test_backend_core.py -v
```

---

## 16. Extension Points

### Adding a New Node Type

1. Create schema in `backend/nodes/builtin.py` (or new file):
   ```python
   schema = NodeTypeSchema(
       node_type="my_node",
       label="My Node",
       category="Custom",
       inputs={...},
       outputs={...},
       args_schema={...},
   )
   ```
2. Implement the callable:
   ```python
   async def my_node(context: NodeContext) -> dict[str, Any]:
       ...
       return {"output_port": result}
   ```
3. Register in `register_builtin_nodes()`:
   ```python
   registry.register(schema, my_node)
   ```

### Swapping Storage Backends

- `InMemoryResultStore` → Redis: implement `set_node_outputs()`, `get()`, `ref()`, `output_refs()`
- `InMemoryExecutionCache` → Redis: implement `make_key()`, `get()`, `set()`

### Adding Auth

Insert at `WorkflowWebSocketServer.handle()` (line 34) — validate the WebSocket handshake or first message.

### Adding Run History

Subscribe to `_emit()` events in the executor and persist to a database.

---

## 17. Key Design Principles

1. **Frontend owns visuals, Backend owns execution truth.** The backend never sees canvas positions, handle UUIDs, or UI state. The frontend never constructs execution state — it only receives it.

2. **Thin model layer, fat validation.** `models.py` is pure dataclass deserialization with basic shape checks. All semantic validation (types, ports, cycles) lives in `validator.py`.

3. **Caching is opt-in.** Only nodes with `config.cache = true` participate in cache lookups. The cache is a SHA-256 hash of `(node_type + args + inputs)`. Cached nodes still write refs to the current run's result store.

4. **Result refs, not values.** `NodeState.outputs` contains string refs (`"store://run_id/node_id/port"`) instead of actual values. This keeps execution state messages small and enables future binary/streaming output storage.

5. **Deterministic scheduling.** `sorted()` is used everywhere — for ready queues, wave ordering, dependency iteration. Same graph always produces the same execution order.

6. **Async-first.** The server, executor, and node callables are all `async`. Sync callables are bridged via `asyncio.to_thread()`. All node execution has configurable timeout.

7. **Retry is a failure mode, not a default.** Retries only activate when `on_node_failure = "retry"` AND `max_retries > 0`.
