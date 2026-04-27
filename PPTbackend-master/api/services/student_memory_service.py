from __future__ import annotations

import importlib
import json
import logging
import math
import os
import sqlite3
import sys
from datetime import datetime
import time
from pathlib import Path
from typing import List, Optional
import httpx

logger = logging.getLogger(__name__)


class StudentMemoryService:
    """学生长期记忆服务（优先使用 mem0，失败时自动降级为不可用）。"""

    def __init__(self) -> None:
        self._memory = None
        self.enabled = False
        self._mem0_search_enabled = True
        self._mem0_add_enabled = True
        self._mem0_backoff_until_ts = 0.0
        self._db_path = self._resolve_db_path()
        self._init_local_db()
        self._init_mem0()

    def _in_backoff(self) -> bool:
        return time.time() < self._mem0_backoff_until_ts

    def _activate_backoff(self, seconds: int = 900) -> None:
        # 默认 15 分钟冷却，避免每次请求都打到远程导致 429 重试风暴
        self._mem0_backoff_until_ts = time.time() + max(60, int(seconds))

    @staticmethod
    def _is_quota_error(err_text: str) -> bool:
        t = (err_text or "").lower()
        return ("insufficient_quota" in t) or ("429" in t) or ("rate limit" in t)

    @staticmethod
    def _is_access_denied_error(err_text: str) -> bool:
        t = (err_text or "").lower()
        return ("access_denied" in t) or ("403" in t) or ("access denied" in t)

    @staticmethod
    def _resolve_embedding_dimension(embedding_model: str) -> Optional[int]:
        """
        解析并校验 embedding 维度：
        - DashScope text-embedding-v3 仅支持 [64,128,256,512,768,1024]
        - 优先读取 MEM0_EMBEDDING_DIMENSION / MEM0_EMBEDDING_DIM
        - 未配置时，对 v3 默认使用 1024，避免 mem0 默认维度触发 400
        """
        valid_dims = {64, 128, 256, 512, 768, 1024}
        raw = (os.getenv("MEM0_EMBEDDING_DIMENSION") or os.getenv("MEM0_EMBEDDING_DIM") or "").strip()
        model = (embedding_model or "").strip().lower()

        if raw:
            try:
                dim = int(raw)
            except ValueError:
                logger.warning("StudentMemoryService: MEM0_EMBEDDING_DIMENSION 非法，忽略: %s", raw)
                dim = None
            if dim in valid_dims:
                return dim
            logger.warning("StudentMemoryService: embedding 维度 %s 不受支持，已回退默认。", raw)

        if "text-embedding-v3" in model:
            return 1024
        return None

    def _resolve_db_path(self) -> str:
        current = Path(__file__).resolve()
        project_root = current.parents[2]  # .../PPTbackend-master
        output_dir = project_root / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        return str(output_dir / "student_memory.sqlite3")

    def _init_local_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS student_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            # 自控 embedding 方案：本地存向量，检索走本地向量相似度
            cols = [r[1] for r in conn.execute("PRAGMA table_info(student_memories)").fetchall()]
            if "embedding" not in cols:
                conn.execute("ALTER TABLE student_memories ADD COLUMN embedding TEXT")
            if "embedding_model" not in cols:
                conn.execute("ALTER TABLE student_memories ADD COLUMN embedding_model TEXT")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_student_memories_user_created "
                "ON student_memories(user_id, created_at DESC)"
            )
            conn.commit()

    def _init_mem0(self) -> None:
        # 先尝试常规导入（pip install mem0ai）
        MemoryClass = self._import_mem0_memory()
        if MemoryClass is None:
            # 再尝试从本地仓库 mem0-main 导入（最小入侵，不依赖安装）
            self._append_local_mem0_path()
            MemoryClass = self._import_mem0_memory()

        if MemoryClass is None:
            logger.warning("StudentMemoryService: mem0 未找到，记忆功能已降级为关闭。")
            return

        try:
            self._memory = self._build_mem0_instance(MemoryClass)
            self.enabled = True
            logger.info("StudentMemoryService: mem0 初始化成功。")
        except Exception as e:
            logger.warning("StudentMemoryService: mem0 初始化失败，降级关闭: %s", e)
            self._memory = None
            self.enabled = False

    def _build_mem0_instance(self, MemoryClass):
        """按环境变量构建 mem0，避免默认 embedding 模型不兼容。"""
        embedding_model = (os.getenv("MEM0_EMBEDDING_MODEL") or "").strip()
        embedding_dimension = self._resolve_embedding_dimension(embedding_model)
        llm_model = (os.getenv("MEM0_LLM_MODEL") or os.getenv("AI_MODEL") or "").strip()
        # 允许 mem0 使用独立的 OpenAI 兼容网关与 Key，避免影响主业务模型链路
        api_key = (os.getenv("MEM0_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
        base_url = (os.getenv("MEM0_OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "").strip()

        logger.info(
            "StudentMemoryService: mem0 config resolved base_url=%s llm_model=%s embedding_model=%s embedding_dimension=%s key_set=%s",
            base_url or "(default)",
            llm_model or "(default)",
            embedding_model or "(default)",
            embedding_dimension if embedding_dimension is not None else "(default)",
            "yes" if bool(api_key) else "no",
        )

        # 未提供 mem0 专属模型时，沿用默认行为
        if not embedding_model and not llm_model:
            return MemoryClass()

        try:
            from mem0.configs.base import MemoryConfig
            from mem0.embeddings.configs import EmbedderConfig
            from mem0.llms.configs import LlmConfig

            embedder_config = {
                "model": embedding_model or "text-embedding-3-small",
                "api_key": api_key or None,
                "openai_base_url": base_url or None,
            }
            if embedding_dimension is not None:
                embedder_config["dimension"] = embedding_dimension
            embedder_cfg = EmbedderConfig(provider="openai", config=embedder_config)
            llm_cfg = LlmConfig(
                provider="openai",
                config={
                    "model": llm_model or "gpt-4.1-mini",
                    "api_key": api_key or None,
                    "openai_base_url": base_url or None,
                },
            )
            mem_cfg = MemoryConfig(embedder=embedder_cfg, llm=llm_cfg)
            return MemoryClass(config=mem_cfg)
        except Exception as e:
            logger.warning("StudentMemoryService: 使用自定义 mem0 配置失败，回退默认配置: %s", e)
            return MemoryClass()

    def _import_mem0_memory(self):
        try:
            mod = importlib.import_module("mem0")
            return getattr(mod, "Memory", None)
        except Exception:
            return None

    def _append_local_mem0_path(self) -> None:
        current = Path(__file__).resolve()
        # .../PPTbackend-master/api/services/student_memory_service.py
        # workspace root: .../ai-teach
        workspace_root = current.parents[3]
        local_mem0 = workspace_root / "mem0-main"
        if local_mem0.exists() and str(local_mem0) not in sys.path:
            sys.path.append(str(local_mem0))

    @staticmethod
    def _normalize_user_id(user_id: Optional[str]) -> Optional[str]:
        if not user_id:
            return None
        uid = str(user_id).strip()
        return uid or None

    def search_weakness_memories(
        self, *, user_id: Optional[str], query: str, limit: int = 3
    ) -> List[str]:
        uid = self._normalize_user_id(user_id)
        if not uid:
            return []
        local_items = self._search_local_memories(user_id=uid, query=query, limit=limit)
        merged: List[str] = []
        seen = set()
        # 工程方案：检索只走本地（embedding + 关键词），不依赖 mem0 embedding
        for text in local_items:
            key = text.strip()
            if key and key not in seen:
                seen.add(key)
                merged.append(key)
            if len(merged) >= limit:
                break
        return merged

    def add_weakness_memory(self, *, user_id: Optional[str], memory_text: str) -> bool:
        uid = self._normalize_user_id(user_id)
        text = (memory_text or "").strip()
        if not uid or not text:
            return False
        local_ok = self._add_local_memory(user_id=uid, memory_text=text)
        remote_ok = False
        if self.enabled and self._memory and self._mem0_add_enabled and not self._in_backoff():
            try:
                # mem0 v1: add(messages=[...], user_id=...)
                self._memory.add(
                    messages=[{"role": "user", "content": text}],
                    user_id=uid,
                )
                remote_ok = True
            except Exception as e:
                msg = str(e)
                if "unexpected keyword argument" in msg or "model_not_found" in msg or "404" in msg:
                    self._mem0_add_enabled = False
                    logger.warning("StudentMemoryService: mem0 写入已自动禁用（接口/模型不可用）。")
                elif self._is_access_denied_error(msg):
                    self._mem0_add_enabled = False
                    self._activate_backoff(1800)
                    logger.warning("StudentMemoryService: mem0 写入已自动禁用（远程权限不足，30分钟后再试）。")
                elif self._is_quota_error(msg):
                    self._activate_backoff(1200)
                    logger.warning("StudentMemoryService: mem0 写入触发配额限制，已进入本地模式冷却 20 分钟。")
                else:
                    logger.warning("StudentMemoryService: 写入记忆失败: %s", e)
        return local_ok or remote_ok

    def _add_local_memory(self, *, user_id: str, memory_text: str) -> bool:
        try:
            vec = self._embed_text(memory_text)
            vec_json = json.dumps(vec) if vec else None
            emb_model = (os.getenv("MEM0_EMBEDDING_MODEL") or "text-embedding-v3").strip()
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "INSERT INTO student_memories(user_id, content, created_at, embedding, embedding_model) VALUES(?, ?, ?, ?, ?)",
                    (user_id, memory_text, datetime.utcnow().isoformat(), vec_json, emb_model),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.warning("StudentMemoryService: 本地写入记忆失败: %s", e)
            return False

    def _search_local_memories(self, *, user_id: str, query: str, limit: int) -> List[str]:
        q = (query or "").strip()
        tokens = [t for t in q.replace("，", " ").replace("。", " ").split() if len(t) >= 2][:6]
        try:
            q_vec = self._embed_text(q) if q else None
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute(
                    "SELECT content, embedding FROM student_memories WHERE user_id=? ORDER BY created_at DESC LIMIT 80",
                    (user_id,),
                ).fetchall()
            candidates = []
            for r in rows:
                if not r:
                    continue
                text = str(r[0]).strip()
                if not text:
                    continue
                emb = None
                if len(r) > 1 and r[1]:
                    try:
                        emb = json.loads(r[1])
                    except Exception:
                        emb = None
                candidates.append((text, emb))
            if not candidates:
                return []
            # 简单相关性：命中词数量 + 新近性（列表前面的优先）
            scored = []
            for idx, (text, emb) in enumerate(candidates):
                score = 0
                # 向量相似度主导（你自控 embedding）
                if q_vec and emb:
                    sim = self._cosine_similarity(q_vec, emb)
                    score += max(0.0, sim) * 10.0
                for t in tokens:
                    if t in text:
                        score += 2
                if q and q in text:
                    score += 3
                score += max(0, 10 - idx // 5)
                scored.append((score, text))
            scored.sort(key=lambda x: x[0], reverse=True)
            out: List[str] = []
            seen = set()
            for score, text in scored:
                if score <= 0:
                    continue
                if text not in seen:
                    seen.add(text)
                    out.append(text)
                if len(out) >= limit:
                    break
            if out:
                return out
            return [text for text, _ in candidates[:limit]]
        except Exception as e:
            logger.warning("StudentMemoryService: 本地查询记忆失败: %s", e)
            return []

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = 0.0
        na = 0.0
        nb = 0.0
        for x, y in zip(a, b):
            dot += x * y
            na += x * x
            nb += y * y
        if na <= 0.0 or nb <= 0.0:
            return 0.0
        return dot / (math.sqrt(na) * math.sqrt(nb))

    def _embed_text(self, text: str) -> Optional[List[float]]:
        """
        工程方案：由我们自己调用 embeddings 接口，不依赖 mem0 的 embedding。
        """
        raw = (text or "").strip()
        if not raw:
            return None
        api_key = (os.getenv("MEM0_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
        base_url = (os.getenv("MEM0_OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "").strip().rstrip("/")
        model = (os.getenv("MEM0_EMBEDDING_MODEL") or "text-embedding-v3").strip()
        if not api_key or not base_url:
            return None

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "input": raw}
        dim = self._resolve_embedding_dimension(model)
        if dim is not None:
            # OpenAI 兼容字段
            payload["dimensions"] = dim
        url = f"{base_url}/embeddings"

        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(url, json=payload, headers=headers)
            if resp.status_code >= 400 and "dimensions" in payload:
                # 兼容部分网关不接受 dimensions 字段：降级重试一次
                payload.pop("dimensions", None)
                with httpx.Client(timeout=20.0) as client:
                    resp = client.post(url, json=payload, headers=headers)
            if resp.status_code >= 400:
                logger.warning("StudentMemoryService: 自控 embedding 调用失败 status=%s body=%s", resp.status_code, resp.text[:300])
                return None
            data = resp.json() or {}
            arr = (data.get("data") or [])
            if not arr:
                return None
            emb = (arr[0] or {}).get("embedding")
            if not isinstance(emb, list) or not emb:
                return None
            return [float(x) for x in emb]
        except Exception as e:
            logger.warning("StudentMemoryService: 自控 embedding 调用异常: %s", e)
            return None

    @staticmethod
    def build_memory_context(memories: List[str]) -> str:
        if not memories:
            return ""
        joined = "\n".join(f"- {m}" for m in memories[:5])
        return f"""【该学生历史薄弱点记忆（长期）】
{joined}

请在生成内容时优先针对上述薄弱点进行强化，做到有针对性的讲解与练习。"""

    @staticmethod
    def summarize_analysis_to_memory(question: str, analysis: str) -> str:
        q = (question or "").strip()
        a = (analysis or "").strip().replace("\n", " ")
        if len(a) > 280:
            a = a[:280] + "..."
        return f"学生提问：{q}。本次分析提示其可能薄弱点/误区：{a}"

    @staticmethod
    def summarize_questions_to_memory(question: str, questions: List[dict]) -> str:
        q = (question or "").strip()
        sample = []
        for item in (questions or [])[:3]:
            title = str((item or {}).get("question", "")).strip()
            if title:
                sample.append(title[:40])
        detail = "；".join(sample) if sample else "已生成针对性练习题"
        return f"围绕学生提问“{q}”已生成练习题，重点覆盖：{detail}"

    @staticmethod
    def summarize_advice_to_memory(question: str, advice: str) -> str:
        q = (question or "").strip()
        a = (advice or "").strip().replace("\n", " ")
        if len(a) > 280:
            a = a[:280] + "..."
        return f"针对提问“{q}”的学习反馈显示：{a}"

