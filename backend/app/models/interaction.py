# -*- coding: utf-8 -*-
"""用户互动模型：点赞、收藏（同一用户对同一篇文章同一行为只保留一条）"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint

from ..database import Base


class UserAction(Base):
    __tablename__ = "user_actions"
    __table_args__ = (
        UniqueConstraint("user_id", "article_id", "action_type", name="uq_user_article_action"),
    )

    id = Column(Integer, primary_key=True, index=True, comment="互动ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="用户ID")
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True, comment="文稿ID")
    # 行为类型：like 点赞 / favorite 收藏 / share 转发（转发去重复用同一唯一约束）
    action_type = Column(String(20), nullable=False, comment="行为类型")
    created_at = Column(DateTime, default=datetime.now, comment="互动时间")

