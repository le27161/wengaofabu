# -*- coding: utf-8 -*-
"""认证接口：注册（用户/编辑）、登录、当前用户、个人资料"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.deps import get_current_user
from ..core.security import create_access_token, hash_password, verify_password
from ..database import get_db
from ..models.user import User
from ..schemas.user import LoginIn, ProfileUpdateIn, RegisterIn
from ..services.settings_service import get_setting

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", summary="注册账号（普通用户或编辑）")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(400, "用户名已存在")

    # 编辑注册开关：后台「门户设置」关闭后，编辑账号只能由管理员在后台创建
    if body.role == "editor" and not get_setting(db, "register_editor_enabled", default=True):
        raise HTTPException(400, "编辑注册已关闭，编辑账号需由管理员在后台创建")

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        nickname=body.nickname or body.username,
        email=body.email,
        role=body.role,  # 注册身份：普通用户，或开关开启时的编辑
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "注册成功", "user": user.to_dict()}


@router.post("/login", summary="登录，返回 JWT")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(400, "用户名或密码错误")
    if user.status == "frozen":
        raise HTTPException(403, "账号已被冻结，请联系管理员")

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"access_token": token, "token_type": "bearer", "user": user.to_dict()}


@router.get("/me", summary="获取当前登录用户信息")
def get_me(user: User = Depends(get_current_user)):
    return user.to_dict()


@router.put("/me", summary="修改个人资料 / 修改密码")
def update_me(body: ProfileUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.nickname is not None:
        user.nickname = body.nickname
    if body.email is not None:
        user.email = body.email
    if body.avatar is not None:
        user.avatar = body.avatar
    if body.bio is not None:
        user.bio = body.bio

    # 修改密码：需要校验原密码
    if body.new_password:
        if not body.old_password or not verify_password(body.old_password, user.password_hash):
            raise HTTPException(400, "原密码错误")
        user.password_hash = hash_password(body.new_password)

    db.commit()
    db.refresh(user)
    return {"message": "保存成功", "user": user.to_dict()}

