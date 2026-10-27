# -*- coding: utf-8 -*-
"""评论模型：文稿评论 + 评论回复（两级：parent_id 为空为顶层评论，非空为回复）"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text

from ..database import Base


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True, comment="评论ID")
    article_id = Column(
        Integer,
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属文稿ID",
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="发表用户ID",
    )
    # 自引用：回复指向顶层评论；删除顶层评论时由数据库 CASCADE 级联删除其回复
    parent_id = Column(
        Integer,
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="父评论ID（回复用；NULL 表示顶层评论）",
    )
    # 评论内容按纯文本存储，前端插值渲染转义，禁止直接 v-html，防存储型 XSS
    content = Column(Text, nullable=False, comment="评论内容（纯文本，不含HTML标签）")
    created_at = Column(DateTime, default=datetime.now, comment="发表时间")
