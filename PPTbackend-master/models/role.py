from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from models.database import Base

class Role(Base):
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="角色名称")
    key = Column(String(100), nullable=False, unique=True, comment="权限字符")
    order = Column(Integer, default=0, comment="显示顺序")
    status = Column(Boolean, default=True, comment="状态：true启用，false禁用")
    description = Column(Text, nullable=True, comment="角色描述")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间") 