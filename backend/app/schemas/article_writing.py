# -*- coding: utf-8 -*-
"""智能采编Article写作建议的输入输出契约。"""
from pydantic import BaseModel, Field, field_validator


class ArticleWritingResult(BaseModel):
    """模型只能返回供编辑预览和选择采用的三个字段。"""

    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=500)
    content_html: str = Field(min_length=1)

    @field_validator("title", "summary", "content_html", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class ArticleWritingResponse(BaseModel):
    """一次不落库的AI写作建议，以及供应商返回的用量元数据。"""

    article_id: int = Field(gt=0)
    synthesis_id: int = Field(gt=0)
    synthesis_version: int = Field(gt=0)
    approved_core_fact_count: int = Field(ge=0)
    requested_model: str = Field(min_length=1)
    actual_model: str = Field(min_length=1)
    # 保留阶段约定的model字段；其值始终等于actual_model。
    model: str = Field(min_length=1)
    elapsed_ms: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    result: ArticleWritingResult
