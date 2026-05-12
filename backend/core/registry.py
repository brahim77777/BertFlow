from __future__ import annotations

import importlib
import logging
import os
import sys
from typing import Any

from backend.core.models import (
    ArgDefinition,
    NodeTypeSchema,
    PortDefinition,
)

log = logging.getLogger("bertflow")


class RegisteredNode:
    def __init__(self, cls: type) -> None:
        self.cls = cls
        self.node_type: str = cls.node_type
        self.label: str = getattr(cls, "label", cls.node_type)
        self.description: str = getattr(cls, "description", "")
        self.category: str = getattr(cls, "category", "general")
        self.version: str = getattr(cls, "version", "1.0.0")
        self.ui_config: dict = getattr(cls, "ui_config", {})
        self.inputs: dict[str, PortDefinition] = self._build_ports(getattr(cls, "inputs", {}))
        self.outputs: dict[str, PortDefinition] = self._build_ports(getattr(cls, "outputs", {}))
        self.args_schema: dict[str, ArgDefinition] = self._build_args(getattr(cls, "args_schema", {}))

    @staticmethod
    def _build_ports(raw: dict[str, dict]) -> dict[str, PortDefinition]:
        return {
            k: PortDefinition(
                name=k, type=v.get("type", "any"),
                required=v.get("required", False), default=v.get("default"),
            )
            for k, v in raw.items()
        }

    @staticmethod
    def _build_args(raw: dict[str, dict]) -> dict[str, ArgDefinition]:
        return {
            k: ArgDefinition(name=k, type=v.get("type", "any"), default=v.get("default"))
            for k, v in raw.items()
        }

    def to_schema(self) -> NodeTypeSchema:
        return NodeTypeSchema(
            node_type=self.node_type,
            label=self.label,
            description=self.description,
            category=self.category,
            version=self.version,
            ui_config=dict(self.ui_config),
            inputs=dict(self.inputs),
            outputs=dict(self.outputs),
            args_schema=dict(self.args_schema),
        )

    async def run(self, args: dict, inputs: dict, context: Any) -> dict:
        return await self.cls.run(args, inputs, context)


_registry: dict[str, RegisteredNode] = {}


def register_node(cls: type) -> type:
    _registry[cls.node_type] = RegisteredNode(cls)
    return cls


def get_registry() -> dict[str, RegisteredNode]:
    return dict(_registry)


class NodeRegistry:
    def __init__(self) -> None:
        self._nodes: dict[str, RegisteredNode] = {}

    @classmethod
    def discover(cls, nodes_path: str | None = None) -> NodeRegistry:
        registry = cls()
        if nodes_path is None:
            nodes_path = os.path.join(os.path.dirname(__file__), "..", "nodes")
        nodes_path = os.path.abspath(nodes_path)

        pkg_dir = os.path.dirname(nodes_path)
        if pkg_dir not in sys.path:
            sys.path.insert(0, pkg_dir)

        for fname in sorted(os.listdir(nodes_path)):
            if fname.startswith("_") or not fname.endswith(".py"):
                continue
            mod_name = f"backend.nodes.{fname[:-3]}"
            try:
                importlib.import_module(mod_name)
            except Exception as exc:
                log.warning("Failed to import node module %s: %s", mod_name, exc)

        registry._nodes = dict(_registry)
        return registry

    def get(self, node_type: str) -> RegisteredNode | None:
        return self._nodes.get(node_type)

    def get_types(self) -> list[dict]:
        return [node.to_schema().to_dict() for node in self._nodes.values()]

    def __contains__(self, node_type: str) -> bool:
        return node_type in self._nodes

    def __len__(self) -> int:
        return len(self._nodes)
