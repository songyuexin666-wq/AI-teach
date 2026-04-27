# -*- coding: utf-8 -*-
"""
学情分析：学生提问按专业/课程记录，大模型分析薄弱章节与题型，反馈给教师/管理员。

鉴权与数据范围：
- 所有接口均通过 Authorization: Bearer <JWT> 解析当前用户（get_current_user_optional）。
- GET /majors、GET /reports：未登录或非教师/管理员时返回 401/403。
- 其余接口（GET /courses、/questions，POST /report，GET /reports/{id}）：未登录或非教师/管理员时返回 401/403。
- 教师：仅能查看/生成本专业数据；专业列表只返回当前用户的任教专业（来自用户信息，与是否有提问记录无关）。
- 管理员：可查看/生成全部专业；专业列表仅来自「信息管理」中的专业（MajorInfo 表），不合并提问记录或用户表。
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, List

import openai
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from models.database import get_db
from models.user import User
from models.student_question_log import StudentQuestionLog
from models.learning_analytics_report import LearningAnalyticsReport
from models.kb_dataset_mapping import KbDatasetMapping
from models.major_info import MajorInfo
from api.auth_utils import get_current_user_optional
from models.schemas import LogQuestionRequest, GenerateReportRequest

logger = logging.getLogger(__name__)


def _get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("AI_MODEL", "qwen-turbo")
    if not api_key:
        return None, None
    return openai.OpenAI(api_key=api_key, base_url=base_url), model


def _require_teacher_or_admin(user: Optional[User]) -> User:
    """学情分析仅允许教师或管理员访问；管理员可看全部专业，教师仅能看本专业。"""
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    if user.role not in ("teacher", "admin"):
        raise HTTPException(status_code=403, detail="仅教师或管理员可进行学情分析")
    return user


router = APIRouter(
    prefix="/api/learning-analytics",
    tags=["Learning Analytics"],
    responses={404: {"description": "Not found"}},
)


@router.post("/log", summary="记录一条学生提问（可选，kb_qa/chat 内也会自动记录）")
async def log_question(
    body: LogQuestionRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """若请求带有效 token，则按当前用户专业写入一条提问记录。"""
    if not current_user:
        return {"success": True, "message": "未登录，已跳过记录"}
    if body.question_type not in ("kb_qa", "chat", "ai_teacher", "quick_qa"):
        return {"success": False, "message": "question_type 不合法"}
    try:
        log = StudentQuestionLog(
            user_id=current_user.id,
            major=current_user.major or "",
            course=body.course,
            question_type=body.question_type,
            question_content=(body.question_content or "")[:8000],
            kb_ids=json.dumps(body.kb_ids) if body.kb_ids else None,
        )
        db.add(log)
        db.commit()
        return {"success": True, "message": "已记录"}
    except Exception as e:
        logger.exception("记录提问失败")
        db.rollback()
        return {"success": False, "message": str(e)}


def _infer_course_from_kb_ids(db: Session, kb_ids: List[str]) -> Optional[str]:
    """根据知识库 ID 从映射表推断课程名（取第一个匹配的 name 或 subject）。"""
    if not kb_ids:
        return None
    mapping = (
        db.query(KbDatasetMapping)
        .filter(KbDatasetMapping.ragflow_dataset_id.in_(kb_ids))
        .first()
    )
    if mapping:
        return mapping.name or mapping.subject
    return None


@router.get("/majors", summary="获取专业列表（教师仅本专业，管理员为信息管理中的全部专业）")
async def list_majors(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    user = _require_teacher_or_admin(current_user)
    if user.role == "teacher":
        # 教师：只返回当前用户的任教专业（来自用户信息）
        major_strip = (user.major or "").strip()
        major_list = [major_strip] if major_strip else []
    else:
        # 管理员：仅「信息管理」中的专业（MajorInfo 表）
        rows = db.query(MajorInfo.major_name).filter(MajorInfo.major_name.isnot(None), MajorInfo.major_name != "").distinct().all()
        major_list = sorted(r[0] for r in rows if r[0])
    return {"success": True, "data": major_list}


@router.get("/courses", summary="获取某专业下的课程列表（教师=注册课程+有提问记录的课程，管理员=有提问记录的课程）")
async def list_courses(
    major: str = Query(..., description="专业名称"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    user = _require_teacher_or_admin(current_user)
    if user.role == "teacher" and (user.major or "").strip() and user.major.strip() != major:
        raise HTTPException(status_code=403, detail="只能查看本专业数据")
    from_logs = (
        db.query(StudentQuestionLog.course)
        .filter(StudentQuestionLog.major == major, StudentQuestionLog.course.isnot(None), StudentQuestionLog.course != "")
        .distinct()
    )
    course_set = {r[0] for r in from_logs.all() if r[0]}
    if user.role == "teacher" and (user.major or "").strip() == major:
        teacher_courses = []
        if getattr(user, "courses", None) and user.courses:
            try:
                teacher_courses = json.loads(user.courses) if isinstance(user.courses, str) else (user.courses or [])
            except Exception:
                pass
        for c in teacher_courses:
            if c and str(c).strip():
                course_set.add(str(c).strip())
    return {"success": True, "data": sorted(course_set)}


@router.get("/questions", summary="聚合查询提问（教师仅本专业）")
async def list_questions(
    major: str = Query(...),
    course: Optional[str] = Query(None),
    time_start: Optional[str] = Query(None, description="ISO datetime"),
    time_end: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    user = _require_teacher_or_admin(current_user)
    if user.role == "teacher" and (user.major or "").strip() != major:
        raise HTTPException(status_code=403, detail="只能查看本专业数据")
    q = db.query(StudentQuestionLog).filter(StudentQuestionLog.major == major)
    if course:
        q = q.filter(StudentQuestionLog.course == course)
    if time_start:
        try:
            q = q.filter(StudentQuestionLog.created_at >= datetime.fromisoformat(time_start.replace("Z", "+00:00")))
        except Exception:
            pass
    if time_end:
        try:
            q = q.filter(StudentQuestionLog.created_at <= datetime.fromisoformat(time_end.replace("Z", "+00:00")))
        except Exception:
            pass
    q = q.order_by(StudentQuestionLog.created_at.desc()).limit(500)
    logs = q.all()
    return {
        "success": True,
        "data": [
            {
                "id": l.id,
                "user_id": l.user_id,
                "major": l.major,
                "course": l.course,
                "question_type": l.question_type,
                "question_content": (l.question_content or "")[:500],
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ],
        "total": len(logs),
    }


@router.post("/report", summary="生成学情分析报告（大模型分析薄弱章节与题型）")
async def generate_report(
    body: GenerateReportRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    user = _require_teacher_or_admin(current_user)
    if user.role == "teacher" and (user.major or "").strip() and user.major.strip() != body.major:
        raise HTTPException(status_code=403, detail="只能生成本专业学情报告")

    time_start = None
    time_end = None
    if body.time_range_start:
        try:
            time_start = datetime.fromisoformat(body.time_range_start.replace("Z", "+00:00"))
        except Exception:
            pass
    if body.time_range_end:
        try:
            time_end = datetime.fromisoformat(body.time_range_end.replace("Z", "+00:00"))
        except Exception:
            pass
    if not time_end:
        time_end = datetime.utcnow()
    if not time_start:
        time_start = time_end - timedelta(days=30)

    q = db.query(StudentQuestionLog).filter(
        StudentQuestionLog.major == body.major,
        StudentQuestionLog.created_at >= time_start,
        StudentQuestionLog.created_at <= time_end,
    )
    if body.course:
        q = q.filter(StudentQuestionLog.course == body.course)
    logs = q.order_by(StudentQuestionLog.created_at.desc()).limit(1000).all()
    if not logs:
        raise HTTPException(status_code=400, detail="该条件下暂无提问数据，无法生成学情分析")

    # 聚合统计
    by_type = {}
    samples = []
    for l in logs:
        by_type[l.question_type] = by_type.get(l.question_type, 0) + 1
        if len(samples) < 80:
            samples.append({"type": l.question_type, "course": l.course, "content": (l.question_content or "")[:300]})

    client, model = _get_openai_client()
    if not client:
        raise HTTPException(status_code=503, detail="大模型未配置，无法生成学情分析")

    prompt = f"""你是一位教学督导专家。请根据以下「学生提问记录」的统计与抽样，撰写一份简明的**学情分析报告**（面向教师），用中文 Markdown 格式。

