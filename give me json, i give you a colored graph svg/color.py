import json
from collections import defaultdict, deque
from graphviz import Digraph

# --- Load JSON ---
with open("graph.json", "r") as f:
    data = json.load(f)


def topological_sort(node_ids, edges):
    """Kahn's algorithm — returns nodes in topological order."""
    in_degree = {n: 0 for n in node_ids}
    adjacency = defaultdict(list)

    for edge in edges:
        adjacency[edge["from"]].append(edge["to"])
        in_degree[edge["to"]] += 1

    queue = deque(n for n in node_ids if in_degree[n] == 0)
    order = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in adjacency[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(node_ids):
        raise ValueError("Graph has a cycle — topological sort is not possible.")

    return order, adjacency


def export_svg(data, output_name="graph"):
    dot = Digraph(format="svg")

    # Better layout for DAGs
    dot.attr(rankdir="LR")  # left → right flow
    dot.attr("node", shape="box")

    node_ids = list(data["nodes"].keys())
    edges = data["edges"]

    # --- Topological sort ---
    sorted_nodes, adjacency = topological_sort(node_ids, edges)
    print("Topological order:")
    for i, n in enumerate(sorted_nodes):
        print(f"  {i + 1}. {n} ({data['nodes'][n]['node_type']})")

    # --- Identify leaf nodes (no incoming edges) ---
    nodes_with_incoming = {edge["to"] for edge in edges}
    leaf_nodes = set(node_ids) - nodes_with_incoming

    # --- Add nodes in topological order ---
    for node_id in sorted_nodes:
        node = data["nodes"][node_id]
        label = f"{node_id}\n{node['node_type']}"
        if node_id in leaf_nodes:
            dot.node(
                node_id,
                label,
                style="filled",
                fillcolor="#4A90D9",   # pretty blue
                fontcolor="white",
                color="#2C6FAC",       # slightly darker border
            )
        else:
            dot.node(node_id, label)

    # --- Add edges ---
    for edge in edges:
        dot.edge(edge["from"], edge["to"])

    # --- Render SVG ---
    dot.render(output_name, cleanup=True)
    print(f"\nSVG saved as {output_name}.svg")


if __name__ == "__main__":
    export_svg(data, "workflow_graph")
