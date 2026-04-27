from __future__ import annotations

import asyncio
import json
import os
import re
from collections import defaultdict
from typing import Any, Dict, List

import openai

from api.tools.base import BaseTool, ToolContext


class _AITeacherToolBase(BaseTool):
    system_prompt = ""
    user_prompt_template = ""
    max_tokens = 2000
    temperature = 0.7

    def _get_client(self):
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        model = os.getenv("AI_MODEL", "qwen-long")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured")
        return openai.OpenAI(api_key=api_key, base_url=base_url), model

    def _build_user_prompt(self, **kwargs) -> str:
        return self.user_prompt_template.format_map(defaultdict(str, kwargs))

    async def call(self, context: ToolContext, **kwargs) -> Dict[str, Any]:
        kwargs = self.validate_args(kwargs)
        client, model = self._get_client()
        prompt = self._build_user_prompt(**kwargs)
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            extra_body={"enable_thinking": False},
        )
        content = (response.choices[0].message.content or "").strip()
        return {"content": content, "model": model}


class AnalyzeQuestionTool(_AITeacherToolBase):
    name = "analyze_question"
    description = "Analyze a student's question and provide teaching-oriented insight."
    parameter_schema = {
        "allow_extra": False,
        "fields": {
            "question": {"type": "str", "required": True, "min_length": 1, "max_length": 4000},
            "knowledge_context": {"type": "str", "required": False, "default": ""},
        },
    }
    system_prompt = "你是一位经验丰富的教师，擅长分析学生问题并提供教学建议。"
    user_prompt_template = """
请对下面的学生问题做教学分析，并优先参考给出的课程知识库上下文。

学生问题：
{question}

课程知识库上下文：
{knowledge_context}

请从这些角度回答：
1. 问题类型与难度
2. 涉及的核心知识点
3. 学生可能存在的误区
4. 讲解思路与教学建议
5. 可以延伸的相关知识

请用中文、结构清晰地输出。
"""


class GenerateScriptTool(_AITeacherToolBase):
    name = "generate_script"
    description = "Generate a teaching script based on question analysis."
    system_prompt = "你是一位优秀教师，擅长把复杂知识讲解成清晰、自然、适合课堂表达的讲稿。"
    max_tokens = 3000
    user_prompt_template = """
请基于下面的信息生成一份结构化教学讲稿，并优先结合课程知识库上下文中的事实、概念和案例。

学生问题：
{question}

问题分析：
{analysis}

PPT内容：
{ppt_content}

课程知识库上下文：
{knowledge_context}

讲稿请包含：
1. 导入与问题引入
2. 核心概念讲解
3. 解题或理解路径演示
4. 示例或类比
5. 总结与拓展

请使用自然中文输出，适合老师直接讲解。
"""


class GenerateSlideScriptTool(_AITeacherToolBase):
    name = "generate_slide_script"
    description = "Generate per-slide teaching script based on slide content."
    system_prompt = "你是一位优秀教师，擅长围绕PPT单页内容进行深入讲解，条理清晰、贴近课堂表达。"
    max_tokens = 1800
    user_prompt_template = """
请基于下面的信息，为“这一页PPT”生成讲解稿。要求：必须围绕本页内容展开，讲清概念、推导/公式含义、常见误区与小结，并优先使用知识库上下文中的表述与事实。

学生最初提问：
{question}

整体问题分析（参考）：
{analysis}

当前页标题：
{slide_title}

当前页内容：
{slide_content}

课程知识库上下文：
{knowledge_context}

输出要求：
- 使用 Markdown
- 结构建议：本页要点 → 详细讲解 → 公式/推导说明（如有）→ 易错点 → 1-2个检查理解的小问题
"""


