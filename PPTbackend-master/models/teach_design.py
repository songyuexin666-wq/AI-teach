from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.database import Base

class TeachDesign(Base):
    __tablename__ = "teach_designs"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, comment="设计标题")
    course = Column(String(100), nullable=False, comment="相关课程")
    teacher = Column(String(50), nullable=False, comment="授课教师")
    status = Column(String(20), default="草稿", comment="状态：草稿、待审核、已发布、已驳回")
    version = Column(Integer, default=1, comment="版本号")
    content = Column(Text, nullable=True, comment="设计内容")
    objectives = Column(Text, nullable=True, comment="教学目标")
    materials = Column(Text, nullable=True, comment="教学材料")
    activities = Column(Text, nullable=True, comment="教学活动")
    assessment = Column(Text, nullable=True, comment="评估方式")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间") 