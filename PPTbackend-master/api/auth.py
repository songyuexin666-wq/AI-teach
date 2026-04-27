import asyncio
import json
import logging
import os

import openai
import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.user import User
from models.database import get_db
from api.auth_utils import create_access_token, get_current_user_optional, log_student_question

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Auth & QA"])

class LoginRequest(BaseModel):
    username: str
    password: str
    role: str = None  # 设为可选，登录时不再验证角色
    college: str = None
    major: str = None

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "student"
    name: str = None
    college: str = None
    major: str = None
    courses: list = None  # 教师可选：任教课程列表，可多填

class QARequest(BaseModel):
    question: str


class KbQARequest(BaseModel):
    question: str
    kb_ids: list = []
    conversation_id: str | None = None


def _get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("AI_MODEL", "qwen-plus")
    if not api_key:
        return None, None, "OPENAI_API_KEY not configured"
    return openai.OpenAI(api_key=api_key, base_url=base_url), model, None


@router.post("/qa/kb_qa", summary="知识库问答")
async def kb_qa(request: KbQARequest, req: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user_optional)):
    client, model, err = _get_openai_client()
    if err or not client:
        return {"success": False, "message": err or "大模型未配置", "answer": None}
    context = ""
    rag_service = getattr(req.app.state, "rag_service", None)
    if rag_service and request.kb_ids:
        try:
            chunks = await asyncio.to_thread(
                rag_service.search,
                query=request.question,
                kb_ids=request.kb_ids,
                top_k=5,
                similarity_threshold=0.2,
            )
            if chunks:
                context = "\n\n".join([c.get("content", "") or "" for c in chunks])
        except Exception as e:
            logger.warning(f"知识库检索失败: {e}")
    system_content = (
        "你是一个教学助手。请严格基于以下「参考内容」回答用户问题；若参考内容中无相关答案，可说明并简要补充。用中文回答。\n\n【参考内容】\n" + context
        if context
        else "你是一个教学助手。请用中文友好、简洁地回答用户问题。"
    )
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": request.question},
            ],
            max_tokens=2000,
            temperature=0.5,
        )
        answer = (response.choices[0].message.content or "").strip()
        # 学情分析：记录学生提问（按专业/课程）
        if current_user:
            course = None
            if request.kb_ids:
                from models.kb_dataset_mapping import KbDatasetMapping
                m = db.query(KbDatasetMapping).filter(KbDatasetMapping.ragflow_dataset_id.in_(request.kb_ids)).first()
                if m:
                    course = (m.name or m.subject or "").strip() or None
            log_student_question(
                db,
                current_user,
                "kb_qa",
                request.question,
                answer_summary=answer[:500],
                course=course,
                kb_ids=request.kb_ids,
                conversation_id=request.conversation_id,
            )
        return {"success": True, "answer": answer}
    except Exception as e:
        logger.error(f"知识库问答失败: {e}", exc_info=True)
        return {"success": False, "message": str(e), "answer": None}


@router.post("/qa/kb_qa_stream", summary="知识库问答（SSE流式）")
def kb_qa_stream(request: KbQARequest, req: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user_optional)):
    client, model, err = _get_openai_client()
    if err or not client:
        def err_stream():
            payload = {"type": "error", "message": err or "大模型未配置"}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield "data: {\"type\":\"done\"}\n\n"
        return StreamingResponse(err_stream(), media_type="text/event-stream")

    context = ""
    rag_service = getattr(req.app.state, "rag_service", None)
    if rag_service and request.kb_ids:
        try:
            chunks = rag_service.search(
                query=request.question,
                kb_ids=request.kb_ids,
                top_k=5,
                similarity_threshold=0.2,
            )
            if chunks:
                context = "\n\n".join([c.get("content", "") or "" for c in chunks])
        except Exception as e:
            logger.warning(f"知识库检索失败: {e}")

    system_content = (
        "你是一个教学助手。请严格基于以下「参考内容」回答用户问题；若参考内容中无相关答案，可说明并简要补充。用中文回答。\n\n【参考内容】\n" + context
        if context
        else "你是一个教学助手。请用中文友好、简洁地回答用户问题。"
    )

    def event_stream():
        full_answer = ""
        try:
            stream = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": request.question},
                ],
                max_tokens=2000,
                temperature=0.5,
                stream=True,
            )
            for chunk in stream:
                delta = ""
                try:
                    delta = (chunk.choices[0].delta.content or "")
                except Exception:
                    delta = ""
                if not delta:
                    continue
                full_answer += delta
                yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"

            if current_user:
                course = None
                if request.kb_ids:
                    from models.kb_dataset_mapping import KbDatasetMapping
                    m = db.query(KbDatasetMapping).filter(KbDatasetMapping.ragflow_dataset_id.in_(request.kb_ids)).first()
                    if m:
                        course = (m.name or m.subject or "").strip() or None
                log_student_question(
                    db,
                    current_user,
                    "kb_qa",
                    request.question,
                    answer_summary=full_answer[:500],
                    course=course,
                    kb_ids=request.kb_ids,
                    conversation_id=request.conversation_id,
                )

            yield "data: {\"type\":\"done\"}\n\n"
        except Exception as e:
            logger.error(f"知识库问答流式失败: {e}", exc_info=True)
            payload = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield "data: {\"type\":\"done\"}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/qa/quick_qa", summary="快速问答（不依赖知识库，学情可记录）")
