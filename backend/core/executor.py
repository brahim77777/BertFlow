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
from backend.core.result_store import InMemoryResultStore, PersistentExecutionCache


def _clean_error(exc: Exception | str) -> str:
    """Strip library noise (e.g. httpx's MDN link) from an error message."""
    msg = str(exc).strip()
    # httpx appends "\nFor more information check: https://developer.mozilla.org/…"
    msg = msg.split("\nFor more information check:")[0].strip()
    return msg or "unknown error"


class AsyncGraphExecutor:
    def __init__(
        self,
        registry: NodeRegistry,
        store: InMemoryResultStore | None = None,
        cache: PersistentExecutionCache | None = None,
    ) -> None:
        self._registry = registry
        self._store = store or InMemoryResultStore()
        self._cache = cache or PersistentExecutionCache()

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

        pending = len(request.nodes)

        timeout = request.execution_config.timeout_seconds
        fail_mode = request.execution_config.on_node_failure
        max_retries = request.execution_config.max_retries

        # Continuous (dataflow) scheduler: each node runs as its own task, and a
        # downstream node is launched the instant *its own* dependencies finish —
        # a fast branch never waits for a slow sibling (no wave barrier).
        async def _do_execute():
            nonlocal pending
            tasks: dict[asyncio.Task, str] = {}
            halt_error: tuple[str, str] | None = None

            def launch(nid: str) -> None:
                task = asyncio.create_task(
                    self._run_node(
                        request,
                        nid,
                        node_states,
                        node_inputs,
                        output_map,
                        max_retries,
                        on_node_status,
                        on_node_output,
                    )
                )
                tasks[task] = nid

            async def propagate_skip(start: str) -> tuple[list[str], list[str]]:
                """Skip-mode fan-out from a failed/skipped node.

                Returns (nodes_now_ready, nodes_marked_skipped). A downstream node
                whose *required* input vanished is skipped (transitively); one whose
                missing input was optional can still run once its other deps arrive.
                """
                ready_now: list[str] = []
                skipped: list[str] = []
                skip_q: deque[str] = deque([start])
                while skip_q:
                    src = skip_q.popleft()
                    for tgt, _src_port, tgt_port in adj.get(src, []):
                        if node_states[tgt].status != "pending":
                            continue
                        reg = self._registry.get(request.nodes[tgt].node_type)
                        port_def = reg.inputs.get(tgt_port) if reg else None
                        in_deg[tgt] -= 1
                        if port_def and port_def.required:
                            node_states[tgt].status = "skipped"
                            node_states[tgt].error = (
                                f"Skipped: required input '{tgt_port}' unavailable "
                                f"(upstream node '{src}' {node_states[src].status})"
                            )
                            if on_node_status:
                                await on_node_status(tgt, "skipped", node_states[tgt].error, None)
                            skipped.append(tgt)
                            skip_q.append(tgt)
                        elif in_deg[tgt] == 0:
                            ready_now.append(tgt)
                return ready_now, skipped

            # Kick off every node that has no dependencies.
            for nid, deg in in_deg.items():
                if deg == 0:
                    launch(nid)

            try:
                while tasks:
                    done, _ = await asyncio.wait(set(tasks), return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        nid = tasks.pop(task)
                        to_launch: list[str] = []
                        exc = task.exception()

                        if exc is not None:
                            node_states[nid].status = "failed"
                            node_states[nid].error = _clean_error(exc)
                            if on_node_status:
                                await on_node_status(nid, "failed", node_states[nid].error, get_duration(nid))
                            pending -= 1
                            if fail_mode == "halt":
                                if halt_error is None:
                                    reg = self._registry.get(request.nodes[nid].node_type)
                                    label = reg.label if reg and reg.label else request.nodes[nid].node_type
                                    halt_error = (nid, f"'{label}' failed — {node_states[nid].error}")
                            elif fail_mode == "skip":
                                ready_now, skipped = await propagate_skip(nid)
                                pending -= len(skipped)
                                to_launch = ready_now
                        else:
                            result = task.result()
                            node_states[nid].status = "completed"
                            if on_node_status:
                                await on_node_status(nid, "completed", None, get_duration(nid))
                            if result is not None:
                                node_states[nid].outputs = self._store.build_outputs(request.run_id, nid, result)
                                for port_name, val in node_states[nid].outputs.items():
                                    output_map[nid][port_name] = val
                            pending -= 1
                            # Feed outputs downstream; launch any node whose deps are now all satisfied.
                            for tgt, src_port, tgt_port in adj.get(nid, []):
                                if node_states[tgt].status != "pending":
                                    continue
                                raw_val = output_map[nid].get(src_port, "")
                                # Resolve store:// references so downstream nodes get actual data.
                                if isinstance(raw_val, str) and raw_val.startswith("store://"):
                                    resolved = self._store.resolve(raw_val)
                                    inp = resolved if resolved is not None else raw_val
                                else:
                                    inp = raw_val
                                node_inputs[tgt].setdefault(tgt_port, []).append(inp)
                                in_deg[tgt] -= 1
                                if in_deg[tgt] == 0:
                                    to_launch.append(tgt)

                        # Once a halt is pending we stop launching new work, but let
                        # already-running tasks drain to a terminal status.
                        if halt_error is None:
                            for n in to_launch:
                                if node_states[n].status == "pending":
                                    launch(n)
            finally:
                # On cancellation (e.g. timeout) make sure no node task is orphaned.
                for task in [t for t in tasks if not t.done()]:
                    task.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

            if halt_error is not None:
                state.status = "failed"
                state.error = halt_error[1]
                return

            # Nodes that never became ready (e.g. a cycle the validator missed).
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
                node_states[nid].cached = True
                node_states[nid].finished_at = time.time()
                logger.info("Cache hit for node %s (%s)", nid, node.node_type)
                # Re-emit cached string outputs so streaming nodes (e.g. LLMs) still
                # show their text in the UI on a cache hit. Marking the node completed
                # and emitting node_status is left to _do_execute, so it happens exactly
                # once.
                if on_node_output:
                    for port, val in cached.items():
                        if isinstance(val, str) and val:
                            await on_node_output(nid, port, val)
                return cached

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                outputs = await reg.run(args, inputs, ctx, emit)
                node_states[nid].finished_at = time.time()
                for port, chunks in stream_buf.items():  # merge first
                    outputs.setdefault(port, "".join(chunks))
                if node.config.cache:
                    self._cache.put(node.node_type, args, inputs, outputs)  # then cache the complete result
                logger.info("Node %s (%s) completed", nid, node.node_type)
                return outputs
            except Exception as exc:
                last_error = exc
                logger.warning("Node %s attempt %d failed: %s", nid, attempt + 1, exc)
                if attempt < max_retries:
                    await asyncio.sleep(0.1 * (attempt + 1))

        reason = _clean_error(last_error) if last_error else "unknown error"
        if max_retries > 0:
            reason = f"{reason} (failed after {max_retries + 1} attempts)"
        raise NodeExecutionError(reason)