【统计】
- 专业：{body.major}
- 课程：{body.course or "全部"}
- 时间范围：{time_start.date()} 至 {time_end.date()}
- 总提问数：{len(logs)}
- 按来源分布：{json.dumps(by_type, ensure_ascii=False)}

【抽样提问（供判断薄弱点）】
{json.dumps(samples, ensure_ascii=False, indent=2)[:6000]}

请从报告中包含：
1. **整体情况**：提问量、主要来源（知识库问答/聊天/教师助手等）。
2. **薄弱环节推断**：根据提问内容推断学生普遍不会的知识点、章节或题型（若能从抽样中看出）。
3. **教学建议**：给教师的 2～4 条具体建议（如加强某章节讲解、补充某类练习题等）。

报告控制在 800 字以内，条理清晰，便于教师快速阅读。"""

    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.5,
        )
        report_content = (response.choices[0].message.content or "").strip()
    except Exception as e:
        logger.exception("学情分析大模型调用失败")
        raise HTTPException(status_code=500, detail=f"生成报告失败: {str(e)}")

    report = LearningAnalyticsReport(
        major=body.major,
        course=body.course,
        report_content=report_content,
        time_range_start=time_start,
        time_range_end=time_end,
        question_count=len(logs),
        generated_by_user_id=user.id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {
        "success": True,
        "data": {
            "id": report.id,
            "major": report.major,
            "course": report.course,
            "report_content": report.report_content,
            "question_count": report.question_count,
            "time_range_start": report.time_range_start.isoformat() if report.time_range_start else None,
            "time_range_end": report.time_range_end.isoformat() if report.time_range_end else None,
            "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        },
        "message": "学情分析报告已生成",
    }


@router.get("/reports", summary="获取学情分析报告列表")
async def list_reports(
    major: Optional[str] = Query(None),
    course: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    user = _require_teacher_or_admin(current_user)
    q = db.query(LearningAnalyticsReport).order_by(LearningAnalyticsReport.generated_at.desc())
    if user.role == "teacher" and (user.major or "").strip():
        q = q.filter(LearningAnalyticsReport.major == user.major.strip())
    elif major:
        q = q.filter(LearningAnalyticsReport.major == major)
    if course:
        q = q.filter(LearningAnalyticsReport.course == course)
    reports = q.limit(50).all()
    return {
        "success": True,
        "data": [
            {
                "id": r.id,
                "major": r.major,
                "course": r.course,
                "question_count": r.question_count,
                "generated_at": r.generated_at.isoformat() if r.generated_at else None,
            }
            for r in reports
        ],
    }


@router.get("/reports/{report_id}", summary="获取单条学情分析报告详情")
async def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    user = _require_teacher_or_admin(current_user)
    report = db.query(LearningAnalyticsReport).filter(LearningAnalyticsReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    if user.role == "teacher" and (user.major or "").strip() != (report.major or "").strip():
        raise HTTPException(status_code=403, detail="只能查看本专业报告")
    return {
        "success": True,
        "data": {
            "id": report.id,
            "major": report.major,
            "course": report.course,
            "report_content": report.report_content,
            "question_count": report.question_count,
            "time_range_start": report.time_range_start.isoformat() if report.time_range_start else None,
            "time_range_end": report.time_range_end.isoformat() if report.time_range_end else None,
            "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        },
    }
