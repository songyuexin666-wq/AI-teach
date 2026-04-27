from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from api.tools.schema_validator import validate_args


@dataclass
class ToolContext:
    services: Dict[str, Any] = field(default_factory=dict)


class BaseTool:
    name = "base_tool"
    description = ""
    # Optional runtime arg schema for lightweight validation.
    # Example:
    # {
    #   "allow_extra": False,
    #   "fields": {"question": {"type": "str", "required": True, "min_length": 1}}
    # }
    parameter_schema: Dict[str, Any] | None = None

    def validate_args(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        return validate_args(kwargs, self.parameter_schema)

    async def call(self, context: ToolContext, **kwargs) -> Any:
        raise NotImplementedError
