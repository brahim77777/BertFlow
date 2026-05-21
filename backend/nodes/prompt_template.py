from __future__ import annotations

from typing import Any

from backend.core.registry import register_node

_DEFAULT_TEMPLATE = """You are a helpful assistant. Answer the user's question using ONLY the provided context.
If the answer is not in the context, say "I don't have enough information to answer that."

{history_block}## Context
{context}

## Question
{query}

## Answer"""


def _format_history(raw_history: str) -> str:
    """Format conversation history into a readable block."""
    text = str(raw_history or "").strip()
    if not text:
        return ""
    return f"## Conversation History\n{text}\n\n"


@register_node
class PromptTemplate:
    node_type = "prompt_template"
    label = "Prompt Template"
    description = (
        "Assembles a structured prompt from context, query, and optional "
        "conversation history. Output connects to any LLM node."
    )
    category = "prompt"
    version = "1.0.0"
    ui_config = {"icon": "template", "color": "#8B5CF6", "category_order": 7}

    inputs = {
        "context": {"type": "string", "required": True},
        "query":   {"type": "string", "required": True},
        "history": {"type": "string", "required": False},
    }

    outputs = {
        "prompt": {"type": "string"},
    }

    args_schema = {
        "template": {
            "type": "string",
            "default": _DEFAULT_TEMPLATE,
            "description": (
                "Prompt template. Use {context}, {query}, and {history_block} "
                "as placeholders."
            ),
        },
        "system_instruction": {
            "type": "string",
            "default": "",
            "description": (
                "Optional system instruction prepended before the template."
            ),
        },
    }

    @staticmethod
    async def run(args: dict, inputs: dict, context: Any) -> dict:
        ctx_text = str(inputs.get("context", "")).strip()
        query    = str(inputs.get("query", "")).strip()
        history  = inputs.get("history", "")

        template = str(args.get("template", _DEFAULT_TEMPLATE))
        system   = str(args.get("system_instruction", "")).strip()

        history_block = _format_history(history)

        # Render the template
        try:
            rendered = template.format(
                context=ctx_text or "(no context provided)",
                query=query or "(no query provided)",
                history_block=history_block,
            )
        except KeyError as exc:
            raise ValueError(f"Template error: unknown placeholder {exc}")

        # Prepend system instruction if provided
        if system:
            rendered = f"{system}\n\n{rendered}"

        return {"prompt": rendered}
