from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .models import JsonMap, NodeTypeSchema


@dataclass(frozen=True)
class NodeContext:
    run_id: str
    node_id: str
    node_type: str
    args: JsonMap
    inputs: JsonMap


NodeResult = dict[str, Any]
NodeCallable = Callable[[NodeContext], NodeResult | Awaitable[NodeResult]]


@dataclass(frozen=True)
class RegisteredNode:
    schema: NodeTypeSchema
    callable: NodeCallable


class NodeRegistry:
    def __init__(self) -> None:
        self._nodes: dict[str, RegisteredNode] = {}

    def register(self, schema: NodeTypeSchema, func: NodeCallable) -> None:
        if schema.node_type in self._nodes:
            raise ValueError(f"node_type already registered: {schema.node_type}")
        self._nodes[schema.node_type] = RegisteredNode(schema=schema, callable=func)

    def decorator(self, schema: NodeTypeSchema) -> Callable[[NodeCallable], NodeCallable]:
        def bind(func: NodeCallable) -> NodeCallable:
            self.register(schema, func)
            return func

        return bind

    def get(self, node_type: str) -> RegisteredNode:
        return self._nodes[node_type]

    def has(self, node_type: str) -> bool:
        return node_type in self._nodes

    def schemas(self) -> list[NodeTypeSchema]:
        return [registered.schema for registered in self._nodes.values()]

    def to_json(self) -> list[JsonMap]:
        return [schema.to_json() for schema in self.schemas()]

