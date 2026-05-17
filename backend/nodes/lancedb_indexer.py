from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List

from backend.core.registry import register_node
import backend.infrastructure.rust_bridge as rust_bridge

# Default DB directory relative to the project root
_DEFAULT_DB_DIR = str(Path(__file__).resolve().parents[2] / "lancedb_store")


def _coerce_chunks(raw) -> List[str]:
    """Accept a list of strings, a single string, or a JSON-encoded list."""
    if isinstance(raw, list):
        return [str(c) for c in raw if c]
    if isinstance(raw, str):
        import json
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(c) for c in parsed if c]
        except (json.JSONDecodeError, ValueError):
            pass
        return [raw] if raw.strip() else []
    return []


def _coerce_sources(raw, n: int) -> List[str]:
    if isinstance(raw, list) and len(raw) >= n:
        return [str(s) for s in raw[:n]]
    if isinstance(raw, str) and raw.strip():
        return [raw] * n
    return ["unknown"] * n


def _coerce_pages(raw, n: int) -> List[int]:
    if isinstance(raw, list) and len(raw) >= n:
        try:
            return [int(p) for p in raw[:n]]
        except (TypeError, ValueError):
            pass
    return list(range(1, n + 1))


@register_node
class LanceDBStore:
    node_type = "lancedb_store"
    label = "LanceDB Store"
    description = (
        "Vector store node — indexes chunks and/or searches by query. "
        "Connect chunks to index, connect a query to search, or both."
    )
    category = "storage"
    version = "2.0.0"
    ui_config = {"icon": "database", "color": "#F59E0B", "category_order": 5}

    inputs = {
        "chunks":  {"type": "array",  "required": False},
        "sources": {"type": "array",  "required": False},
        "pages":   {"type": "array",  "required": False},
        "query":   {"type": "string", "required": False},
    }

    outputs = {
        "results":  {"type": "array"},
        "contexts": {"type": "string"},
    }

    args_schema = {
        "db_dir": {
            "type": "string",
            "default": _DEFAULT_DB_DIR,
            "description": "Path to the LanceDB database directory",
        },
        "table_name": {
            "type": "string",
            "default": "documents",
            "description": "LanceDB table name",
        },
        "embed_backend": {
            "type": "string",
            "default": "local",
            "description": "Embedding backend: 'zembed' or 'local'",
        },
        "batch_size": {
            "type": "number",
            "default": 32,
            "description": "Number of chunks to embed per batch",
        },
        "top_k": {
            "type": "number",
            "default": 5,
            "description": "Number of search results to return",
        },
        "rebuild": {
            "type": "boolean",
            "default": False,
            "description": "Drop and rebuild the table from scratch",
        },
    }

    @staticmethod
    async def run(args: dict, inputs: dict, context: Any) -> dict:
        db_dir        = str(args.get("db_dir", _DEFAULT_DB_DIR)).strip() or _DEFAULT_DB_DIR
        table_name    = str(args.get("table_name", "documents")).strip() or "documents"
        embed_backend = str(args.get("embed_backend", "local")).strip().lower()
        batch_size    = max(1, int(args.get("batch_size", 32)))
        top_k         = max(1, int(args.get("top_k", 5)))
        rebuild       = bool(args.get("rebuild", False))

        use_zembed = embed_backend != "local"
        os.makedirs(db_dir, exist_ok=True)

        raw_chunks = inputs.get("chunks", [])
        query      = str(inputs.get("query", "") or "").strip()
        chunks     = _coerce_chunks(raw_chunks)

        try:
            rust_bridge.load_embed_model(use_zembed=use_zembed)

            # ── Phase 1: Index (if chunks are provided) ──────────────
            if chunks:
                n       = len(chunks)
                sources = _coerce_sources(inputs.get("sources", []), n)
                pages   = _coerce_pages(inputs.get("pages", []), n)

                if use_zembed:
                    embeddings = rust_bridge.embed_texts_zembed(chunks, batch_size)
                else:
                    embeddings = rust_bridge.embed_texts_local(chunks, batch_size)

                if len(embeddings) != n:
                    raise ValueError(
                        f"Embedding count mismatch: expected {n}, got {len(embeddings)}"
                    )

                rust_bridge.lancedb_create_or_open(
                    db_dir=db_dir,
                    table_name=table_name,
                    texts=chunks,
                    sources=sources,
                    pages=pages,
                    embeddings=embeddings,
                    rebuild=rebuild,
                )

            # ── Phase 2: Search (if query is provided) ───────────────
            if not query:
                # Index-only mode — return confirmation
                msg = f"Indexed {len(chunks)} chunks into '{table_name}'" if chunks else "No chunks or query provided"
                return {"results": [], "contexts": msg}

            if use_zembed:
                q_vecs = rust_bridge.embed_texts_zembed([query], 1)
            else:
                q_vecs = rust_bridge.embed_texts_local([query], 1)

            if not q_vecs:
                raise ValueError("Failed to embed query")

            raw_results = rust_bridge.lancedb_search(
                db_dir=db_dir,
                table_name=table_name,
                query_vector=q_vecs[0],
                top_k=top_k,
            )

            # ── Format results ───────────────────────────────────────
            # Rust lancedb_search returns Vec<(text, source, page, distance)>
            results: List[dict] = []
            context_parts: List[str] = []

            for i, row in enumerate(raw_results or []):
                if isinstance(row, (tuple, list)) and len(row) >= 4:
                    # Rust returns (text, source, page, distance)
                    entry = {
                        "rank":     i + 1,
                        "text":     str(row[0]),
                        "source":   str(row[1]),
                        "page":     int(row[2]),
                        "distance": float(row[3]),
                    }
                elif isinstance(row, dict):
                    entry = {
                        "rank":     i + 1,
                        "text":     row.get("text", ""),
                        "source":   row.get("source", "unknown"),
                        "page":     row.get("page", 0),
                        "distance": row.get("_distance", None),
                    }
                else:
                    entry = {"rank": i + 1, "text": str(row), "source": "unknown", "page": 0, "distance": None}

                results.append(entry)
                context_parts.append(
                    f"[{entry['rank']}] (source: {entry['source']}, p.{entry['page']})\n"
                    f"{entry['text']}"
                )

            contexts = "\n\n---\n\n".join(context_parts) if context_parts else "(no results found)"

            return {"results": results, "contexts": contexts}

        except Exception as exc:
            return {"results": [], "contexts": f"Error: {exc}"}
