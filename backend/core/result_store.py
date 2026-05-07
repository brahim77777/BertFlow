from __future__ import annotations

import hashlib
import json
from typing import Any


class InMemoryResultStore:
    """Run-scoped result store using result_store[run_id][node_id][port]."""

    def __init__(self) -> None:
        self._values: dict[str, dict[str, dict[str, Any]]] = {}

    def set_node_outputs(self, run_id: str, node_id: str, outputs: dict[str, Any]) -> None:
        self._values.setdefault(run_id, {})[node_id] = dict(outputs)

    def get(self, run_id: str, node_id: str, port: str) -> Any:
        return self._values[run_id][node_id][port]

    def ref(self, run_id: str, node_id: str, port: str) -> str:
        return f"store://{run_id}/{node_id}/{port}"

    def output_refs(self, run_id: str, node_id: str, outputs: dict[str, Any]) -> dict[str, str]:
        return {port: self.ref(run_id, node_id, port) for port in outputs}

    def value_hash(self, value: Any) -> str:
        encoded = json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class InMemoryExecutionCache:
    """Small cache boundary that can be swapped with Redis later."""

    def __init__(self) -> None:
        self._values: dict[str, dict[str, Any]] = {}

    def make_key(self, node_type: str, args: dict[str, Any], inputs: dict[str, Any]) -> str:
        encoded = json.dumps(
            {"node_type": node_type, "args": args, "inputs": inputs},
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        cached = self._values.get(key)
        return dict(cached) if cached is not None else None

    def set(self, key: str, outputs: dict[str, Any]) -> None:
        self._values[key] = dict(outputs)

