from __future__ import annotations

import asyncio
import json
import traceback
from typing import Any

from backend.core.errors import GraphValidationError
from backend.core.executor import AsyncGraphExecutor
from backend.core.logging import logger
from backend.core.models import RunRequest
from backend.core.registry import NodeRegistry
from backend.core.result_store import InMemoryExecutionCache, InMemoryResultStore
from backend.core.validator import validate_run_request

_shared_store = InMemoryResultStore()
_shared_cache = InMemoryExecutionCache()


def build_registry() -> NodeRegistry:
    return NodeRegistry.discover()


def _make_error(msg: str, code: str = "error") -> str:
    return json.dumps({"type": code, "message": msg})


async def handle_message(
    text: str,
    registry: NodeRegistry,
    executor: AsyncGraphExecutor,
    send_fn: Any,
    store: InMemoryResultStore | None = None,
) -> None:
    try:
        msg = json.loads(text)
    except json.JSONDecodeError as exc:
        await send_fn(_make_error(f"Invalid JSON: {exc}", "parse_error"))
        return

    msg_type = msg.get("type", "")

    if msg_type == "ping":
        await send_fn(json.dumps({"type": "pong"}))
        return

    if msg_type == "get_node_types":
        await send_fn(json.dumps({
            "type": "node_types",
            "node_types": registry.get_types(),
        }))
        return

    if msg_type == "run":
        payload = msg.get("payload", {})
        run_id = payload.get("run_id", "unknown")

        try:
            request = RunRequest.from_dict(payload)
        except (KeyError, TypeError, ValueError) as exc:
            await send_fn(json.dumps({
                "type": "run_rejected",
                "run_id": run_id,
                "errors": [f"Invalid run request: {exc}"],
            }))
            return

        try:
            validate_run_request(request, registry)
        except GraphValidationError as exc:
            await send_fn(json.dumps({
                "type": "run_rejected",
                "run_id": run_id,
                "errors": [str(exc)],
            }))
            return

        await send_fn(json.dumps({
            "type": "run_accepted",
            "run_id": run_id,
            "n_nodes": len(request.nodes),
            "n_edges": len(request.edges),
        }))

        try:
            async def on_node_status(nid: str, status: str, error: str | None = None) -> None:
                await send_fn(json.dumps({
                    "type": "node_status",
                    "run_id": run_id,
                    "node_id": nid,
                    "status": status,
                    "error": error,
                }))

            async def on_node_output(nid: str, port: str, data: str) -> None:
                await send_fn(json.dumps({
                    "type": "stream_chunk",
                    "run_id": run_id,
                    "node_id": nid,
                    "port": port,
                    "data": data,
                }))

            state = await executor.execute(request, on_node_status=on_node_status, on_node_output=on_node_output)
            result = {
                "type": "run_finished",
                "run_id": run_id,
                "state": {
                    "status": state.status,
                    "node_states": {
                        nid: {
                            "status": ns.status,
                            "outputs": ns.outputs,
                            "cached": ns.cached,
                            "error": ns.error,
                        }
                        for nid, ns in state.node_states.items()
                    },
                },
            }
            if state.error:
                result["state"]["error"] = state.error
            await send_fn(json.dumps(result))
        except Exception as exc:
            logger.error("Execution failed: %s\n%s", exc, traceback.format_exc())
            await send_fn(json.dumps({
                "type": "run_finished",
                "run_id": run_id,
                "state": {"status": "failed", "error": str(exc)},
            }))
        return

    if msg_type == "resolve_refs":
        refs: list[str] = msg.get("refs", [])
        values: dict[str, Any] = {}
        if store is not None:
            for ref in refs:
                values[ref] = store.resolve(ref)
        await send_fn(json.dumps({"type": "refs_resolved", "values": values}))
        return

    await send_fn(_make_error(f"Unknown message type '{msg_type}'", "unknown_type"))


async def ws_handler(websocket: Any) -> None:
    registry = build_registry()
    executor = AsyncGraphExecutor(registry, _shared_store, _shared_cache)

    logger.info(
        "New connection — %d node types available",
        len(registry),
    )

    async def send(data: str) -> None:
        try:
            await websocket.send(data)
        except Exception:
            pass

    await send(json.dumps({
        "type": "node_types",
        "node_types": registry.get_types(),
    }))

    async for raw in websocket:
        try:
            await handle_message(raw, registry, executor, send, _shared_store)
        except Exception as exc:
            logger.error("Unhandled error: %s\n%s", exc, traceback.format_exc())
            await send(_make_error(f"Internal server error: {exc}", "internal_error"))


async def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    import websockets.asyncio.server

    logger.info("Starting BertFlow WebSocket server on %s:%s", host, port)
    async with websockets.asyncio.server.serve(ws_handler, host, port):
        await asyncio.get_running_loop().create_future()


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_server())
