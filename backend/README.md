# BertLike Backend Core

This package is the execution spine for the visual workflow platform.

## Run The WebSocket Backend

```powershell
python -m pip install -r requirements.txt
python -m backend --host 127.0.0.1 --port 8765
```

The React Flow frontend connects to:

```text
ws://127.0.0.1:8765/ws
```

Override it in Vite with:

```text
VITE_BACKEND_WS_URL=ws://127.0.0.1:8765/ws
```

## WebSocket Messages

Request node schemas:

```json
{ "type": "get_node_types" }
```

Run a graph:

```json
{ "type": "run", "payload": { "...": "Run Request JSON #2" } }
```

The backend streams JSON #3 as:

```json
{
  "type": "execution_state",
  "event": "node_completed",
  "state": { "...": "Execution State JSON #3" }
}
```

## Extension Points

- Add new Python node logic in `backend/nodes/`.
- Register each node with a `NodeTypeSchema` and callable in `build_registry()`.
- Replace `InMemoryResultStore` or `InMemoryExecutionCache` with Redis-backed versions later.
- Keep frontend port names aligned with backend schema port names. The current frontend slugifies labels and disambiguates duplicates with `_2`, `_3`, etc.

