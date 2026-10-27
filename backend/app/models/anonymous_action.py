# -*- coding: utf-8 -*-
"""匿名行为去重模型：未登录用户按设备指纹哈希去重（当前用于转发）

与 user_actions 对应：登录用户按 user_id 去重，匿名用户按 fingerprint_hash 去重。
只存 SHA-256 哈希，不落库原始指纹，降低隐私风险。
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from ..database import Base


class AnonymousAction(Base):
    __tablename__ = "anonymous_actions"
    __table_args__ = (
        UniqueConstraint("fingerprint_hash", "article_id", "action_type", name="uq_anon_fingerprint_article_action"),
    )

    id = Column(Integer, primary_key=True, index=True, comment="记录ID")
    fingerprint_hash = Column(String(64), nullable=False, index=True, comment="设备指纹 SHA-256 哈希")
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True, comment="文稿ID")
    # 行为类型：share 转发（后续如需匿名点赞/收藏去重可直接复用）
    action_type = Column(String(20), nullable=False, comment="行为类型")
    created_at = Column(DateTime, default=datetime.now, comment="发生时间")
