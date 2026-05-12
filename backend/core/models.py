from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.core.types import normalize_type


@dataclass
class ExecutionConfig:
    timeout_seconds: int = 120
    on_node_failure: str = "halt"
    max_retries: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> ExecutionConfig:
        return cls(
            timeout_seconds=d.get("timeout_seconds", 120),
            on_node_failure=d.get("on_node_failure", "halt"),
            max_retries=d.get("max_retries", 0),
        )


@dataclass
class NodeConfig:
    cache: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> NodeConfig:
        return cls(cache=d.get("cache", False))


@dataclass
class NodeInstance:
    node_type: str
    args: dict[str, Any] = field(default_factory=dict)
    config: NodeConfig = field(default_factory=NodeConfig)

    @classmethod
    def from_dict(cls, d: dict) -> NodeInstance:
        return cls(
            node_type=d["node_type"],
            args=d.get("args", {}),
            config=NodeConfig.from_dict(d.get("config", {})),
        )


@dataclass
class Edge:
    id: str
    source: str
    source_port: str
    target: str
    target_port: str
    source_type: str = ""
    target_type: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> Edge:
        return cls(
            id=d["id"],
            source=d["from"],
            source_port=d["from_port"],
            target=d["to"],
            target_port=d["to_port"],
            source_type=normalize_type(d.get("from_type", "any")),
            target_type=normalize_type(d.get("to_type", "any")),
        )


@dataclass
class RunRequest:
    run_id: str
    flow_id: str
    schema_version: int
    flow_revision: int
    execution_config: ExecutionConfig
    nodes: dict[str, NodeInstance]
    edges: list[Edge]
    user_id: str = ""
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> RunRequest:
        return cls(
            run_id=d.get("run_id", ""),
            flow_id=d.get("flow_id", ""),
            user_id=d.get("user_id", ""),
            schema_version=d.get("schema_version", 1),
            flow_revision=d.get("flow_revision", 1),
            created_at=d.get("created_at", ""),
            metadata=d.get("metadata", {}),
            execution_config=ExecutionConfig.from_dict(d.get("execution_config", {})),
            nodes={k: NodeInstance.from_dict(v) for k, v in d.get("nodes", {}).items()},
            edges=[Edge.from_dict(e) for e in d.get("edges", [])],
        )


@dataclass
class NodeState:
    node_id: str
    node_type: str
    status: str = "pending"
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    cached: bool = False
    started_at: float | None = None
    finished_at: float | None = None


@dataclass
class ExecutionState:
    run_id: str
    status: str = "pending"
    node_states: dict[str, NodeState] = field(default_factory=dict)
    error: str | None = None


@dataclass
class PortDefinition:
    name: str
    type: str
    required: bool = False
    default: Any = None


@dataclass
class ArgDefinition:
    name: str
    type: str
    default: Any = None


@dataclass
class NodeTypeSchema:
    node_type: str
    label: str
    category: str = "general"
    version: str = "1.0.0"
    description: str = ""
    ui_config: dict[str, Any] = field(default_factory=dict)
    inputs: dict[str, PortDefinition] = field(default_factory=dict)
    outputs: dict[str, PortDefinition] = field(default_factory=dict)
    args_schema: dict[str, ArgDefinition] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "node_type": self.node_type,
            "version": self.version,
            "label": self.label,
            "description": self.description,
            "category": self.category,
            "ui_config": dict(self.ui_config),
            "ports": {
                "inputs": {
                    k: {"type": v.type, "required": v.required, "default": v.default}
                    for k, v in self.inputs.items()
                },
                "outputs": {
                    k: {"type": v.type} for k, v in self.outputs.items()
                },
            },
            "args_schema": {
                k: {"type": v.type, "default": v.default}
                for k, v in self.args_schema.items()
            },
        }


@dataclass
class GraphPlan:
    nodes: dict[str, NodeInstance]
    edges: list[Edge]
    connected_components: list[list[str]]
    topological_order: list[str]
