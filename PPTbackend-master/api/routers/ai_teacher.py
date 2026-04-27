import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from api.response import APIResponse
from api.auth_utils import get_current_user_optional, log_student_question
from api.services.ai_teacher_service import AITeacherService
from models.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/ai_teacher",
    tags=["AI Teacher Assistant"],
    responses={404: {"description": "Not found"}},
)


def get_ai_teacher_service(request: Request) -> AITeacherService:
    svc = getattr(request.app.state, "ai_teacher_service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="AITeacherService not initialized")
    return svc


def _resolve_student_id(current_user) -> Optional[str]:
    if not current_user:
        return None
    uid = getattr(current_user, "id", None)
    if uid is None:
        return None
    return str(uid)


# 请求模型
class QuestionAnalysisRequest(BaseModel):
    question: str
    kb_ids: Optional[List[str]] = None
    rag_query: Optional[str] = None
    course_run_id: Optional[str] = None


class ScriptGenerationRequest(BaseModel):
    question: str
    analysis: str
    ppt_content: Optional[str] = None
    kb_ids: Optional[List[str]] = None
    rag_query: Optional[str] = None
    course_run_id: Optional[str] = None


class SlideScriptsRequest(BaseModel):
    question: str
    analysis: str
    slides: List[dict]
    kb_ids: Optional[List[str]] = None
    rag_query: Optional[str] = None
    course_run_id: Optional[str] = None


class QuestionGenerationRequest(BaseModel):
    question: str
    analysis: str
    script: str
    kb_ids: Optional[List[str]] = None
    rag_query: Optional[str] = None
    course_run_id: Optional[str] = None


class SceneOutlineRequest(BaseModel):
    topic: str
    audience: Optional[str] = "学生"
    duration_minutes: Optional[int] = 20
    style: Optional[str] = "互动讲解"
    kb_ids: Optional[List[str]] = None
    rag_query: Optional[str] = None
    course_run_id: Optional[str] = None


class SceneQuestionsRequest(BaseModel):
    question: str
    analysis: str
    script: str
    scenes: List[dict]
    kb_ids: Optional[List[str]] = None
    rag_query: Optional[str] = None
    course_run_id: Optional[str] = None


class QuestionItem(BaseModel):
    question: str
    type: str  # "choice" or "text"
    options: Optional[List[str]] = None
    correct_answer: str
    explanation: str


@router.post("/analyze_question", summary="分析学生问题")
async def analyze_question(
    request: QuestionAnalysisRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
    service: AITeacherService = Depends(get_ai_teacher_service),
):
    """分析学生提出的问题（OpenClaw：统一走 Tools 层）。"""
    try:
        result = await service.analyze_question(
            request.question,
            kb_ids=request.kb_ids,
            rag_query=request.rag_query,
            student_id=_resolve_student_id(current_user),
            course_run_id=request.course_run_id,
        )
        analysis = result.get("analysis", "")
        log_student_question(
            db,
            current_user,
            "ai_teacher",
            request.question,
            answer_summary=analysis[:500],
            kb_ids=result.get("kb_ids") or None,
        )
        return APIResponse.success(
            data={"analysis": analysis, "memory": result.get("memory") or {}, "meta": result.get("meta") or {}},
            message="问题解析完成",
        )
    except Exception as e:
        logger.error(f"问题解析失败: {e}", exc_info=True)
        return APIResponse.internal_error(message=f"问题解析失败: {str(e)}")


@router.post("/generate_script", summary="生成教学讲稿")
async def generate_script(
    request: ScriptGenerationRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
    service: AITeacherService = Depends(get_ai_teacher_service),
):
    """基于问题分析和PPT内容生成教学讲稿（OpenClaw：统一走 Tools 层）。"""
    try:
        result = await service.generate_script(
            request.question,
            request.analysis,
            request.ppt_content,
            kb_ids=request.kb_ids,
            rag_query=request.rag_query,
            student_id=_resolve_student_id(current_user),
            course_run_id=request.course_run_id,
        )
        script = result.get("script", "")
        log_student_question(
            db,
            current_user,
            "ai_teacher",
            request.question,
            answer_summary=script[:500],
            kb_ids=result.get("kb_ids") or None,
        )
        return APIResponse.success(
            data={"script": script, "memory": result.get("memory") or {}, "meta": result.get("meta") or {}},
            message="讲稿生成完成",
        )
    except Exception as e:
        logger.error(f"讲稿生成失败: {e}", exc_info=True)
        return APIResponse.internal_error(message=f"讲稿生成失败: {str(e)}")


@router.post("/generate_slide_scripts", summary="按页生成讲解稿（用于深入讲解）")
async def generate_slide_scripts(
    request: SlideScriptsRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
    service: AITeacherService = Depends(get_ai_teacher_service),
):
    try:
        result = await service.generate_slide_scripts(
            question=request.question,
            analysis=request.analysis,
            slides=request.slides or [],
            kb_ids=request.kb_ids,
            rag_query=request.rag_query,
            student_id=_resolve_student_id(current_user),
            course_run_id=request.course_run_id,
        )
        slides = result.get("slides") or []
        # 记录学情：写入 kb_ids，摘要可空（避免超长）
        log_student_question(
            db,
            current_user,
            "ai_teacher",
            request.question,
            answer_summary=None,
            kb_ids=result.get("kb_ids") or None,
        )
        return APIResponse.success(
            data={"slides": slides, "memory": result.get("memory") or {}, "meta": result.get("meta") or {}},
            message="逐页讲解稿生成完成",
        )
    except Exception as e:
        logger.error(f"逐页讲解稿生成失败: {e}", exc_info=True)
        return APIResponse.internal_error(message=f"逐页讲解稿生成失败: {str(e)}")

@router.post("/generate_questions", summary="生成练习题")
async def generate_questions(
    request: QuestionGenerationRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
    service: AITeacherService = Depends(get_ai_teacher_service),
):
    """基于学习内容和知识库生成练习题（OpenClaw：统一走 Tools 层）。"""
    try:
        result = await service.generate_questions(
            request.question,
            request.analysis,
            request.script,
            kb_ids=request.kb_ids,
            rag_query=request.rag_query,
            student_id=_resolve_student_id(current_user),
            course_run_id=request.course_run_id,
        )
        questions = result.get("questions") or []
        if not questions:
            log_student_question(
                db,
                current_user,
                "ai_teacher",
                request.question,
                answer_summary="题目生成失败：模型未返回可解析的结构化题目",
                kb_ids=result.get("kb_ids") or None,
            )
            raise HTTPException(
                status_code=422,
                detail="题目生成失败：模型未返回可解析的结构化题目，请重试或调整问题描述。"
            )
        log_student_question(
            db,
            current_user,
            "ai_teacher",
            request.question,
            answer_summary=str(questions)[:500],
            kb_ids=result.get("kb_ids") or None,
        )
        return {
            "success": True,
            "questions": questions,
            "memory": result.get("memory") or {},
            "meta": result.get("meta") or {},
            "message": "练习题生成完成",
        }
    except HTTPException:
        # 透传业务级错误状态码（如 422），避免被包装成 500
        raise
    except Exception as e:
        logger.error(f"练习题生成失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"练习题生成失败: {str(e)}")


@router.post("/get_advice", summary="获取教学建议")
async def get_advice(
    request: QuestionAnalysisRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
    service: AITeacherService = Depends(get_ai_teacher_service),
):
    """获取针对特定问题的教学建议（OpenClaw：统一走 Tools 层）。"""
    try:
        result = await service.get_advice(
            request.question,
            kb_ids=request.kb_ids,
            rag_query=request.rag_query,
            student_id=_resolve_student_id(current_user),
            course_run_id=request.course_run_id,
        )
        content = result.get("content", "")
        log_student_question(
            db,
            current_user,
            "ai_teacher",
            request.question,
            answer_summary=content[:500],
            kb_ids=result.get("kb_ids") or None,
        )
        return {
            "success": True,
            "content": content,
            "memory": result.get("memory") or {},
            "meta": result.get("meta") or {},
            "message": "教学建议生成完成",
        }
    except Exception as e:
        logger.error(f"教学建议生成失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"教学建议生成失败: {str(e)}") 


@router.post("/generate_scene_outline", summary="生成课堂场景大纲（slide/quiz）")
async def generate_scene_outline(
    request: SceneOutlineRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
    service: AITeacherService = Depends(get_ai_teacher_service),
):
    result = await service.generate_scene_outline(
        topic=request.topic,
        audience=request.audience or "学生",
        duration_minutes=request.duration_minutes or 20,
        style=request.style or "互动讲解",
        kb_ids=request.kb_ids,
        rag_query=request.rag_query,
        student_id=_resolve_student_id(current_user),
        course_run_id=request.course_run_id,
    )
    return APIResponse.success(
        data={
            "scenes": result.get("scenes") or [],
            "memory": result.get("memory") or {},
            "meta": result.get("meta") or {},
        },
        message="课堂场景大纲生成完成",
    )


@router.post("/generate_scene_questions", summary="按场景生成练习题")
async def generate_scene_questions(
    request: SceneQuestionsRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
    service: AITeacherService = Depends(get_ai_teacher_service),
):
    result = await service.generate_scene_questions(
        question=request.question,
        analysis=request.analysis,
        script=request.script,
        scenes=request.scenes or [],
        kb_ids=request.kb_ids,
        rag_query=request.rag_query,
        student_id=_resolve_student_id(current_user),
        course_run_id=request.course_run_id,
    )
    return APIResponse.success(
        data={
            "scene_question_sets": result.get("scene_question_sets") or [],
            "questions": result.get("questions") or [],
            "meta": result.get("meta") or {},
        },
        message="按场景练习题生成完成",
    )