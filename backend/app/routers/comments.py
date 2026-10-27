# -*- coding: utf-8 -*-
"""评论接口：前台发表/回复/删除/列表 + 后台评论管理（管理员）

业务规则：
- 仅登录用户可发表评论与回复；未登录仅可查看。
- 评论只分两级：顶层评论 + 回复（禁止三级回复）。
- 删除权限：评论作者本人或管理员；删除顶层评论时由数据库级联删除其回复。
- 评论内容按纯文本处理（去 HTML 标签后存储），前端插值渲染转义，防存储型 XSS。
"""
import re
from collections import defaultdict
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, get_optional_user, require_roles
from ..core.pagination import paginate
from ..database import get_db
from ..models.article import Article
from ..models.comment import Comment
from ..models.user import User
from ..schemas.comment import CommentIn

router = APIRouter(prefix="/comments", tags=["评论"])
admin_router = APIRouter(prefix="/admin/comments", tags=["后台-评论管理"])


def _clean_content(raw: str) -> str:
    """把评论内容清洗为纯文本：去掉 HTML 标签并压缩多余空白，防御存储型 XSS"""
    text = re.sub(r"<[^>]*>", "", raw or "")
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _get_published_article(db: Session, article_id: int) -> Article:
    article = db.get(Article, article_id)
    if not article or article.status != "published":
        raise HTTPException(404, "文稿不存在或未发布")
    return article


def _serialize_comment(comment: Comment, viewer: Optional[User]) -> dict:
    """序列化单条评论；viewer 用于标记本人/管理员（控制前端删除按钮）"""
    return {
        "id": comment.id,
        "article_id": comment.article_id,
        "user_id": comment.user_id,
        "parent_id": comment.parent_id,
        "nickname": "",
        "avatar": "",
        "content": comment.content,
        "created_at": comment.created_at.strftime("%Y-%m-%d %H:%M:%S") if comment.created_at else None,
        "is_mine": viewer is not None and viewer.id == comment.user_id,
        "is_admin": viewer is not None and viewer.role == "admin",
    }


@router.get("", summary="评论列表（公开，顶层评论分页 + 回复嵌套）")
def list_comments(
    article_id: int = Query(..., description="文稿ID"),
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    viewer: Optional[User] = Depends(get_optional_user),
):
    _get_published_article(db, article_id)

    # 顶层评论按新到旧分页
    query = (
        db.query(Comment)
        .filter(Comment.article_id == article_id, Comment.parent_id.is_(None))
        .order_by(Comment.id.desc())
    )
    top_comments, total = paginate(query, page, page_size)

    # 一次性查出这些顶层评论的全部回复（回复数量有限，不分页，按时间正序）
    top_ids = [c.id for c in top_comments]
    replies = []
    if top_ids:
        replies = (
            db.query(Comment)
            .filter(Comment.parent_id.in_(top_ids))
            .order_by(Comment.id.asc())
            .all()
        )
    reply_map = defaultdict(list)
    for reply in replies:
        reply_map[reply.parent_id].append(reply)

    # 批量取用户昵称/头像，避免逐条查询
    user_ids = {c.user_id for c in top_comments} | {r.user_id for r in replies}
    users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}

    def _serialize_with_user(comment: Comment) -> dict:
        data = _serialize_comment(comment, viewer)
        user = users.get(comment.user_id)
        data["nickname"] = (user.nickname or user.username) if user else "已注销用户"
        data["avatar"] = user.avatar if user else ""
        return data

    items = []
    for comment in top_comments:
        data = _serialize_with_user(comment)
        data["replies"] = [_serialize_with_user(r) for r in reply_map.get(comment.id, [])]
        items.append(data)

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("", summary="发表评论 / 回复（需登录）")
def create_comment(
    body: CommentIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    article = _get_published_article(db, body.article_id)
    content = _clean_content(body.content)
    if not content:
        raise HTTPException(400, "评论内容不能为空")

    parent = None
    if body.parent_id is not None:
        parent = db.get(Comment, body.parent_id)
        # 回复校验：父评论必须存在、属于同一篇文稿、且是顶层评论（禁止三级回复）
        if not parent:
            raise HTTPException(404, "要回复的评论不存在或已删除")
        if parent.article_id != body.article_id:
            raise HTTPException(400, "回复的评论与文稿不匹配")
        if parent.parent_id is not None:
            raise HTTPException(400, "评论只支持一层回复，请在原评论下回复")

    comment = Comment(
        article_id=article.id,
        user_id=user.id,
        parent_id=parent.id if parent else None,
        content=content,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    data = _serialize_comment(comment, user)
    data["nickname"] = user.nickname or user.username
    data["avatar"] = user.avatar or ""
    return {"message": "评论成功", "comment": data}


@router.delete("/{comment_id}", summary="删除评论（作者本人或管理员；顶层评论级联删除回复）")
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    comment = db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(404, "评论不存在或已删除")
    if user.id != comment.user_id and user.role != "admin":
        raise HTTPException(403, "没有权限删除该评论")

    # 删除顶层评论时，其回复由数据库 ON DELETE CASCADE 一并删除
    db.delete(comment)
    db.commit()
    return {"message": "评论已删除"}


@admin_router.get("", summary="后台评论列表（管理员，可按用户/内容/文稿搜索）")
def admin_comments(
    keyword: str | None = Query(default=None, description="按用户名/昵称/评论内容/文稿标题模糊搜索"),
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    query = (
        db.query(Comment, User, Article)
        .join(User, User.id == Comment.user_id)
        .join(Article, Article.id == Comment.article_id)
    )
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            or_(
                User.username.like(like),
                User.nickname.like(like),
                Comment.content.like(like),
                Article.title.like(like),
            )
        )
    query = query.order_by(Comment.id.desc())
    rows, total = paginate(query, page, page_size)

    # 批量取父评论内容，用于后台展示"回复了谁"
    parent_ids = [c.parent_id for c, _, _ in rows if c.parent_id is not None]
    parent_map = {}
    if parent_ids:
        for p in db.query(Comment).filter(Comment.id.in_(parent_ids)).all():
            parent_map[p.id] = p.content[:80]

    items = []
    for comment, user, article in rows:
        items.append({
            "id": comment.id,
            "article_id": article.id,
            "article_title": article.title,
            "user_id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "content": comment.content,
            "parent_id": comment.parent_id,
            "parent_content": parent_map.get(comment.parent_id),
            "created_at": comment.created_at.strftime("%Y-%m-%d %H:%M:%S") if comment.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}
