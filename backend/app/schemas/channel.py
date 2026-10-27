# -*- coding: utf-8 -*-
"""分发渠道相关请求体 Schema"""
from pydantic import BaseModel, Field


class ChannelIn(BaseModel):
    name: str = Field(min_length=1, max_length=50, description="渠道名称")
    slug: str = Field(min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$", description="渠道标识")
    description: str = Field(default="", max_length=500, description="渠道简介")
    sort_order: int = Field(default=0, ge=0, description="排序权重")
    status: str = Field(default="active", pattern="^(active|disabled)$", description="渠道状态")
