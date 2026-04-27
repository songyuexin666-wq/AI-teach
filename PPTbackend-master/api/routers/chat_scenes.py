# -*- coding: utf-8 -*-
"""
场景 → RAGFlow chat_id 配置接口。
对话入口可根据场景选择对应 chat_id，再调现有 ChatService 创建 session / 提问。
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from models.database import get_db
from models.chat_assistant_scene import ChatAssistantScene
from models.schemas import ChatSceneCreate, ChatSceneUpdate

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/chat/scenes",
    tags=["Chat Scene Mapping"],
    responses={404: {"description": "Not found"}},
)


@router.get("", summary="列表：场景→chat 映射")
async def list_chat_scenes(
    scene_key: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(ChatAssistantScene)
    if scene_key is not None:
        q = q.filter(ChatAssistantScene.scene_key == scene_key)
    items = q.all()
    return {
        "success": True,
        "data": [
            {
                "id": m.id,
                "scene_key": m.scene_key,
                "scene_name": m.scene_name,
                "ragflow_chat_id": m.ragflow_chat_id,
                "description": m.description,
            }
            for m in items
        ],
    }


@router.get("/by-key/{scene_key}", summary="按 scene_key 获取 chat_id")
async def get_chat_id_by_scene(
    scene_key: str,
    db: Session = Depends(get_db),
):
    """对话入口根据场景获取 ragflow_chat_id，再调 /api/chat/assistants/{id}/sessions 等。"""
    m = db.query(ChatAssistantScene).filter(ChatAssistantScene.scene_key == scene_key).first()
    if not m:
        raise HTTPException(status_code=404, detail=f"未找到场景: {scene_key}")
    return {
        "success": True,
        "data": {
            "scene_key": m.scene_key,
            "scene_name": m.scene_name,
            "ragflow_chat_id": m.ragflow_chat_id,
        },
    }


@router.post("", summary="创建场景映射", status_code=201)
async def create_chat_scene(
    body: ChatSceneCreate,
    db: Session = Depends(get_db),
):
    existing = db.query(ChatAssistantScene).filter(ChatAssistantScene.scene_key == body.scene_key).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"scene_key 已存在: {body.scene_key}")
    m = ChatAssistantScene(
        scene_key=body.scene_key,
        scene_name=body.scene_name,
        ragflow_chat_id=body.ragflow_chat_id,
        description=body.description,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return {
        "success": True,
        "data": {
            "id": m.id,
            "scene_key": m.scene_key,
            "scene_name": m.scene_name,
            "ragflow_chat_id": m.ragflow_chat_id,
        },
        "message": "场景映射创建成功",
    }


@router.put("/{scene_id}", summary="更新场景映射")
async def update_chat_scene(
    scene_id: int,
    body: ChatSceneUpdate,
    db: Session = Depends(get_db),
):
    m = db.query(ChatAssistantScene).filter(ChatAssistantScene.id == scene_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="未找到该场景映射")
    if body.scene_name is not None:
        m.scene_name = body.scene_name
    if body.ragflow_chat_id is not None:
        m.ragflow_chat_id = body.ragflow_chat_id
    if body.description is not None:
        m.description = body.description
    db.commit()
    db.refresh(m)
    return {"success": True, "data": {"id": m.id}, "message": "场景映射已更新"}


@router.delete("/{scene_id}", summary="删除场景映射")
async def delete_chat_scene(
    scene_id: int,
    db: Session = Depends(get_db),
):
    m = db.query(ChatAssistantScene).filter(ChatAssistantScene.id == scene_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="未找到该场景映射")
    db.delete(m)
    db.commit()
    return {"success": True, "message": "场景映射已删除"}
