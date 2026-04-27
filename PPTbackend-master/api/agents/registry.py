from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from api.agents.base import BaseAgent
from api.agents.teacher_assistant import TeacherAssistantAgent
from api.agents.teacher_chat import TeacherChatAgent
from api.tools.base import BaseTool, ToolContext
from api.tools.registry import ToolRegistry


class AgentRegistry:
    def __init__(
        self,
        services: Dict[str, Any] | None = None,
        tool_registry: ToolRegistry | None = None,
        config_path: str | None = None,
    ):
        self._services = services or {}
        self._tool_registry = tool_registry or ToolRegistry()
        self._agents: Dict[str, BaseAgent] = {}
        self._config_path = (
            Path(config_path)
            if config_path
            else Path(__file__).resolve().parents[2] / "config" / "agents.json"
        )
        self._register_from_config()

    def _register_from_config(self) -> None:
        if not self._config_path.exists():
            self.register(TeacherChatAgent())
            return

        with self._config_path.open("r", encoding="utf-8") as f:
            config = json.load(f)

        for item in config.get("agents", []):
            self.register(self._create_agent(item))

        if not self._agents:
            self.register(TeacherChatAgent())

    def _resolve_tools(self, tool_names: list[str]) -> list[BaseTool]:
        tools: list[BaseTool] = []
        for tool_name in tool_names:
            tool = self._tool_registry.get(tool_name)
            if tool is not None:
                tools.append(tool)
        return tools

    def _create_agent(self, config: Dict[str, Any]) -> BaseAgent:
        agent_type = config.get("type", "teacher_chat")
        tools = self._resolve_tools(config.get("tools", []))

        if agent_type == "teacher_chat":
            agent = TeacherChatAgent(
                name=config.get("name"),
                description=config.get("description"),
                system_prompt=config.get("system_prompt"),
                tools=tools,
            )
        elif agent_type == "teacher_assistant":
            agent = TeacherAssistantAgent(
                name=config.get("name"),
                description=config.get("description"),
                tools=tools,
            )
        else:
            raise ValueError(f"Unsupported agent type: {agent_type}")

        if config.get("id"):
            agent.id = config["id"]
        return agent

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.id] = agent

    def get(self, agent_id: str) -> BaseAgent | None:
        return self._agents.get(agent_id)

    def list(self) -> list[BaseAgent]:
        return list(self._agents.values())

    def build_context(self) -> ToolContext:
        return ToolContext(services=self._services)