async def quick_qa(request: QARequest, db: Session = Depends(get_db), current_user=Depends(get_current_user_optional)):
    """简单问答，直接调用大模型；登录用户提问会记入学情。"""
    client, model, err = _get_openai_client()
    if err or not client:
        return {"success": False, "message": err or "大模型未配置", "answer": None}
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=[
                {"role": "system", "content": "你是一个教学助手，请用中文友好、简洁地回答用户问题。"},
                {"role": "user", "content": request.question},
            ],
            max_tokens=2000,
            temperature=0.5,
        )
        answer = (response.choices[0].message.content or "").strip()
        if current_user:
            log_student_question(db, current_user, "quick_qa", request.question, answer_summary=answer[:500])
        return {"success": True, "answer": answer}
    except Exception as e:
        logger.error(f"快速问答失败: {e}", exc_info=True)
        return {"success": False, "message": str(e), "answer": None}


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    print(f"收到登录请求: 用户名={req.username}, 密码={req.password}")
    user = db.query(User).filter(User.username == req.username).first()
    print(f"数据库查到用户: {user}")
    if not user:
        print("未查到该用户，登录失败")
        return {"success": False, "message": "用户不存在"}
    print(f"数据库密码: {user.password}，用户输入密码: {req.password}")
    if user.password != req.password:
        print("密码错误，登录失败")
        return {"success": False, "message": "密码错误"}
    
    print("登录成功")
    token = create_access_token(user)
    res = {
        "success": True,
        "username": user.username,
        "role": user.role,
        "userId": user.id,
        "major": user.major or "",
        "token": token
    }
    if getattr(user, "courses", None) and user.role == "teacher":
        import json
        try:
            res["courses"] = json.loads(user.courses) if isinstance(user.courses, str) else (user.courses or [])
        except Exception:
            res["courses"] = []
    return res

@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    print(f"收到注册请求: 用户名={req.username}, 角色={req.role}, 姓名={req.name}")
    print(f"学院={req.college}, 专业={req.major}")
    
    # 检查用户名是否已存在
    existing_user = db.query(User).filter(User.username == req.username).first()
    if existing_user:
        print(f"用户名 {req.username} 已存在，注册失败")
        return {"success": False, "message": "用户名已存在"}
    
    # 创建用户，包含额外字段
    user_data = {
        "username": req.username,
        "password": req.password,
        "role": req.role,
        "name": req.name
    }
    
    # 根据角色添加额外字段
    if req.role == "student":
        if req.college and req.major:
            user_data["college"] = req.college
            user_data["major"] = req.major
    elif req.role == "teacher":
        if req.college:
            user_data["college"] = req.college
        if req.major:
            user_data["major"] = req.major
        if req.courses and isinstance(req.courses, list):
            import json
            user_data["courses"] = json.dumps([str(c).strip() for c in req.courses if str(c).strip()], ensure_ascii=False)
    
    print(f"准备创建用户数据: {user_data}")
    
    try:
        user = User(**user_data)
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"用户 {req.username} 注册成功")
        return {"success": True, "message": "注册成功"}
    except Exception as e:
        print(f"注册失败，错误信息: {str(e)}")
        db.rollback()
        return {"success": False, "message": f"注册失败: {str(e)}"}

@router.post("/qa")
async def qa(request: QARequest):
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        return {"error": "OPENAI_API_KEY not set"}
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": request.question}
        ]
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        if resp.status_code == 200:
            answer = resp.json()["choices"][0]["message"]["content"]
            return {"answer": answer}
        else:
            return {"error": resp.text} 