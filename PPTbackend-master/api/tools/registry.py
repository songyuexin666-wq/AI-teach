from __future__ import annotations

from typing import Dict, Iterable

from api.tools.ai_teacher_tools import (
    AnalyzeQuestionTool,
    GenerateQuestionsTool,
    GenerateScriptTool,
    GetAdviceTool,
)
from api.tools.base import BaseTool
from api.tools.rag_search import RAGSearchTool
from api.tools.simple_chat import SimpleChatTool


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register(SimpleChatTool())
        self.register(RAGSearchTool())
        self.register(AnalyzeQuestionTool())
        self.register(GenerateScriptTool())
        self.register(GenerateQuestionsTool())
        self.register(GetAdviceTool())

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, tool_name: str) -> BaseTool | None:
        return self._tools.get(tool_name)

    def list(self) -> Iterable[BaseTool]:
        return self._tools.values()
