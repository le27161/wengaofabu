# -*- coding: utf-8 -*-
"""后台系统配置模型：键值对存储，便于后续扩展任意后台配置项

- config_key   配置键（唯一，如 auto_review）
- value_type   值类型：string / int / bool / json
- config_value 按 value_type 序列化后的文本
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from ..database import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True, comment="配置ID")
    config_key = Column(String(100), unique=True, nullable=False, index=True, comment="配置键")
    config_value = Column(Text, nullable=False, default="", comment="配置值（文本存储，按 value_type 解析）")
    value_type = Column(String(20), default="string", comment="值类型：string/int/bool/json")
    description = Column(String(255), default="", comment="配置说明")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
