# -*- coding: utf-8 -*-
"""AI 调用记录服务：写手调用 AI 辅助功能时统一落库

后续接入真实 AI 能力时，在 router 中拿到真实返回值后仍走 log_ai_call 记录即可，
保证后台「AI 调用记录」页面数据完整。
"""
from sqlalchemy.orm import Session

from ..models.ai_call import AICallLog
from ..models.user import User


def log_ai_call(
    db: Session, user: User, feature_type: int, inputs: dict, outputs: dict,
    article_id: int | None = None, draft_key: str | None = None,
) -> AICallLog:
    """记录一次 AI 调用：调用人、功能类型、入参、返回值、调用时间；draft_key 供未保存草稿关联"""
    row = AICallLog(
        user_id=user.id,
        article_id=article_id,
        draft_key=draft_key,
        feature_type=feature_type,
        input_params=inputs,
        output_data=outputs,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
