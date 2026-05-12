from __future__ import annotations

_ALIASES = {
    "str": "string",
    "text": "string",
    "file": "string",
    "bool": "boolean",
    "toggle": "boolean",
    "checkbox": "boolean",
    "integer": "int",
}

_COMPATIBILITY = {
    ("int", "number"): True,
    ("number", "int"): True,
    ("float", "number"): True,
    ("number", "float"): True,
    ("int", "float"): True,
    ("float", "int"): True,
}


def normalize_type(raw: str) -> str:
    t = raw.strip().lower().replace(" ", "")
    base = t.split("[")[0] if "[" in t else t
    normalized_base = _ALIASES.get(base, base)
    if "[" in t:
        inner = t[t.index("[") + 1 : t.index("]")]
        return f"{normalized_base}[{normalize_type(inner)}]"
    return normalized_base


def are_types_compatible(source: str, target: str) -> bool:
    s = normalize_type(source)
    t = normalize_type(target)
    return (
        s == "any"
        or t == "any"
        or s == t
        or _COMPATIBILITY.get((s, t), False)
    )
