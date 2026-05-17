from __future__ import annotations

import os
from typing import Any

import httpx

from backend.core.registry import register_node


@register_node
class WebSearchTool:
    node_type = "tool_web_search"
    label = "Web Search"
    description = "Searches the internet using a search API"
    category = "tools"
    version = "1.0.0"
    ui_config = {"icon": "search", "color": "#3B82F6", "category_order": 2}

    inputs = {}

    outputs = {
        "tool": {"type": "object", "mode": "extension"},
    }

    args_schema = {
        "api_key": {"type": "string", "default": ""},
        "engine": {"type": "string", "default": "google"},
    }

    @staticmethod
    async def run(args: dict, inputs: dict, context: Any, emit=None) -> dict:
        api_key = args.get("api_key") or os.environ.get("SERPAPI_KEY", "")
        engine = args.get("engine", "google")

        async def execute(tool_args: dict) -> str:
            query = tool_args.get("query", "")
            if not api_key:
                return "Error: SERPAPI_KEY not configured"

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://serpapi.com/search",
                    params={"q": query, "api_key": api_key, "engine": engine},
                )
                resp.raise_for_status()
                data = resp.json()

            results = []
            for r in data.get("organic_results", [])[:5]:
                results.append(f"{r.get('title', '')}: {r.get('snippet', '')}")
            return "\n".join(results) if results else "No results found"

        return {
            "tool": {
                "type": "tool",
                "name": "web_search",
                "definition": {
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": "Searches the web and returns relevant results with titles and snippets.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The search query",
                                }
                            },
                            "required": ["query"],
                        },
                    },
                },
                "execute": execute,
            }
        }
