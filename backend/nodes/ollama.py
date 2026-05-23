from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any
from backend.core.errors import NodeExecutionError

import httpx

from backend.core.registry import register_node


@register_node
class OllamaLLM:
    node_type = "ollama_llm"
    label = "Ollama LLM"
    description = "Streams LLM responses from a local or remote Ollama instance"
    category = "llm"
    version = "1.0.0"
    ui_config = {"icon": "bot", "color": "#ED64A6", "category_order": 1}

    inputs = {
        "prompt": {"type": "string", "required": True},
    }

    outputs = {
        "response": {"type": "string"},
    }

    args_schema = {
        "base_url": {"type": "string", "default": "http://localhost:11434/api"},
        "model": {"type": "string", "default": "llama3"},
        "temperature": {"type": "number", "default": 0.2},
        "timeout": {"type": "integer", "default": 300},
    }

    @staticmethod
    async def run(
        args: dict,
        inputs: dict,
        context: Any,
        emit: Callable[[str, str], Any],
    ) -> dict:
        base_url = args.get("base_url") or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/api")
        base_url = base_url.rstrip("/")

        prompt = inputs.get("prompt", "")
        if not prompt:
            raise NodeExecutionError("Prompt input is empty. Connect a text source or enter a prompt.")

        model = args.get("model", "llama3")
        temperature = args.get("temperature", 0.2)
        if temperature > 1.00:
            raise NodeExecutionError("Enter a valid temperature value between 0.00 and 1.00.")

        timeout = args.get("timeout", 300)
        full: list[str] = []

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "options": {"temperature": temperature},
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{base_url}/chat",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp:
                resp.raise_for_status()

                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)

                        if "error" in chunk:
                            raise NodeExecutionError(f"Ollama Error: {chunk['error']}")

                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            full.append(content)
                            await emit("response", content)

                        if chunk.get("done", False):
                            break

                    except json.JSONDecodeError:
                        continue

        return {"response": "".join(full)}
