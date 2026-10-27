# -*- coding: utf-8 -*-
"""文稿审核记录模型（二级审核：一审 level=1、二审 level=2）"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from ..database import Base


class ArticleReview(Base):
    __tablename__ = "article_reviews"

    id = Column(Integer, primary_key=True, index=True, comment="审核记录ID")
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"),
                        nullable=False, index=True, comment="文稿ID")
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="审核人ID（系统自动审核时为空）")
    review_level = Column(Integer, default=1, comment="审核级别：1 一审 / 2 二审")
    # 动作：approve 通过 / reject 驳回
    action = Column(String(20), nullable=False, comment="审核动作")
    comment = Column(String(500), comment="审核意见")
    created_at = Column(DateTime, default=datetime.now, comment="审核时间")

    article = relationship("Article", back_populates="reviews")
    reviewer = relationship("User", foreign_keys=[reviewer_id])
