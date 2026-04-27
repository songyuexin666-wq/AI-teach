import logging
import sys
from contextlib import asynccontextmanager
from typing import Optional

import httpx
import uvicorn
from fastapi import FastAPI, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.agents.registry import AgentRegistry
from api.chat_service import ChatService
from api.services.ai_teacher_service import AITeacherService
from api.services.student_memory_service import StudentMemoryService
from api.local_ppt_generator import LocalPPTGenerator
from api.rag_service import RAGService
from api.routers import chat, media, ppt, rag, ai_teacher, dashboard, major_info, teach_designs, papers, system_manage, roles, login_logs, kb_mapping, chat_scenes, learning_analytics, agent_router
from api.text_to_speech import TextToSpeechService
from api.video_generator import VideoGenerator
import os
from models.database import Base, engine, get_db
from models.user import User
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from fastapi import Depends
from api.auth import router as auth_router

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)
# --- End Logging Configuration ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理器。
    在应用启动时，初始化所有服务并将其存储在 app.state 中。
    """
    logger.info("--- 应用启动: 正在初始化服务... ---")
    
    # 将服务实例存储在 app.state 中，以便通过依赖注入访问
    # 尝试初始化RAGService，如果失败则跳过
    try:
        app.state.rag_service = RAGService()
        logger.info("RAGService 初始化成功")
    except Exception as e:
        logger.warning(f"RAGService 初始化失败，知识库管理功能将不可用: {e}")
        app.state.rag_service = None
    
    # 初始化本地PPT生成器
    try:
        import openai
        # 设置默认的OpenAI配置
        api_key = os.getenv("OPENAI_API_KEY", "sk-default-key")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        ai_model = os.getenv("AI_MODEL", "qwen-long")
        
        openai_client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        app.state.ppt_generator = LocalPPTGenerator(openai_client=openai_client, ai_model=ai_model)
        logger.info(f"LocalPPTGenerator 初始化成功 (Model: {ai_model})")
    except Exception as e:
        logger.warning(f"LocalPPTGenerator 初始化失败，将使用fallback模式: {e}")
        app.state.ppt_generator = LocalPPTGenerator()
    
    # 初始化视频生成器（注入 openai_client 以便生成 Manim 代码）
    ai_model = os.getenv("AI_MODEL", "qwen-long")
    try:
        import openai
        _api_key = os.getenv("OPENAI_API_KEY", "sk-default-key")
        _base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        _openai_client = openai.OpenAI(api_key=_api_key, base_url=_base_url)
        app.state.video_generator = VideoGenerator(openai_client=_openai_client, ai_model=ai_model)
    except Exception as e:
        logger.warning(f"VideoGenerator 使用无 OpenAI 客户端模式: {e}")
        app.state.video_generator = VideoGenerator(ai_model=ai_model)
    app.state.tts_service = TextToSpeechService()
    
    # 尝试初始化ChatService，如果失败则跳过
    try:
        app.state.chat_service = ChatService()
        logger.info("ChatService 初始化成功")
    except Exception as e:
        logger.warning(f"ChatService 初始化失败，聊天功能将不可用: {e}")
        app.state.chat_service = None

    app.state.agent_registry = AgentRegistry(
        services={
            "rag_service": app.state.rag_service,
            "chat_service": app.state.chat_service,
            "ppt_generator": app.state.ppt_generator,
            "video_generator": app.state.video_generator,
            "tts_service": app.state.tts_service,
        }
    )
    logger.info("AgentRegistry 初始化成功")

    # OpenClaw：AI 教师能力统一服务层（REST 与 Agent 共用同一套 Tools）
    app.state.student_memory_service = StudentMemoryService()
    app.state.ai_teacher_service = AITeacherService(
        services={
            "rag_service": app.state.rag_service,
            "student_memory_service": app.state.student_memory_service,
        }
    )
    logger.info("AITeacherService 初始化成功")
    
    app.state.http_client = httpx.AsyncClient(timeout=300.0)
    
    yield
    
    # 应用关闭时清理 httpx 客户端
    await app.state.http_client.aclose()
    logger.info("--- 应用已关闭 ---")


app = FastAPI(
    title="智能PPT生成系统", 
    version="1.0.0",
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含模块化路由
app.include_router(ppt.router)
app.include_router(rag.router)
app.include_router(chat.router)
app.include_router(media.router)
app.include_router(auth_router)
app.include_router(ai_teacher.router)
app.include_router(dashboard.router)
app.include_router(major_info.router)
app.include_router(teach_designs.router)
app.include_router(papers.router)
app.include_router(system_manage.router)
app.include_router(roles.router)
app.include_router(login_logs.router)
app.include_router(kb_mapping.router)
app.include_router(chat_scenes.router)
app.include_router(learning_analytics.router)
app.include_router(agent_router.router)

# 导入所有模型以便 create_all 建表（含课程-知识库映射、场景-chat 映射、学情分析）
from models.kb_dataset_mapping import KbDatasetMapping  # noqa: F401
from models.chat_assistant_scene import ChatAssistantScene  # noqa: F401
from models.student_question_log import StudentQuestionLog  # noqa: F401
from models.learning_analytics_report import LearningAnalyticsReport  # noqa: F401
# 创建所有表（自动建表，避免循环导入）
Base.metadata.create_all(bind=engine)

# 兼容升级：为 student_question_logs 增加 conversation_id 列（若不存在）
try:
    inspector = inspect(engine)
    if "student_question_logs" in inspector.get_table_names():
        cols = {c.get("name") for c in inspector.get_columns("student_question_logs")}
        if "conversation_id" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE student_question_logs ADD COLUMN conversation_id VARCHAR(64) NULL"))
                conn.execute(text("CREATE INDEX ix_student_question_logs_conversation_id ON student_question_logs (conversation_id)"))
            logger.info("已为 student_question_logs 补充 conversation_id 列")
except Exception as e:
    logger.warning(f"补充 student_question_logs.conversation_id 失败: {e}")

@app.get("/")
async def root():
    return {"message": "智能教师系统API", "version": "1.0.0"}


@app.get("/api/health", summary="健康检查（含 RAGFlow 可选探测）")
async def health_check(request: Request):
    """业务后端健康；若配置了 RAGFlow 则探测其可用性。"""
    status = {"status": "ok", "service": "ai-teach-backend"}
    rag_ok = None
    if getattr(request.app.state, "rag_service", None):
        try:
            request.app.state.rag_service.rag_client.list_datasets(page=1, page_size=1)
            rag_ok = True
        except Exception as e:
            logger.warning(f"RAGFlow 探测失败: {e}")
            rag_ok = False
        status["ragflow"] = "ok" if rag_ok else "unavailable"
    return status

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=7878, 
        log_level="info",
        reload=True
    ) 
