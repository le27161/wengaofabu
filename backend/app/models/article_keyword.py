# -*- coding: utf-8 -*-
"""文章关键词模型：存储 AI 提取的核心术语及前置知识链"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from ..database import Base


class ArticleKeyword(Base):
    __tablename__ = "article_keywords"

    id = Column(Integer, primary_key=True, index=True, comment="关键词记录ID")
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True, comment="所属文稿ID")
    keyword = Column(String(100), nullable=False, comment="主关键词（核心术语）")
    prerequisites = Column(JSON, nullable=False, comment="前置知识标签链（由浅入深排列，如 [\"哈希算法\", \"分布式账本\"]）")
    color = Column(String(20), nullable=False, default="#4A90D9", comment="该关键词组的颜色标识（同一组用同一颜色）")
    sort_order = Column(Integer, default=0, comment="排序序号")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    article = relationship("Article", back_populates="keywords")
