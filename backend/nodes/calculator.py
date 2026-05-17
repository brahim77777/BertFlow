from __future__ import annotations

import ast
import operator
from typing import Any

from backend.core.registry import register_node

_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.Mod: operator.mod,
}


def _safe_eval(node: ast.AST) -> float | int:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp):
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        op_fn = _ALLOWED_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Operator {type(node.op).__name__} not allowed")
        return op_fn(left, right)
    if isinstance(node, ast.UnaryOp):
        operand = _safe_eval(node.operand)
        op_fn = _ALLOWED_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Operator {type(node.op).__name__} not allowed")
        return op_fn(operand)
    raise ValueError(f"Expression contains unsupported construct: {type(node).__name__}")


@register_node
class CalculatorTool:
    node_type = "tool_calculator"
    label = "Calculator"
    description = "Safely evaluates arithmetic expressions"
    category = "tools"
    version = "1.0.0"
    ui_config = {"icon": "calculator", "color": "#F59E0B", "category_order": 1}

    inputs = {}

    outputs = {
        "tool": {"type": "object", "mode": "extension"},
    }

    args_schema = {}

    @staticmethod
    async def run(args: dict, inputs: dict, context: Any, emit=None) -> dict:
        def execute(tool_args: dict) -> str:
            expr = tool_args.get("expression", "")
            tree = ast.parse(expr, mode="eval")
            result = _safe_eval(tree.body)
            return str(result)

        return {
            "tool": {
                "type": "tool",
                "name": "calculator",
                "definition": {
                    "type": "function",
                    "function": {
                        "name": "calculator",
                        "description": (
                            "Evaluates a mathematical expression. "
                            "Supports +, -, *, /, **, %, and parentheses."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "expression": {
                                    "type": "string",
                                    "description": "The arithmetic expression to evaluate, e.g. '42 * 17 + 3'",
                                }
                            },
                            "required": ["expression"],
                        },
                    },
                },
                "execute": execute,
            }
        }
