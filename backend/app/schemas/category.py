# -*- coding: utf-8 -*-
"""栏目相关请求体 Schema"""
from pydantic import BaseModel, Field


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=50, description="栏目名称")
    slug: str = Field(min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$", description="栏目标识")
    description: str = Field(default="", max_length=500, description="栏目简介")
    sort_order: int = 0
    status: str = "active"

