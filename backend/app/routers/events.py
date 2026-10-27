# -*- coding: utf-8 -*-
"""埋点接口：前端上报用户行为（观看/点赞/收藏/转发等）

点赞/收藏/转发在 interactions 接口内部同步写埋点；
这里主要承载「进入文稿详情页观看」等页面级埋点。
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import update
from sqlalchemy.orm import Session

from ..core.deps import get_optional_user
from ..database import get_db
from ..models.article import Article
from ..models.user import User
from ..schemas.event import EventIn
from ..services.event_service import record_event

router = APIRouter(prefix="/events", tags=["埋点"])


@router.post("", summary="上报行为埋点（view 观看等）")
def report_event(
    body: EventIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    article = None
    if body.article_id:
        article = db.get(Article, body.article_id)
        if not article or article.status != "published":
            return {"ok": False, "message": "文稿不存在或未发布"}

    record_event(
        db,
        event_type=body.event_type,
        article_id=body.article_id,
        user_id=user.id if user else None,
        request=request,
    )

    # view 埋点同时累加浏览量（观看计数）
    if body.event_type == "view" and article:
        # bulk update 累加浏览量，避免触发 updated_at 刷新
        db.execute(
            update(Article).where(Article.id == article.id).values(view_count=Article.view_count + 1, updated_at=Article.updated_at)
        )

    db.commit()
    return {"ok": True}
