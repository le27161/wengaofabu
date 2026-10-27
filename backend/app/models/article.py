# -*- coding: utf-8 -*-
"""文稿模型：基础信息 + 栏目多对多 + 互动计数 + 审核状态"""
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Table,
)
from sqlalchemy.orm import relationship

from ..database import Base
from .channel import article_channels


# 文稿-栏目 多对多关联表
article_categories = Table(
    "article_categories",
    Base.metadata,
    Column("article_id", ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
    comment="文稿与栏目多对多关系",
)


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True, comment="文稿ID")
    title = Column(String(200), nullable=False, index=True, comment="标题")
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="作者（编辑）ID")
    summary = Column(String(500), comment="摘要")
    content = Column(Text, comment="正文（HTML）")
    content_source = Column(Text, comment="正文纯文本（无 HTML 标签，供搜索/AI/字数统计使用）")
    cover_url = Column(String(255), comment="封面图URL（来自资源管理）")
    # 同城搜索：文稿归属城市（空串/None 表示全国，不参与同城过滤）
    city = Column(String(50), index=True, comment="城市（同城搜索）")

    # 审核状态机：draft 草稿 → pending_first 待一审 → pending_second 待二审
    #            → published 已发布 / rejected 已驳回 / offline 已下线
    status = Column(String(20), default="draft", index=True, comment="审核状态")

    # 互动计数（冗余字段，便于列表展示，避免实时聚合）
    view_count = Column(Integer, default=0, comment="浏览量")
    like_count = Column(Integer, default=0, comment="点赞数")
    favorite_count = Column(Integer, default=0, comment="收藏数")
    share_count = Column(Integer, default=0, comment="转发数")

    published_at = Column(DateTime, nullable=True, comment="发布时间")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    author = relationship("User", foreign_keys=[author_id])
    categories = relationship("Category", secondary=article_categories, back_populates="articles")
    # 分发渠道：一篇文稿可同时分发给多个渠道（基础渠道始终包含，见 articles.py _apply_channels）
    channels = relationship("Channel", secondary=article_channels, back_populates="articles")
    # passive_deletes: 删除文稿时交给数据库 ON DELETE CASCADE 处理审核记录，
    # 避免 SQLAlchemy 默认把 article_reviews.article_id 置空（该列不允许为空，会报错）
    reviews = relationship(
        "ArticleReview",
        back_populates="article",
        order_by="ArticleReview.id",
        passive_deletes=True,
    )
    # passive_deletes：删除文稿时交给数据库 ON DELETE CASCADE，避免把 article_id 置空报错
    main_tags = relationship(
        "ArticleMainTag",
        back_populates="article",
        passive_deletes=True,
    )
    keywords = relationship(
        "ArticleKeyword",
        back_populates="article",
        passive_deletes=True,
    )
    smart_collect_source = relationship(
        "SmartCollectArticleSource",
        primaryjoin="Article.id == foreign(SmartCollectArticleSource.article_id)",
        back_populates="article",
        cascade="all, delete-orphan",
        uselist=False,
    )

    def to_dict(self, include_content: bool = False, include_reviews: bool = False) -> dict:
        """序列化为字典；正文与审核记录默认不返回（列表场景更轻量）"""
        data = {
            "id": self.id,
            "title": self.title,
            "author_id": self.author_id,
            "author_name": self.author.nickname or self.author.username if self.author else "",
            "summary": self.summary,
            "cover_url": self.cover_url,
            "city": self.city,
            "status": self.status,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "favorite_count": self.favorite_count,
            "share_count": self.share_count,
            "categories": [c.to_dict() for c in self.categories],
            "channels": [
                {"id": c.id, "name": c.name, "slug": c.slug, "is_default": bool(c.is_default)}
                for c in self.channels
            ],
            "published_at": self.published_at.strftime("%Y-%m-%d %H:%M:%S") if self.published_at else None,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
        if include_content:
            data["content"] = self.content
            data["content_source"] = self.content_source or ""
        if include_reviews:
            data["reviews"] = [
                {
                    "id": r.id,
                    "review_level": r.review_level,
                    "action": r.action,
                    "comment": r.comment,
                    "reviewer_name": (r.reviewer.nickname or r.reviewer.username) if r.reviewer else "系统自动审核",
                    "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None,
                }
                for r in self.reviews
            ]
        return data
