# -*- coding: utf-8 -*-
"""门户模块请求体 Schema"""
from typing import Any

from pydantic import BaseModel, Field


class PortalModuleIn(BaseModel):
    module_key: str = Field(min_length=1, max_length=50, description="模块标识")
    title: str = Field(default="", max_length=100, description="模块标题")
    content: Any = None
    enabled: bool = True


class ThemeSwitchIn(BaseModel):
    """切换门户主题"""
    theme: str = Field(min_length=1, max_length=50, description="主题标识（editorial/cyber/comic）")


class RegisterEditorIn(BaseModel):
    """注册为编辑的开放策略"""
    enabled: bool = Field(description="是否允许用户注册为编辑写手")


class SplashSwitchIn(BaseModel):
    """开屏动画开关请求体。"""
    enabled: bool = Field(description="是否播放登录后的 3D 地球开屏动画")


class AiReadingSwitchIn(BaseModel):
    """门户 AI 阅读功能总开关请求体。"""
    enabled: bool = Field(description="是否开启门户 AI 全文总结、划词分析、核心术语知识链")


class OssConfigIn(BaseModel):
    """S3 兼容对象存储配置；endpoint 留空 = 本地模式"""
    endpoint: str = Field(default="", max_length=255, description="服务地址，如 https://oss-cn-hangzhou.aliyuncs.com 或 http://127.0.0.1:9000")
    bucket: str = Field(default="", max_length=255, description="存储桶（需公开读）")
    region: str = Field(default="", max_length=100, description="区域，默认 us-east-1（MinIO 可随意）")
    access_key: str = Field(default="", max_length=255, description="Access Key")
    secret_key: str = Field(default="", max_length=255, description="Secret Key；传 **** 或空表示保留原值")
    path_prefix: str = Field(default="", max_length=255, description="对象前缀，如 articles/")
    public_base_url: str = Field(default="", max_length=255, description="公开访问前缀（兼容虚拟主机风格/CDN），留空按 endpoint/bucket 拼接")

