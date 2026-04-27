from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel
from models.database import get_db
from models.paper import Paper
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/papers",
    tags=["Paper Management"],
    responses={404: {"description": "Not found"}},
)

# 请求和响应模型
class PaperCreate(BaseModel):
    title: str
    description: Optional[str] = None
    creator: str
    status: str = "草稿"
    subject: Optional[str] = None
    grade: Optional[str] = None
    duration: Optional[int] = None
    total_score: Optional[int] = None
    difficulty: Optional[str] = None
    content: Optional[str] = None

class PaperUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    creator: Optional[str] = None
    status: Optional[str] = None
    subject: Optional[str] = None
    grade: Optional[str] = None
    duration: Optional[int] = None
    total_score: Optional[int] = None
    difficulty: Optional[str] = None
    content: Optional[str] = None

@router.get("/", summary="获取试卷列表")
async def get_papers(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    title: Optional[str] = Query(None),
    creator: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """获取试卷列表，支持分页和筛选"""
    try:
        query = db.query(Paper)
        
        if title:
            query = query.filter(Paper.title.contains(title))
        if creator:
            query = query.filter(Paper.creator.contains(creator))
        if status:
            query = query.filter(Paper.status == status)
        
        total = query.count()
        papers = query.offset(skip).limit(limit).all()
        
        return {
            "success": True,
            "data": {
                "items": papers,
                "total": total,
                "skip": skip,
                "limit": limit
            },
            "message": "获取试卷列表成功"
        }
    except Exception as e:
        logger.error(f"获取试卷列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取试卷列表失败: {str(e)}")

@router.post("/", summary="创建试卷")
async def create_paper(
    paper: PaperCreate,
    db: Session = Depends(get_db)
):
    """创建新的试卷"""
    try:
        db_paper = Paper(**paper.dict())
        db.add(db_paper)
        db.commit()
        db.refresh(db_paper)
        
        return {
            "success": True,
            "data": db_paper,
            "message": "试卷创建成功"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"创建试卷失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建试卷失败: {str(e)}")

@router.get("/{paper_id}", summary="获取试卷详情")
async def get_paper(
    paper_id: int,
    db: Session = Depends(get_db)
):
    """根据ID获取试卷详情"""
    try:
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if not paper:
            raise HTTPException(status_code=404, detail="试卷不存在")
        
        return {
            "success": True,
            "data": paper,
            "message": "获取试卷详情成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取试卷详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取试卷详情失败: {str(e)}")

@router.put("/{paper_id}", summary="更新试卷")
async def update_paper(
    paper_id: int,
    paper_update: PaperUpdate,
    db: Session = Depends(get_db)
):
    """更新试卷"""
    try:
        db_paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if not db_paper:
            raise HTTPException(status_code=404, detail="试卷不存在")
        
        update_data = paper_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_paper, field, value)
        
        db.commit()
        db.refresh(db_paper)
        
        return {
            "success": True,
            "data": db_paper,
            "message": "试卷更新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新试卷失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新试卷失败: {str(e)}")

@router.delete("/{paper_id}", summary="删除试卷")
async def delete_paper(
    paper_id: int,
    db: Session = Depends(get_db)
):
    """删除试卷"""
    try:
        db_paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if not db_paper:
            raise HTTPException(status_code=404, detail="试卷不存在")
        
        db.delete(db_paper)
        db.commit()
        
        return {
            "success": True,
            "message": "试卷删除成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除试卷失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除试卷失败: {str(e)}") 