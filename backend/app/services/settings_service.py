# -*- coding: utf-8 -*-
"""后台系统配置读写服务：统一处理 value_type 的序列化/反序列化，业务代码直接取用"""
import json

from sqlalchemy.orm import Session

from ..models.system_setting import SystemSetting


def parse_value(raw: str, value_type: str):
    """按值类型把数据库文本还原为对应类型"""
    if value_type == "bool":
        return str(raw).lower() in ("1", "true", "yes", "on")
    if value_type == "int":
        return int(raw)
    if value_type == "json":
        return json.loads(raw or "null")
    return raw


def serialize_value(value, value_type: str) -> str:
    """按值类型把配置值转为数据库文本"""
    if value_type == "bool":
        return "true" if bool(value) else "false"
    if value_type == "int":
        return str(int(value))
    if value_type == "json":
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def get_setting(db: Session, key: str, default=None):
    """读取配置（已按类型解析）；不存在或解析失败时返回 default"""
    row = db.query(SystemSetting).filter(SystemSetting.config_key == key).first()
    if not row:
        return default
    try:
        return parse_value(row.config_value, row.value_type)
    except (ValueError, TypeError, json.JSONDecodeError):
        return default


def set_setting(
    db: Session,
    key: str,
    value,
    value_type: str = "string",
    description: str = "",
) -> SystemSetting:
    """写入配置（键已存在则更新，否则新建）"""
    row = db.query(SystemSetting).filter(SystemSetting.config_key == key).first()
    if row is None:
        row = SystemSetting(
            config_key=key,
            config_value=serialize_value(value, value_type),
            value_type=value_type,
            description=description,
        )
        db.add(row)
    else:
        row.config_value = serialize_value(value, value_type)
        row.value_type = value_type
        if description is not None:
            row.description = description
    db.flush()
    return row
