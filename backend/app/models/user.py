# -*- coding: utf-8 -*-
"""用户模型：注册用户 / 编辑 / 管理员，三种身份通过 role 区分"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime

from ..database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, comment="用户ID")
    username = Column(String(50), unique=True, nullable=False, index=True, comment="登录账号")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    nickname = Column(String(50), comment="昵称")
    email = Column(String(100), comment="邮箱")
    avatar = Column(String(255), comment="头像URL")
    # 角色：user 普通用户 / editor 编辑 / admin 管理员
    role = Column(String(20), default="user", index=True, comment="角色")
    # 状态：active 正常 / frozen 冻结（冻结后无法登录与互动）
    status = Column(String(20), default="active", index=True, comment="账号状态")
    # 积分：每日签到获得，后台可调整（正加负减，不小于 0）
    # nullable=False + server_default="0"：新库 DDL 与老库 ALTER 迁移保持一致（NOT NULL DEFAULT 0）
    points = Column(Integer, nullable=False, default=0, server_default="0", comment="用户积分")
    bio = Column(String(255), comment="个人简介（编辑简介）")
    created_at = Column(DateTime, default=datetime.now, comment="注册时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def to_dict(self, with_password: bool = False) -> dict:
        """序列化为字典，默认不返回密码哈希"""
        data = {
            "id": self.id,
            "username": self.username,
            "nickname": self.nickname,
            "email": self.email,
            "avatar": self.avatar,
            "role": self.role,
            "status": self.status,
            "points": self.points or 0,
            "bio": self.bio,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }
        if with_password:
            data["password_hash"] = self.password_hash
        return data

