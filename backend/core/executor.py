from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from .errors import GraphValidationError, NodeExecutionError
from .models import ExecutionState, NodeState, RunRequest, now_iso
from .registry import NodeContext, NodeRegistry
from .result_store import InMemoryExecutionCache, InMemoryResultStore
from .types import value_matches_type
from .validator import GraphPlan, validate_run_request

EventSink = Callable[[dict[str, Any]], Awaitable[None]]


class AsyncGraphExecutor:
    def __init__(
        self,
        registry: NodeRegistry,
        result_store: InMemoryResultStore | None = None,
        cache: InMemoryExecutionCache | None = None,
        event_sink: EventSink | None = None,
    ) -> None:
        self.registry = registry
        self.result_store = result_store or InMemoryResultStore()
        self.cache = cache or InMemoryExecutionCache()
        self.event_sink = event_sink

    async def execute(self, request: RunRequest | dict[str, Any]) -> ExecutionState:
        if isinstance(request, dict):
            request = RunRequest.from_dict(request)

        plan = validate_run_request(request, self.registry)
        state = ExecutionState.for_request(request)
        state.status = "running"
        state.started_at = now_iso()
        await self._emit("run_started", state, connected_components=plan.connected_components)

        remaining_deps = {node_id: set(upstream) for node_id, upstream in plan.dependencies.items()}
        ready = sorted(node_id for node_id, upstream in remaining_deps.items() if not upstream)
        halted = False

        while ready and not halted:
            wave = ready
            ready = []
            await self._emit("wave_started", state, nodes=wave)
            await asyncio.gather(*(self._run_or_skip_node(request, plan, state, node_id) for node_id in wave))

            failed_in_wave = any(state.node_states[node_id].status == "failed" for node_id in wave)
            if failed_in_wave and request.execution_config.on_node_failure == "halt":
                halted = True
                break

            for node_id in wave:
                remaining_deps.pop(node_id, None)
                for child_id in sorted(plan.dependents[node_id]):
                    if child_id in remaining_deps:
                        remaining_deps[child_id].discard(node_id)
                        if not remaining_deps[child_id] and child_id not in ready:
                            ready.append(child_id)
            ready.sort()

        if halted:
            state.status = "failed"
        else:
            statuses = [node_state.status for node_state in state.node_states.values()]
            if any(status == "failed" for status in statuses):
                state.status = "partial" if request.execution_config.on_node_failure == "skip" else "failed"
            elif any(status == "skipped" for status in statuses):
                state.status = "partial"
            else:
                state.status = "completed"

        state.completed_at = now_iso()
        await self._emit("run_completed", state)
        return state

    async def _run_or_skip_node(
        self,
        request: RunRequest,
        plan: GraphPlan,
        state: ExecutionState,
        node_id: str,
    ) -> None:
        node_state = state.node_states[node_id]
        failed_dependencies = [
            dependency_id
            for dependency_id in plan.dependencies[node_id]
            if state.node_states[dependency_id].status in {"failed", "skipped"}
        ]

        if failed_dependencies:
            node_state.status = "skipped"
            node_state.error = f"upstream dependency did not complete: {', '.join(sorted(failed_dependencies))}"
            node_state.completed_at = now_iso()
            await self._emit("node_skipped", state, node_id=node_id)
            return

        await self._execute_node(request, plan, state, node_id)

    async def _execute_node(
        self,
        request: RunRequest,
        plan: GraphPlan,
        state: ExecutionState,
        node_id: str,
    ) -> None:
        node = request.nodes[node_id]
        registered = self.registry.get(node.node_type)
        node_state = state.node_states[node_id]
        inputs = {
            edge.to_port: self.result_store.get(request.run_id, edge.from_node, edge.from_port)
            for edge in plan.incoming_edges[node_id]
        }
        attempts_allowed = request.execution_config.max_retries + 1 if request.execution_config.on_node_failure == "retry" else 1

        for attempt in range(1, attempts_allowed + 1):
            node_state.status = "running"
            node_state.started_at = node_state.started_at or now_iso()
            node_state.attempts = attempt
            node_state.error = None
            await self._emit("node_started", state, node_id=node_id)

            try:
                outputs, cached, cache_key = await self._execute_with_cache(request, node_id, inputs)
                self._validate_outputs(registered.schema.outputs, outputs, node_id)
                if node.config.cache and not cached:
                    self.cache.set(cache_key, outputs)
                self.result_store.set_node_outputs(request.run_id, node_id, outputs)
                node_state.outputs = self.result_store.output_refs(request.run_id, node_id, outputs)
                node_state.cached = cached
                node_state.status = "completed"
                node_state.completed_at = now_iso()
                await self._emit("node_completed", state, node_id=node_id)
                return
            except Exception as exc:  # noqa: BLE001 - node boundary must contain all callable failures
                node_state.error = str(exc)
                if attempt < attempts_allowed:
                    await self._emit("node_retrying", state, node_id=node_id)
                    continue
                node_state.status = "failed"
                node_state.completed_at = now_iso()
                await self._emit("node_failed", state, node_id=node_id)

    async def _execute_with_cache(
        self,
        request: RunRequest,
        node_id: str,
        inputs: dict[str, Any],
    ) -> tuple[dict[str, Any], bool, str]:
        node = request.nodes[node_id]

        cache_key = self.cache.make_key(node.node_type, node.args, inputs)
        if node.config.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached, True, cache_key

        registered = self.registry.get(node.node_type)
        context = NodeContext(
            run_id=request.run_id,
            node_id=node_id,
            node_type=node.node_type,
            args=node.args,
            inputs=inputs,
        )

        if inspect.iscoroutinefunction(registered.callable):
            result = registered.callable(context)
            outputs = await asyncio.wait_for(result, timeout=request.execution_config.timeout_seconds)
        else:
            outputs = await asyncio.wait_for(
                asyncio.to_thread(registered.callable, context),
                timeout=request.execution_config.timeout_seconds,
            )
            if inspect.isawaitable(outputs):
                outputs = await asyncio.wait_for(outputs, timeout=request.execution_config.timeout_seconds)

        if not isinstance(outputs, dict):
            raise NodeExecutionError(f"node {node_id} must return an object keyed by output port")

        return outputs, False, cache_key

    def _validate_outputs(self, output_schema: dict[str, Any], outputs: dict[str, Any], node_id: str) -> None:
        for port_name, port_def in output_schema.items():
            if port_def.required and port_name not in outputs:
                raise NodeExecutionError(f"node {node_id} did not return required output {port_name!r}")
            if port_name in outputs and not value_matches_type(outputs[port_name], port_def.type):
                raise NodeExecutionError(
                    f"node {node_id} output {port_name!r} expected {port_def.type}, "
                    f"got {type(outputs[port_name]).__name__}"
                )

        for port_name in outputs:
            if port_name not in output_schema:
                raise NodeExecutionError(f"node {node_id} returned undeclared output {port_name!r}")

    async def _emit(self, event: str, state: ExecutionState, **extra: Any) -> None:
        if self.event_sink is None:
            return
        payload = {"type": "execution_state", "event": event, "state": state.to_json(), **extra}
        await self.event_sink(payload)
