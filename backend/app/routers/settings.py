# -*- coding: utf-8 -*-
"""后台系统配置接口（仅管理员）：统一管理后台功能开关等配置项

扩展方式：向 system_settings 表新增配置键（如 auto_review），
前端设置页会自动按 value_type 渲染对应控件（bool→开关 / int→数字 / string→输入框 / json→文本域）。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.deps import require_roles
from ..database import get_db
from ..models.system_setting import SystemSetting
from ..models.user import User
from ..schemas.setting import SettingCreateIn, SettingUpdateIn
from ..services.settings_service import parse_value, set_setting

router = APIRouter(prefix="/settings", tags=["系统设置"])


def _to_dict(row: SystemSetting) -> dict:
    """序列化配置项：value 转为对应类型返回，便于前端直接使用"""
    try:
        value = parse_value(row.config_value, row.value_type)
    except (ValueError, TypeError):
        value = row.config_value
    return {
        "config_key": row.config_key,
        "value": value,
        "value_type": row.value_type,
        "description": row.description,
        "updated_at": row.updated_at.strftime("%Y-%m-%d %H:%M:%S") if row.updated_at else None,
    }


@router.get("", summary="配置列表（管理员）")
def list_settings(db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    rows = db.query(SystemSetting).order_by(SystemSetting.id).all()
    return {"items": [_to_dict(r) for r in rows]}


@router.post("", summary="新建配置（管理员）")
def create_setting(
    body: SettingCreateIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    if db.query(SystemSetting).filter(SystemSetting.config_key == body.config_key).first():
        raise HTTPException(400, "配置键已存在")
    row = set_setting(db, body.config_key, body.value, body.value_type, body.description)
    db.commit()
    db.refresh(row)
    return {"message": "创建成功", "setting": _to_dict(row)}


@router.put("/{config_key}", summary="更新配置（管理员，键不存在时自动创建）")
def update_setting(
    config_key: str,
    body: SettingUpdateIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    row = set_setting(db, config_key, body.value, body.value_type, body.description)
    db.commit()
    db.refresh(row)
    return {"message": "保存成功", "setting": _to_dict(row)}


@router.delete("/{config_key}", summary="删除配置（管理员）")
def delete_setting(
    config_key: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    row = db.query(SystemSetting).filter(SystemSetting.config_key == config_key).first()
    if not row:
        raise HTTPException(404, "配置不存在")
    db.delete(row)
    db.commit()
    return {"message": "删除成功"}
