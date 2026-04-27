from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AgentChatMessage(BaseModel):
    role: str
    content: str


class AgentAskRequest(BaseModel):
    agent_id: str
    message: str
    messages: Optional[List[AgentChatMessage]] = None
    metadata: Optional[Dict[str, Any]] = None
