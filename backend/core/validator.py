from __future__ import annotations

from collections import deque

from backend.core.errors import GraphValidationError
from backend.core.models import GraphPlan, RunRequest
from backend.core.registry import NodeRegistry
from backend.core.types import are_types_compatible


def validate_run_request(request: RunRequest, registry: NodeRegistry) -> GraphPlan:
    nodes = request.nodes
    edges = request.edges

    if not nodes:
        raise GraphValidationError("Run request must contain at least one node")

    for nid, node in nodes.items():
        if node.node_type not in registry:
            known = sorted(registry._nodes.keys()) if hasattr(registry, '_nodes') else []
            raise GraphValidationError(
                f"Unknown node type '{node.node_type}' for node '{nid}'. "
                f"Known types: {known}"
            )
        reg = registry.get(node.node_type)
        if reg is None:
            continue
        for arg_name in reg.args_schema:
            if arg_name not in node.args:
                node.args[arg_name] = reg.args_schema[arg_name].default

    seen_edge_ids: set[str] = set()
    for edge in edges:
        if edge.id in seen_edge_ids:
            raise GraphValidationError(f"Duplicate edge id '{edge.id}'")
        seen_edge_ids.add(edge.id)

        if edge.source not in nodes:
            raise GraphValidationError(f"Edge '{edge.id}' references unknown source node '{edge.source}'")
        if edge.target not in nodes:
            raise GraphValidationError(f"Edge '{edge.id}' references unknown target node '{edge.target}'")

        src_reg = registry.get(nodes[edge.source].node_type)
        tgt_reg = registry.get(nodes[edge.target].node_type)
        if src_reg and edge.source_port not in src_reg.outputs:
            valid = list(src_reg.outputs.keys())
            raise GraphValidationError(
                f"Edge '{edge.id}': source port '{edge.source_port}' not found on '{edge.source}'. "
                f"Valid ports: {valid}"
            )
        if tgt_reg and edge.target_port not in tgt_reg.inputs:
            valid = list(tgt_reg.inputs.keys())
            raise GraphValidationError(
                f"Edge '{edge.id}': target port '{edge.target_port}' not found on '{edge.target}'. "
                f"Valid ports: {valid}"
            )

        if not are_types_compatible(edge.source_type, edge.target_type):
            raise GraphValidationError(
                f"Edge '{edge.id}': type mismatch '{edge.source_type}' → '{edge.target_type}'"
            )

    target_inputs: dict[tuple[str, str], str] = {}
    for edge in edges:
        if edge.mode == "extension":
            continue
        key = (edge.target, edge.target_port)
        if key in target_inputs:
            raise GraphValidationError(
                f"Node '{edge.target}' port '{edge.target_port}' has more than one incoming edge "
                f"('{target_inputs[key]}' and '{edge.id}')"
            )
        target_inputs[key] = edge.id

    adj: dict[str, list[str]] = {nid: [] for nid in nodes}
    in_deg: dict[str, int] = {nid: 0 for nid in nodes}
    for edge in edges:
        adj.setdefault(edge.source, []).append(edge.target)
        in_deg[edge.target] = in_deg.get(edge.target, 0) + 1

    queue: deque[str] = deque(nid for nid, d in in_deg.items() if d == 0)
    topo: list[str] = []
    while queue:
        nid = queue.popleft()
        topo.append(nid)
        for nb in adj.get(nid, []):
            in_deg[nb] -= 1
            if in_deg[nb] == 0:
                queue.append(nb)

    if len(topo) != len(nodes):
        raise GraphValidationError(
            f"Graph contains a cycle. {len(nodes) - len(topo)} node(s) unreachable."
        )

    unvisited = set(nodes.keys())
    components: list[list[str]] = []
    while unvisited:
        start = next(iter(unvisited))
        comp: list[str] = []
        q: deque[str] = deque([start])
        while q:
            nid = q.popleft()
            if nid not in unvisited:
                continue
            unvisited.discard(nid)
            comp.append(nid)
            for edge in edges:
                if edge.source == nid and edge.target in unvisited:
                    q.append(edge.target)
                if edge.target == nid and edge.source in unvisited:
                    q.append(edge.source)
        components.append(comp)

    return GraphPlan(
        nodes=nodes,
        edges=edges,
        connected_components=components,
        topological_order=topo,
    )
