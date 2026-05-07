from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


TYPE_ALIASES = {
    "str": "string",
    "text": "string",
    "file": "string",
    "bool": "boolean",
    "toggle": "boolean",
    "checkbox": "boolean",
    "integer": "int",
    "double": "float",
    "dict": "object",
    "json": "object",
    "list": "array",
}


def normalize_type(type_name: str | None) -> str:
    value = str(type_name or "any").strip().lower().replace(" ", "")
    return TYPE_ALIASES.get(value, value or "any")


def are_types_compatible(source_type: str | None, target_type: str | None) -> bool:
    source = normalize_type(source_type)
    target = normalize_type(target_type)

    if source == "any" or target == "any":
        return True
    if source == target:
        return True
    if target == "number" and source in {"int", "float"}:
        return True
    if target == "float" and source in {"int", "number"}:
        return True
    if target == "string" and source == "file":
        return True
    return False


def value_matches_type(value: Any, type_name: str | None) -> bool:
    expected = normalize_type(type_name)

    if expected == "any" or value is None:
        return True
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected in {"float", "number"}:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array" or expected.startswith("list["):
        return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
    return True

