from __future__ import annotations

import unittest

from backend.core.errors import GraphValidationError
from backend.core.executor import AsyncGraphExecutor
from backend.core.models import RunRequest
from backend.core.validator import validate_run_request
from backend.ws_server import build_registry


def demo_node(args: dict | None = None, cache: bool = False) -> dict:
    return {
        "node_type": "brahim_&_youcef_demo",
        "args": {
            "file": "seed.txt",
            "cach_results": False,
            "number_field": 8,
            "checkbox_field": False,
            **(args or {}),
        },
        "config": {"cache": cache},
    }


class BackendCoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.registry = build_registry()

    async def test_executor_runs_topological_waves_and_stores_refs(self) -> None:
        request = RunRequest.from_dict(
            {
                "run_id": "run-test",
                "flow_id": "flow-test",
                "schema_version": 1,
                "flow_revision": 1,
                "execution_config": {"timeout_seconds": 5, "on_node_failure": "halt", "max_retries": 0},
                "nodes": {
                    "demo-a": demo_node(),
                    "demo-b": demo_node({"number_field": 13}),
                    "out": {"node_type": "output", "args": {}, "config": {"cache": False}},
                },
                "edges": [
                    {"id": "e1", "from": "demo-a", "from_port": "text", "to": "demo-b", "to_port": "input_2"},
                    {"id": "e2", "from": "demo-b", "from_port": "text", "to": "out", "to_port": "text"},
                ],
            }
        )

        executor = AsyncGraphExecutor(self.registry)
        state = await executor.execute(request)

        self.assertEqual(state.status, "completed")
        self.assertEqual(state.node_states["demo-a"].status, "completed")
        self.assertEqual(state.node_states["demo-b"].outputs["text"], "store://run-test/demo-b/text")
        self.assertEqual(state.node_states["out"].outputs, {})

    async def test_disconnected_components_run_without_manual_selection(self) -> None:
        request = RunRequest.from_dict(
            {
                "run_id": "run-components",
                "flow_id": "flow-test",
                "schema_version": 1,
                "flow_revision": 1,
                "nodes": {
                    "prompt": {
                        "node_type": "prompt_builder",
                        "args": {"model_name": "bert-base", "temperature": 0.2},
                        "config": {"cache": False},
                    },
                    "demo": demo_node(),
                },
                "edges": [],
            }
        )

        plan = validate_run_request(request, self.registry)
        state = await AsyncGraphExecutor(self.registry).execute(request)

        self.assertEqual(len(plan.connected_components), 2)
        self.assertEqual(state.status, "completed")
        self.assertEqual(state.node_states["prompt"].status, "completed")
        self.assertEqual(state.node_states["demo"].status, "completed")

    async def test_cache_boundary_marks_reused_node_outputs(self) -> None:
        executor = AsyncGraphExecutor(self.registry)
        base_payload = {
            "flow_id": "flow-cache",
            "schema_version": 1,
            "flow_revision": 1,
            "nodes": {"demo": demo_node(cache=True)},
            "edges": [],
        }

        first_state = await executor.execute(RunRequest.from_dict({"run_id": "run-cache-a", **base_payload}))
        second_state = await executor.execute(RunRequest.from_dict({"run_id": "run-cache-b", **base_payload}))

        self.assertFalse(first_state.node_states["demo"].cached)
        self.assertTrue(second_state.node_states["demo"].cached)

    def test_cycles_are_rejected_before_execution(self) -> None:
        request = RunRequest.from_dict(
            {
                "run_id": "run-cycle",
                "flow_id": "flow-test",
                "schema_version": 1,
                "flow_revision": 1,
                "nodes": {"a": demo_node(), "b": demo_node()},
                "edges": [
                    {"id": "e1", "from": "a", "from_port": "text", "to": "b", "to_port": "input_2"},
                    {"id": "e2", "from": "b", "from_port": "text", "to": "a", "to_port": "input_2"},
                ],
            }
        )

        with self.assertRaises(GraphValidationError) as raised:
            validate_run_request(request, self.registry)

        self.assertIn("cycle", str(raised.exception))

    def test_duplicate_target_input_is_rejected(self) -> None:
        request = RunRequest.from_dict(
            {
                "run_id": "run-duplicate-input",
                "flow_id": "flow-test",
                "schema_version": 1,
                "flow_revision": 1,
                "nodes": {
                    "a": demo_node(),
                    "b": demo_node(),
                    "out": {"node_type": "output", "args": {}, "config": {"cache": False}},
                },
                "edges": [
                    {"id": "e1", "from": "a", "from_port": "text", "to": "out", "to_port": "text"},
                    {"id": "e2", "from": "b", "from_port": "text", "to": "out", "to_port": "text"},
                ],
            }
        )

        with self.assertRaises(GraphValidationError) as raised:
            validate_run_request(request, self.registry)

        self.assertIn("more than one incoming edge", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
