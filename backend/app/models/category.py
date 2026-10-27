# -*- coding: utf-8 -*-
"""栏目（分类）模型"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship

from ..database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True, comment="栏目ID")
    name = Column(String(50), nullable=False, comment="栏目名称")
    slug = Column(String(50), unique=True, index=True, comment="栏目标识（用于URL）")
    description = Column(String(500), comment="栏目简介")
    sort_order = Column(Integer, default=0, comment="排序权重（越小越靠前）")
    # 状态：active 启用 / hidden 隐藏（前台不可见）
    status = Column(String(20), default="active", comment="栏目状态")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 与文稿的多对多关系（一篇文章可挂多个栏目）
    articles = relationship("Article", secondary="article_categories", back_populates="categories")

    def to_dict(self, article_count: int = 0) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "sort_order": self.sort_order,
            "status": self.status,
            "article_count": article_count,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }

