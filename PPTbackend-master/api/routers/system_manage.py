from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel
from models.database import get_db
from models.system_config import SystemConfig
import logging
import psutil
import time
import os
import platform

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/system",
    tags=["System Management"],
    responses={404: {"description": "Not found"}},
)

# 实时监控数据模型
class SystemMonitorInfo(BaseModel):
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    uptime: float
    os_info: str
    python_version: str
    process_count: int

@router.get("/monitor", summary="获取服务器实时监控信息")
async def get_system_monitor():
    """获取服务器 CPU、内存、磁盘等实时监控信息"""
    try:
        # CPU 使用率
        cpu_usage = psutil.cpu_percent(interval=0.1)
        
        # 内存使用率
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
        
        # 磁盘使用率
        disk = psutil.disk_usage('/')
        disk_usage = disk.percent
        
        # 运行时间
        boot_time = psutil.boot_time()
        uptime = time.time() - boot_time
        
        # 系统信息
        os_info = f"{platform.system()} {platform.release()}"
        python_version = platform.python_version()
        
        # 进程数
        process_count = len(psutil.pids())
        
        return {
            "success": True,
            "data": {
                "cpu_usage": cpu_usage,
                "memory_usage": memory_usage,
                "disk_usage": disk_usage,
                "uptime": uptime,
                "os_info": os_info,
                "python_version": python_version,
                "process_count": process_count
            },
            "message": "获取监控信息成功"
        }
    except Exception as e:
        logger.error(f"获取监控信息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取监控信息失败: {str(e)}")

# 请求和响应模型
class SystemConfigCreate(BaseModel):
    config_key: str
    config_value: Optional[str] = None
    config_type: str = "string"
    description: Optional[str] = None
    is_active: bool = True

class SystemConfigUpdate(BaseModel):
    config_value: Optional[str] = None
    config_type: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

@router.get("/configs", summary="获取系统配置列表")
async def get_system_configs(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    config_key: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db)
):
    """获取系统配置列表"""
    try:
        query = db.query(SystemConfig)
        
        if config_key:
            query = query.filter(SystemConfig.config_key.contains(config_key))
        if is_active is not None:
            query = query.filter(SystemConfig.is_active == is_active)
        
        total = query.count()
        configs = query.offset(skip).limit(limit).all()
        
        return {
            "success": True,
            "data": {
                "items": configs,
                "total": total,
                "skip": skip,
                "limit": limit
            },
            "message": "获取系统配置列表成功"
        }
    except Exception as e:
        logger.error(f"获取系统配置列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取系统配置列表失败: {str(e)}")

@router.post("/configs", summary="创建系统配置")
async def create_system_config(
    config: SystemConfigCreate,
    db: Session = Depends(get_db)
):
    """创建新的系统配置"""
    try:
        # 检查配置键是否已存在
        existing_config = db.query(SystemConfig).filter(SystemConfig.config_key == config.config_key).first()
        if existing_config:
            raise HTTPException(status_code=400, detail="配置键已存在")
        
        db_config = SystemConfig(**config.dict())
        db.add(db_config)
        db.commit()
        db.refresh(db_config)
        
        return {
            "success": True,
            "data": db_config,
            "message": "系统配置创建成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"创建系统配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建系统配置失败: {str(e)}")

@router.put("/configs/{config_id}", summary="更新系统配置")
async def update_system_config(
    config_id: int,
    config_update: SystemConfigUpdate,
    db: Session = Depends(get_db)
):
    """更新系统配置"""
    try:
        db_config = db.query(SystemConfig).filter(SystemConfig.id == config_id).first()
        if not db_config:
            raise HTTPException(status_code=404, detail="系统配置不存在")
        
        update_data = config_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_config, field, value)
        
        db.commit()
        db.refresh(db_config)
        
        return {
            "success": True,
            "data": db_config,
            "message": "系统配置更新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新系统配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新系统配置失败: {str(e)}")

@router.delete("/configs/{config_id}", summary="删除系统配置")
async def delete_system_config(
    config_id: int,
    db: Session = Depends(get_db)
):
    """删除系统配置"""
    try:
        db_config = db.query(SystemConfig).filter(SystemConfig.id == config_id).first()
        if not db_config:
            raise HTTPException(status_code=404, detail="系统配置不存在")
        
        db.delete(db_config)
        db.commit()
        
        return {
            "success": True,
            "message": "系统配置删除成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除系统配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除系统配置失败: {str(e)}")

@router.get("/stats", summary="获取系统统计信息")
async def get_system_stats(db: Session = Depends(get_db)):
    """获取系统统计信息"""
    try:
        # 获取配置总数
        total_configs = db.query(func.count(SystemConfig.id)).scalar()
        active_configs = db.query(func.count(SystemConfig.id)).filter(SystemConfig.is_active == True).scalar()
        
        stats = {
            "configs": {
                "total": total_configs,
                "active": active_configs,
                "inactive": total_configs - active_configs
            }
        }
        
        return {
            "success": True,
            "data": stats,
            "message": "获取系统统计信息成功"
        }
    except Exception as e:
        logger.error(f"获取系统统计信息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取系统统计信息失败: {str(e)}") 