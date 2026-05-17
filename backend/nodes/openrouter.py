from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

import httpx

from backend.core.errors import NodeExecutionError
from backend.core.registry import register_node


@register_node
class OpenRouterLLM:
    node_type = "openrouter_llm"
    label = "OpenRouter LLM"
    description = "Streams LLM responses from OpenRouter API with optional tool support"
    category = "llm"
    version = "1.1.0"
    ui_config = {"icon": "bot", "color": "#7C3AED", "category_order": 0}

    inputs = {
        "prompt": {"type": "string", "required": True},
        "tools": {"type": "array", "mode": "extension", "required": False},
    }

    outputs = {
        "response": {"type": "string"},
    }

    args_schema = {
        "api_key": {"type": "string", "default": ""},
        "model": {"type": "string", "default": "openrouter/free"},
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
            raise NodeExecutionError("OPENROUTER_API_KEY not set. Configure it in the node settings or environment.")

        prompt = inputs.get("prompt", "")
        if not prompt:
            raise NodeExecutionError("Prompt input is empty. Connect a text source or enter a prompt.")

        model = args.get("model", "openai/gpt-4o-mini")
        max_tokens = args.get("max_tokens", 1024)
        temperature = args.get("temperature", 0.7)

        tools = context.get("extensions", {}).get("tools", [])
        tool_defs = [t.get("definition") for t in tools if isinstance(t, dict)]
        tool_map = {t.get("name"): t for t in tools if isinstance(t, dict)}

        messages = [{"role": "user", "content": prompt}]
        full: list[str] = []
        max_tool_rounds = 5

        async with httpx.AsyncClient(timeout=120) as client:
            for _ in range(max_tool_rounds):
                body = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True,
                }
                if tool_defs:
                    body["tools"] = tool_defs

                async with client.stream(
                    "POST",
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://bertflow.local",
                    },
                    json=body,
                ) as resp:
                    resp.raise_for_status()
                    content_buf: list[str] = []
                    tool_calls_raw: list[dict] = []

                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        payload = line[6:]
                        if payload.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(payload)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            tc = delta.get("tool_calls")
                            if tc:
                                for tc_item in tc:
                                    idx = tc_item.get("index", 0)
                                    if idx >= len(tool_calls_raw):
                                        tool_calls_raw.append(tc_item)
                                    else:
                                        existing = tool_calls_raw[idx]
                                        fn = existing.setdefault("function", {})
                                        fn["arguments"] = fn.get("arguments", "") + tc_item.get("function", {}).get(
                                            "arguments", ""
                                        )
                            else:
                                c = delta.get("content", "")
                                if c:
                                    content_buf.append(c)
                                    full.append(c)
                                    await emit("response", c)
                        except json.JSONDecodeError:
                            continue

                if content_buf:
                    messages.append({"role": "assistant", "content": "".join(content_buf)})

                if not tool_calls_raw:
                    break

                tool_results = []
                for tc in tool_calls_raw:
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    args_str = fn.get("arguments", "{}")
                    tool_args = json.loads(args_str) if args_str else {}
                    tool = tool_map.get(name)
                    if tool and "execute" in tool:
                        result = tool["execute"](tool_args)
                        if isinstance(result, str):
                            await emit("response", f"\n[tool:{name}] {result[:200]}")
                        tool_results.append(
                            {
                                "tool_call_id": tc.get("id", ""),
                                "role": "tool",
                                "name": name,
                                "content": str(result),
                            }
                        )
                    else:
                        tool_results.append(
                            {
                                "tool_call_id": tc.get("id", ""),
                                "role": "tool",
                                "name": name,
                                "content": f"Error: tool '{name}' not found",
                            }
                        )

                messages.append({"role": "assistant", "tool_calls": tool_calls_raw})
                messages.extend(tool_results)
                content_buf = []

        return {"response": "".join(full)}
