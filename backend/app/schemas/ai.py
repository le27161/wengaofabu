# -*- coding: utf-8 -*-
"""AI 协作台相关请求体 Schema"""
from datetime import datetime

from pydantic import BaseModel, Field


class AIAssistIn(BaseModel):
    """AI 协作台通用入参：各功能按需取用其中字段"""
    title: str = Field(default="", max_length=500, description="文稿标题")
    summary: str = Field(default="", max_length=1000, description="文稿摘要（生成摘要功能不需要传）")
    content: str = Field(default="", description="文稿正文（HTML 原文）")
    category_ids: list[int] = Field(default_factory=list, description="当前已选栏目ID列表（可选，供 AI 参考）")
    article_id: int | None = Field(default=None, description="关联文稿ID（编辑时传入，新建未保存时为 null）")
    draft_key: str | None = Field(default=None, max_length=64, description="草稿会话标识（新建未保存文稿生成；保存后用于回填关联文稿ID）")


class AITaskOut(BaseModel):
    """AI 任务提交响应：立即返回 task_id，结果异步产生"""
    task_id: int = Field(description="任务ID，前端据此轮询状态")
    status: str = Field(description="任务初始状态：pending")


class AITaskStatusOut(BaseModel):
    """AI 任务状态查询响应"""
    task_id: int = Field(description="任务ID")
    article_id: int | None = Field(default=None, description="关联文稿ID")
    feature_type: int = Field(description="AI功能类型（1~5）")
    feature_name: str = Field(description="AI功能中文名")
    status: str = Field(description="任务状态：pending/running/success/failed")
    result: dict | None = Field(default=None, description="任务成功后的业务返回数据")
    error: str | None = Field(default=None, description="失败原因（status=failed 时非空）")
    created_at: datetime | None = Field(default=None, description="任务提交时间")
    started_at: datetime | None = Field(default=None, description="任务开始执行时间")
    finished_at: datetime | None = Field(default=None, description="任务完成时间")


class AICorrectionIn(BaseModel):
    """AI 分类纠正入参：一条训练样本（标题 + 正文 + 纠错前后分类）"""
    title: str = Field(min_length=1, max_length=200, description="文稿标题")
    content: str = Field(default="", max_length=20000, description="文稿正文纯文本（可空）")
    model_category: str = Field(default="", max_length=50, description="AI 模型原始分类（中文名）")
    corrected_category: str = Field(min_length=1, max_length=50, description="用户纠正后的分类（中文名）")
    article_id: int | None = Field(default=None, description="关联文稿ID（可选）")
    draft_key: str | None = Field(default=None, max_length=64, description="草稿会话标识（可选，保存后回填 article_id）")
