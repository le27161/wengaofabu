# -*- coding: utf-8 -*-
"""文章标签双表模型：主关键词（article_main_tags）+ 分支关键词（article_sub_tags）

主关键词为文章核心术语，分支关键词为由浅入深的前置知识链。
新文章入库时 AI 自动提取并写入，前端直接读取展示。
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base


class ArticleMainTag(Base):
    """文章主关键词表"""
    __tablename__ = "article_main_tags"

    id = Column(Integer, primary_key=True, index=True, comment="主关键词ID")
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True, comment="所属文稿ID")
    tag_name = Column(String(50), nullable=False, comment="主关键词名称（核心术语）")
    category = Column(String(20), nullable=False, default="", comment="分类")
    sort_order = Column(Integer, default=0, comment="排序序号")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    article = relationship("Article", back_populates="main_tags")
    sub_tags = relationship(
        "ArticleSubTag", back_populates="main_tag",
        order_by="ArticleSubTag.sort_order",
        cascade="all, delete-orphan",
    )


class ArticleSubTag(Base):
    """文章分支关键词表（前置知识链）"""
    __tablename__ = "article_sub_tags"

    id = Column(Integer, primary_key=True, index=True, comment="分支关键词ID")
    main_tag_id = Column(Integer, ForeignKey("article_main_tags.id", ondelete="CASCADE"), nullable=False, index=True, comment="所属主关键词ID")
    tag_name = Column(String(50), nullable=False, comment="分支关键词名称（前置知识）")
    sort_order = Column(Integer, default=0, comment="知识链位置（1=最靠近主标签，N=最远的基础知识）")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    main_tag = relationship("ArticleMainTag", back_populates="sub_tags")
