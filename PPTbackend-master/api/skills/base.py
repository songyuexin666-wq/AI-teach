from __future__ import annotations

from typing import Any, Dict

from api.tools.base import ToolContext


class BaseSkill:
    name = "base_skill"
    description = ""

    async def run(self, context: ToolContext, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError
