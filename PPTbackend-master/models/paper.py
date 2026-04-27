from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.database import Base

class Paper(Base):
    __tablename__ = "papers"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, comment="试卷名称")
    description = Column(Text, nullable=True, comment="试卷描述")
    creator = Column(String(50), nullable=False, comment="创建人")
    status = Column(String(20), default="草稿", comment="状态：草稿、已发布、已归档")
    subject = Column(String(50), nullable=True, comment="科目")
    grade = Column(String(20), nullable=True, comment="年级")
    duration = Column(Integer, nullable=True, comment="考试时长（分钟）")
    total_score = Column(Integer, nullable=True, comment="总分")
    difficulty = Column(String(20), nullable=True, comment="难度：简单、中等、困难")
    content = Column(Text, nullable=True, comment="试卷内容")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间") 