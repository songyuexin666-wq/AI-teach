# -*- coding: utf-8 -*-
"""
课程/学科/年级/教师 与 RAGFlow 知识库(dataset) 的映射。
业务语义在业务库维护，RAGFlow 仅存 dataset_id。
"""
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from models.database import Base


class KbDatasetMapping(Base):
    __tablename__ = "kb_dataset_mappings"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(String(64), index=True, nullable=True, comment="课程ID，可选")
    subject = Column(String(64), index=True, nullable=True, comment="学科，如 数学/语文")
    grade = Column(String(32), index=True, nullable=True, comment="年级，如 初一/高一")
    teacher_id = Column(String(64), index=True, nullable=True, comment="教师ID，可选，用于个人资料库")
    ragflow_dataset_id = Column(String(128), nullable=False, index=True, comment="RAGFlow 中的 dataset ID")
    dataset_type = Column(String(32), default="教材库", comment="类型：教材库/题库/教案库/校本资料库/教师个人资料库")
    name = Column(String(200), nullable=True, comment="显示名称，便于前端展示")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
