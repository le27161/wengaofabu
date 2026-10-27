# -*- coding: utf-8 -*-
"""AI 新闻助手接口 DTO。"""
from pydantic import BaseModel, Field


class AINewsChatIn(BaseModel):
    """新闻门户用户向 AI 新闻助手发送的问题。"""

    question: str = Field(min_length=1, max_length=2000, description="新闻相关问题")
    category: str | None = Field(default=None, min_length=1, max_length=50, description="可选栏目名称")
