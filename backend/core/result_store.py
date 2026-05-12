from __future__ import annotations

import hashlib
import json
from typing import Any

HYBRID_THRESHOLD = 1024


def should_inline(value: Any) -> bool:
    if value is None or isinstance(value, (bool, int, float)):
        return True
    if isinstance(value, str):
        return len(value) < HYBRID_THRESHOLD
    try:
        return len(json.dumps(value, default=str)) < HYBRID_THRESHOLD
    except (TypeError, ValueError):
        return False


def parse_ref(ref: str) -> tuple[str, str, str] | None:
    parts = ref.split("/")
    if len(parts) == 4 and parts[0] == "store:" and parts[1] == "":
        return (parts[2], parts[3], "")
    if len(parts) == 5 and parts[0] == "store:" and parts[1] == "":
        return (parts[2], parts[3], parts[4])
    return None


class InMemoryResultStore:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def put(self, run_id: str, node_id: str, outputs: dict[str, Any]) -> None:
        self._data.setdefault(run_id, {})[node_id] = outputs

    def get(self, run_id: str, node_id: str) -> dict[str, Any]:
        return self._data.get(run_id, {}).get(node_id, {})

    def resolve(self, ref: str) -> Any:
        parsed = parse_ref(ref)
        if parsed is None:
            return None
        run_id, node_id, port = parsed
        node_outputs = self.get(run_id, node_id)
        if port:
            return node_outputs.get(port)
        return node_outputs

    def ref(self, run_id: str, node_id: str, port: str) -> str:
        return f"store://{run_id}/{node_id}/{port}"

    def build_outputs(self, run_id: str, node_id: str, result: dict[str, Any]) -> dict[str, Any]:
        self.put(run_id, node_id, result)
        outputs: dict[str, Any] = {}
        for port_name, value in result.items():
            if should_inline(value):
                outputs[port_name] = value
            else:
                outputs[port_name] = self.ref(run_id, node_id, port_name)
        return outputs


class InMemoryExecutionCache:
    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}

    def _key(self, node_type: str, args: dict, inputs: dict) -> str:
        raw = json.dumps([node_type, args, inputs], sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, node_type: str, args: dict, inputs: dict) -> dict | None:
        return self._cache.get(self._key(node_type, args, inputs))

    def put(self, node_type: str, args: dict, inputs: dict, outputs: dict) -> None:
        self._cache[self._key(node_type, args, inputs)] = outputs
