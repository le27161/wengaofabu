# -*- coding: utf-8 -*-
"""后台用户行为查看接口（管理员）：观看历史、不感兴趣记录"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..core.deps import require_roles
from ..core.pagination import paginate
from ..database import get_db
from ..models.article import Article
from ..models.interaction import UserAction
from ..models.user import User
from ..models.view_history import ViewHistory

router = APIRouter(prefix="/admin/behavior", tags=["后台-用户行为"])


@router.get("/history", summary="用户观看历史（管理员，可按用户/文稿搜索）")
def admin_view_history(
    keyword: str | None = Query(default=None, description="按用户名/昵称/文稿标题模糊搜索"),
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    query = (
        db.query(ViewHistory, User, Article)
        .join(User, User.id == ViewHistory.user_id)
        .join(Article, Article.id == ViewHistory.article_id)
    )
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(User.username.like(like), User.nickname.like(like), Article.title.like(like)))
    query = query.order_by(ViewHistory.viewed_at.desc(), ViewHistory.id.desc())
    rows, total = paginate(query, page, page_size)

    # 全部匹配记录的累计观看时长（便于后台看总量，不受分页影响）
    sum_query = db.query(func.coalesce(func.sum(ViewHistory.watch_seconds), 0))
    if keyword:
        like = f"%{keyword}%"
        sum_query = sum_query.join(User, User.id == ViewHistory.user_id).join(Article, Article.id == ViewHistory.article_id)
        sum_query = sum_query.filter(or_(User.username.like(like), User.nickname.like(like), Article.title.like(like)))
    total_watch_seconds = int(sum_query.scalar() or 0)

    items = []
    for history, user, article in rows:
        items.append({
            "id": history.id,
            "user_id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "article_id": article.id,
            "article_title": article.title,
            "viewed_at": history.viewed_at.strftime("%Y-%m-%d %H:%M:%S") if history.viewed_at else None,
            "watch_seconds": history.watch_seconds,
            "watch_count": history.watch_count,
        })
    return {
        "items": items,
        "total": total,
        "total_watch_seconds": total_watch_seconds,
        "page": page,
        "page_size": page_size,
    }


@router.get("/dislikes", summary="用户不感兴趣记录（管理员）")
def admin_dislikes(
    keyword: str | None = Query(default=None, description="按用户名/昵称/文稿标题模糊搜索"),
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    query = (
        db.query(UserAction, User, Article)
        .join(User, User.id == UserAction.user_id)
        .join(Article, Article.id == UserAction.article_id)
        .filter(UserAction.action_type == "dislike")
    )
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(User.username.like(like), User.nickname.like(like), Article.title.like(like)))
    query = query.order_by(UserAction.id.desc())
    rows, total = paginate(query, page, page_size)
    items = []
    for action, user, article in rows:
        items.append({
            "id": action.id,
            "user_id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "article_id": article.id,
            "article_title": article.title,
            "created_at": action.created_at.strftime("%Y-%m-%d %H:%M:%S") if action.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}
