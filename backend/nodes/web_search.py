from __future__ import annotations

import html
import re
from typing import Any

import httpx

from backend.core.errors import NodeExecutionError
from backend.core.registry import register_node

# DuckDuckGo's HTML endpoint is free and needs no API key.
_DDG_URL = "https://html.duckduckgo.com/html/"
_TITLE_RE = re.compile(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', re.DOTALL)
_SNIPPET_RE = re.compile(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)
_TAG_RE = re.compile(r"<.*?>", re.DOTALL)


def _clean(raw: str) -> str:
    """Strip HTML tags/entities and collapse whitespace."""
    return html.unescape(_TAG_RE.sub("", raw)).strip()


@register_node
class WebSearchTool:
    node_type = "tool_web_search"
    label = "Web Search"
    description = "Searches the web for free via DuckDuckGo (no API key required)"
    category = "tools"
    version = "2.0.0"
    ui_config = {"icon": "search", "color": "#3B82F6", "category_order": 2}

    inputs = {}

    outputs = {
        "tool": {"type": "object", "mode": "extension"},
    }

    args_schema = {
        "max_results": {
            "type": "integer",
            "default": 5,
            "description": "Maximum number of results to return",
        },
    }

    @staticmethod
    async def run(args: dict, inputs: dict, context: Any, emit=None) -> dict:
        try:
            max_results = int(args.get("max_results", 5))
        except (TypeError, ValueError):
            raise NodeExecutionError("max_results must be an integer")
        max_results = max(1, max_results)

        def execute(tool_args: dict) -> str:
            query = str(tool_args.get("query", "")).strip()
            if not query:
                return "Error: no search query provided"

            try:
                resp = httpx.post(
                    _DDG_URL,
                    data={"q": query},
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=15,
                )
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                return f"Error: web search request failed ({exc})"

            titles = _TITLE_RE.findall(resp.text)
            snippets = _SNIPPET_RE.findall(resp.text)

            results = []
            for title, snippet in zip(titles, snippets):
                results.append(f"{_clean(title)}: {_clean(snippet)}")
                if len(results) >= max_results:
                    break

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
