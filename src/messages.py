"""JSON-safe localized message descriptors emitted by backend-owned flows."""
from __future__ import annotations

import math
from typing import Any, TypeAlias


RenderableMessage: TypeAlias = str | dict[str, Any]


def _is_json_value(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_is_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json_value(item) for key, item in value.items())
    return False


def message(code: str, params: dict[str, Any] | None = None, *, fallback: str) -> dict[str, Any]:
    """Build a descriptor with a readable English fallback."""
    if not isinstance(code, str) or not code.strip():
        raise ValueError("code must be a nonblank string")
    if not isinstance(fallback, str) or not fallback.strip():
        raise ValueError("fallback must be a nonblank string")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise TypeError("params must be a JSON object")
    if not _is_json_value(params):
        raise TypeError("params must contain JSON-compatible values")
    return {"code": code, "params": params, "message": fallback}


def format_message(value: RenderableMessage) -> str:
    """Return the readable English representation without changing raw data."""
    if isinstance(value, str):
        return value
    readable = value.get("message")
    return readable if isinstance(readable, str) else ""
