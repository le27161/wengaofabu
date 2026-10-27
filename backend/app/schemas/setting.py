# -*- coding: utf-8 -*-
"""后台系统配置请求体 Schema"""
from typing import Any, Literal

from pydantic import BaseModel, Field


class SettingCreateIn(BaseModel):
    """新建配置"""
    config_key: str = Field(
        min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$", description="配置键"
    )
    value: Any = None
    value_type: Literal["string", "int", "bool", "json"] = "string"
    description: str = Field(default="", max_length=255, description="配置说明")


class SettingUpdateIn(BaseModel):
    """更新配置（键不存在时自动创建）"""
    value: Any = None
    value_type: Literal["string", "int", "bool", "json"] = "string"
    description: str | None = Field(default=None, max_length=255, description="配置说明")
