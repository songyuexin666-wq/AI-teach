#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sys
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.database import get_db
from models.user import User

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 请求模型
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str
    name: str
    college: Optional[str] = None
    major: Optional[str] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("--- 认证服务启动中 ---")
    
    # 检查数据库连接
    try:
        db = next(get_db())
        users = db.query(User).all()
        logger.info(f"数据库连接成功，当前用户数量: {len(users)}")
        db.close()
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
    
    logger.info("--- 认证服务启动完成 ---")
    yield
    
    logger.info("--- 认证服务已关闭 ---")

# 创建FastAPI应用
app = FastAPI(
    title="AI教师助手 - 认证服务",
    description="AI教师助手系统 - 登录注册功能",
    version="1.0.0",
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """根路径"""
    return {"message": "AI教师助手认证服务", "status": "running"}

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "message": "认证服务正常运行"}

@app.post("/api/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """用户登录"""
    logger.info(f"收到登录请求: 用户名={req.username}")
    
    user = db.query(User).filter(User.username == req.username).first()
    if not user:
        logger.warning(f"用户 {req.username} 不存在")
        return {"success": False, "message": "用户不存在"}
    
    if user.password != req.password:
        logger.warning(f"用户 {req.username} 密码错误")
        return {"success": False, "message": "密码错误"}
    
    logger.info(f"用户 {req.username} 登录成功")
    return {
        "success": True,
        "username": user.username,
        "role": user.role,
        "name": user.name,
        "college": user.college,
        "major": user.major,
        "token": f"{user.role}-token"
    }

@app.post("/api/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """用户注册"""
    logger.info(f"收到注册请求: 用户名={req.username}, 角色={req.role}, 姓名={req.name}")
    
    # 检查用户名是否已存在
    existing_user = db.query(User).filter(User.username == req.username).first()
    if existing_user:
        logger.warning(f"用户名 {req.username} 已存在")
        return {"success": False, "message": "用户名已存在"}
    
    # 创建用户
    user_data = {
        "username": req.username,
        "password": req.password,
        "role": req.role,
        "name": req.name
    }
    
    # 根据角色添加额外字段
    if req.role == "student":
        if req.college and req.major:
            user_data["college"] = req.college
            user_data["major"] = req.major
    elif req.role == "teacher":
        if req.college:
            user_data["college"] = req.college
    
    try:
        user = User(**user_data)
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"用户 {req.username} 注册成功")
        return {"success": True, "message": "注册成功"}
    except Exception as e:
        logger.error(f"注册失败: {str(e)}")
        db.rollback()
        return {"success": False, "message": f"注册失败: {str(e)}"}

@app.get("/api/users")
def get_users(db: Session = Depends(get_db)):
    """获取所有用户列表（调试用）"""
    users = db.query(User).all()
    return {
        "success": True,
        "data": [
            {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "name": user.name,
                "college": user.college,
                "major": user.major
            }
            for user in users
        ],
        "count": len(users)
    }

if __name__ == "__main__":
    logger.info("启动AI教师助手认证服务")
    uvicorn.run(
        "auth_server:app",
        host="0.0.0.0",
        port=7878,
        reload=True,
        log_level="info"
    )








