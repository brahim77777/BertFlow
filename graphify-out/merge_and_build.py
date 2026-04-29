import json
from pathlib import Path

from graphify.build import build_from_json
from graphify.cache import save_semantic_cache
from graphify.cluster import cluster, score_all
from graphify.analyze import god_nodes, surprising_connections
from graphify.report import generate
from graphify.export import to_html, to_json

root = Path(".")
out = Path("graphify-out")

ast = json.loads((out / ".graphify_ast.json").read_text())
cached = json.loads((out / ".graphify_cached.json").read_text()) if (out / ".graphify_cached.json").exists() else {
    "nodes": [],
    "edges": [],
    "hyperedges": [],
}
chunk = json.loads((out / ".graphify_chunk_01.json").read_text())

semantic_new = {
    "nodes": chunk.get("nodes", []),
    "edges": chunk.get("edges", []),
    "hyperedges": chunk.get("hyperedges", []),
    "input_tokens": chunk.get("input_tokens", 0),
    "output_tokens": chunk.get("output_tokens", 0),
}
(out / ".graphify_semantic_new.json").write_text(json.dumps(semantic_new, indent=2))

saved = save_semantic_cache(
    semantic_new.get("nodes", []),
    semantic_new.get("edges", []),
    semantic_new.get("hyperedges", []),
)

semantic = {
    "nodes": cached.get("nodes", []) + semantic_new.get("nodes", []),
    "edges": cached.get("edges", []) + semantic_new.get("edges", []),
    "hyperedges": cached.get("hyperedges", []) + semantic_new.get("hyperedges", []),
    "input_tokens": semantic_new.get("input_tokens", 0),
    "output_tokens": semantic_new.get("output_tokens", 0),
}
(out / ".graphify_semantic.json").write_text(json.dumps(semantic, indent=2))

merged = {
    "nodes": ast.get("nodes", []) + semantic.get("nodes", []),
    "edges": ast.get("edges", []) + semantic.get("edges", []),
    "hyperedges": semantic.get("hyperedges", []),
    "input_tokens": ast.get("input_tokens", 0) + semantic.get("input_tokens", 0),
    "output_tokens": ast.get("output_tokens", 0) + semantic.get("output_tokens", 0),
}
(out / ".graphify_extract.json").write_text(json.dumps(merged, indent=2))

graph = build_from_json(merged)
communities = cluster(graph)
cohesion = score_all(graph, communities)
gods = god_nodes(graph)
surprises = surprising_connections(graph, communities)
labels = {community_id: f"Community {community_id}" for community_id in communities}

detection = json.loads((out / ".graphify_detect.json").read_text())
tokens = {
    "input": merged.get("input_tokens", 0),
    "output": merged.get("output_tokens", 0),
}

report = generate(graph, communities, cohesion, labels, gods, surprises, detection, tokens, str(root))
(out / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
to_json(graph, communities, out / "graph.json")
to_html(graph, communities, out / "graph.html")

analysis = {
    "communities": {str(key): value for key, value in communities.items()},
    "cohesion": {str(key): value for key, value in cohesion.items()},
    "gods": gods,
    "surprises": surprises,
    "cached_files": saved,
}
(out / ".graphify_analysis.json").write_text(json.dumps(analysis, indent=2))

print(
    f"Graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges, "
    f"{len(communities)} communities, cached {saved} files"
)
