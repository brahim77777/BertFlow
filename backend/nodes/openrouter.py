from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

import httpx

from backend.core.registry import register_node


@register_node
class OpenRouterLLM:
    node_type = "openrouter_llm"
    label = "OpenRouter LLM"
    description = "Streams LLM responses from OpenRouter API"
    category = "llm"
    version = "1.0.0"
    ui_config = {"icon": "bot", "color": "#7C3AED", "category_order": 0}

    inputs = {
        "prompt": {"type": "string", "required": True},
    }

    outputs = {
        "response": {"type": "string"},
    }

    args_schema = {
        "api_key": {"type": "string", "default": ""},
        "model": {"type": "string", "default": "openai/gpt-4o-mini"},
        "max_tokens": {"type": "integer", "default": 1024},
        "temperature": {"type": "number", "default": 0.7},
    }

    @staticmethod
    async def run(
        args: dict,
        inputs: dict,
        context: Any,
        emit: Callable[[str, str], Any],
    ) -> dict:
        api_key = args.get("api_key") or os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            return {"response": "Error: OPENROUTER_API_KEY not set"}

        prompt = inputs.get("prompt", "")
        if not prompt:
            return {"response": "Error: prompt is empty"}

        model = args.get("model", "openai/gpt-4o-mini")
        max_tokens = args.get("max_tokens", 1024)
        temperature = args.get("temperature", 0.7)
        full: list[str] = []

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://bertflow.local",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True,
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                        content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if content:
                            full.append(content)
                            await emit("response", content)
                    except json.JSONDecodeError:
                        continue

        return {"response": "".join(full)}
