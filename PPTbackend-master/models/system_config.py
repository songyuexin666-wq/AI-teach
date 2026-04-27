from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.sql import func
from models.database import Base

class SystemConfig(Base):
    __tablename__ = "system_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String(100), unique=True, nullable=False, comment="配置键")
    config_value = Column(Text, nullable=True, comment="配置值")
    config_type = Column(String(20), default="string", comment="配置类型：string、int、float、boolean、json")
    description = Column(String(200), nullable=True, comment="配置描述")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间") 