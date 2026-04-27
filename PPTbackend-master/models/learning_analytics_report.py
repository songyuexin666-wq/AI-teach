# -*- coding: utf-8 -*-
"""
学情分析报告表：按专业、课程存储大模型生成的学情分析结果。
"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from models.database import Base


class LearningAnalyticsReport(Base):
    __tablename__ = "learning_analytics_reports"

    id = Column(Integer, primary_key=True, index=True)
    major = Column(String(100), index=True, nullable=False, comment="专业名称")
    course = Column(String(200), index=True, nullable=True, comment="课程名称，空表示专业整体")
    report_content = Column(Text, nullable=False, comment="报告内容(Markdown)")
    time_range_start = Column(DateTime(timezone=True), nullable=True, comment="统计开始时间")
    time_range_end = Column(DateTime(timezone=True), nullable=True, comment="统计结束时间")
    question_count = Column(Integer, default=0, comment="参与分析的提问条数")
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    generated_by_user_id = Column(Integer, nullable=True, comment="触发生成的用户ID(教师/管理员)")
