from __future__ import annotations

from api.agents.base import AgentInput, AgentOutput, BaseAgent
from api.skills.teaching_assistant import TeachingAssistantSkill
from api.tools.ai_teacher_tools import (
    AnalyzeQuestionTool,
    GenerateQuestionsTool,
    GenerateScriptTool,
    GetAdviceTool,
)
from api.tools.base import ToolContext
from api.tools.rag_search import RAGSearchTool


class TeacherAssistantAgent(BaseAgent):
    id = "teacher_assistant"
    name = "Teacher Assistant Agent"
    description = "Multi-step teaching assistant for analysis, script, questions, and advice."

    def __init__(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        tools=None,
    ):
        resolved_tools = tools or [
            RAGSearchTool(),
            AnalyzeQuestionTool(),
            GenerateScriptTool(),
            GenerateQuestionsTool(),
            GetAdviceTool(),
        ]
        super().__init__(tools=resolved_tools)
        if name:
            self.name = name
        if description:
            self.description = description

        tool_map = {tool.name: tool for tool in self.tools}
        self.skill = TeachingAssistantSkill(
            rag_tool=tool_map.get("rag_search"),
            analyze_tool=tool_map["analyze_question"],
            script_tool=tool_map["generate_script"],
            questions_tool=tool_map["generate_questions"],
            advice_tool=tool_map["get_advice"],
        )

    async def run(self, agent_input: AgentInput, context: ToolContext) -> AgentOutput:
        result = await self.skill.run(
            context,
            question=agent_input.message,
            ppt_content=agent_input.metadata.get("ppt_content"),
            include_script=agent_input.metadata.get("include_script", True),
            include_questions=agent_input.metadata.get("include_questions", True),
            include_advice=agent_input.metadata.get("include_advice", True),
            metadata=agent_input.metadata,
        )
        return AgentOutput(
            content=result["content"],
            agent_id=self.id,
            tool_outputs=result["outputs"],
            metadata={
                "agent_name": self.name,
                "skill_used": self.skill.name,
                "kb_ids": result.get("kb_ids", []),
            },
        )
