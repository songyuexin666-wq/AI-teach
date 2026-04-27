from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from models.database import Base

class MajorInfo(Base):
    __tablename__ = "major_info"
    
    id = Column(Integer, primary_key=True, index=True)
    major_name = Column(String(100), nullable=False, comment="专业名称")
    college = Column(String(100), nullable=False, comment="所属学院")
    description = Column(Text, nullable=True, comment="专业描述")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间") 