class GenerateQuestionsTool(_AITeacherToolBase):
    name = "generate_questions"
    description = "Generate follow-up practice questions from analysis and script."
    parameter_schema = {
        "allow_extra": False,
        "fields": {
            "question": {"type": "str", "required": True, "min_length": 1, "max_length": 4000},
            "analysis": {"type": "str", "required": True, "min_length": 1},
            "script": {"type": "str", "required": False, "default": ""},
            "knowledge_context": {"type": "str", "required": False, "default": ""},
        },
    }
    system_prompt = "你是一位专业教师，擅长根据教学内容设计高质量练习题。"
    max_tokens = 3000
    user_prompt_template = """
请基于下面的学习内容生成 6 道练习题，并优先结合课程知识库上下文中的具体概念、公式和案例。

学生问题：
{question}

问题分析：
{analysis}

教学讲稿：
{script}

课程知识库上下文：
{knowledge_context}

请按 JSON 返回，格式如下：
{{
  "questions": [
    {{
      "question": "题目内容",
      "type": "choice",
      "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"],
      "correct_answer": "A",
      "explanation": "解析内容"
    }},
    {{
      "question": "题目内容",
      "type": "text",
      "correct_answer": "标准答案",
      "explanation": "解析内容"
    }}
  ]
}}
"""

    def _parse_questions(self, content: str) -> List[Dict[str, Any]]:
        json_content = content or ""
        if "```json" in json_content:
            json_start = json_content.find("```json") + 7
            json_end = json_content.find("```", json_start)
            json_content = json_content[json_start:json_end].strip()
        elif "```" in json_content:
            json_start = json_content.find("```") + 3
            json_end = json_content.find("```", json_start)
            json_content = json_content[json_start:json_end].strip()

        # 尝试 1：直接解析
        try:
            obj = json.loads(json_content)
            if isinstance(obj, dict):
                items = obj.get("questions", [])
            elif isinstance(obj, list):
                items = obj
            else:
                items = []
            return [q for q in items if isinstance(q, dict)]
        except Exception:
            pass

        # 尝试 2：提取 {...}
        try:
            m = re.search(r"\{[\s\S]*\}", json_content)
            if m:
                obj = json.loads(m.group(0))
                if isinstance(obj, dict):
                    items = obj.get("questions", [])
                elif isinstance(obj, list):
                    items = obj
                else:
                    items = []
                return [q for q in items if isinstance(q, dict)]
        except Exception:
            pass

        # 尝试 3：提取 [...]
        try:
            m = re.search(r"\[[\s\S]*\]", json_content)
            if m:
                obj = json.loads(m.group(0))
                if isinstance(obj, list):
                    return [q for q in obj if isinstance(q, dict)]
        except Exception:
            pass
        return []

    @staticmethod
    def _normalize_question_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        q = str(item.get("question", "")).strip()
        q_type = str(item.get("type", "")).strip().lower()
        if not q or q_type not in ("choice", "text"):
            return None
        out = {
            "question": q,
            "type": q_type,
            "correct_answer": str(item.get("correct_answer", "")).strip(),
            "explanation": str(item.get("explanation", "")).strip(),
        }
        if q_type == "choice":
            options = item.get("options") or []
            if not isinstance(options, list) or len(options) < 2:
                return None
            out["options"] = [str(x).strip() for x in options if str(x).strip()]
            if len(out["options"]) < 2:
                return None
        return out

    async def call(self, context: ToolContext, **kwargs) -> Dict[str, Any]:
        result = await super().call(context, **kwargs)
        content = result["content"]
        parsed_questions = self._parse_questions(content)
        normalized: List[Dict[str, Any]] = []
        for item in parsed_questions:
            row = self._normalize_question_item(item)
            if row:
                normalized.append(row)
        result["questions"] = normalized
        result["raw_content"] = content
        return result


class GetAdviceTool(_AITeacherToolBase):
    name = "get_advice"
    description = "Provide targeted teaching advice for the question."
    system_prompt = "你是一位经验丰富的教师，擅长给出可执行的教学建议。"
    user_prompt_template = """
请针对下面的学生问题给出教学建议，并在有帮助时结合课程知识库上下文。

学生问题：
{question}

课程知识库上下文：
{knowledge_context}

请提供：
1. 教学重点和难点
2. 推荐教学方法
3. 推荐教学资源
4. 学生可能遇到的困难
5. 教学效果评估建议
"""


class GenerateSceneOutlineTool(_AITeacherToolBase):
    name = "generate_scene_outline"
    description = "Generate scene outline for classroom flow."
    system_prompt = "你是一位课程设计专家，擅长将教学需求转为结构化课堂场景。"
    max_tokens = 2200
    user_prompt_template = """
请根据以下信息生成“课堂场景大纲”，只输出 JSON 数组，不要输出任何解释文字。

主题：{topic}
受众：{audience}
时长（分钟）：{duration_minutes}
风格：{style}
课程知识库上下文：{knowledge_context}
学生历史记忆（可为空）：{memory_context}

要求：
1) 场景类型仅限 slide / quiz
2) 场景总数 6~10，至少 1 个 quiz
3) 每个场景字段：
   id, type, title, description, keyPoints, order, estimatedDuration
4) quiz 额外字段：
   questionCount, focus

输出示例：
[
  {{
    "id":"scene_1",
    "type":"slide",
    "title":"课程导入",
    "description":"明确学习目标与问题情境",
    "keyPoints":["目标","背景","路径"],
    "order":1,
    "estimatedDuration":120
  }},
  {{
    "id":"scene_2",
    "type":"quiz",
    "title":"随堂检测",
    "description":"检查核心知识掌握情况",
    "keyPoints":["概念辨析","方法应用"],
    "order":2,
    "estimatedDuration":180,
    "questionCount":3,
    "focus":"薄弱点巩固"
  }}
]
"""

    async def call(self, context: ToolContext, **kwargs) -> Dict[str, Any]:
        result = await super().call(context, **kwargs)
        content = result.get("content", "") or ""
        scenes: List[Dict[str, Any]] = []
        text = content
        try:
            if "```json" in text:
                s = text.find("```json") + 7
                e = text.find("```", s)
                text = text[s:e].strip()
            elif "```" in text:
                s = text.find("```") + 3
                e = text.find("```", s)
                text = text[s:e].strip()
            try:
                obj = json.loads(text)
            except Exception:
                m = re.search(r"\[[\s\S]*\]", text)
                obj = json.loads(m.group(0)) if m else []
            if isinstance(obj, list):
                for i, row in enumerate(obj, start=1):
                    if not isinstance(row, dict):
                        continue
                    row.setdefault("id", f"scene_{i}")
                    row.setdefault("type", "slide")
                    row.setdefault("title", f"场景{i}")
                    row.setdefault("description", "")
                    row.setdefault("keyPoints", [])
                    row.setdefault("order", i)
                    row.setdefault("estimatedDuration", 120)
                    if row.get("type") == "quiz":
                        row.setdefault("questionCount", 3)
                        row.setdefault("focus", "薄弱点巩固")
                    scenes.append(row)
        except Exception:
            scenes = []
        result["scenes"] = scenes
        return result
