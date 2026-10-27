# -*- coding: utf-8 -*-
"""Dify 工作流登记模型：一个 Dify 应用（工作流）= 一组 API 地址 + Key + 输入参数说明

用于在后台管理多个 Dify 工作流（如文章摘要、智能审核、标题生成等），
业务代码通过 services/dify_service.py 统一调用。
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text

from ..database import Base


class DifyWorkflow(Base):
    __tablename__ = "dify_workflows"

    id = Column(Integer, primary_key=True, index=True, comment="工作流ID")
    name = Column(String(100), unique=True, nullable=False, index=True, comment="业务标识（唯一，如 article_summary）")
    api_base = Column(String(255), nullable=False, comment="Dify API 地址（如 https://api.dify.ai/v1）")
    api_key = Column(String(255), nullable=False, comment="Dify 应用 API Key（app-xxx）")
    description = Column(String(500), default="", comment="用途说明")
    # 输入参数说明：JSON 结构，如 {"title": "文章标题", "content": "正文"}
    input_schema = Column(JSON, default=dict, comment="输入参数说明（JSON）")
    enabled = Column(Boolean, default=True, comment="是否启用")
    timeout = Column(Integer, default=30, comment="调用超时（秒）")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def to_dict(self, with_key: bool = False) -> dict:
        """序列化；API Key 默认脱敏只显示后 4 位，避免泄露"""
        data = {
            "id": self.id,
            "name": self.name,
            "api_base": self.api_base,
            "description": self.description,
            "input_schema": self.input_schema,
            "enabled": self.enabled,
            "timeout": self.timeout,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
        data["api_key"] = self.api_key if with_key else f"****{self.api_key[-4:]}"
        return data
