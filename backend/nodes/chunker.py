from __future__ import annotations

from typing import Any

from backend.core.registry import register_node
import backend.infrastructure.rust_bridge as rust_bridge


@register_node
class SemanticChunker:
    node_type = "semantic_chunker"
    label = "Semantic Chunker"
    description = (
        "Splits text into semantically coherent chunks using "
        "an advanced sliding-window algorithm (Rust backend). "
        "When connected to PDFium Processor, preserves page and source metadata per chunk."
    )
    category = "processing"
    version = "1.1.0"
    ui_config = {"icon": "scissors", "color": "#8B5CF6", "category_order": 4}

    inputs = {
        "text": {"type": "string", "required": False},
        "pages": {"type": "array", "required": False},
    }

    outputs = {
        "chunks": {"type": "array"},
        "sources": {"type": "array"},
        "pages": {"type": "array"},
        "text": {"type": "string"},
        "metadata": {"type": "json"},
    }

    args_schema = {
        "max_chars": {
            "type": "number",
            "default": 1500,
            "description": "Maximum number of characters per chunk",
        },
        "window_size": {
            "type": "number",
            "default": 3,
            "description": "Number of sentences in the sliding window",
        },
    }

    @staticmethod
    async def run(args: dict, inputs: dict, context: Any) -> dict:
        max_chars = int(args.get("max_chars", 1500))
        window_size = int(args.get("window_size", 3))

        raw_pages = inputs.get("pages")

        # ── Per-page mode: each item can be a string or {"text": ..., "source": ..., "page": ...} ──
        if raw_pages and isinstance(raw_pages, list) and len(raw_pages) > 0:
            all_chunks = []
            all_sources = []
            all_pages = []

            for i, item in enumerate(raw_pages):
                if isinstance(item, dict):
                    page_text = item.get("text", "")
                    source = item.get("source", "unknown")
                    page_num = item.get("page", i + 1)
                else:
                    page_text = str(item)
                    source = "unknown"
                    page_num = i + 1

                if not page_text or not str(page_text).strip():
                    continue

                page_chunks = rust_bridge.semantic_window_chunker_advanced(
                    text=str(page_text),
                    max_chars=max_chars,
                    window_size=window_size,
                )
                for chunk in page_chunks:
                    if chunk.strip():
                        all_chunks.append(chunk)
                        all_sources.append(source)
                        all_pages.append(page_num)

            unified_text = "\n\n---\n\n".join(all_chunks)

            return {
                "chunks": all_chunks,
                "sources": all_sources,
                "pages": all_pages,
                "text": unified_text,
                "metadata": {
                    "total_chunks": len(all_chunks),
                    "max_chars": max_chars,
                    "window_size": window_size,
                    "total_characters": len(unified_text),
                    "mode": "per_page",
                    "input_pages": len(raw_pages),
                },
            }

        # ── Flat text fallback: no page metadata available ──
        text = inputs.get("text", "")
        if isinstance(text, list):
            text = text[0] if text else ""

        if not text or not str(text).strip():
            return {
                "chunks": [],
                "sources": [],
                "pages": [],
                "text": "",
                "metadata": {"total_chunks": 0, "mode": "flat_text"},
            }

        chunks = rust_bridge.semantic_window_chunker_advanced(
            text=str(text),
            max_chars=max_chars,
            window_size=window_size,
        )

        unified_text = "\n\n---\n\n".join(chunks)

        return {
            "chunks": chunks,
            "sources": ["unknown"] * len(chunks),
            "pages": list(range(1, len(chunks) + 1)),
            "text": unified_text,
            "metadata": {
                "total_chunks": len(chunks),
                "max_chars": max_chars,
                "window_size": window_size,
                "total_characters": len(unified_text),
                "mode": "flat_text",
            },
        }
