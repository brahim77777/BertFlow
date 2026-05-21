from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any

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

    async def execute(
        self,
        request: RunRequest,
        on_node_status: Callable[[str, str, str | None, float | None], Awaitable[None]] | None = None,
        on_node_output: Callable[[str, str, str], Awaitable[None]] | None = None,
    ) -> ExecutionState:
        state = ExecutionState(run_id=request.run_id, status="running")
        node_states: dict[str, NodeState] = {}
        for nid, node in request.nodes.items():
            node_states[nid] = NodeState(node_id=nid, node_type=node.node_type)
        state.node_states = node_states

        def get_duration(nid: str) -> float | None:
            ns = node_states.get(nid)
            if ns and ns.started_at is not None:
                fin = ns.finished_at or time.time()
                return round(fin - ns.started_at, 3)
            return None

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

        async def _do_execute():
            nonlocal pending
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
                                    await on_node_status(nid, "failed", node_states[nid].error, get_duration(nid))
                            state.status = "failed"
                            state.error = "Execution stuck: some nodes never became ready"
                        break
                    break

                tasks = []
                for nid in wave:
                    tasks.append(
                        self._run_node(
                            request, nid, node_states, node_inputs,
                            output_map, max_retries, on_node_status, on_node_output,
                        )
                    )

                results = await asyncio.gather(*tasks, return_exceptions=True)

                # FIX 1: Process ALL results before acting on halt, so every node
                # in the wave gets its final status — none stay stuck at "running".
                halt_node: tuple[str, Exception] | None = None
                for nid, result in zip(wave, results, strict=True):
                    if isinstance(result, Exception):
                        node_states[nid].status = "failed"
                        node_states[nid].error = str(result)
                        if on_node_status:
                            await on_node_status(nid, "failed", node_states[nid].error, get_duration(nid))
                        # Record the first failure for halt, but keep iterating.
                        if fail_mode == "halt" and halt_node is None:
                            halt_node = (nid, result)
                    else:
                        node_states[nid].status = "completed"
                        if on_node_status:
                            await on_node_status(nid, "completed", None, get_duration(nid))
                        if result is not None:
                            node_states[nid].outputs = self._store.build_outputs(request.run_id, nid, result)
                            for port_name, val in node_states[nid].outputs.items():
                                output_map[nid][port_name] = val
                    pending -= 1

                # Now it's safe to halt — every node in the wave has a terminal status.
                if halt_node is not None:
                    nid, result = halt_node
                    state.status = "failed"
                    state.error = f"Node '{nid}' failed: {result}"
                    return

                # Propagate outputs to downstream nodes, and handle skip propagation.
                #
                # skip_queue holds nodes whose status just became "failed" or "skipped"
                # while fail_mode == "skip". We drain it transitively so that every
                # downstream node that depended on a required output is also marked
                # "skipped" before the next wave is built — no node ever gets stranded
                # at "pending" and no ambiguous None leaks into the data ports.
                skip_queue: deque[str] = deque()

                for src in wave:
                    if node_states[src].status == "completed":
                        for tgt, src_port, tgt_port in adj.get(src, []):
                            if node_states[tgt].status != "pending":
                                continue
                            raw_val = output_map[src].get(src_port, "")
                            # Resolve store:// references so downstream nodes get actual data.
                            if isinstance(raw_val, str) and raw_val.startswith("store://"):
                                resolved = self._store.resolve(raw_val)
                                inp = resolved if resolved is not None else raw_val
                            else:
                                inp = raw_val
                            node_inputs[tgt].setdefault(tgt_port, []).append(inp)
                            in_deg[tgt] -= 1
                            if in_deg[tgt] == 0:
                                ready.append(tgt)

                    elif node_states[src].status == "failed" and fail_mode == "skip":
                        skip_queue.append(src)

                # Drain transitively: a skipped node is itself a skip source.
                while skip_queue:
                    src = skip_queue.popleft()
                    for tgt, src_port, tgt_port in adj.get(src, []):
                        if node_states[tgt].status != "pending":
                            continue

                        port_def = self._registry.get(request.nodes[tgt].node_type).inputs.get(tgt_port)
                        in_deg[tgt] -= 1

                        if port_def and port_def.required:
                            # Required input is gone → skip this node and propagate.
                            src_outcome = node_states[src].status  # "failed" or "skipped"
                            node_states[tgt].status = "skipped"
                            node_states[tgt].error = (
                                f"Skipped: required input '{tgt_port}' unavailable "
                                f"(upstream node '{src}' {src_outcome})"
                            )
                            if on_node_status:
                                await on_node_status(tgt, "skipped", node_states[tgt].error, None)
                            pending -= 1
                            skip_queue.append(tgt)
                        else:
                            # Optional input — node can still run without it.
                            # Simply don't inject anything; the node uses its own default.
                            if in_deg[tgt] == 0:
                                ready.append(tgt)

        try:
            await asyncio.wait_for(_do_execute(), timeout=timeout)
            if state.status == "running":
                state.status = "completed"
        except asyncio.TimeoutError:
            state.status = "failed"
            state.error = f"Execution timed out after {timeout}s"
            for ns in node_states.values():
                if ns.status == "running":
                    ns.status = "failed"
                    ns.error = "Node was running when execution timed out"
                    ns.finished_at = time.time()
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
        on_node_status: Callable[[str, str, str | None, float | None], Awaitable[None]] | None = None,
        on_node_output: Callable[[str, str, str], Awaitable[None]] | None = None,
    ) -> dict | None:
        node = request.nodes[nid]
        reg = self._registry.get(node.node_type)
        if reg is None:
            raise NodeExecutionError(f"Node type '{node.node_type}' not registered")

        node_states[nid].status = "running"
        node_states[nid].started_at = time.time()
        if on_node_status:
            await on_node_status(nid, "running", None, None)

        args = dict(node.args)
        raw_inputs = node_inputs.get(nid, {})
        inputs = {}
        for k, v in raw_inputs.items():
            inputs[k] = v[0] if isinstance(v, list) and len(v) == 1 else v

        ext_ports = [p for p in reg.inputs.values() if p.mode == "extension"]
        ctx: dict[str, Any] = {}
        if ext_ports:
            extensions: dict[str, Any] = {}
            for port_def in ext_ports:
                val = raw_inputs.get(port_def.name)
                if val is not None:
                    extensions[port_def.name] = val if isinstance(val, list) else [val]
            if extensions:
                ctx["extensions"] = extensions

        stream_buf: dict[str, list[str]] = defaultdict(list)

        async def emit(port: str, data: str) -> None:
            stream_buf[port].append(data)
            if on_node_output:
                await on_node_output(nid, port, data)

        if node.config.cache:
            cached = self._cache.get(node.node_type, args, inputs)
            if cached is not None:
                node_states[nid].status = "completed"
                node_states[nid].cached = True
                node_states[nid].finished_at = time.time()
                if on_node_status:
                    dur = round(node_states[nid].finished_at - node_states[nid].started_at, 3) if node_states[nid].finished_at and node_states[nid].started_at else None
                    await on_node_status(nid, "completed", None, dur)
                logger.info("Cache hit for node %s (%s)", nid, node.node_type)
                return cached

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                outputs = await reg.run(args, inputs, ctx, emit)
                node_states[nid].finished_at = time.time()
                if node.config.cache:
                    self._cache.put(node.node_type, args, inputs, outputs)
                for port, chunks in stream_buf.items():
                    outputs.setdefault(port, "".join(chunks))
                logger.info("Node %s (%s) completed", nid, node.node_type)
                return outputs
            except Exception as exc:
                last_error = exc
                logger.warning("Node %s attempt %d failed: %s", nid, attempt + 1, exc)
                if attempt < max_retries:
                    await asyncio.sleep(0.1 * (attempt + 1))

        raise NodeExecutionError(f"Node '{nid}' failed after {max_retries + 1} attempt(s): {last_error}")
