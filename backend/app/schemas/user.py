# -*- coding: utf-8 -*-
"""用户相关请求体 Schema"""
from typing import Literal

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    """注册请求：普通用户或编辑注册"""
    username: str = Field(min_length=3, max_length=50, description="登录账号")
    password: str = Field(min_length=6, max_length=64, description="密码")
    nickname: str = Field(default="", max_length=50, description="昵称")
    email: str = Field(default="", max_length=100, description="邮箱")
    role: Literal["user", "editor"] = "user"  # 注册时只能选普通用户或编辑


class LoginIn(BaseModel):
    """登录请求"""
    username: str
    password: str


class ProfileUpdateIn(BaseModel):
    """修改个人资料"""
    nickname: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=100)
    avatar: str | None = Field(default=None, max_length=255)
    bio: str | None = Field(default=None, max_length=255)
    old_password: str | None = Field(default=None, max_length=64, description="修改密码时必填原密码")
    new_password: str | None = Field(default=None, min_length=6, max_length=64, description="新密码")


class UserAdminCreate(BaseModel):
    """系统管理员创建账号（可创建管理员/编辑/用户；moderator 即“管理员”，仅能后台创建）"""
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=64)
    nickname: str = Field(default="", max_length=50)
    email: str = Field(default="", max_length=100)
    role: Literal["user", "editor", "moderator", "admin"] = "user"


class UserAdminUpdate(BaseModel):
    """系统管理员编辑用户：改角色 / 冻结解冻 / 资料"""
    nickname: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=100)
    bio: str | None = Field(default=None, max_length=255)
    role: Literal["user", "editor", "moderator", "admin"] | None = None
    status: Literal["active", "frozen"] | None = None

