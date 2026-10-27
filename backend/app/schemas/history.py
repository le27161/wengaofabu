# -*- coding: utf-8 -*-
"""观看历史相关请求体 Schema"""
from pydantic import BaseModel, Field


class DurationIn(BaseModel):
    """观看时长上报：单篇单次上限 600 秒（10 分钟）"""
    seconds: int = Field(ge=1, le=600, description="本次观看时长（秒），上限600秒")
