"""
OpenClaw 架构：AI 教师能力统一服务层。
- 所有能力通过 Tools 层（api.tools.ai_teacher_tools）实现，此处仅做编排与 RAG 上下文注入。
- 被 api/routers/ai_teacher.py（REST 直连）与 Agent 路径共用同一套 Tool 实现，避免重复逻辑。
"""
from __future__ import annotations

import asyncio
import logging
import os
import json
import uuid
from typing import Any, Dict, List, Optional

from api.tools.ai_teacher_tools import (
    AnalyzeQuestionTool,
    GenerateSceneOutlineTool,
    GenerateQuestionsTool,
    GenerateScriptTool,
    GenerateSlideScriptTool,
    GetAdviceTool,
)
from api.tools.base import ToolContext

logger = logging.getLogger(__name__)


class AITeacherService:
    def __init__(self, services: Optional[Dict[str, Any]] = None):
        self._services = services or {}
        self._ctx = ToolContext(services=self._services)
        self._course_runs_dir = os.path.join("outputs", "course_runs")
        os.makedirs(self._course_runs_dir, exist_ok=True)

    def _memory_service(self):
        return self._services.get("student_memory_service")

    def _memory_lookup(self, *, student_id: Optional[str], query: str, limit: int = 3) -> Dict[str, Any]:
        svc = self._memory_service()
        if not svc:
            return {"enabled": False, "hits": 0, "items": [], "source": "disabled"}
        items = svc.search_weakness_memories(user_id=student_id, query=query, limit=limit)
        return {
            "enabled": True,
            "hits": len(items),
            "items": items,
            "source": "hybrid" if items else "none",
        }

    def _inject_memory_context(self, *, base_context: str, memory_items: List[str]) -> str:
        if not memory_items:
            return base_context
        svc = self._memory_service()
        extra = svc.build_memory_context(memory_items) if svc else ""
        if not extra:
            return base_context
        if (base_context or "").strip():
            return f"{base_context}\n\n{extra}"
        return extra

    def _save_memory_analysis(self, *, student_id: Optional[str], question: str, analysis: str) -> None:
        svc = self._memory_service()
        if not svc:
            return
        text = svc.summarize_analysis_to_memory(question, analysis)
        svc.add_weakness_memory(user_id=student_id, memory_text=text)

    def _save_memory_questions(self, *, student_id: Optional[str], question: str, questions: List[Dict[str, Any]]) -> None:
        svc = self._memory_service()
        if not svc:
            return
        text = svc.summarize_questions_to_memory(question, questions)
        svc.add_weakness_memory(user_id=student_id, memory_text=text)

    def _save_memory_advice(self, *, student_id: Optional[str], question: str, advice: str) -> None:
        svc = self._memory_service()
        if not svc:
            return
        text = svc.summarize_advice_to_memory(question, advice)
        svc.add_weakness_memory(user_id=student_id, memory_text=text)

    @staticmethod
    def _is_sentence_query(query: str) -> bool:
        q = (query or "").strip()
        if not q:
            return False
        if len(q) >= 12:
            return True
        if " " in q:
            return True
        return any(p in q for p in ("，", "。", "？", "！", ",", ".", "?", "!"))

    async def _get_knowledge_context(
        self,
        query: str,
        *,
        kb_ids: Optional[List[str]] = None,
        top_k: int = 8,
    ) -> (str, List[str]):
        """从 RAG 获取知识库上下文，供 Tools 使用。

        返回 (knowledge_context, kb_ids_used) 便于调用方写入学情日志。
        """
        rag = self._services.get("rag_service")
        if not rag:
            return "", []
        try:
            kb_ids_used: List[str] = [str(x) for x in (kb_ids or []) if str(x).strip()]
            if not kb_ids_used:
                bases = await asyncio.to_thread(rag.list_knowledge_bases)
                bases = bases if isinstance(bases, list) else []
                kb_ids_used = [b["id"] for b in bases if b.get("id")]
            if not kb_ids_used:
                return "", []
            # 自适应召回策略：
            # - 句子查询：阈值偏高（0.2），强调语义
            # - 关键词查询：阈值更低（0.05），强调召回
            is_sentence = self._is_sentence_query(query)
            threshold = 0.2 if is_sentence else 0.05

            results = await asyncio.to_thread(
                rag.search,
                query,
                kb_ids_used,
                top_k=top_k,
                similarity_threshold=threshold,
                vector_similarity_weight=None,  # 让 rag_service 内部按 0.7/0.3 自适应
            )
            if not results:
                return "", kb_ids_used
            ctx = "\n\n".join(
                f"{i}. {r.get('content', '')}" for i, r in enumerate(results, 1)
            )
            return ctx, kb_ids_used
        except Exception as e:
            logger.warning("RAG 检索失败，将不使用知识库上下文: %s", e)
            return "", []

    def _persist_course_snapshot(self, *, course_run_id: str, patch: Dict[str, Any]) -> None:
        if not course_run_id:
            return
        path = os.path.join(self._course_runs_dir, f"{course_run_id}.json")
        data: Dict[str, Any] = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f) or {}
            except Exception:
                data = {}
        data.update(patch or {})
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _estimate_rag_hits(knowledge_context: str) -> int:
        if not knowledge_context:
            return 0
        return len([line for line in knowledge_context.splitlines() if line.strip().startswith(tuple(str(i) + "." for i in range(1, 10)))])

    async def analyze_question(
        self,
        question: str,
        kb_ids: Optional[List[str]] = None,
        rag_query: Optional[str] = None,
        student_id: Optional[str] = None,
        course_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """分析学生问题，返回 { analysis: str }。"""
        q = (rag_query or "").strip() or question
        knowledge_context, kb_ids_used = await self._get_knowledge_context(q, kb_ids=kb_ids)
        mem = self._memory_lookup(student_id=student_id, query=q, limit=3)
        knowledge_context = self._inject_memory_context(
            base_context=knowledge_context or "",
            memory_items=mem["items"],
        )
        rag_hits = self._estimate_rag_hits(knowledge_context)
        tool = AnalyzeQuestionTool()
        result = await tool.call(
            self._ctx,
            question=question,
            knowledge_context=knowledge_context or "无",
        )
        analysis = result.get("content", "").strip()
        self._save_memory_analysis(student_id=student_id, question=question, analysis=analysis)
        run_id = course_run_id or str(uuid.uuid4())
        meta = {"memory_hits": mem["hits"], "memory_enabled": mem["enabled"], "rag_hits": rag_hits, "used_retry": False, "course_run_id": run_id}
        self._persist_course_snapshot(
            course_run_id=run_id,
            patch={"course_run_id": run_id, "student_id": student_id, "question": question, "analysis": analysis},
        )
        return {"analysis": analysis, "kb_ids": kb_ids_used, "memory": mem, "meta": meta}

    async def generate_script(
        self,
        question: str,
        analysis: str,
        ppt_content: Optional[str] = None,
        kb_ids: Optional[List[str]] = None,
        rag_query: Optional[str] = None,
        student_id: Optional[str] = None,
        course_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成教学讲稿，返回 { script: str }。"""
        q = (rag_query or "").strip() or f"{question} {analysis}"
        knowledge_context, kb_ids_used = await self._get_knowledge_context(q, kb_ids=kb_ids)
        mem = self._memory_lookup(student_id=student_id, query=q, limit=3)
        knowledge_context = self._inject_memory_context(
            base_context=knowledge_context or "",
            memory_items=mem["items"],
        )
        rag_hits = self._estimate_rag_hits(knowledge_context)
        tool = GenerateScriptTool()
        result = await tool.call(
            self._ctx,
            question=question,
            analysis=analysis,
            ppt_content=ppt_content or "无PPT内容",
            knowledge_context=knowledge_context or "无",
        )
        run_id = course_run_id or str(uuid.uuid4())
        script = result.get("content", "").strip()
        meta = {"memory_hits": mem["hits"], "memory_enabled": mem["enabled"], "rag_hits": rag_hits, "used_retry": False, "course_run_id": run_id}
        self._persist_course_snapshot(
            course_run_id=run_id,
            patch={"course_run_id": run_id, "script": script},
        )
        return {"script": script, "kb_ids": kb_ids_used, "memory": mem, "meta": meta}

    async def generate_slide_scripts(
        self,
        *,
        question: str,
        analysis: str,
        slides: List[Dict[str, Any]],
        kb_ids: Optional[List[str]] = None,
        rag_query: Optional[str] = None,
        student_id: Optional[str] = None,
        course_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """按页生成讲解稿：返回 { slides: [{title, content, script}], kb_ids }"""
        q = (rag_query or "").strip() or question
        knowledge_context, kb_ids_used = await self._get_knowledge_context(q, kb_ids=kb_ids, top_k=8)
        mem = self._memory_lookup(student_id=student_id, query=q, limit=3)
        knowledge_context = self._inject_memory_context(
            base_context=knowledge_context or "",
            memory_items=mem["items"],
        )

        rag_hits = self._estimate_rag_hits(knowledge_context)
        tool = GenerateSlideScriptTool()
        out_slides: List[Dict[str, Any]] = []

        # 顺序生成，避免并发触发限流；如需加速可改为 gather + 限流
        for idx, s in enumerate(slides or [], start=1):
            title = (s.get("title") or f"第 {idx} 页").strip()
            content = (s.get("content") or s.get("text") or "").strip()
            result = await tool.call(
                self._ctx,
                question=question,
                analysis=analysis,
                slide_title=title,
                slide_content=content,
                knowledge_context=knowledge_context or "无",
            )
            out_slides.append(
                {
                    "index": idx - 1,
                    "title": title,
                    "content": content,
                    "script": (result.get("content") or "").strip(),
                }
            )

        run_id = course_run_id or str(uuid.uuid4())
        meta = {"memory_hits": mem["hits"], "memory_enabled": mem["enabled"], "rag_hits": rag_hits, "used_retry": False, "course_run_id": run_id}
        self._persist_course_snapshot(
            course_run_id=run_id,
            patch={"course_run_id": run_id, "slide_scripts": out_slides},
        )
        return {"slides": out_slides, "kb_ids": kb_ids_used, "memory": mem, "meta": meta}

    async def generate_questions(
        self,
        question: str,
        analysis: str,
        script: str,
        kb_ids: Optional[List[str]] = None,
        rag_query: Optional[str] = None,
        student_id: Optional[str] = None,
        course_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成练习题，返回 { questions: List[dict] }。"""
        q = (rag_query or "").strip() or f"{question} {analysis}"
        knowledge_context, kb_ids_used = await self._get_knowledge_context(q, kb_ids=kb_ids, top_k=5)
        mem = self._memory_lookup(student_id=student_id, query=q, limit=5)
        knowledge_context = self._inject_memory_context(
            base_context=knowledge_context or "",
            memory_items=mem["items"],
        )
        rag_hits = self._estimate_rag_hits(knowledge_context)
        tool = GenerateQuestionsTool()
        result = await tool.call(
            self._ctx,
            question=question,
            analysis=analysis,
            script=script or analysis,
            knowledge_context=knowledge_context or "无",
        )
        questions: List[Dict[str, Any]] = result.get("questions") or []
        # 一次严格重试：若首次解析为空，强制要求“只输出 JSON”
        used_retry = False
        if not questions:
            original_temp = getattr(tool, "temperature", 0.7)
            tool.temperature = 0.2
            strict_analysis = (
                f"{analysis}\n\n"
                "【严格格式要求】只输出合法 JSON，不要 markdown，不要解释文本。"
                " 顶层必须是 {\"questions\":[...]}，且每题必须包含 question/type/correct_answer/explanation。"
            )
            retry = await tool.call(
                self._ctx,
                question=question,
                analysis=strict_analysis,
                script=script or analysis,
                knowledge_context=knowledge_context or "无",
            )
            tool.temperature = original_temp
            questions = retry.get("questions") or []
            used_retry = True
        if questions:
            self._save_memory_questions(student_id=student_id, question=question, questions=questions)
        run_id = course_run_id or str(uuid.uuid4())
        meta = {"memory_hits": mem["hits"], "memory_enabled": mem["enabled"], "rag_hits": rag_hits, "used_retry": used_retry, "course_run_id": run_id}
        self._persist_course_snapshot(
            course_run_id=run_id,
            patch={"course_run_id": run_id, "questions": questions},
        )
        return {"questions": questions, "kb_ids": kb_ids_used, "memory": mem, "meta": meta}

    async def get_advice(
        self,
        question: str,
        kb_ids: Optional[List[str]] = None,
        rag_query: Optional[str] = None,
        student_id: Optional[str] = None,
        course_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取教学建议，返回 { content: str }。"""
        q = (rag_query or "").strip() or question
        knowledge_context, kb_ids_used = await self._get_knowledge_context(q, kb_ids=kb_ids)
        mem = self._memory_lookup(student_id=student_id, query=q, limit=3)
        knowledge_context = self._inject_memory_context(
            base_context=knowledge_context or "",
            memory_items=mem["items"],
        )
        rag_hits = self._estimate_rag_hits(knowledge_context)
        tool = GetAdviceTool()
        result = await tool.call(
            self._ctx,
            question=question,
            knowledge_context=knowledge_context or "无",
        )
        content = result.get("content", "").strip()
        self._save_memory_advice(student_id=student_id, question=question, advice=content)
        run_id = course_run_id or str(uuid.uuid4())
        meta = {"memory_hits": mem["hits"], "memory_enabled": mem["enabled"], "rag_hits": rag_hits, "used_retry": False, "course_run_id": run_id}
        self._persist_course_snapshot(
            course_run_id=run_id,
            patch={"course_run_id": run_id, "advice": content},
        )
        return {"content": content, "kb_ids": kb_ids_used, "memory": mem, "meta": meta}

    async def generate_scene_outline(
        self,
        *,
        topic: str,
        audience: str = "学生",
        duration_minutes: int = 20,
        style: str = "互动讲解",
        kb_ids: Optional[List[str]] = None,
        rag_query: Optional[str] = None,
        student_id: Optional[str] = None,
        course_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        q = (rag_query or "").strip() or topic
        knowledge_context, kb_ids_used = await self._get_knowledge_context(q, kb_ids=kb_ids, top_k=8)
        mem = self._memory_lookup(student_id=student_id, query=q, limit=5)
        knowledge_context = self._inject_memory_context(base_context=knowledge_context or "", memory_items=mem["items"])
        rag_hits = self._estimate_rag_hits(knowledge_context)
        tool = GenerateSceneOutlineTool()
        res = await tool.call(
            self._ctx,
            topic=topic,
            audience=audience,
            duration_minutes=duration_minutes,
            style=style,
            knowledge_context=knowledge_context or "无",
            memory_context=(self._memory_service().build_memory_context(mem["items"]) if self._memory_service() else "无"),
        )
        scenes = res.get("scenes") or []
        run_id = course_run_id or str(uuid.uuid4())
        meta = {"memory_hits": mem["hits"], "memory_enabled": mem["enabled"], "rag_hits": rag_hits, "used_retry": False, "course_run_id": run_id}
        self._persist_course_snapshot(
            course_run_id=run_id,
            patch={"course_run_id": run_id, "topic": topic, "scene_outline": scenes},
        )
        return {"scenes": scenes, "kb_ids": kb_ids_used, "memory": mem, "meta": meta}

    async def generate_scene_questions(
        self,
        *,
        question: str,
        analysis: str,
        script: str,
        scenes: List[Dict[str, Any]],
        kb_ids: Optional[List[str]] = None,
        rag_query: Optional[str] = None,
        student_id: Optional[str] = None,
        course_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        scene_sets: List[Dict[str, Any]] = []
        merged: List[Dict[str, Any]] = []
        run_id = course_run_id or str(uuid.uuid4())
        for s in (scenes or []):
            if str(s.get("type", "")).lower() != "quiz":
                continue
            focus = str(s.get("focus", "")).strip() or "薄弱点巩固"
            title = str(s.get("title", "")).strip() or "随堂检测"
            count = int(s.get("questionCount", 3) or 3)
            r = await self.generate_questions(
                question=question,
                analysis=f"{analysis}\n\n[当前场景]\n标题：{title}\n重点：{focus}",
                script=script,
                kb_ids=kb_ids,
                rag_query=rag_query,
                student_id=student_id,
                course_run_id=run_id,
            )
            qs = r.get("questions") or []
            if len(qs) > count:
                qs = qs[:count]
            scene_sets.append(
                {
                    "scene_id": s.get("id"),
                    "scene_title": title,
                    "scene_focus": focus,
                    "question_count": len(qs),
                    "questions": qs,
                }
            )
            merged.extend(qs)
        self._persist_course_snapshot(
            course_run_id=run_id,
            patch={"course_run_id": run_id, "scene_question_sets": scene_sets},
        )
        return {
            "scene_question_sets": scene_sets,
            "questions": merged,
            "meta": {"course_run_id": run_id, "scene_count": len(scene_sets)},
        }
