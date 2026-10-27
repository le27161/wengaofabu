# -*- coding: utf-8 -*-
"""二级审核接口（系统管理员 / 审核管理员 moderator）：待审列表、审核操作、审核记录"""
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core.deps import require_roles
from ..core.pagination import paginate
from ..database import get_db
from ..models.article import Article
from ..models.review import ArticleReview
from ..models.user import User
from ..schemas.article import ReviewIn
from ..services.rag_news_service import sync_published_article_safely

router = APIRouter(prefix="/reviews", tags=["审核"])


@router.get("/pending", summary="待审列表（level=1 待一审 / level=2 待二审）")
def pending_reviews(
    level: int = Query(default=1, ge=1, le=2),
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin", "moderator")),
):
    status = "pending_first" if level == 1 else "pending_second"
    query = db.query(Article).filter(Article.status == status).order_by(Article.updated_at.desc())
    rows, total = paginate(query, page, page_size)
    return {"items": [a.to_dict() for a in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/history", summary="审核记录（管理员）")
def review_history(
    keyword: str | None = Query(default=None, description="按文稿标题筛选"),
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin", "moderator")),
):
    query = db.query(ArticleReview).join(Article, Article.id == ArticleReview.article_id)
    if keyword:
        query = query.filter(Article.title.like(f"%{keyword}%"))
    query = query.order_by(ArticleReview.id.desc())
    rows, total = paginate(query, page, page_size)
    items = []
    for r in rows:
        item = {
            "id": r.id,
            "article_id": r.article_id,
            "article_title": r.article.title if r.article else "",
            "review_level": r.review_level,
            "action": r.action,
            "comment": r.comment,
            "reviewer_name": (r.reviewer.nickname or r.reviewer.username) if r.reviewer else "系统自动审核",
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None,
        }
        items.append(item)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("", summary="执行审核（一审通过 → 待二审；二审通过 → 发布）")
def review_article(
    body: ReviewIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin", "moderator")),
):
    article = db.get(Article, body.article_id)
    if not article:
        raise HTTPException(404, "文稿不存在")

    # 校验当前状态与审核级别匹配，防止重复/越级审核
    expected = "pending_first" if body.level == 1 else "pending_second"
    if article.status != expected:
        raise HTTPException(400, f"当前状态为 {article.status}，不能进行{body.level}级审核")

    # 两级审核需由不同管理员完成：二审时若一审审核人是当前用户则拒绝
    # （系统自动审核的一审 reviewer_id 为空，不受此限制）
    if body.level == 2:
        first_review = (
            db.query(ArticleReview)
            .filter(ArticleReview.article_id == article.id, ArticleReview.review_level == 1)
            .order_by(ArticleReview.id.desc())
            .first()
        )
        if first_review and first_review.reviewer_id == admin.id:
            raise HTTPException(400, "一审与二审需由不同管理员审核，请交由其他管理员处理")

    db.add(ArticleReview(
        article_id=article.id,
        reviewer_id=admin.id,
        review_level=body.level,
        action=body.action,
        comment=body.comment,
    ))

    if body.action == "approve":
        if body.level == 1:
            article.status = "pending_second"  # 一审通过 → 待二审
            message = "一审通过，进入二审"
        else:
            article.status = "published"  # 二审通过 → 发布
            article.published_at = datetime.now()
            message = "二审通过，文稿已发布"
    else:
        article.status = "rejected"  # 任意一级驳回 → 退回编辑
        message = f"{body.level}级审核驳回，已退回编辑"

    db.commit()
    if article.status == "published":
        # 二审事务提交成功后才同步，确保 RAG 不会看到未发布内容。
        background_tasks.add_task(sync_published_article_safely, article.id)
    return {"message": message, "article": article.to_dict()}
