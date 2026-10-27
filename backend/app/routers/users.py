# -*- coding: utf-8 -*-
"""用户管理接口（仅管理员）：列表、创建（含管理员）、编辑（冻结/角色）、删除

删除用户时会联动处理其关联数据：
- 用户创建的文稿级联删除（含栏目/渠道关联、审核记录、互动、观看历史）
- 用户上传的资源保留并转移给系统管理员（避免其他文稿引用失效）
- 用户作为审核人的审核记录保留，审核人置空（留痕不丢）
- 用户的点赞/收藏/转发等互动记录删除
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, require_roles
from ..core.pagination import paginate
from ..core.security import hash_password
from ..database import get_db
from ..models.article import Article
from ..models.interaction import UserAction
from ..models.review import ArticleReview
from ..models.resource import Resource
from ..models.user import User
from ..schemas.user import UserAdminCreate, UserAdminUpdate

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("", summary="用户列表（可按关键词/角色/状态筛选）")
def list_users(
    keyword: str | None = Query(default=None, description="用户名/昵称关键词"),
    role: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    query = db.query(User)
    if keyword:
        query = query.filter(or_(User.username.like(f"%{keyword}%"), User.nickname.like(f"%{keyword}%")))
    if role:
        query = query.filter(User.role == role)
    if status:
        query = query.filter(User.status == status)
    query = query.order_by(User.created_at.desc())

    rows, total = paginate(query, page, page_size)
    return {"items": [u.to_dict() for u in rows], "total": total, "page": page, "page_size": page_size}


@router.post("", summary="管理员创建账号（可创建管理员/编辑/用户）")
def create_user(body: UserAdminCreate, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(400, "用户名已存在")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        nickname=body.nickname or body.username,
        email=body.email,
        role=body.role,
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "创建成功", "user": user.to_dict()}


@router.put("/{user_id}", summary="编辑用户（角色 / 冻结解冻 / 资料）")
def update_user(
    user_id: int,
    body: UserAdminUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")

    # 防止把最后一个管理员降级或冻结，导致系统失去管理员
    if user.role == "admin":
        admin_count = db.query(User).filter(User.role == "admin", User.status == "active").count()
        if (body.role and body.role != "admin") or (body.status == "frozen") and admin_count <= 1:
            raise HTTPException(400, "至少保留一名正常状态的管理员")

    if body.nickname is not None:
        user.nickname = body.nickname
    if body.email is not None:
        user.email = body.email
    if body.bio is not None:
        user.bio = body.bio
    if body.role is not None:
        user.role = body.role
    if body.status is not None:
        user.status = body.status  # frozen 冻结 / active 解冻

    db.commit()
    db.refresh(user)
    return {"message": "保存成功", "user": user.to_dict()}


@router.delete("/{user_id}", summary="删除用户")
def delete_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    if user_id == admin.id:
        raise HTTPException(400, "不能删除当前登录账号")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.role == "admin":
        admin_count = db.query(User).filter(User.role == "admin", User.status == "active").count()
        if admin_count <= 1:
            raise HTTPException(400, "至少保留一名管理员，无法删除")

    # 1. 删除该用户创建的文稿（审核记录、互动、观看历史随文稿外键级联删除）
    articles = db.query(Article).filter(Article.author_id == user_id).all()
    for article in articles:
        db.delete(article)

    # 2. 资源保留：转移给系统管理员，避免其他文稿封面/正文引用失效
    fallback_admin = db.query(User).filter(User.role == "admin", User.status == "active").first()
    if fallback_admin:
        db.query(Resource).filter(Resource.user_id == user_id).update(
            {"user_id": fallback_admin.id}, synchronize_session=False
        )

    # 3. 审核记录保留：审核人置空（相当于系统审核，留痕不丢）
    db.query(ArticleReview).filter(ArticleReview.reviewer_id == user_id).update(
        {"reviewer_id": None}, synchronize_session=False
    )

    # 4. 删除该用户的互动记录（点赞/收藏/转发/不感兴趣）
    db.query(UserAction).filter(UserAction.user_id == user_id).delete(synchronize_session=False)

    # 5. 删除用户（观看历史、AI 调用记录由数据库外键 CASCADE 自动清理）
    db.delete(user)
    db.commit()
    return {"message": f"删除成功，已联动删除其创建的 {len(articles)} 篇文稿"}

