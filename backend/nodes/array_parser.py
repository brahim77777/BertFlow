from __future__ import annotations

import json
from typing import Any

from backend.core.registry import register_node


@register_node
class ArrayParser:
    node_type = "array_parser"
    label = "Array Parser"
    description = (
        "Converts an array input into a formatted string. "
        "Useful for passing structured results to text-based nodes."
    )
    category = "utility"
    version = "1.0.0"
    ui_config = {"icon": "parser", "color": "#6366F1", "category_order": 8}

    inputs = {
        "data": {"type": "array", "required": True},
    }

    outputs = {
        "text": {"type": "string"},
    }

    args_schema = {
        "format": {
            "type": "string",
            "default": "readable",
            "description": "Output format: 'readable', 'json', or 'csv'",
        },
        "separator": {
            "type": "string",
            "default": "\\n---\\n",
            "description": "Separator between items (for readable format)",
        },
    }

    @staticmethod
    async def run(args: dict, inputs: dict, context: Any) -> dict:
        raw = inputs.get("data", [])
        data = raw if isinstance(raw, list) else [raw]
        fmt = str(args.get("format", "readable")).strip().lower()
        sep = str(args.get("separator", "\n---\n")).replace("\\n", "\n")

        if not data:
            return {"text": "(empty)"}

        if fmt == "json":
            return {"text": json.dumps(data, indent=2, default=str, ensure_ascii=False)}

        if fmt == "csv":
            lines = []
            if data and isinstance(data[0], dict):
                keys = list(data[0].keys())
                lines.append(",".join(keys))
                for row in data:
                    lines.append(",".join(str(row.get(k, "")) for k in keys))
            else:
                lines = [str(item) for item in data]
            return {"text": "\n".join(lines)}

        # Default: readable
        parts = []
        for i, item in enumerate(data):
            if isinstance(item, dict):
                rank = item.get("rank", i + 1)
                text = item.get("text", "")
                source = item.get("source", "")
                page = item.get("page", "")
                distance = item.get("distance", None)

                header = f"[{rank}]"
                if source:
                    header += f" {source}"
                if page:
                    header += f", p.{page}"
                if distance is not None:
                    header += f"  (dist: {distance:.4f})"

                parts.append(f"{header}\n{text}")
            else:
                parts.append(str(item))

        return {"text": sep.join(parts)}
