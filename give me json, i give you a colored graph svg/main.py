import json
from graphviz import Digraph

# --- Load JSON ---
with open("graph.json", "r") as f:
    data = json.load(f)


def export_svg(data, output_name="graph"):
    dot = Digraph(format="svg")

    # Better layout for DAGs
    dot.attr(rankdir="LR")  # left → right flow
    dot.attr("node", shape="box")

    # --- Add nodes ---
    for node_id, node in data["nodes"].items():
        label = f"{node_id}\n{node['node_type']}"
        dot.node(node_id, label)

    # --- Add edges ---
    for edge in data["edges"]:
        dot.edge(edge["from"], edge["to"])

    # --- Render SVG ---
    dot.render(output_name, cleanup=True)
    print(f"SVG saved as {output_name}.svg")


if __name__ == "__main__":
    export_svg(data, "workflow_graph")
