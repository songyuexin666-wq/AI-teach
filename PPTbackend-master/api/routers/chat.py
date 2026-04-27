import asyncio
import json
import logging
import os
from typing import AsyncGenerator, Optional

import openai
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.chat_service import ChatService
from api.auth_utils import get_current_user_optional, log_student_question
from models.database import get_db
from models.schemas import (
    AskQuestionRequest,
    CreateChatAssistantRequest,
    CreateSessionRequest,
    DeleteChatAssistantsRequest,
    DeleteSessionsRequest,
    SimpleCompletionRequest,
)

logger = logging.getLogger(__name__)

# Dependency
def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


def _get_openai_client():
    """与 ai_teacher 一致，用于简单对话补全（不依赖 RAGFlow）。"""
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("AI_MODEL", "qwen-plus")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not configured")
    return openai.OpenAI(api_key=api_key, base_url=base_url), model


router = APIRouter(
    prefix="/api/chat",
    tags=["Chat Service"],
    responses={404: {"description": "Not found"}},
)

@router.post("/assistants", summary="创建聊天助手")
async def create_chat_assistant(
    request: CreateChatAssistantRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    try:
        assistant = await asyncio.to_thread(
            chat_service.create_chat_assistant,
            name=request.name,
            dataset_ids=request.dataset_ids
        )
        assistant_dict = {"id": assistant.id, "name": assistant.name}
        return {"success": True, "data": assistant_dict, "message": "聊天助手创建成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建聊天助手失败: {e}")

@router.get("/assistants", summary="列出所有聊天助手")
async def list_chat_assistants(
    name: Optional[str] = Query(None),
    chat_service: ChatService = Depends(get_chat_service)
):
    try:
        assistants = await asyncio.to_thread(chat_service.list_chat_assistants, name=name)
        assistants_list = [{"id": a.id, "name": a.name, "description": getattr(a, 'description', '')} for a in assistants]
        return {"success": True, "data": assistants_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"列出聊天助手失败: {e}")

@router.delete("/assistants", summary="删除聊天助手")
async def delete_chat_assistants(
    request: DeleteChatAssistantsRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    try:
        await asyncio.to_thread(chat_service.delete_chat_assistant, assistant_ids=request.assistant_ids)
        return {"success": True, "message": "聊天助手删除成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除聊天助手失败: {e}")

@router.post("/assistants/{assistant_id}/sessions", summary="创建会话")
async def create_session(
    assistant_id: str, 
    request: CreateSessionRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    try:
        session = await asyncio.to_thread(
            chat_service.create_session,
            assistant_id=assistant_id,
            session_name=request.session_name or "New session"
        )
        session_dict = {"id": session.id, "name": session.name}
        return {"success": True, "data": session_dict, "message": "会话创建成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建会话失败: {e}")

@router.get("/assistants/{assistant_id}/sessions", summary="列出所有会话")
async def list_sessions(
    assistant_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    chat_service: ChatService = Depends(get_chat_service),
):
    try:
        sessions = await asyncio.to_thread(
            chat_service.list_sessions,
            assistant_id=assistant_id,
            page=page,
            page_size=page_size
        )
        sessions_list = [{"id": s.id, "name": s.name} for s in sessions]
        return {"success": True, "data": sessions_list}
    except Exception as e:
        logger.error(f"列出助手 {assistant_id} 的会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"列出会话失败: {str(e)}")

@router.delete("/assistants/{assistant_id}/sessions", summary="删除会话")
async def delete_sessions(
    assistant_id: str,
    request: DeleteSessionsRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    try:
        await asyncio.to_thread(
            chat_service.delete_session,
            assistant_id=assistant_id,
            session_ids=request.session_ids
        )
        return {"success": True, "message": "会话删除成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除会话失败: {e}")

@router.post("/assistants/{assistant_id}/sessions/{session_id}/ask", summary="向会话提问")
async def ask_question(
    assistant_id: str,
    session_id: str,
    request: AskQuestionRequest,
    assistant_name: Optional[str] = None,
    session_name: Optional[str] = None,
    chat_service: ChatService = Depends(get_chat_service),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional),
):
    async def stream_generator() -> AsyncGenerator[str, None]:
        try:
            gen = await asyncio.to_thread(
                chat_service.ask_question,
                assistant_id=assistant_id,
                assistant_name=assistant_name,
                session_id=session_id,
                session_name=session_name,
                question=request.question,
                stream=True
            )
            for message in gen:
                if hasattr(message, 'content') and message.content:
                    message_dict = {
                        "content": message.content,
                        "role": getattr(message, 'role', 'assistant'),
                        "id": getattr(message, 'id', None)
                    }
                    yield f"data: {json.dumps(message_dict, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"流式响应生成错误: {e}", exc_info=True)
            error_data = {"error": str(e)}
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    try:
        if request.stream:
            return StreamingResponse(stream_generator(), media_type="text/event-stream")
        else:
            # 注意: ChatService中的ask_question目前只适配了流式输出
            # 如需非流式，需要修改ChatService
            answer = await asyncio.to_thread(
                chat_service.ask_question,
                assistant_id=assistant_id,
                assistant_name=None,
                session_id=session_id,
                session_name=None,
                question=request.question,
                stream=False
            )
            # 在非流式情况下，ask返回的是一个Message对象
            final_message = ""
            if answer:
                # 如果SDK返回的是生成器，需要迭代取完
                if hasattr(answer, '__iter__'):
                    for msg in answer:
                        final_message += msg.content if hasattr(msg, 'content') else ''
                else:
                    final_message = getattr(answer, 'content', '')

            # 学情分析：记录助手会话提问（非流式）
            _log_chat_question(db, current_user, request.question, final_message)
            answer_dict = {
                "content": final_message,
                "role": 'assistant',
            }
            return {"success": True, "data": answer_dict}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提问失败: {e}")


def _log_chat_question(db, current_user, last_user_content: str, answer_content: str):
    """学情分析：记录聊天提问。"""
    log_student_question(db, current_user, "chat", last_user_content or "", answer_summary=answer_content)


@router.post("/simple_completion", summary="AI 聊天助手简单对话（不依赖 RAGFlow，支持聊天记录持久化）")
async def simple_completion(
    request: SimpleCompletionRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional),
):
    """
    传入历史消息列表，返回助手回复。前端可将 messages 存 localStorage，每次发送时带上历史并保存新消息。
    """
    try:
        client, model = _get_openai_client()
        max_messages = 20
        msgs = [{"role": m.role, "content": m.content} for m in request.messages[-max_messages:]]
        if not msgs or msgs[-1].get("role") != "user":
            raise HTTPException(status_code=400, detail="messages 末尾需为 user 消息")
        last_user_content = msgs[-1].get("content", "")
        system = {"role": "system", "content": "你是 AI 教学助手，请用中文友好、简洁地回答用户问题。"}
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=[system] + msgs,
            max_tokens=2000,
            temperature=0.7,
        )
        content = (response.choices[0].message.content or "").strip()
        _log_chat_question(db, current_user, last_user_content, content)
        return {"success": True, "data": {"content": content, "role": "assistant"}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"simple_completion 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"对话失败: {str(e)}") 