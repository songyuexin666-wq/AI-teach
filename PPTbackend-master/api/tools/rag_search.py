from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from models.database import SessionLocal
from models.kb_dataset_mapping import KbDatasetMapping

from api.tools.base import BaseTool, ToolContext


class RAGSearchTool(BaseTool):
    name = "rag_search"
    description = "Search course knowledge bases and return relevant context for downstream agent steps."

    def _resolve_kb_ids(self, *, course_id=None, subject=None, grade=None, teacher_id=None) -> List[str]:
        db = SessionLocal()
        try:
            query = db.query(KbDatasetMapping)
            if course_id:
                query = query.filter(KbDatasetMapping.course_id == str(course_id))
            if subject:
                query = query.filter(KbDatasetMapping.subject == str(subject))
            if grade:
                query = query.filter(KbDatasetMapping.grade == str(grade))
            if teacher_id:
                query = query.filter(KbDatasetMapping.teacher_id == str(teacher_id))

            return [
                item.ragflow_dataset_id
                for item in query.all()
                if getattr(item, "ragflow_dataset_id", None)
            ]
        finally:
            db.close()

    async def call(self, context: ToolContext, **kwargs) -> Dict[str, Any]:
        rag_service = context.services.get("rag_service")
        if rag_service is None:
            return {
                "kb_ids": [],
                "results": [],
                "context_text": "",
                "source": "rag_service_unavailable",
            }

        query = (kwargs.get("query") or "").strip()
        if not query:
            return {"kb_ids": [], "results": [], "context_text": "", "source": "empty_query"}

        kb_ids = list(kwargs.get("kb_ids") or [])
        source = "metadata"

        if not kb_ids:
            kb_ids = self._resolve_kb_ids(
                course_id=kwargs.get("course_id"),
                subject=kwargs.get("subject"),
                grade=kwargs.get("grade"),
                teacher_id=kwargs.get("teacher_id"),
            )
            source = "mapping"

        if not kb_ids:
            try:
                knowledge_bases = await asyncio.to_thread(rag_service.list_knowledge_bases)
                kb_ids = [item["id"] for item in knowledge_bases if item.get("id")]
                source = "all_kbs"
            except Exception:
                kb_ids = []

        if not kb_ids:
            return {"kb_ids": [], "results": [], "context_text": "", "source": "no_kb_available"}

        top_k = int(kwargs.get("top_k", 5) or 5)
        similarity_threshold = float(kwargs.get("similarity_threshold", 0.2) or 0.2)

        try:
            results = await asyncio.to_thread(
                rag_service.search,
                query=query,
                kb_ids=kb_ids,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
            )
        except Exception as exc:
            return {
                "kb_ids": kb_ids,
                "results": [],
                "context_text": "",
                "source": source,
                "error": str(exc),
            }

        context_lines = []
        for index, item in enumerate(results, start=1):
            content = (item.get("content") or "").strip()
            if not content:
                continue

            title = item.get("document_name") or item.get("document_id") or item.get("dataset_id") or "knowledge"
            similarity = item.get("similarity")
            prefix = f"{index}. [{title}]"
            if similarity is not None:
                prefix += f" (similarity={similarity})"
            context_lines.append(f"{prefix}\n{content}")

        return {
            "kb_ids": kb_ids,
            "results": results,
            "context_text": "\n\n".join(context_lines),
            "source": source,
        }
