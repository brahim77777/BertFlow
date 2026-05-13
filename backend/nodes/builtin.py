from __future__ import annotations

from typing import Any

from backend.core.registry import register_node


@register_node
class PromptBuilder:
    node_type = "prompt_builder"
    label = "Prompt Builder"
    description = "Collects prompt settings and sends the configured prompt to the next node"
    category = "llm"
    version = "1.0.0"
    ui_config = {"icon": "bot", "color": "#4A90D9", "category_order": 1}

    inputs = {
        "context": {"type": "string", "required": False},
    }

    outputs = {
        "result": {"type": "string"},
    }

    args_schema = {
        "model_name": {"type": "string", "default": "bert-base"},
        "temperature": {"type": "number", "default": 0.7},
        "use_cache": {"type": "boolean", "default": True},
    }

    @staticmethod
    async def run(args: dict, inputs: dict, context: Any) -> dict:
        return {
            "result": (
                f"Model: {args.get('model_name', 'bert-base')} | "
                f"Temp: {args.get('temperature', 0.7)} | "
                f"Input: {inputs.get('context', '')}"
            )
        }


@register_node
class BrahimYoucefDemo:
    node_type = "brahim_&_youcef_demo"
    label = "Brahim & Youcef Demo"
    description = "Demo node for testing the execution pipeline"
    category = "demo"
    version = "1.0.0"
    ui_config = {"icon": "test-tube", "color": "#6B7280", "category_order": 99}

    inputs = {
        "input_1": {"type": "string", "required": False},
        "input_2": {"type": "string", "required": False},
    }

    outputs = {
        "text": {"type": "string"},
        "metadata": {"type": "json"},
    }

    args_schema = {
        "file": {"type": "string", "default": "seed.txt"},
        "cach_results": {"type": "boolean", "default": False},
        "number_field": {"type": "integer", "default": 8},
        "checkbox_field": {"type": "boolean", "default": False},
    }

    @staticmethod
    async def run(args: dict, inputs: dict, context: Any) -> dict:
        combined = (
            f"Demo processed: file={args.get('file')}, "
            f"num={args.get('number_field')}, "
            f"input1={inputs.get('input_1', '')}, "
            f"input2={inputs.get('input_2', '')}"
        )
        return {
            "text": combined,
            "metadata": {
                "file": args.get("file"),
                "number_field": args.get("number_field"),
                "checkbox_field": args.get("checkbox_field"),
                "cach_results": args.get("cach_results"),
            },
        }


@register_node
class OutputNode:
    node_type = "output"
    label = "Output"
    description = "Terminal output node — prints and discards input"
    category = "io"
    version = "1.0.0"
    ui_config = {"icon": "terminal", "color": "#059669", "category_order": 0}

    inputs = {
        "text": {"type": "string", "required": False},
    }

    outputs = {}

    args_schema = {}

    @staticmethod
    async def run(args: dict, inputs: dict, context: Any) -> dict:
        return {}
