# -*- coding: utf-8 -*-
"""资源管理相关请求体 Schema"""
from pydantic import BaseModel, Field


class ResourceUrlIn(BaseModel):
    """通过图片链接上传：后端下载该地址的图片并存入资源库"""
    url: str = Field(min_length=1, max_length=2000, description="线上图片完整链接（http/https）")
