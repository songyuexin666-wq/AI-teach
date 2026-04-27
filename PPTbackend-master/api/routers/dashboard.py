from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from models.database import get_db
from models.user import User
from api.auth_utils import get_current_user_optional
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
    responses={404: {"description": "Not found"}},
)

@router.get("/stats", summary="获取首页统计数据")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    获取首页显示的统计数据
    """
    try:
        # 获取总用户数
        total_users = db.query(func.count(User.id)).scalar()
        
        # 获取今日注册用户数
        today = datetime.now().date()
        today_users = db.query(func.count(User.id)).filter(
            func.date(User.id) == today
        ).scalar()
        
        # 获取用户角色分布
        role_stats = db.query(
            User.role,
            func.count(User.id).label('count')
        ).group_by(User.role).all()
        
        # 获取学院分布
        college_stats = db.query(
            User.college,
            func.count(User.id).label('count')
        ).filter(User.college.isnot(None)).group_by(User.college).all()
        
        # 获取专业分布
        major_stats = db.query(
            User.major,
            func.count(User.id).label('count')
        ).filter(User.major.isnot(None)).group_by(User.major).all()
        
        # 获取最近注册的用户
        recent_users = db.query(User).order_by(User.id.desc()).limit(5).all()
        
        # 构建统计数据
        stats = {
            "total_users": total_users,
            "today_users": today_users,
            "role_distribution": [
                {"role": role, "count": count} for role, count in role_stats
            ],
            "college_distribution": [
                {"college": college, "count": count} for college, count in college_stats
            ],
            "major_distribution": [
                {"major": major, "count": count} for major, count in major_stats
            ],
            "recent_users": [
                {
                    "id": user.id,
                    "username": user.username,
                    "name": user.name,
                    "role": user.role,
                    "college": user.college,
                    "major": user.major
                } for user in recent_users
            ]
        }
        
        return {
            "success": True,
            "data": stats,
            "message": "统计数据获取成功"
        }
        
    except Exception as e:
        logger.error(f"获取统计数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取统计数据失败: {str(e)}")

@router.get("/user-info", summary="获取当前用户信息")
async def get_current_user_info(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """从 JWT 解析当前用户并返回其信息；无有效 token 时返回 200 且 data 为 null，避免刚登录就被 401 踢出。"""
    if not current_user:
        return {
            "success": True,
            "data": None,
            "message": "未登录或登录已过期",
        }
    return {
        "success": True,
        "data": {
            "id": current_user.id,
            "username": current_user.username,
            "name": current_user.name or current_user.username,
            "role": current_user.role or "student",
            "college": current_user.college or "",
            "major": current_user.major or "",
        },
        "message": "用户信息获取成功",
    } 