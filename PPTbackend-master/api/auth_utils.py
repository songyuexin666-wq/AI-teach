# -*- coding: utf-8 -*-
"""JWT 签发与解析，用于学情分析等需要当前用户的接口。"""
import json as _json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, List, Any

from fastapi import Request, Depends
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from models.database import get_db
from models.user import User

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "ai-teach-default-secret-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))  # 7 days


def create_access_token(user: User) -> str:
    """登录成功后签发 JWT，payload 含 user_id, username, role, major。"""
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": user.id,
        "username": user.username,
        "role": user.role or "student",
        "major": user.major or "",
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """解析 Bearer token，失败返回 None。"""
    if not token or not token.strip():
        return None
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """
    解析当前用户，与整站登录方式一致：
    1) 优先从 Authorization: Bearer <token> 按 JWT 解析出 user_id，再查库；
    2) 若 token 不是有效 JWT（如其他认证服务下发的简单 token），则从请求头 X-User-Id 取用户 id 并查库。
    这样学情分析与信息管理/角色管理等页面共用同一套登录态，不再因 token 形态不同而 401。
    """
    auth = request.headers.get("Authorization")
    token = (auth[7:].strip() if auth and auth.startswith("Bearer ") else "") or None
    user_id = None

    if token:
        payload = decode_token(token)
        if payload and "sub" in payload:
            try:
                sub = payload.get("sub")
                user_id = int(sub) if not isinstance(sub, int) else sub
            except (TypeError, ValueError):
                pass

    if user_id is None:
        # 与前端约定：登录后请求可带 X-User-Id（来自 localStorage 的 user.userId / user.id）
        raw = request.headers.get("X-User-Id") or request.headers.get("x-user-id")
        if raw is not None and str(raw).strip():
            try:
                user_id = int(raw)
            except (TypeError, ValueError):
                pass

    if user_id is None:
        return None
    user = db.query(User).filter(User.id == user_id).first()
    return user


def log_student_question(
    db: Session,
    user: Optional[User],
    question_type: str,
    question_content: str,
    answer_summary: Optional[str] = None,
    course: Optional[str] = None,
    kb_ids: Optional[List[Any]] = None,
    conversation_id: Optional[str] = None,
) -> None:
    """学情分析：写入一条学生提问记录（kb_qa/chat/ai_teacher/quick_qa 等统一调用）。"""
    if not user or not getattr(user, "id", None):
        return
    try:
        from models.student_question_log import StudentQuestionLog
        log = StudentQuestionLog(
            user_id=user.id,
            major=(getattr(user, "major", None) or "").strip(),
            course=(course or "").strip() or None,
            question_type=question_type,
            question_content=(question_content or "")[:8000],
            answer_summary=(answer_summary or "")[:2000] if answer_summary else None,
            kb_ids=_json.dumps(kb_ids) if kb_ids else None,
            conversation_id=(conversation_id or "").strip()[:64] or None,
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.warning("学情记录(%s)写入失败: %s", question_type, e)
        if db:
            db.rollback()
