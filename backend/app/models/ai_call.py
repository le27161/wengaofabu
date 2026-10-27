# -*- coding: utf-8 -*-
"""AI 协作台调用记录模型：记录写手调用 AI 辅助功能的信息

feature_type 数字含义（与后端 routers/ai_assist.py 常量、后台页面筛选一一对应）：
    1 = AI 分类（根据标题自动选择栏目）
    2 = AI 生成摘要（根据标题 + 正文生成文稿摘要）
    3 = AI 多维度审核（色情 / 暴力 / 文明 / 涉政等维度审查）
    4 = AI 内容校验（错别字、标点等错误检测）
    5 = AI 文稿打分（正文质量评分）
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String

from ..database import Base


class AICallLog(Base):
    """AI 调用日志：谁、何时、调用了哪个 AI 功能，以及入参与返回值"""
    __tablename__ = "ai_call_logs"

    id = Column(Integer, primary_key=True, index=True, comment="记录ID")
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="调用用户ID",
    )
    # 数字含义见本文件顶部注释：1=AI分类 2=AI生成摘要 3=AI多维度审核 4=AI内容校验 5=AI文稿打分
    article_id = Column(
        Integer, nullable=True, index=True,
        comment="关联文稿ID；新建文稿未保存时为NULL",
    )
    draft_key = Column(
        String(64), nullable=True, index=True,
        comment="草稿会话标识：新建文稿未保存时用于关联同一草稿会话的调用记录，保存后回填 article_id",
    )
    feature_type = Column(Integer, nullable=False, index=True, comment="AI功能类型（1=AI分类 2=AI生成摘要 3=AI多维度审核 4=AI内容校验 5=AI文稿打分）")
    input_params = Column(JSON, nullable=False, comment="调用入参（JSON，含标题/摘要/正文等）")
    output_data = Column(JSON, nullable=False, comment="接口返回值（JSON）")
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True, comment="调用时间")
