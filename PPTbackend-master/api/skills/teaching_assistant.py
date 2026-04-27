from __future__ import annotations

from typing import Any, Dict

from api.skills.base import BaseSkill
from api.tools.ai_teacher_tools import (
    AnalyzeQuestionTool,
    GenerateQuestionsTool,
    GenerateScriptTool,
    GetAdviceTool,
)
from api.tools.base import ToolContext
from api.tools.rag_search import RAGSearchTool


class TeachingAssistantSkill(BaseSkill):
    name = "teaching_assistant"
    description = "Compose ai_teacher tools into a multi-step teaching assistant workflow."

    def __init__(
        self,
        rag_tool: RAGSearchTool | None,
        analyze_tool: AnalyzeQuestionTool,
        script_tool: GenerateScriptTool,
        questions_tool: GenerateQuestionsTool,
        advice_tool: GetAdviceTool,
    ):
        self.rag_tool = rag_tool
        self.analyze_tool = analyze_tool
        self.script_tool = script_tool
        self.questions_tool = questions_tool
        self.advice_tool = advice_tool

    async def run(self, context: ToolContext, **kwargs) -> Dict[str, Any]:
        question = kwargs["question"]
        ppt_content = kwargs.get("ppt_content") or "No PPT content"
        include_script = kwargs.get("include_script", True)
        include_questions = kwargs.get("include_questions", True)
        include_advice = kwargs.get("include_advice", True)
        metadata = kwargs.get("metadata") or {}

        outputs: Dict[str, Any] = {}
        knowledge_context = ""
        kb_ids = list(metadata.get("kb_ids") or [])

        if self.rag_tool is not None:
            rag_result = await self.rag_tool.call(
                context,
                query=metadata.get("rag_query") or question,
                kb_ids=kb_ids,
                course_id=metadata.get("course_id"),
                subject=metadata.get("subject"),
                grade=metadata.get("grade"),
                teacher_id=metadata.get("teacher_id"),
                top_k=metadata.get("top_k", 5),
                similarity_threshold=metadata.get("similarity_threshold", 0.2),
            )
            outputs[self.rag_tool.name] = rag_result
            knowledge_context = rag_result.get("context_text", "")
            kb_ids = rag_result.get("kb_ids", kb_ids)

        analysis = kwargs.get("analysis_override") or ""
        if not analysis:
            analysis_result = await self.analyze_tool.call(
                context,
                question=question,
                knowledge_context=knowledge_context,
            )
            outputs[self.analyze_tool.name] = analysis_result
            analysis = analysis_result["content"]
        else:
            outputs[self.analyze_tool.name] = {
                "content": analysis,
                "source": "metadata_override",
            }

        script = ""
        if include_script:
            script_result = await self.script_tool.call(
                context,
                question=question,
                analysis=analysis,
                ppt_content=ppt_content,
                knowledge_context=knowledge_context,
            )
            outputs[self.script_tool.name] = script_result
            script = script_result["content"]
        elif kwargs.get("script_override"):
            script = kwargs["script_override"]

        if include_questions:
            questions_result = await self.questions_tool.call(
                context,
                question=question,
                analysis=analysis,
                script=kwargs.get("script_override") or script or analysis,
                knowledge_context=knowledge_context,
            )
            outputs[self.questions_tool.name] = questions_result

        if include_advice:
            advice_result = await self.advice_tool.call(
                context,
                question=question,
                knowledge_context=knowledge_context,
            )
            outputs[self.advice_tool.name] = advice_result

        content_parts = [f"问题分析：\n{analysis}"]
        if include_script and outputs.get(self.script_tool.name):
            content_parts.append(f"教学讲稿：\n{outputs[self.script_tool.name]['content']}")
        if include_questions and outputs.get(self.questions_tool.name):
            q_count = len(outputs[self.questions_tool.name].get("questions", []))
            content_parts.append(f"练习题：\n已生成 {q_count} 道练习题。")
        if include_advice and outputs.get(self.advice_tool.name):
            content_parts.append(f"教学建议：\n{outputs[self.advice_tool.name]['content']}")

        return {
            "content": "\n\n".join(content_parts),
            "outputs": outputs,
            "kb_ids": kb_ids,
        }
