from __future__ import annotations

import os
from typing import Any

from backend.core.registry import register_node


@register_node
class DocumentProcessor:
    node_type = "document_processor"
    label = "Upload Document"
    description = "Uploads a file and extracts its text content for downstream processing"
    category = "io"
    version = "1.0.0"
    ui_config = {"icon": "file-text", "color": "#8B5CF6", "category_order": 2}

    inputs = {}

    outputs = {
        "text": {"type": "string"},
        "filename": {"type": "string"},
        "metadata": {"type": "json"},
    }

    args_schema = {
        "file": {"type": "file", "default": ""},
    }

    @staticmethod
    async def run(args: dict, inputs: dict, context: Any) -> dict:
        file_path = args.get("file", "")

        if not file_path:
            return {
                "text": "",
                "filename": "",
                "metadata": {"filename": "", "size": 0},
            }

        candidates = [
            file_path,
            os.path.join("files", file_path),
            os.path.join(os.path.dirname(__file__), "..", "..", "files", file_path),
        ]

        resolved = None
        for c in candidates:
            if os.path.isfile(c):
                resolved = c
                break

        if resolved is None:
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(resolved, encoding="utf-8", errors="replace") as f:
            text = f.read()

        return {
            "text": text,
            "filename": os.path.basename(file_path),
            "metadata": {
                "filename": os.path.basename(file_path),
                "size": len(text),
            },
        }
