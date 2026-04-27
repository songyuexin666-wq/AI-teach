from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel
from models.database import get_db
from models.teach_design import TeachDesign
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/teach-designs",
    tags=["Teach Design Management"],
    responses={404: {"description": "Not found"}},
)

# 请求和响应模型
class TeachDesignCreate(BaseModel):
    title: str
    course: str
    teacher: str
    status: str = "草稿"
    content: Optional[str] = None
    objectives: Optional[str] = None
    materials: Optional[str] = None
    activities: Optional[str] = None
    assessment: Optional[str] = None

class TeachDesignUpdate(BaseModel):
    title: Optional[str] = None
    course: Optional[str] = None
    teacher: Optional[str] = None
    status: Optional[str] = None
    content: Optional[str] = None
    objectives: Optional[str] = None
    materials: Optional[str] = None
    activities: Optional[str] = None
    assessment: Optional[str] = None

@router.get("/", summary="获取教学设计列表")
async def get_teach_designs(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    title: Optional[str] = Query(None),
    teacher: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """获取教学设计列表，支持分页和筛选"""
    try:
        query = db.query(TeachDesign)
        
        if title:
            query = query.filter(TeachDesign.title.contains(title))
        if teacher:
            query = query.filter(TeachDesign.teacher.contains(teacher))
        if status:
            query = query.filter(TeachDesign.status == status)
        
        total = query.count()
        teach_designs = query.offset(skip).limit(limit).all()
        
        return {
            "success": True,
            "data": {
                "items": teach_designs,
                "total": total,
                "skip": skip,
                "limit": limit
            },
            "message": "获取教学设计列表成功"
        }
    except Exception as e:
        logger.error(f"获取教学设计列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取教学设计列表失败: {str(e)}")

@router.post("/", summary="创建教学设计")
async def create_teach_design(
    teach_design: TeachDesignCreate,
    db: Session = Depends(get_db)
):
    """创建新的教学设计"""
    try:
        db_teach_design = TeachDesign(**teach_design.dict())
        db.add(db_teach_design)
        db.commit()
        db.refresh(db_teach_design)
        
        return {
            "success": True,
            "data": db_teach_design,
            "message": "教学设计创建成功"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"创建教学设计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建教学设计失败: {str(e)}")

@router.get("/{design_id}", summary="获取教学设计详情")
async def get_teach_design(
    design_id: int,
    db: Session = Depends(get_db)
):
    """根据ID获取教学设计详情"""
    try:
        teach_design = db.query(TeachDesign).filter(TeachDesign.id == design_id).first()
        if not teach_design:
            raise HTTPException(status_code=404, detail="教学设计不存在")
        
        return {
            "success": True,
            "data": teach_design,
            "message": "获取教学设计详情成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取教学设计详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取教学设计详情失败: {str(e)}")

@router.put("/{design_id}", summary="更新教学设计")
async def update_teach_design(
    design_id: int,
    teach_design_update: TeachDesignUpdate,
    db: Session = Depends(get_db)
):
    """更新教学设计"""
    try:
        db_teach_design = db.query(TeachDesign).filter(TeachDesign.id == design_id).first()
        if not db_teach_design:
            raise HTTPException(status_code=404, detail="教学设计不存在")
        
        update_data = teach_design_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_teach_design, field, value)
        
        db.commit()
        db.refresh(db_teach_design)
        
        return {
            "success": True,
            "data": db_teach_design,
            "message": "教学设计更新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新教学设计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新教学设计失败: {str(e)}")

@router.delete("/{design_id}", summary="删除教学设计")
async def delete_teach_design(
    design_id: int,
    db: Session = Depends(get_db)
):
    """删除教学设计"""
    try:
        db_teach_design = db.query(TeachDesign).filter(TeachDesign.id == design_id).first()
        if not db_teach_design:
            raise HTTPException(status_code=404, detail="教学设计不存在")
        
        db.delete(db_teach_design)
        db.commit()
        
        return {
            "success": True,
            "message": "教学设计删除成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除教学设计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除教学设计失败: {str(e)}") 