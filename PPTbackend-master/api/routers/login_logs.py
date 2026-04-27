from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from pydantic import BaseModel
from models.database import get_db
from models.login_log import LoginLog
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/login-logs",
    tags=["Login Logs Management"],
    responses={404: {"description": "Not found"}},
)

# 请求和响应模型
class LoginLogCreate(BaseModel):
    username: str
    ip_address: Optional[str] = None
    login_location: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    status: str = "success"
    message: Optional[str] = None

class LoginLogResponse(BaseModel):
    id: int
    username: str
    ip_address: Optional[str] = None
    login_location: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    status: str
    message: Optional[str] = None
    login_time: str
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True

@router.get("/", summary="获取登录日志列表")
async def get_login_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    username: Optional[str] = Query(None),
    ip_address: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    begin_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """获取登录日志列表，支持分页和筛选"""
    try:
        query = db.query(LoginLog)
        
        if username:
            query = query.filter(LoginLog.username.contains(username))
        if ip_address:
            query = query.filter(LoginLog.ip_address.contains(ip_address))
        if status:
            query = query.filter(LoginLog.status == status)
        if begin_time:
            query = query.filter(LoginLog.login_time >= begin_time)
        if end_time:
            query = query.filter(LoginLog.login_time <= end_time)
        
        total = query.count()
        login_logs = query.order_by(desc(LoginLog.login_time)).offset(skip).limit(limit).all()
        
        return {
            "success": True,
            "data": {
                "items": login_logs,
                "total": total,
                "skip": skip,
                "limit": limit
            },
            "message": "获取登录日志列表成功"
        }
    except Exception as e:
        logger.error(f"获取登录日志列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取登录日志列表失败: {str(e)}")

@router.post("/", summary="创建登录日志")
async def create_login_log(
    login_log: LoginLogCreate,
    db: Session = Depends(get_db)
):
    """创建新的登录日志"""
    try:
        db_login_log = LoginLog(**login_log.dict())
        db.add(db_login_log)
        db.commit()
        db.refresh(db_login_log)
        
        return {
            "success": True,
            "data": db_login_log,
            "message": "登录日志创建成功"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"创建登录日志失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建登录日志失败: {str(e)}")

@router.get("/{log_id}", summary="获取登录日志详情")
async def get_login_log(
    log_id: int,
    db: Session = Depends(get_db)
):
    """根据ID获取登录日志详情"""
    try:
        login_log = db.query(LoginLog).filter(LoginLog.id == log_id).first()
        if not login_log:
            raise HTTPException(status_code=404, detail="登录日志不存在")
        
        return {
            "success": True,
            "data": login_log,
            "message": "获取登录日志详情成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取登录日志详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取登录日志详情失败: {str(e)}")

@router.delete("/{log_id}", summary="删除登录日志")
async def delete_login_log(
    log_id: int,
    db: Session = Depends(get_db)
):
    """删除登录日志"""
    try:
        login_log = db.query(LoginLog).filter(LoginLog.id == log_id).first()
        if not login_log:
            raise HTTPException(status_code=404, detail="登录日志不存在")
        
        db.delete(login_log)
        db.commit()
        
        return {
            "success": True,
            "message": "登录日志删除成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除登录日志失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除登录日志失败: {str(e)}")

@router.delete("/", summary="清空所有登录日志")
async def delete_all_login_logs(
    db: Session = Depends(get_db)
):
    """清空所有登录日志"""
    try:
        db.query(LoginLog).delete()
        db.commit()
        
        return {
            "success": True,
            "message": "所有登录日志已清空"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"清空登录日志失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"清空登录日志失败: {str(e)}")








