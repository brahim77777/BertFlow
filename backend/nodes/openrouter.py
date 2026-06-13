from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable
from typing import Any

import httpx

from backend.core.errors import NodeExecutionError
from backend.core.registry import register_node

# Human-readable summary per HTTP status, so users don't see raw httpx noise.
_HTTP_REASONS = {
    400: "Bad request",
    401: "Invalid or missing API key",
    402: "Insufficient credits",
    403: "Access forbidden",
    404: "Model not found",
    408: "Request timed out",
    429: "Rate limit exceeded",
    500: "OpenRouter server error",
    502: "OpenRouter is unavailable",
    503: "OpenRouter is unavailable",
}


def _format_openrouter_error(status: int, body: bytes) -> str:
    """Turn an OpenRouter error response into a short, user-friendly message."""
    detail = ""
    try:
        data = json.loads(body)
        err = data.get("error")
        if isinstance(err, dict):
            detail = err.get("message", "")
        detail = detail or data.get("message", "")
    except (json.JSONDecodeError, ValueError, AttributeError):
        detail = body.decode(errors="replace").strip()
    detail = " ".join(detail.split())[:300]
    reason = _HTTP_REASONS.get(status, f"HTTP {status}")
    return f"{reason} ({status}){f' — {detail}' if detail else ''}"


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
                    if resp.status_code >= 400:
                        error_body = await resp.aread()
                        raise NodeExecutionError(
                            _format_openrouter_error(resp.status_code, error_body)
                        )
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

                # Record this turn as a single assistant message carrying both the
                # streamed content and any tool calls — the OpenAI/OpenRouter API
                # expects them together in one turn, not as two separate assistant
                # messages.
                assistant_msg: dict[str, Any] = {"role": "assistant"}
                if content_buf:
                    assistant_msg["content"] = "".join(content_buf)
                if tool_calls_raw:
                    assistant_msg["tool_calls"] = tool_calls_raw

                if not tool_calls_raw:
                    # No tools requested — this is the final answer.
                    if content_buf:
                        messages.append(assistant_msg)
                    break

                messages.append(assistant_msg)

                tool_results = []
                for tc in tool_calls_raw:
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    args_str = fn.get("arguments", "{}")
                    tool_args = json.loads(args_str) if args_str else {}
                    tool = tool_map.get(name)
                    if tool and "execute" in tool:
                        # execute() may perform blocking I/O (e.g. web search); run it
                        # off the event loop so other nodes keep progressing in parallel.
                        result = await asyncio.to_thread(tool["execute"], tool_args)
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

                messages.extend(tool_results)

        return {"response": "".join(full)}
