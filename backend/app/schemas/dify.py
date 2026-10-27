# -*- coding: utf-8 -*-
"""Dify 工作流相关请求体 Schema"""
from pydantic import BaseModel, Field


class DifyWorkflowIn(BaseModel):
    """新建/编辑 Dify 工作流登记"""
    name: str = Field(
        min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$",
        description="业务标识（唯一，如 article_summary）",
    )
    api_base: str = Field(min_length=1, max_length=255, description="Dify API 地址")
    api_key: str | None = Field(default=None, max_length=255, description="Dify 应用 API Key，编辑时留空/传空表示保留原 Key")
    description: str = Field(default="", max_length=500, description="用途说明")
    input_schema: dict = Field(default_factory=dict, description="输入参数说明（JSON）")
    enabled: bool = True
    timeout: int = Field(default=30, ge=5, le=3600, description="调用超时（秒），最长 60 分钟")


class DifyRunIn(BaseModel):
    """试运行 Dify 工作流的输入"""
    inputs: dict = Field(default_factory=dict, description="工作流输入参数")
    user: str = Field(default="dify-user", max_length=100, description="调用用户标识")
