from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.sql import func
from .database import Base

class LoginLog(Base):
    __tablename__ = "login_logs"
    
    id = Column(Integer, primary_key=True, index=True, comment="日志ID")
    username = Column(String(50), nullable=False, comment="用户名")
    ip_address = Column(String(50), nullable=True, comment="IP地址")
    login_location = Column(String(100), nullable=True, comment="登录地点")
    browser = Column(String(100), nullable=True, comment="浏览器")
    os = Column(String(100), nullable=True, comment="操作系统")
    status = Column(String(20), default="success", comment="登录状态：success、failed")
    message = Column(Text, nullable=True, comment="操作信息")
    login_time = Column(DateTime(timezone=True), server_default=func.now(), comment="登录时间")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")








