# -*- coding: utf-8 -*-
"""AI 协作台任务模型：异步执行 AI 辅助功能的持久化任务状态

与 ai_call_logs（调用记录）职责分离：
- ai_tasks：任务执行载体（pending → running → success / failed），支撑前端轮询
- ai_call_logs：调用事实记录（谁、何时、入参、返回值），后台可查看

feature_type 数字含义与 ai_call_logs 一致：
    1 = AI 分类（根据标题自动选择栏目）
    2 = AI 生成摘要（根据标题 + 正文生成文稿摘要）
    3 = AI 多维度审核（色情 / 暴力 / 文明 / 涉政等维度审查）
    4 = AI 内容校验（错别字、标点等错误检测）
    5 = AI 文稿打分（正文质量评分）
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text

from ..database import Base


class AITask(Base):
    """AI 异步任务：提交后立即返回 task_id，后台线程执行并更新状态，前端轮询获取结果"""
    __tablename__ = "ai_tasks"

    id = Column(Integer, primary_key=True, index=True, comment="任务ID")
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="发起任务用户ID",
    )
    # 数字含义见本文件顶部注释：1=AI分类 2=AI生成摘要 3=AI多维度审核 4=AI内容校验 5=AI文稿打分
    article_id = Column(
        Integer, nullable=True, index=True,
        comment="关联文稿ID；新建文稿未保存时为NULL，避免跨文稿恢复旧结果",
    )
    draft_key = Column(
        String(64), nullable=True, index=True,
        comment="草稿会话标识：新建文稿未保存时用于关联同一草稿会话的任务，保存后回填 article_id",
    )
    feature_type = Column(Integer, nullable=False, index=True, comment="AI功能类型（1=AI分类 2=AI生成摘要 3=AI多维度审核 4=AI内容校验 5=AI文稿打分）")
    status = Column(String(16), nullable=False, default="pending", index=True, comment="任务状态：pending/running/success/failed")
    input_params = Column(JSON, nullable=False, comment="调用入参（JSON，含标题/摘要/正文等）")
    result_data = Column(JSON, nullable=True, comment="任务成功后的业务返回数据（JSON）")
    error_message = Column(String(500), nullable=True, comment="失败原因")
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True, comment="任务提交时间")
    started_at = Column(DateTime, nullable=True, comment="任务开始执行时间")
    finished_at = Column(DateTime, nullable=True, comment="任务完成时间")
