# -*- coding: utf-8 -*-
"""积分接口：用户每日签到 + 后台积分管理（查看/调整）

业务规则：
- 每自然日每个用户最多签到一次（checkin_logs 唯一约束兜底并发），积分在
  系统设置 signin_min_points ~ signin_max_points 之间随机（默认 1~5）。
- 后台管理员可正负调整用户积分，调整后积分不能小于 0。
"""
import random
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, require_roles
from ..core.pagination import paginate
from ..database import get_db
from ..models.checkin import CheckinLog
from ..models.user import User
from ..schemas.points import PointsDeltaIn
from ..services.settings_service import get_setting

router = APIRouter(prefix="/points", tags=["积分"])
admin_router = APIRouter(prefix="/admin/points", tags=["后台-积分管理"])


def _checkin_range(db: Session) -> tuple[int, int]:
    """读取签到积分范围；配置缺失或异常时退化为 1~5，min>max 时自动交换"""
    try:
        min_p = max(1, int(get_setting(db, "signin_min_points", 1)))
        max_p = max(1, int(get_setting(db, "signin_max_points", 5)))
    except (TypeError, ValueError):
        min_p, max_p = 1, 5
    if min_p > max_p:
        min_p, max_p = max_p, min_p
    return min_p, max_p


@router.get("/me", summary="我的积分与今日签到状态（需登录）")
def my_points(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = datetime.now().strftime("%Y-%m-%d")
    checked = (
        db.query(CheckinLog)
        .filter(CheckinLog.user_id == user.id, CheckinLog.checkin_date == today)
        .first()
    )
    return {
        "points": user.points or 0,
        "today_checked_in": checked is not None,
    }


@router.post("/checkin", summary="每日签到（需登录，每天一次，积分范围取系统设置）")
def checkin(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = datetime.now().strftime("%Y-%m-%d")
    existing = (
        db.query(CheckinLog)
        .filter(CheckinLog.user_id == user.id, CheckinLog.checkin_date == today)
        .first()
    )
    if existing:
        raise HTTPException(400, "今日已签到，明天再来吧")

    min_p, max_p = _checkin_range(db)
    gained = random.randint(min_p, max_p)
    user.points = (user.points or 0) + gained
    db.add(CheckinLog(user_id=user.id, checkin_date=today, points=gained))
    try:
        db.commit()
    except IntegrityError:
        # 并发双击兜底：唯一约束拒绝重复签到
        db.rollback()
        raise HTTPException(400, "今日已签到，明天再来吧")
    db.refresh(user)
    return {
        "message": f"签到成功，获得 {gained} 积分",
        "gained": gained,
        "points": user.points or 0,
        "today_checked_in": True,
    }


@admin_router.get("", summary="后台积分列表（管理员，可按用户名/昵称搜索）")
def admin_points(
    keyword: str | None = Query(default=None, description="按用户名/昵称模糊搜索"),
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    # 关联签到记录统计：签到次数与最近签到时间
    query = (
        db.query(
            User,
            func.count(CheckinLog.id),
            func.max(CheckinLog.created_at),
        )
        .outerjoin(CheckinLog, CheckinLog.user_id == User.id)
        .group_by(User.id)
    )
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(User.username.like(like), User.nickname.like(like)))
    query = query.order_by(User.points.desc(), User.id.desc())
    rows, total = paginate(query, page, page_size)

    items = []
    for user, checkin_count, last_checkin_at in rows:
        items.append({
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "avatar": user.avatar,
            "role": user.role,
            "points": user.points or 0,
            "checkin_count": checkin_count or 0,
            "last_checkin_at": last_checkin_at.strftime("%Y-%m-%d %H:%M:%S") if last_checkin_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@admin_router.put("/{user_id}", summary="调整用户积分（管理员，正加负减，积分不小于0）")
def adjust_points(
    user_id: int,
    body: PointsDeltaIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    new_points = (user.points or 0) + body.delta
    if new_points < 0:
        raise HTTPException(400, "调整后积分不能小于 0")
    user.points = new_points
    db.commit()
    db.refresh(user)
    return {"message": "积分已调整", "points": user.points or 0}
