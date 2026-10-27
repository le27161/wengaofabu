# -*- coding: utf-8 -*-
"""数据统计接口（管理员）：概览、趋势、Top文稿、栏目数据、埋点明细、用户活跃"""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.deps import require_roles
from ..core.pagination import paginate
from ..database import get_db
from ..models.article import Article, article_categories
from ..models.category import Category
from ..models.event import EventLog
from ..models.user import User

router = APIRouter(prefix="/stats", tags=["统计"])


def _fill_dates(dates: dict, days: int) -> list[dict]:
    """将按日聚合结果补齐缺失日期，返回 [{date, count}]"""
    today = date.today()
    result = []
    for i in range(days - 1, -1, -1):
        day = (today - timedelta(days=i)).isoformat()
        result.append({"date": day, "count": dates.get(day, 0)})
    return result


@router.get("/overview", summary="数据概览（管理员）")
def overview(db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    today_start = datetime.combine(date.today(), datetime.min.time())
    pending_count = (
        db.query(Article)
        .filter(Article.status.in_(["pending_first", "pending_second"]))
        .count()
    )
    today_views = (
        db.query(func.count(EventLog.id))
        .filter(EventLog.event_type == "view", EventLog.created_at >= today_start)
        .scalar()
    )
    return {
        "total_users": db.query(User).count(),
        "total_editors": db.query(User).filter(User.role == "editor").count(),
        "total_articles": db.query(Article).count(),
        "published_articles": db.query(Article).filter(Article.status == "published").count(),
        "pending_review": pending_count,
        "total_views": db.query(func.coalesce(func.sum(Article.view_count), 0)).scalar(),
        "total_likes": db.query(func.coalesce(func.sum(Article.like_count), 0)).scalar(),
        "total_favorites": db.query(func.coalesce(func.sum(Article.favorite_count), 0)).scalar(),
        "total_shares": db.query(func.coalesce(func.sum(Article.share_count), 0)).scalar(),
        "today_views": today_views or 0,
        "today_events": db.query(func.count(EventLog.id)).filter(EventLog.created_at >= today_start).scalar() or 0,
    }


@router.get("/trends", summary="行为趋势（按日）")
def trends(
    days: int = Query(default=30, ge=1, le=365),
    event_type: str = Query(default="view", pattern="^(view|like|favorite|share)$"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    since = datetime.combine(date.today() - timedelta(days=days - 1), datetime.min.time())
    rows = (
        db.query(func.date(EventLog.created_at), func.count(EventLog.id))
        .filter(EventLog.event_type == event_type, EventLog.created_at >= since)
        .group_by(func.date(EventLog.created_at))
        .all()
    )
    return {"event_type": event_type, "items": _fill_dates({str(d): c for d, c in rows}, days)}


@router.get("/articles", summary="Top 文稿（按浏览量/点赞数）")
def top_articles(
    sort: str = Query(default="view_count", pattern="^(view_count|like_count|favorite_count|share_count)$"),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    rows = (
        db.query(Article)
        .filter(Article.status == "published")
        .order_by(getattr(Article, sort).desc(), Article.published_at.desc())
        .limit(limit)
        .all()
    )
    return {"items": [a.to_dict() for a in rows], "sort": sort}


@router.get("/categories", summary="栏目数据（浏览量分布 + 文稿数）")
def category_stats(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    since = datetime.combine(date.today() - timedelta(days=days - 1), datetime.min.time())
    # 栏目浏览量：埋点日志 join 文稿-栏目关联表
    view_rows = (
        db.query(article_categories.c.category_id, func.count(EventLog.id))
        .join(EventLog, EventLog.article_id == article_categories.c.article_id)
        .filter(EventLog.event_type == "view", EventLog.created_at >= since)
        .group_by(article_categories.c.category_id)
        .all()
    )
    # 栏目已发布文稿数
    article_rows = (
        db.query(article_categories.c.category_id, func.count(article_categories.c.article_id))
        .join(Article, Article.id == article_categories.c.article_id)
        .filter(Article.status == "published")
        .group_by(article_categories.c.category_id)
        .all()
    )
    view_map = dict(view_rows)
    article_map = dict(article_rows)
    cats = db.query(Category).order_by(Category.sort_order).all()
    return {
        "items": [
            {
                "category_id": c.id,
                "category_name": c.name,
                "views": view_map.get(c.id, 0),
                "article_count": article_map.get(c.id, 0),
            }
            for c in cats
        ]
    }


@router.get("/events", summary="埋点明细（可按类型/时间筛选）")
def event_logs(
    event_type: str | None = Query(default=None),
    start: date | None = Query(default=None, description="开始日期"),
    end: date | None = Query(default=None, description="结束日期"),
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    query = db.query(EventLog)
    if event_type:
        query = query.filter(EventLog.event_type == event_type)
    if start:
        query = query.filter(EventLog.created_at >= datetime.combine(start, datetime.min.time()))
    if end:
        query = query.filter(EventLog.created_at <= datetime.combine(end, datetime.max.time()))
    query = query.order_by(EventLog.id.desc())
    rows, total = paginate(query, page, page_size)
    return {"items": [e.to_dict() for e in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/user-activity", summary="用户活跃与新增（按日）")
def user_activity(
    days: int = Query(default=7, ge=1, le=365),
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    since = datetime.combine(date.today() - timedelta(days=days - 1), datetime.min.time())
    new_rows = (
        db.query(func.date(User.created_at), func.count(User.id))
        .filter(User.created_at >= since)
        .group_by(func.date(User.created_at))
        .all()
    )
    active_rows = (
        db.query(func.date(EventLog.created_at), func.count(func.distinct(EventLog.user_id)))
        .filter(EventLog.created_at >= since, EventLog.user_id.isnot(None))
        .group_by(func.date(EventLog.created_at))
        .all()
    )
    new_map = {str(d): c for d, c in new_rows}
    active_map = {str(d): c for d, c in active_rows}

    items = []
    for i in range(days - 1, -1, -1):
        day = (date.today() - timedelta(days=i)).isoformat()
        items.append({"date": day, "new_users": new_map.get(day, 0), "active_users": active_map.get(day, 0)})
    return {"items": items}

