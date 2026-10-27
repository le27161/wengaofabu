# -*- coding: utf-8 -*-
"""积分相关请求体 Schema"""
from pydantic import BaseModel, Field


class PointsDeltaIn(BaseModel):
    """后台调整积分：正数加分、负数扣分"""
    delta: int = Field(ge=-100000, le=100000, description="积分调整量（正加负减）")
