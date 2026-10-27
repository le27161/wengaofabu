# -*- coding: utf-8 -*-
"""埋点请求体 Schema"""
from pydantic import BaseModel, Field


class EventIn(BaseModel):
    event_type: str = Field(pattern="^(view|like|favorite|share)$", description="事件类型")
    article_id: int | None = Field(default=None, description="关联文稿ID（可选）")

