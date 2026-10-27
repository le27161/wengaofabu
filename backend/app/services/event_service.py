# -*- coding: utf-8 -*-
"""埋点记录服务：所有行为埋点统一从这里写入 event_logs"""
from fastapi import Request
from sqlalchemy.orm import Session

from ..core.deps import get_client_ip
from ..models.event import EventLog


def record_event(
    db: Session,
    *,
    event_type: str,
    article_id: int | None = None,
    user_id: int | None = None,
    request: Request | None = None,
) -> EventLog:
    """写入一条埋点日志。request 用于提取 IP / UA / 来源页。"""
    log = EventLog(
        event_type=event_type,
        article_id=article_id,
        user_id=user_id,
        ip=get_client_ip(request) if request else None,
        user_agent=(request.headers.get("user-agent") or "")[:500] if request else None,
        referer=(request.headers.get("referer") or "")[:500] if request else None,
    )
    db.add(log)
    db.flush()
    return log

