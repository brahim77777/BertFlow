from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .errors import RunRequestError

JsonMap = dict[str, Any]


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def expect_map(value: Any, label: str) -> JsonMap:
    if not isinstance(value, dict):
        raise RunRequestError(f"{label} must be an object")
    return value


@dataclass(frozen=True)
class PortDefinition:
    name: str
    type: str = "any"
    label: str | None = None
    description: str = ""
    required: bool = True

    def to_json(self) -> JsonMap:
        return {
            "name": self.name,
            "label": self.label or self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
        }


@dataclass(frozen=True)
class ArgDefinition:
    name: str
    type: str = "any"
    required: bool = False
    default: Any = None
    description: str = ""

    def to_json(self) -> JsonMap:
        return {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "default": self.default,
            "description": self.description,
        }


@dataclass(frozen=True)
class NodeTypeSchema:
    node_type: str
    label: str
    category: str
    inputs: dict[str, PortDefinition] = field(default_factory=dict)
    outputs: dict[str, PortDefinition] = field(default_factory=dict)
    args_schema: dict[str, ArgDefinition] = field(default_factory=dict)

    def to_json(self) -> JsonMap:
        return {
            "node_type": self.node_type,
            "label": self.label,
            "category": self.category,
            "ports": {
                "inputs": [port.to_json() for port in self.inputs.values()],
                "outputs": [port.to_json() for port in self.outputs.values()],
            },
            "args_schema": [arg.to_json() for arg in self.args_schema.values()],
        }


@dataclass(frozen=True)
class NodeConfig:
    cache: bool = False

    @classmethod
    def from_dict(cls, data: Any) -> "NodeConfig":
        raw = expect_map(data or {}, "node config")
        return cls(cache=bool(raw.get("cache", False)))


@dataclass(frozen=True)
class NodeInstance:
    id: str
    node_type: str
    args: JsonMap = field(default_factory=dict)
    config: NodeConfig = field(default_factory=NodeConfig)

    @classmethod
    def from_dict(cls, node_id: str, data: Any) -> "NodeInstance":
        raw = expect_map(data, f"node {node_id}")
        node_type = raw.get("node_type")
        if not isinstance(node_type, str) or not node_type:
            raise RunRequestError(f"node {node_id} must include node_type")
        return cls(
            id=node_id,
            node_type=node_type,
            args=dict(expect_map(raw.get("args", {}), f"node {node_id}.args")),
            config=NodeConfig.from_dict(raw.get("config", {})),
        )


@dataclass(frozen=True)
class Edge:
    id: str
    from_node: str
    from_port: str
    to_node: str
    to_port: str

    @classmethod
    def from_dict(cls, data: Any, index: int) -> "Edge":
        raw = expect_map(data, f"edge {index}")
        try:
            return cls(
                id=str(raw["id"]),
                from_node=str(raw["from"]),
                from_port=str(raw["from_port"]),
                to_node=str(raw["to"]),
                to_port=str(raw["to_port"]),
            )
        except KeyError as exc:
            raise RunRequestError(f"edge {index} is missing {exc.args[0]}") from exc


@dataclass(frozen=True)
class ExecutionConfig:
    timeout_seconds: float = 120
    on_node_failure: str = "halt"
    max_retries: int = 0

    @classmethod
    def from_dict(cls, data: Any) -> "ExecutionConfig":
        raw = expect_map(data or {}, "execution_config")
        on_node_failure = str(raw.get("on_node_failure", "halt"))
        if on_node_failure not in {"halt", "skip", "retry"}:
            raise RunRequestError("execution_config.on_node_failure must be halt, skip, or retry")
        return cls(
            timeout_seconds=float(raw.get("timeout_seconds", 120)),
            on_node_failure=on_node_failure,
            max_retries=max(0, int(raw.get("max_retries", 0))),
        )


@dataclass(frozen=True)
class RunRequest:
    run_id: str
    flow_id: str
    schema_version: int
    flow_revision: int
    created_at: str
    execution_config: ExecutionConfig
    nodes: dict[str, NodeInstance]
    edges: list[Edge]

    @classmethod
    def from_dict(cls, data: Any) -> "RunRequest":
        raw = expect_map(data, "run request")
        nodes_raw = expect_map(raw.get("nodes", {}), "nodes")
        edges_raw = raw.get("edges", [])
        if not isinstance(edges_raw, list):
            raise RunRequestError("edges must be an array")

        nodes = {
            str(node_id): NodeInstance.from_dict(str(node_id), node_data)
            for node_id, node_data in nodes_raw.items()
        }
        edges = [Edge.from_dict(edge, index) for index, edge in enumerate(edges_raw)]

        return cls(
            run_id=str(raw.get("run_id") or f"run-{now_iso()}"),
            flow_id=str(raw.get("flow_id") or "flow"),
            schema_version=int(raw.get("schema_version", 1)),
            flow_revision=int(raw.get("flow_revision", 1)),
            created_at=str(raw.get("created_at") or now_iso()),
            execution_config=ExecutionConfig.from_dict(raw.get("execution_config", {})),
            nodes=nodes,
            edges=edges,
        )


@dataclass
class NodeState:
    status: str = "pending"
    outputs: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    cached: bool = False
    started_at: str | None = None
    completed_at: str | None = None
    attempts: int = 0

    def to_json(self) -> JsonMap:
        return {
            "status": self.status,
            "outputs": self.outputs,
            "error": self.error,
            "cached": self.cached,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "attempts": self.attempts,
        }


@dataclass
class ExecutionState:
    run_id: str
    flow_id: str
    status: str = "pending"
    started_at: str | None = None
    completed_at: str | None = None
    node_states: dict[str, NodeState] = field(default_factory=dict)

    @classmethod
    def for_request(cls, request: RunRequest) -> "ExecutionState":
        return cls(
            run_id=request.run_id,
            flow_id=request.flow_id,
            node_states={node_id: NodeState() for node_id in request.nodes},
        )

    def to_json(self) -> JsonMap:
        return {
            "run_id": self.run_id,
            "flow_id": self.flow_id,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "node_states": {
                node_id: node_state.to_json()
                for node_id, node_state in self.node_states.items()
            },
        }

