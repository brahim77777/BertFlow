# BertFlow WebSocket Protocol

Transport: `ws://127.0.0.1:8765` (configurable via `VITE_BACKEND_WS_URL`)

All messages are JSON. The server pushes `node_types` on connect; all other
exchanges are request–response (or request–stream).

---

## Client → Server

### ping

Keepalive — server replies `pong`.

```json
{"type": "ping"}
```

### get_node_types

Fetch all registered node types from the backend.

```json
{"type": "get_node_types"}
```

### run

Execute a flow. The server replies:
1. `run_accepted` — validation passed, execution started
2. Zero or more `node_status` — per-node status updates as execution progresses
3. `run_rejected` — validation failed, no execution

```json
{
  "type": "run",
  "payload": {
    "run_id": "run-<uuid>",
    "flow_id": "flow_abc123",
    "schema_version": 1,
    "flow_revision": 1,
    "created_at": "2026-05-12T...",
    "execution_config": {
      "timeout_seconds": 120,
      "on_node_failure": "halt" | "skip",
      "max_retries": 0
    },
    "nodes": {
      "<node_id>": {
        "node_type": "prompt_builder",
        "args": {
          "model_name": "bert-base",
          "temperature": 0.7
        },
        "config": {
          "cache": false
        }
      }
    },
    "edges": [
      {
        "id": "edge-<uuid>",
        "from": "<source_node_id>",
        "from_port": "output_name",
        "to": "<target_node_id>",
        "to_port": "input_name"
      }
    ]
  }
}
```

### resolve_refs

Resolve `store://` URIs returned in node outputs.

```json
{
  "type": "resolve_refs",
  "refs": ["store://run-<uuid>/<node_id>/output_name"]
}
```

---

## Server → Client

### node_types

Sent automatically on new connection, and in reply to `get_node_types`.

```json
{
  "type": "node_types",
  "node_types": [
    {
      "node_type": "prompt_builder",
      "version": "1.0.0",
      "label": "Prompt Builder",
      "description": "...",
      "category": "llm",
      "ui_config": {
        "icon": "bot",
        "color": "#4A90D9",
        "category_order": 1
      },
      "ports": {
        "inputs": {
          "context": { "type": "string", "required": false, "default": null }
        },
        "outputs": {
          "result": { "type": "string" }
        }
      },
      "args_schema": {
        "model_name": { "type": "string", "default": "bert-base" },
        "temperature": { "type": "number", "default": 0.7 },
        "use_cache": { "type": "boolean", "default": true }
      }
    }
  ]
}
```

### pong

Reply to `ping`.

```json
{"type": "pong"}
```

### run_accepted

Sent after validation passes, before execution begins. The client should
set all nodes to `pending` on receipt.

```json
{
  "type": "run_accepted",
  "run_id": "run-<uuid>",
  "n_nodes": 3,
  "n_edges": 2
}
```

### node_status

**Streamed during execution.** Sent each time a node transitions
between states. The client updates the single referenced node without
waiting for the full run to finish.

```json
{
  "type": "node_status",
  "run_id": "run-<uuid>",
  "node_id": "flow-node-<uuid>",
  "status": "running" | "completed" | "failed",
  "error": null | "Error message if failed"
}
```

State machine:

```
pending ──(run_accepted)──▶ pending
pending ──(node_status)──▶ running
running ──(node_status)──▶ completed
running ──(node_status)──▶ failed
```

There is no `pending` node_status message — the initial `pending` state
is set client-side when `run_accepted` arrives. The server streams
`running`, `completed`, and `failed` as they happen.

### run_rejected

Sent when the run request fails validation. No execution occurs.

```json
{
  "type": "run_rejected",
  "run_id": "run-<uuid>",
  "errors": ["Node type 'foo' not registered"]
}
```

### run_finished

Sent after all nodes have completed (or the execution timed out/failed).
This is the **final** message for a run. The `node_states` map is the
authoritative snapshot — the client should reconcile any streaming
`node_status` updates against this.

```json
{
  "type": "run_finished",
  "run_id": "run-<uuid>",
  "state": {
    "status": "completed" | "failed",
    "node_states": {
      "flow-node-<uuid>": {
        "status": "completed" | "failed" | "pending",
        "outputs": {
          "result": "store://run-<uuid>/<nid>/result",
          "text": "inline value"
        },
        "cached": false,
        "error": null | "Error message"
      }
    },
    "error": null | "Overall error message"
  }
}
```

If the run itself crashed (not a node failure), the `node_states` map may
be absent:

```json
{
  "type": "run_finished",
  "run_id": "run-<uuid>",
  "state": {
    "status": "failed",
    "error": "Execution timed out after 120s"
  }
}
```

### refs_resolved

Reply to `resolve_refs`. Maps each `store://` URI to its resolved value.

```json
{
  "type": "refs_resolved",
  "values": {
    "store://run-<uuid>/<nid>/result": "resolved text content"
  }
}
```

### error / parse_error / internal_error / unknown_type

Generic error sent when a problem is not specific to a run.

```json
{"type": "error", "message": "Something went wrong"}
{"type": "parse_error", "message": "Invalid JSON: ..."}
{"type": "internal_error", "message": "Internal server error: ..."}
{"type": "unknown_type", "message": "Unknown message type 'foo'"}
```

---

## Message flow for a typical run

```
Client                         Server
  │                              │
  ├── get_node_types ──────────▶ │
  │                              ├── node_types
  │◀──────────────────────────── ┤
  │                              │
  ├── run(payload) ────────────▶ │
  │                              ├── run_accepted
  │◀──────────────────────────── ┤
  │                              │  (execution starts)
  │                              ├── node_status(running)  ── for node A
  │◀──────────────────────────── ┤
  │                              ├── node_status(completed) ── for node A
  │◀──────────────────────────── ┤
  │                              ├── node_status(running)  ── for node B
  │◀──────────────────────────── ┤
  │                              ├── node_status(completed) ── for node B
  │◀──────────────────────────── ┤
  │                              ├── run_finished
  │◀──────────────────────────── ┤
  │                              │
  ├── resolve_refs(refs) ──────▶ │
  │                              ├── refs_resolved
  │◀──────────────────────────── ┤
```
