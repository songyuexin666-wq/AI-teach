from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel
from models.database import get_db
from models.major_info import MajorInfo
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/major-info",
    tags=["Major Info Management"],
    responses={404: {"description": "Not found"}},
)

# 请求和响应模型
class MajorInfoCreate(BaseModel):
    major_name: str
    college: str
    description: Optional[str] = None

class MajorInfoUpdate(BaseModel):
    major_name: Optional[str] = None
    college: Optional[str] = None
    description: Optional[str] = None

class MajorInfoResponse(BaseModel):
    id: int
    major_name: str
    college: str
    description: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True

@router.get("/", summary="获取专业信息列表")
async def get_major_infos(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    major_name: Optional[str] = Query(None),
    college: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """获取专业信息列表，支持分页和筛选"""
    try:
        query = db.query(MajorInfo)
        
        if major_name:
            query = query.filter(MajorInfo.major_name.contains(major_name))
        if college:
            query = query.filter(MajorInfo.college.contains(college))
        
        total = query.count()
        major_infos = query.offset(skip).limit(limit).all()
        
        return {
            "success": True,
            "data": {
                "items": major_infos,
                "total": total,
                "skip": skip,
                "limit": limit
            },
            "message": "获取专业信息列表成功"
        }
    except Exception as e:
        logger.error(f"获取专业信息列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取专业信息列表失败: {str(e)}")

@router.post("/", summary="创建专业信息")
async def create_major_info(
    major_info: MajorInfoCreate,
    db: Session = Depends(get_db)
):
    """创建新的专业信息"""
    try:
        db_major_info = MajorInfo(**major_info.dict())
        db.add(db_major_info)
        db.commit()
        db.refresh(db_major_info)
        
        return {
            "success": True,
            "data": db_major_info,
            "message": "专业信息创建成功"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"创建专业信息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建专业信息失败: {str(e)}")

@router.get("/{major_info_id}", summary="获取专业信息详情")
async def get_major_info(
    major_info_id: int,
    db: Session = Depends(get_db)
):
    """根据ID获取专业信息详情"""
    try:
        major_info = db.query(MajorInfo).filter(MajorInfo.id == major_info_id).first()
        if not major_info:
            raise HTTPException(status_code=404, detail="专业信息不存在")
        
        return {
            "success": True,
            "data": major_info,
            "message": "获取专业信息详情成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取专业信息详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取专业信息详情失败: {str(e)}")

@router.put("/{major_info_id}", summary="更新专业信息")
async def update_major_info(
    major_info_id: int,
    major_info_update: MajorInfoUpdate,
    db: Session = Depends(get_db)
):
    """更新专业信息"""
    try:
        db_major_info = db.query(MajorInfo).filter(MajorInfo.id == major_info_id).first()
        if not db_major_info:
            raise HTTPException(status_code=404, detail="专业信息不存在")
        
        update_data = major_info_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_major_info, field, value)
        
        db.commit()
        db.refresh(db_major_info)
        
        return {
            "success": True,
            "data": db_major_info,
            "message": "专业信息更新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新专业信息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新专业信息失败: {str(e)}")

@router.delete("/{major_info_id}", summary="删除专业信息")
async def delete_major_info(
    major_info_id: int,
    db: Session = Depends(get_db)
):
    """删除专业信息"""
    try:
        db_major_info = db.query(MajorInfo).filter(MajorInfo.id == major_info_id).first()
        if not db_major_info:
            raise HTTPException(status_code=404, detail="专业信息不存在")
        
        db.delete(db_major_info)
        db.commit()
        
        return {
            "success": True,
            "message": "专业信息删除成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除专业信息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除专业信息失败: {str(e)}") 