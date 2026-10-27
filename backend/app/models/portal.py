# -*- coding: utf-8 -*-
"""门户模块模型：管理员可配置首页轮播、公告等内容模块"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, JSON, Boolean, DateTime

from ..database import Base


class PortalModule(Base):
    __tablename__ = "portal_modules"

    id = Column(Integer, primary_key=True, index=True, comment="模块ID")
    module_key = Column(String(50), unique=True, nullable=False, comment="模块标识（banner/notice/...）")
    title = Column(String(100), comment="模块标题")
    # 模块内容：JSON 结构，不同模块结构不同
    # banner: [{"title": "轮播标题", "image": "图片URL", "link": "跳转链接或文章ID"}]
    # notice: 字符串公告文本
    content = Column(JSON, default=dict, comment="模块内容（JSON）")
    enabled = Column(Boolean, default=True, comment="是否启用")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "module_key": self.module_key,
            "title": self.title,
            "content": self.content,
            "enabled": self.enabled,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }

