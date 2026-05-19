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
        # Treat the whole string as a single chunk
        return [raw] if raw.strip() else []
    return []


def _coerce_sources(raw, n: int) -> List[str]:
    """Accept a list of strings or fall back to a repeated default."""
    if isinstance(raw, list) and len(raw) >= n:
        return [str(s) for s in raw[:n]]
    if isinstance(raw, str) and raw.strip():
        return [raw] * n
    return ["unknown"] * n


def _coerce_pages(raw, n: int) -> List[int]:
    """Accept a list of ints or fall back to sequential page numbers."""
    if isinstance(raw, list) and len(raw) >= n:
        try:
            return [int(p) for p in raw[:n]]
        except (TypeError, ValueError):
            pass
    return list(range(1, n + 1))


@register_node
class LanceDBIndexer:
    node_type = "lancedb_indexer"
    label = "LanceDB Indexer"
    description = (
        "Embeds text chunks and writes them to a LanceDB vector store. "
        "Supports both the local Rust embedding model and the ZEmbed API."
    )
    category = "storage"
    version = "1.0.0"
    ui_config = {"icon": "database", "color": "#F59E0B", "category_order": 5}

    inputs = {
        "chunks":   {"type": "array",  "required": True},
        "sources":  {"type": "array",  "required": False},
        "pages":    {"type": "array",  "required": False},
    }

    outputs = {
        "status":   {"type": "string"},
        "metadata": {"type": "json"},
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
            "default": "zembed",
            "description": "Embedding backend: 'zembed' (ZeroEntropy API) or 'local' (fastembed, requires recompiled rag_rust)",
        },
        "batch_size": {
            "type": "number",
            "default": 32,
            "description": "Number of chunks to embed per batch",
        },
        "rebuild": {
            "type": "boolean",
            "default": False,
            "description": "Drop and rebuild the table from scratch",
        },
    }

    @staticmethod
    async def run(args: dict, inputs: dict, context: Any) -> dict:
        raw_chunks  = inputs.get("chunks",  [])
        raw_sources = inputs.get("sources", [])
        raw_pages   = inputs.get("pages",   [])

        chunks = _coerce_chunks(raw_chunks)
        if not chunks:
            return {
                "status":   "error",
                "metadata": {"error": "No chunks provided"},
            }

        n = len(chunks)
        sources = _coerce_sources(raw_sources, n)
        pages   = _coerce_pages(raw_pages, n)

        db_dir       = str(args.get("db_dir", _DEFAULT_DB_DIR)).strip() or _DEFAULT_DB_DIR
        table_name   = str(args.get("table_name", "documents")).strip() or "documents"
        embed_backend = str(args.get("embed_backend", "zembed")).strip().lower()
        batch_size   = max(1, int(args.get("batch_size", 32)))
        rebuild      = bool(args.get("rebuild", False))

        os.makedirs(db_dir, exist_ok=True)

        try:
            # ── 1. Load embedding model ──────────────────────────────
            use_zembed = embed_backend != "local"

            # Guard: local model requires a recompiled rag_rust.so that
            # includes BGESmallENV15 in its match arm. The current binary
            # (copied from Agentic-RAG-Rust-Core-PFE-26) does not have it.
            # Until rag_rust_src/ is recompiled, use embed_backend='zembed'.
            if not use_zembed:
                probe = rust_bridge.load_embed_model(use_zembed=False)
                # load_embed_model returns None on success; an exception means
                # the model name is unsupported in the current binary.
            else:
                rust_bridge.load_embed_model(use_zembed=True)

            # ── 2. Embed all chunks in batches ───────────────────────
            embeddings: List[List[float]] = []
            if use_zembed:
                embeddings = rust_bridge.embed_texts_zembed(chunks, batch_size)
            else:
                embeddings = rust_bridge.embed_texts_local(chunks, batch_size)

            if len(embeddings) != n:
                raise ValueError(
                    f"Embedding count mismatch: expected {n}, got {len(embeddings)}"
                )

            # ── 3. Write to LanceDB ──────────────────────────────────
            rust_bridge.lancedb_create_or_open(
                db_dir=db_dir,
                table_name=table_name,
                texts=chunks,
                sources=sources,
                pages=pages,
                embeddings=embeddings,
                rebuild=rebuild,
            )

            return {
                "status": "ok",
                "metadata": {
                    "chunks_indexed": n,
                    "table_name":     table_name,
                    "db_dir":         db_dir,
                    "embed_backend":  embed_backend,
                    "rebuild":        rebuild,
                    "error":          None,
                },
            }

        except Exception as exc:
            return {
                "status":   "error",
                "metadata": {"error": f"LanceDB indexing failed: {exc}"},
            }
