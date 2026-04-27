# -*- coding: utf-8 -*-
"""
课程/学科/年级/教师 与 RAGFlow 知识库(dataset_id) 的映射接口。
业务侧维护「谁用哪个知识库」，RAGFlow 只存 dataset。
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from models.database import get_db
from models.kb_dataset_mapping import KbDatasetMapping
from models.schemas import KbMappingCreate, KbMappingUpdate

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/kb-mapping",
    tags=["Knowledge Base Mapping"],
    responses={404: {"description": "Not found"}},
)


@router.get("", summary="列表：课程-知识库映射")
async def list_kb_mappings(
    course_id: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    grade: Optional[str] = Query(None),
    teacher_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(KbDatasetMapping)
    if course_id is not None:
        q = q.filter(KbDatasetMapping.course_id == course_id)
    if subject is not None:
        q = q.filter(KbDatasetMapping.subject == subject)
    if grade is not None:
        q = q.filter(KbDatasetMapping.grade == grade)
    if teacher_id is not None:
        q = q.filter(KbDatasetMapping.teacher_id == teacher_id)
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {
        "success": True,
        "data": {
            "items": [
                {
                    "id": m.id,
                    "course_id": m.course_id,
                    "subject": m.subject,
                    "grade": m.grade,
                    "teacher_id": m.teacher_id,
                    "ragflow_dataset_id": m.ragflow_dataset_id,
                    "dataset_type": m.dataset_type,
                    "name": m.name,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "updated_at": m.updated_at.isoformat() if m.updated_at else None,
                }
                for m in items
            ],
            "total": total,
        },
    }


@router.post("", summary="创建映射", status_code=201)
async def create_kb_mapping(
    body: KbMappingCreate,
    db: Session = Depends(get_db),
):
    m = KbDatasetMapping(
        course_id=body.course_id,
        subject=body.subject,
        grade=body.grade,
        teacher_id=body.teacher_id,
        ragflow_dataset_id=body.ragflow_dataset_id,
        dataset_type=body.dataset_type,
        name=body.name,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return {
        "success": True,
        "data": {
            "id": m.id,
            "course_id": m.course_id,
            "subject": m.subject,
            "grade": m.grade,
            "teacher_id": m.teacher_id,
            "ragflow_dataset_id": m.ragflow_dataset_id,
            "dataset_type": m.dataset_type,
            "name": m.name,
        },
        "message": "映射创建成功",
    }


@router.put("/{mapping_id}", summary="更新映射")
async def update_kb_mapping(
    mapping_id: int,
    body: KbMappingUpdate,
    db: Session = Depends(get_db),
):
    m = db.query(KbDatasetMapping).filter(KbDatasetMapping.id == mapping_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="未找到该映射")
    if body.course_id is not None:
        m.course_id = body.course_id
    if body.subject is not None:
        m.subject = body.subject
    if body.grade is not None:
        m.grade = body.grade
    if body.teacher_id is not None:
        m.teacher_id = body.teacher_id
    if body.ragflow_dataset_id is not None:
        m.ragflow_dataset_id = body.ragflow_dataset_id
    if body.dataset_type is not None:
        m.dataset_type = body.dataset_type
    if body.name is not None:
        m.name = body.name
    db.commit()
    db.refresh(m)
    return {"success": True, "data": {"id": m.id}, "message": "映射更新成功"}


@router.delete("/{mapping_id}", summary="删除映射")
async def delete_kb_mapping(
    mapping_id: int,
    db: Session = Depends(get_db),
):
    m = db.query(KbDatasetMapping).filter(KbDatasetMapping.id == mapping_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="未找到该映射")
    db.delete(m)
    db.commit()
    return {"success": True, "message": "映射已删除"}
