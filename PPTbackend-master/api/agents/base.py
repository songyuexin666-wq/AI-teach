from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from api.tools.base import BaseTool, ToolContext


@dataclass
class AgentInput:
    message: str
    messages: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentOutput:
    content: str
    agent_id: str
    tool_outputs: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAgent:
    id = "base_agent"
    name = "Base Agent"
    description = ""
    system_prompt = ""

    def __init__(self, tools: Optional[List[BaseTool]] = None):
        self.tools = tools or []

    async def run(self, agent_input: AgentInput, context: ToolContext) -> AgentOutput:
        raise NotImplementedError
