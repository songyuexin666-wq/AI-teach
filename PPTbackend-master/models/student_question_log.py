# -*- coding: utf-8 -*-
"""
学生提问记录表：按专业、课程、提问类型存储，用于学情分析。
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from sqlalchemy.sql import func
from models.database import Base


class StudentQuestionLog(Base):
    __tablename__ = "student_question_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False, comment="学生用户ID")
    major = Column(String(100), index=True, nullable=True, comment="专业名称，冗余便于按专业统计")
    course = Column(String(200), index=True, nullable=True, comment="课程名称，可选")
    question_type = Column(String(32), index=True, nullable=False, comment="kb_qa|chat|ai_teacher|quick_qa")
    question_content = Column(Text, nullable=False, comment="提问内容")
    answer_summary = Column(Text, nullable=True, comment="回答摘要，可选用于分析")
    kb_ids = Column(Text, nullable=True, comment="知识库ID列表(JSON)，仅 kb_qa 时有")
    conversation_id = Column(String(64), index=True, nullable=True, comment="会话ID，用于按会话聚合分析")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_sql_major_course_time", "major", "course", "created_at"),
        Index("ix_sql_major_type_time", "major", "question_type", "created_at"),
    )
