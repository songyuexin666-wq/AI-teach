# -*- coding: utf-8 -*-
"""
场景与 RAGFlow chat assistant 的映射。
用于「备课助手 / 题目解析助手 / 学生答疑」等场景选择对应的 chat_id。
"""
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from models.database import Base


class ChatAssistantScene(Base):
    __tablename__ = "chat_assistant_scenes"

    id = Column(Integer, primary_key=True, index=True)
    scene_key = Column(String(64), unique=True, nullable=False, index=True, comment="场景唯一键，如 prep/qa/student")
    scene_name = Column(String(128), nullable=False, comment="显示名称，如 备课助手")
    ragflow_chat_id = Column(String(128), nullable=False, comment="RAGFlow 中的 chat assistant ID")
    description = Column(Text, nullable=True, comment="场景说明")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
