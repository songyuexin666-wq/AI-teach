from __future__ import annotations

from typing import Any, Dict


class ToolValidationError(ValueError):
    """Raised when tool arguments do not satisfy schema constraints."""


def validate_args(args: Dict[str, Any], schema: Dict[str, Any] | None) -> Dict[str, Any]:
    """
    Minimal schema validator for tools.

    Supported field rules:
    - type: str | int | float | bool | list | dict
    - required: bool
    - default: Any
    - enum: list[Any]
    - min_length / max_length (str, list)
    - min / max (int, float)
    """
    if not schema:
        return args

    fields = schema.get("fields", {}) or {}
    allow_extra = schema.get("allow_extra", True)
    normalized: Dict[str, Any] = dict(args or {})

    if not allow_extra:
        extras = [k for k in normalized.keys() if k not in fields]
        if extras:
            raise ToolValidationError(f"Unexpected arguments: {', '.join(extras)}")

    # Apply defaults + required checks
    for key, rule in fields.items():
        if key not in normalized and "default" in rule:
            normalized[key] = rule["default"]
        if rule.get("required") and key not in normalized:
            raise ToolValidationError(f"Missing required argument: {key}")

    # Type/range checks
    for key, value in normalized.items():
        if key not in fields:
            continue
        rule = fields[key]
        expected_type = rule.get("type")
        if expected_type is not None and value is not None:
            py_type = _type_to_python(expected_type)
            if not isinstance(value, py_type):
                raise ToolValidationError(
                    f"Argument '{key}' must be {expected_type}, got {type(value).__name__}"
                )

        enum_vals = rule.get("enum")
        if enum_vals is not None and value not in enum_vals:
            raise ToolValidationError(f"Argument '{key}' must be one of {enum_vals}")

        if isinstance(value, (str, list)):
            min_len = rule.get("min_length")
            max_len = rule.get("max_length")
            if min_len is not None and len(value) < min_len:
                raise ToolValidationError(f"Argument '{key}' length must be >= {min_len}")
            if max_len is not None and len(value) > max_len:
                raise ToolValidationError(f"Argument '{key}' length must be <= {max_len}")

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            min_val = rule.get("min")
            max_val = rule.get("max")
            if min_val is not None and value < min_val:
                raise ToolValidationError(f"Argument '{key}' must be >= {min_val}")
            if max_val is not None and value > max_val:
                raise ToolValidationError(f"Argument '{key}' must be <= {max_val}")

    return normalized


def _type_to_python(type_name: str):
    m = {
        "str": str,
        "int": int,
        "float": (int, float),
        "bool": bool,
        "list": list,
        "dict": dict,
    }
    if type_name not in m:
        raise ToolValidationError(f"Unsupported schema type: {type_name}")
    return m[type_name]

