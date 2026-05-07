from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import Any

from websockets.asyncio.server import serve

from backend.core.errors import BackendError, GraphValidationError
from backend.core.executor import AsyncGraphExecutor
from backend.core.models import RunRequest
from backend.core.registry import NodeRegistry
from backend.core.result_store import InMemoryExecutionCache, InMemoryResultStore
from backend.nodes.builtin import register_builtin_nodes

LOGGER = logging.getLogger("bertlike.backend")
PROTOCOL_VERSION = 1


def build_registry() -> NodeRegistry:
    registry = NodeRegistry()
    register_builtin_nodes(registry)
    return registry


class WorkflowWebSocketServer:
    def __init__(self, registry: NodeRegistry | None = None) -> None:
        self.registry = registry or build_registry()
        self.result_store = InMemoryResultStore()
        self.cache = InMemoryExecutionCache()

    async def handle(self, websocket: Any) -> None:
        send_lock = asyncio.Lock()

        async def send(payload: dict[str, Any]) -> None:
            async with send_lock:
                await websocket.send(json.dumps(payload, default=str))

        await send(
            {
                "type": "hello",
                "protocol_version": PROTOCOL_VERSION,
                "node_types": self.registry.to_json(),
            }
        )

        async for raw_message in websocket:
            try:
                message = json.loads(raw_message)
                await self._handle_message(message, send)
            except GraphValidationError as exc:
                await send({"type": "run_rejected", "status": "failed", "errors": exc.issues})
            except BackendError as exc:
                await send({"type": "error", "message": str(exc)})
            except json.JSONDecodeError:
                await send({"type": "error", "message": "message must be JSON"})
            except Exception as exc:  # noqa: BLE001 - protects the socket session
                LOGGER.exception("unexpected websocket handler failure")
                await send({"type": "error", "message": str(exc)})

    async def _handle_message(self, message: dict[str, Any], send: Any) -> None:
        message_type = message.get("type")

        if message_type == "ping":
            await send({"type": "pong"})
            return

        if message_type == "get_node_types":
            await send({"type": "node_types", "node_types": self.registry.to_json()})
            return

        if message_type == "run":
            request = RunRequest.from_dict(message.get("payload"))
            await send({"type": "run_accepted", "run_id": request.run_id})
            executor = AsyncGraphExecutor(
                registry=self.registry,
                result_store=self.result_store,
                cache=self.cache,
                event_sink=send,
            )
            final_state = await executor.execute(request)
            await send({"type": "run_finished", "run_id": request.run_id, "state": final_state.to_json()})
            return

        await send({"type": "error", "message": f"unknown message type: {message_type!r}"})


async def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = WorkflowWebSocketServer()
    async with serve(server.handle, host, port):
        LOGGER.info("Workflow backend listening on ws://%s:%s/ws", host, port)
        await asyncio.Future()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the BertLike asyncio WebSocket backend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(run_server(args.host, args.port))

