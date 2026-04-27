from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.agents.base import AgentInput
from api.agents.registry import AgentRegistry
from api.auth_utils import get_current_user_optional, log_student_question
from models.agent_schemas import AgentAskRequest
from models.database import get_db


router = APIRouter(
    prefix="/api/agent_router",
    tags=["Agent Router"],
    responses={404: {"description": "Not found"}},
)


def get_agent_registry(request: Request) -> AgentRegistry:
    registry = getattr(request.app.state, "agent_registry", None)
    if registry is None:
        raise HTTPException(status_code=503, detail="AgentRegistry not initialized")
    return registry


@router.get("/agents", summary="列出已注册 Agent")
async def list_agents(registry: AgentRegistry = Depends(get_agent_registry)):
    data = [
        {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "tools": [tool.name for tool in getattr(agent, "tools", [])],
        }
        for agent in registry.list()
    ]
    return {"success": True, "data": data}


@router.post("/ask", summary="统一 Agent 问答入口")
async def ask_agent(
    request: AgentAskRequest,
    registry: AgentRegistry = Depends(get_agent_registry),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    agent = registry.get(request.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{request.agent_id}' not found")

    output = await agent.run(
        AgentInput(
            message=request.message,
            messages=[m.model_dump() for m in request.messages] if request.messages else [],
            metadata=request.metadata or {},
        ),
        registry.build_context(),
    )

    # OpenClaw Memory 层：教师助手 Agent 调用后写入学情（与直连 ai_teacher 路由行为一致）
    if request.agent_id == "teacher_assistant" and (request.message or "").strip():
        summary = (output.content or "").strip()[:500]
        kb_ids = None
        try:
            kb_ids = (output.metadata or {}).get("kb_ids") or None
        except Exception:
            kb_ids = None
        log_student_question(
            db,
            current_user,
            "ai_teacher",
            request.message.strip(),
            answer_summary=summary or None,
            kb_ids=kb_ids,
        )

    return {
        "success": True,
        "data": {
            "agent_id": output.agent_id,
            "content": output.content,
            "tool_outputs": output.tool_outputs,
            "metadata": output.metadata,
        },
    }
