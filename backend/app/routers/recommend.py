# -*- coding: utf-8 -*-
"""个性化推荐接口（独立模块）

推荐优先级：
1. 用户显式兴趣偏好（user_preferences 表，登录弹窗多选）
2. 近30天行为统计偏好栏目（埋点 + 互动）
3. 未登录/无任何数据：全站热门兜底
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.deps import get_optional_user
from ..database import get_db
from ..models.article import Article, article_categories
from ..models.event import EventLog
from ..models.interaction import UserAction
from ..models.preference import UserPreference
from ..models.user import User
from ..services.recommendation_service import recommend_articles as legacy_recommend_articles

router = APIRouter(prefix="/articles", tags=["个性化推荐"])

# 行为权重：收藏 > 点赞/分享 > 浏览
WEIGHT = {"favorite": 3, "like": 2, "share": 2, "view": 1}


def _behavior_categories(db: Session, user_id: int, days: int = 30) -> list[int]:
    """近 N 天行为统计出的偏好栏目（按得分取 Top3）"""
    since = datetime.now() - timedelta(days=days)

    logs = (
        db.query(EventLog.event_type, article_categories.c.category_id, func.count(EventLog.id))
        .join(article_categories, EventLog.article_id == article_categories.c.article_id)
        .filter(EventLog.user_id == user_id, EventLog.created_at >= since)
        .group_by(EventLog.event_type, article_categories.c.category_id)
        .all()
    )
    acts = (
        db.query(UserAction.action_type, article_categories.c.category_id, func.count(UserAction.id))
        .join(article_categories, UserAction.article_id == article_categories.c.article_id)
        .filter(UserAction.user_id == user_id, UserAction.created_at >= since)
        .group_by(UserAction.action_type, article_categories.c.category_id)
        .all()
    )
    score: dict[int, int] = {}
    for etype, cid, cnt in logs:
        score[cid] = score.get(cid, 0) + WEIGHT.get(etype, 1) * cnt
    for atype, cid, cnt in acts:
        score[cid] = score.get(cid, 0) + WEIGHT.get(atype, 1) * cnt
    return [cid for cid, _ in sorted(score.items(), key=lambda kv: kv[1], reverse=True)][:3]


@router.get("/recommend", summary="个性化推荐（兴趣偏好 → 行为偏好 → 全站热文）")
def recommend_articles(
    limit: int = Query(default=6, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    fav_categories: list[int] = []
    reason = "全站热门推荐"

    if user is not None:
        # 1) 显式兴趣偏好优先
        pref_rows = (
            db.query(UserPreference.category_id)
            .filter(UserPreference.user_id == user.id)
            .all()
        )
        fav_categories = [r[0] for r in pref_rows]
        if fav_categories:
            reason = "根据您的兴趣偏好推荐"
        else:
            # 2) 无显式偏好则用行为统计
            fav_categories = _behavior_categories(db, user.id)
            if fav_categories:
                reason = "根据您的浏览与互动偏好推荐"

    if fav_categories:
        query = db.query(Article).filter(Article.status == "published")
        query = (
            query.join(article_categories, Article.id == article_categories.c.article_id)
            .filter(article_categories.c.category_id.in_(fav_categories))
            .distinct()
        )
        query = query.order_by(Article.view_count.desc(), Article.published_at.desc()).limit(limit)
        rows = query.all()
        return {
            "reason": reason,
            "items": [a.to_dict() for a in rows],
            "total": len(rows),
        }

    # 3) 无显式偏好/行为数据时，沿用原有向量召回与通用推荐逻辑
    items = legacy_recommend_articles(db, user, limit)
    return {
        "reason": reason,
        "items": [a.to_dict() for a in items],
        "total": len(items),
    }
