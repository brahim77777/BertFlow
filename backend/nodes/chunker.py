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
        "an advanced sliding-window algorithm (Rust backend)."
    )
    category = "processing"
    version = "1.0.0"
    ui_config = {"icon": "scissors", "color": "#8B5CF6", "category_order": 4}

    inputs = {
        "text": {"type": "string", "required": True},
    }

    outputs = {
        "chunks": {"type": "array"},
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
        text = inputs.get("text", "")

        if not text or not text.strip():
            return {
                "chunks": [],
                "text": "",
                "metadata": {"error": "No input text provided"},
            }

        max_chars = int(args.get("max_chars", 1500))
        window_size = int(args.get("window_size", 3))

        try:
            chunks = rust_bridge.semantic_window_chunker_advanced(
                text=text,
                max_chars=max_chars,
                window_size=window_size,
            )

            unified_text = "\n\n---\n\n".join(chunks)

            return {
                "chunks": chunks,
                "text": unified_text,
                "metadata": {
                    "total_chunks": len(chunks),
                    "max_chars": max_chars,
                    "window_size": window_size,
                    "total_characters": len(unified_text),
                    "error": None,
                },
            }
        except Exception as e:
            return {
                "chunks": [],
                "text": "",
                "metadata": {"error": f"Chunking failed: {str(e)}"},
            }
