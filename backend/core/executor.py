from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Awaitable, Callable

from backend.core.errors import NodeExecutionError
from backend.core.logging import logger
from backend.core.models import ExecutionState, NodeState, RunRequest
from backend.core.registry import NodeRegistry
from backend.core.result_store import InMemoryExecutionCache, InMemoryResultStore


class AsyncGraphExecutor:
    def __init__(
        self,
        registry: NodeRegistry,
        store: InMemoryResultStore | None = None,
        cache: InMemoryExecutionCache | None = None,
    ) -> None:
        self._registry = registry
        self._store = store or InMemoryResultStore()
        self._cache = cache or InMemoryExecutionCache()

    async def execute(self, request: RunRequest, on_node_status: Callable[[str, str, str | None], Awaitable[None]] | None = None) -> ExecutionState:
        state = ExecutionState(run_id=request.run_id, status="running")
        node_states: dict[str, NodeState] = {}
        for nid, node in request.nodes.items():
            node_states[nid] = NodeState(node_id=nid, node_type=node.node_type)
        state.node_states = node_states

        adj: dict[str, list[tuple[str, str, str]]] = {nid: [] for nid in request.nodes}
        in_deg: dict[str, int] = {nid: 0 for nid in request.nodes}
        for edge in request.edges:
            adj.setdefault(edge.source, []).append((edge.target, edge.source_port, edge.target_port))
            in_deg[edge.target] = in_deg.get(edge.target, 0) + 1

        output_map: dict[str, dict[str, str]] = defaultdict(dict)
        node_inputs: dict[str, dict[str, object]] = defaultdict(dict)

        ready: deque[str] = deque(nid for nid, d in in_deg.items() if d == 0)
        pending = len(request.nodes)

        timeout = request.execution_config.timeout_seconds
        fail_mode = request.execution_config.on_node_failure
        max_retries = request.execution_config.max_retries

        try:
            async with asyncio.timeout(timeout):
                while ready or pending > 0:
                    wave = list(ready)
                    ready.clear()

                    if not wave:
                        if pending > 0:
                            remaining = [n for n in request.nodes if node_states[n].status == "pending"]
                            if remaining:
                                for nid in remaining:
                                    node_states[nid].status = "failed"
                                    node_states[nid].error = "Dependency not satisfied (possible cycle or disconnected)"
                                    if on_node_status:
                                        await on_node_status(nid, "failed", node_states[nid].error)
                                state.status = "failed"
                                state.error = "Execution stuck: some nodes never became ready"
                            break
                        break

                    tasks = []
                    for nid in wave:
                        tasks.append(self._run_node(request, nid, node_states, node_inputs, output_map, max_retries, on_node_status))

                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    for nid, result in zip(wave, results, strict=True):
                        if isinstance(result, Exception):
                            node_states[nid].status = "failed"
                            node_states[nid].error = str(result)
                            if on_node_status:
                                await on_node_status(nid, "failed", node_states[nid].error)
                            if fail_mode == "halt":
                                state.status = "failed"
                                state.error = f"Node '{nid}' failed: {result}"
                                return state
                            elif fail_mode == "skip":
                                pass
                        else:
                            node_states[nid].status = "completed"
                            if on_node_status:
                                await on_node_status(nid, "completed")
                            if result is not None:
                                node_states[nid].outputs = self._store.build_outputs(request.run_id, nid, result)
                                for port_name, val in node_states[nid].outputs.items():
                                    output_map[nid][port_name] = val

                        pending -= 1

                    new_ready: list[str] = []
                    for edge in request.edges:
                        src = edge.source
                        tgt = edge.target
                        if node_states[src].status == "completed" and node_states[tgt].status == "pending":
                            inp = node_states[src].outputs.get(edge.source_port, "")
                            node_inputs[tgt][edge.target_port] = inp
                            in_deg[tgt] -= 1
                            if in_deg[tgt] == 0:
                                new_ready.append(tgt)

                    ready.extend(nid for nid in new_ready if nid not in ready)

            if state.status == "running":
                state.status = "completed"
        except TimeoutError:
            state.status = "failed"
            state.error = f"Execution timed out after {timeout}s"
        except Exception as exc:
            state.status = "failed"
            state.error = str(exc)
            logger.error("Execution error: %s", exc)

        return state

    async def _run_node(
        self,
        request: RunRequest,
        nid: str,
        node_states: dict[str, NodeState],
        node_inputs: dict[str, dict[str, object]],
        output_map: dict[str, dict[str, str]],
        max_retries: int,
        on_node_status: Callable[[str, str, str | None], Awaitable[None]] | None = None,
    ) -> dict | None:
        node = request.nodes[nid]
        reg = self._registry.get(node.node_type)
        if reg is None:
            raise NodeExecutionError(f"Node type '{node.node_type}' not registered")

        node_states[nid].status = "running"
        node_states[nid].started_at = time.time()
        if on_node_status:
            await on_node_status(nid, "running")

        args = dict(node.args)
        inputs = dict(node_inputs.get(nid, {}))

        if node.config.cache:
            cached = self._cache.get(node.node_type, args, inputs)
            if cached is not None:
                node_states[nid].status = "completed"
                node_states[nid].cached = True
                node_states[nid].finished_at = time.time()
                if on_node_status:
                    await on_node_status(nid, "completed")
                logger.info("Cache hit for node %s (%s)", nid, node.node_type)
                return cached

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                outputs = await reg.run(args, inputs, nid)
                node_states[nid].finished_at = time.time()
                if node.config.cache:
                    self._cache.put(node.node_type, args, inputs, outputs)
                logger.info("Node %s (%s) completed", nid, node.node_type)
                return outputs
            except Exception as exc:
                last_error = exc
                logger.warning("Node %s attempt %d failed: %s", nid, attempt + 1, exc)
                if attempt < max_retries:
                    await asyncio.sleep(0.1 * (attempt + 1))

        raise NodeExecutionError(f"Node '{nid}' failed after {max_retries + 1} attempt(s): {last_error}")
