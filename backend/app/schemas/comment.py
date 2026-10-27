# -*- coding: utf-8 -*-
"""评论相关请求体 Schema"""
from typing import Optional

from pydantic import BaseModel, Field


class CommentIn(BaseModel):
    """发表评论/回复"""
    article_id: int = Field(description="所属文稿ID")
    content: str = Field(min_length=1, max_length=2000, description="评论内容（纯文本，1~2000字）")
    parent_id: Optional[int] = Field(default=None, description="回复的父评论ID；不传或null为顶层评论")
