from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from .errors import GraphValidationError
from .models import Edge, RunRequest
from .registry import NodeRegistry
from .types import are_types_compatible, value_matches_type


@dataclass(frozen=True)
class GraphPlan:
    dependencies: dict[str, set[str]]
    dependents: dict[str, set[str]]
    incoming_edges: dict[str, list[Edge]]
    outgoing_edges: dict[str, list[Edge]]
    connected_components: list[list[str]]
    topo_order: list[str]


def validate_run_request(request: RunRequest, registry: NodeRegistry) -> GraphPlan:
    issues: list[str] = []

    if not request.nodes:
        issues.append("run request must contain at least one node")

    for node_id, node in request.nodes.items():
        if not registry.has(node.node_type):
            issues.append(f"node {node_id} uses unknown node_type {node.node_type!r}")
            continue

        schema = registry.get(node.node_type).schema
        for arg_name, arg_def in schema.args_schema.items():
            if arg_def.required and arg_name not in node.args:
                issues.append(f"node {node_id} is missing required arg {arg_name!r}")
            if arg_name in node.args and not value_matches_type(node.args[arg_name], arg_def.type):
                issues.append(
                    f"node {node_id} arg {arg_name!r} expected {arg_def.type}, got {type(node.args[arg_name]).__name__}"
                )

        for arg_name in node.args:
            if arg_name not in schema.args_schema:
                issues.append(f"node {node_id} includes unknown arg {arg_name!r}")

    incoming_edges: dict[str, list[Edge]] = defaultdict(list)
    outgoing_edges: dict[str, list[Edge]] = defaultdict(list)
    dependencies: dict[str, set[str]] = {node_id: set() for node_id in request.nodes}
    dependents: dict[str, set[str]] = {node_id: set() for node_id in request.nodes}
    target_ports_seen: set[tuple[str, str]] = set()
    edge_ids_seen: set[str] = set()

    for edge in request.edges:
        if edge.id in edge_ids_seen:
            issues.append(f"edge id {edge.id!r} is duplicated")
        edge_ids_seen.add(edge.id)

        if edge.from_node not in request.nodes:
            issues.append(f"edge {edge.id} references missing from node {edge.from_node!r}")
            continue
        if edge.to_node not in request.nodes:
            issues.append(f"edge {edge.id} references missing to node {edge.to_node!r}")
            continue

        if edge.from_node == edge.to_node:
            issues.append(f"edge {edge.id} creates a self dependency on node {edge.from_node!r}")

        source_node = request.nodes[edge.from_node]
        target_node = request.nodes[edge.to_node]
        if not registry.has(source_node.node_type) or not registry.has(target_node.node_type):
            continue

        source_schema = registry.get(source_node.node_type).schema
        target_schema = registry.get(target_node.node_type).schema
        source_port = source_schema.outputs.get(edge.from_port)
        target_port = target_schema.inputs.get(edge.to_port)

        if source_port is None:
            issues.append(
                f"edge {edge.id} references missing output port {edge.from_port!r} on {source_node.node_type}"
            )
            continue
        if target_port is None:
            issues.append(
                f"edge {edge.id} references missing input port {edge.to_port!r} on {target_node.node_type}"
            )
            continue

        if not are_types_compatible(source_port.type, target_port.type):
            issues.append(
                f"edge {edge.id} type mismatch: {source_node.node_type}.{edge.from_port} "
                f"({source_port.type}) -> {target_node.node_type}.{edge.to_port} ({target_port.type})"
            )

        target_key = (edge.to_node, edge.to_port)
        if target_key in target_ports_seen:
            issues.append(f"input port {edge.to_node}.{edge.to_port} has more than one incoming edge")
        target_ports_seen.add(target_key)

        incoming_edges[edge.to_node].append(edge)
        outgoing_edges[edge.from_node].append(edge)
        dependencies[edge.to_node].add(edge.from_node)
        dependents[edge.from_node].add(edge.to_node)

    topo_order = _topological_order(dependencies, dependents)
    if len(topo_order) != len(request.nodes):
        issues.append("graph contains at least one cycle")

    if issues:
        raise GraphValidationError(issues)

    return GraphPlan(
        dependencies=dependencies,
        dependents=dependents,
        incoming_edges={node_id: list(incoming_edges[node_id]) for node_id in request.nodes},
        outgoing_edges={node_id: list(outgoing_edges[node_id]) for node_id in request.nodes},
        connected_components=_connected_components(request.nodes.keys(), dependencies, dependents),
        topo_order=topo_order,
    )


def _topological_order(dependencies: dict[str, set[str]], dependents: dict[str, set[str]]) -> list[str]:
    remaining_deps = {node_id: set(upstream) for node_id, upstream in dependencies.items()}
    ready = deque(sorted(node_id for node_id, upstream in remaining_deps.items() if not upstream))
    order: list[str] = []

    while ready:
        node_id = ready.popleft()
        order.append(node_id)
        for child_id in sorted(dependents[node_id]):
            remaining_deps[child_id].discard(node_id)
            if not remaining_deps[child_id]:
                ready.append(child_id)

    return order


def _connected_components(
    node_ids: object,
    dependencies: dict[str, set[str]],
    dependents: dict[str, set[str]],
) -> list[list[str]]:
    unseen = set(node_ids)
    components: list[list[str]] = []

    while unseen:
        start = min(unseen)
        queue = deque([start])
        unseen.remove(start)
        component: list[str] = []

        while queue:
            node_id = queue.popleft()
            component.append(node_id)
            neighbors = dependencies[node_id] | dependents[node_id]
            for neighbor in sorted(neighbors):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)

        components.append(component)

    return components

