from __future__ import annotations

import asyncio
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
        "pages": {"type": "array", "required": False},
    }

    outputs = {
        "chunks": {"type": "array"},
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
        if not raw_pages or not isinstance(raw_pages, list) or len(raw_pages) == 0:
            return {"chunks": []}

        def _chunk_pages() -> list[dict]:
            chunks: list[dict] = []
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

                split_chunks = rust_bridge.semantic_window_chunker_advanced(
                    text=str(page_text),
                    max_chars=max_chars,
                    window_size=window_size,
                )
                for chunk in split_chunks:
                    if chunk.strip():
                        chunks.append({
                            "text": chunk,
                            "source": source,
                            "page": page_num,
                        })
            return chunks

        # The Rust chunker is a blocking, CPU-bound call. Run it in a worker
        # thread so it doesn't freeze the event loop — other nodes (LLM
        # streaming, status updates) keep progressing while it runs.
        all_chunks = await asyncio.to_thread(_chunk_pages)
        return {"chunks": all_chunks}
