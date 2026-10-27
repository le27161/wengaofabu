# -*- coding: utf-8 -*-
"""AI 分类纠正数据集模型

写手在 AI 协作台对不准确的 AI 分类结果提交纠正，形成「标题 + 正文 + 模型分类 + 纠正分类」
的高质量训练样本，供后续二次训练模型使用。
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from ..database import Base


class AICorrection(Base):
    """AI 分类纠正记录：一条 = 一个训练样本（标题 + 正文 + 纠错前后分类）"""
    __tablename__ = "ai_corrections"

    id = Column(Integer, primary_key=True, index=True, comment="记录ID")
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="提交纠正的用户ID",
    )
    article_id = Column(Integer, nullable=True, index=True, comment="关联文稿ID（可选）")
    draft_key = Column(String(64), nullable=True, index=True, comment="草稿会话标识：保存后回填 article_id")
    title = Column(String(200), nullable=False, comment="文稿标题（训练样本文本）")
    content = Column(Text, nullable=False, default="", comment="文稿正文纯文本（训练样本正文，可空）")
    model_category = Column(String(50), nullable=False, default="", comment="AI 模型原始分类（中文名）")
    corrected_category = Column(String(50), nullable=False, index=True, comment="用户纠正后的分类（中文名）")
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True, comment="提交时间")
