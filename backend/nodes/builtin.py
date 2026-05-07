from __future__ import annotations

import asyncio
from typing import Any

from backend.core.models import ArgDefinition, NodeTypeSchema, PortDefinition
from backend.core.registry import NodeContext, NodeRegistry


def register_builtin_nodes(registry: NodeRegistry) -> None:
    registry.register(_prompt_builder_schema(), prompt_builder)
    registry.register(_demo_schema(), brahim_youcef_demo)
    registry.register(_output_schema(), output_node)


def _prompt_builder_schema() -> NodeTypeSchema:
    return NodeTypeSchema(
        node_type="prompt_builder",
        label="Prompt Builder",
        category="Text",
        inputs={
            "context": PortDefinition("context", "string", "Context", "Text or metadata used as input context.", required=False),
        },
        outputs={
            "result": PortDefinition("result", "string", "Result", "Configured prompt text."),
        },
        args_schema={
            "model_name": ArgDefinition("model_name", "string", default="bert-base"),
            "temperature": ArgDefinition("temperature", "number", default=0.7),
        },
    )


async def prompt_builder(context: NodeContext) -> dict[str, Any]:
    await asyncio.sleep(0)
    model_name = context.args.get("model_name", "bert-base")
    temperature = context.args.get("temperature", 0.7)
    upstream = context.inputs.get("context", "")
    result = f"model={model_name}; temperature={temperature}; context={upstream}"
    return {"result": result}


def _demo_schema() -> NodeTypeSchema:
    return NodeTypeSchema(
        node_type="brahim_&_youcef_demo",
        label="Brahim & Youcef Demo",
        category="Documents",
        inputs={
            "input_2": PortDefinition("input_2", "string", "Input 2", "Primary text input.", required=False),
            "input_2_2": PortDefinition("input_2_2", "any", "Input 2", "Secondary demo input.", required=False),
        },
        outputs={
            "text": PortDefinition("text", "string", "text", "Extracted text."),
            "output_2": PortDefinition("output_2", "any", "Output 2", "Demo payload."),
            "output_3": PortDefinition("output_3", "any", "Output 3", "Demo flag."),
            "output_4": PortDefinition("output_4", "any", "Output 4", "Demo numeric result."),
        },
        args_schema={
            "file": ArgDefinition("file", "string", default=""),
            "cach_results": ArgDefinition("cach_results", "boolean", default=False),
            "number_field": ArgDefinition("number_field", "number", default=0),
            "checkbox_field": ArgDefinition("checkbox_field", "boolean", default=False),
        },
    )


async def brahim_youcef_demo(context: NodeContext) -> dict[str, Any]:
    await asyncio.sleep(0)
    source_text = context.inputs.get("input_2") or context.inputs.get("input_2_2") or context.args.get("file") or "empty"
    number = context.args.get("number_field", 0)
    checked = context.args.get("checkbox_field", False)
    text = f"{source_text} | number={number} | checked={checked}"
    return {
        "text": text,
        "output_2": {"args": context.args, "inputs": context.inputs},
        "output_3": checked,
        "output_4": number,
    }


def _output_schema() -> NodeTypeSchema:
    return NodeTypeSchema(
        node_type="output",
        label="Output",
        category="IO",
        inputs={
            "text": PortDefinition("text", "string", "text", "Text to collect.", required=True),
        },
        outputs={},
        args_schema={},
    )


async def output_node(context: NodeContext) -> dict[str, Any]:
    await asyncio.sleep(0)
    print(f"[{context.run_id}] output:{context.node_id}: {context.inputs.get('text', '')}")
    return {}

