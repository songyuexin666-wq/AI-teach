from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel
from models.database import get_db
from models.role import Role
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/roles",
    tags=["Role Management"],
    responses={404: {"description": "Not found"}},
)

# 请求和响应模型
class RoleCreate(BaseModel):
    name: str
    key: str
    order: int = 0
    status: bool = True
    description: Optional[str] = None

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    key: Optional[str] = None
    order: Optional[int] = None
    status: Optional[bool] = None
    description: Optional[str] = None

@router.get("/", summary="获取角色列表")
async def get_roles(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    name: Optional[str] = Query(None),
    status: Optional[bool] = Query(None),
    db: Session = Depends(get_db)
):
    """获取角色列表，支持分页和筛选"""
    try:
        query = db.query(Role)
        
        if name:
            query = query.filter(Role.name.contains(name))
        if status is not None:
            query = query.filter(Role.status == status)
        
        total = query.count()
        roles = query.order_by(Role.order).offset(skip).limit(limit).all()
        
        return {
            "success": True,
            "data": {
                "roles": roles,
                "total": total,
                "skip": skip,
                "limit": limit
            },
            "message": "获取角色列表成功"
        }
    except Exception as e:
        logger.error(f"获取角色列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取角色列表失败: {str(e)}")

@router.post("/", summary="创建角色")
async def create_role(
    role: RoleCreate,
    db: Session = Depends(get_db)
):
    """创建新的角色"""
    try:
        # 检查权限字符是否已存在
        existing_role = db.query(Role).filter(Role.key == role.key).first()
        if existing_role:
            raise HTTPException(status_code=400, detail="权限字符已存在")
        
        db_role = Role(**role.dict())
        db.add(db_role)
        db.commit()
        db.refresh(db_role)
        
        return {
            "success": True,
            "data": db_role,
            "message": "角色创建成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"创建角色失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建角色失败: {str(e)}")

@router.get("/{role_id}", summary="获取角色详情")
async def get_role(
    role_id: int,
    db: Session = Depends(get_db)
):
    """根据ID获取角色详情"""
    try:
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="角色不存在")
        
        return {
            "success": True,
            "data": role,
            "message": "获取角色详情成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取角色详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取角色详情失败: {str(e)}")

@router.put("/{role_id}", summary="更新角色")
async def update_role(
    role_id: int,
    role_update: RoleUpdate,
    db: Session = Depends(get_db)
):
    """更新角色"""
    try:
        db_role = db.query(Role).filter(Role.id == role_id).first()
        if not db_role:
            raise HTTPException(status_code=404, detail="角色不存在")
        
        # 如果更新权限字符，检查是否重复
        if role_update.key and role_update.key != db_role.key:
            existing_role = db.query(Role).filter(Role.key == role_update.key).first()
            if existing_role:
                raise HTTPException(status_code=400, detail="权限字符已存在")
        
        update_data = role_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_role, field, value)
        
        db.commit()
        db.refresh(db_role)
        
        return {
            "success": True,
            "data": db_role,
            "message": "角色更新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新角色失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新角色失败: {str(e)}")

@router.delete("/{role_id}", summary="删除角色")
async def delete_role(
    role_id: int,
    db: Session = Depends(get_db)
):
    """删除角色"""
    try:
        db_role = db.query(Role).filter(Role.id == role_id).first()
        if not db_role:
            raise HTTPException(status_code=404, detail="角色不存在")
        
        # 检查是否为系统默认角色
        if db_role.key in ['admin', 'teacher', 'student']:
            raise HTTPException(status_code=400, detail="系统默认角色不能删除")
        
        db.delete(db_role)
        db.commit()
        
        return {
            "success": True,
            "message": "角色删除成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除角色失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除角色失败: {str(e)}") 