# -*- coding: utf-8 -*-
"""用户兴趣偏好接口（独立模块）：登录后选择感兴趣的栏目，多选，全量覆盖保存"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.deps import get_current_user
from ..database import get_db
from ..models.category import Category
from ..models.preference import UserPreference
from ..models.user import User

router = APIRouter(prefix="/preferences", tags=["用户偏好"])


class PreferencesIn(BaseModel):
    """保存请求体：所选栏目ID列表（多选，全量覆盖）"""
    category_ids: list[int]


@router.get("", summary="获取当前用户兴趣偏好")
def get_preferences(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(UserPreference).filter(UserPreference.user_id == user.id).all()
    return {
        "has_preference": len(rows) > 0,
        "category_ids": sorted(r.category_id for r in rows),
    }


@router.put("", summary="保存当前用户兴趣偏好（全量覆盖）")
def save_preferences(
    payload: PreferencesIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ids = list(dict.fromkeys(payload.category_ids))  # 去重
    valid_ids: set[int] = set()
    if ids:
        valid = db.query(Category.id).filter(Category.id.in_(ids)).all()
        valid_ids = {v[0] for v in valid}
    if not valid_ids:
        raise HTTPException(422, "请至少选择一个有效分类")

    db.query(UserPreference).filter(UserPreference.user_id == user.id).delete()
    for cid in valid_ids:
        db.add(UserPreference(user_id=user.id, category_id=cid))
    db.commit()
    return {"has_preference": True, "category_ids": sorted(valid_ids)}
