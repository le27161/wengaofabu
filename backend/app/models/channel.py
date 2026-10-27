# -*- coding: utf-8 -*-
"""分发渠道模型：文稿可同时分发到多个渠道；is_default 为基础渠道（所有文稿默认包含）"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship

from ..database import Base


# 文稿-分发渠道 多对多关联表
article_channels = Table(
    "article_channels",
    Base.metadata,
    Column("article_id", ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    Column("channel_id", ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True),
    comment="文稿与分发渠道多对多关系",
)


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True, comment="渠道ID")
    name = Column(String(50), nullable=False, comment="渠道名称")
    slug = Column(String(50), unique=True, index=True, comment="渠道标识（用于RSS地址等）")
    description = Column(String(500), comment="渠道简介")
    sort_order = Column(Integer, default=0, comment="排序权重（越小越靠前）")
    # 状态：active 启用 / disabled 停用（停用渠道不再出现在写稿勾选与RSS中）
    status = Column(String(20), default="active", comment="渠道状态")
    # 基础渠道：门户（所有文稿默认包含且不可移除，禁止删除）
    is_default = Column(Boolean, default=False, comment="是否为基础渠道（门户）")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    articles = relationship("Article", secondary=article_channels, back_populates="channels")

    def to_dict(self, article_count: int = 0) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "sort_order": self.sort_order,
            "status": self.status,
            "is_default": bool(self.is_default),
            "article_count": article_count,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }
