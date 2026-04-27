from __future__ import annotations

from api.agents.base import AgentInput, AgentOutput, BaseAgent
from api.tools.base import ToolContext
from api.tools.simple_chat import SimpleChatTool


class TeacherChatAgent(BaseAgent):
    id = "teacher_chat"
    name = "Teacher Chat Agent"
    description = "General-purpose teaching dialogue for teachers without KB dependency."
    system_prompt = "You are an AI teaching assistant. Reply in concise, helpful Chinese."

    def __init__(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        system_prompt: str | None = None,
        tools=None,
    ):
        super().__init__(tools=tools or [SimpleChatTool()])
        if name:
            self.name = name
        if description:
            self.description = description
        if system_prompt:
            self.system_prompt = system_prompt

    async def run(self, agent_input: AgentInput, context: ToolContext) -> AgentOutput:
        tool = self.tools[0]
        tool_result = await tool.call(
            context,
            system_prompt=self.system_prompt,
            messages=agent_input.messages or [{"role": "user", "content": agent_input.message}],
        )
        return AgentOutput(
            content=tool_result["content"],
            agent_id=self.id,
            tool_outputs={tool.name: tool_result},
            metadata={"agent_name": self.name, "tool_used": tool.name},
        )
