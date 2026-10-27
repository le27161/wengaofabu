# -*- coding: utf-8 -*-
"""埋点日志模型：记录用户观看、点赞、收藏、转发等行为"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, BigInteger

from ..database import Base


class EventLog(Base):
    __tablename__ = "event_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="日志ID")
    user_id = Column(Integer, nullable=True, index=True, comment="用户ID（未登录为空）")
    article_id = Column(Integer, nullable=True, index=True, comment="文稿ID（非文章行为为空）")
    # 事件类型：view 观看 / like 点赞 / favorite 收藏 / share 转发
    event_type = Column(String(20), nullable=False, index=True, comment="事件类型")
    ip = Column(String(64), comment="客户端IP")
    user_agent = Column(String(500), comment="浏览器UA")
    referer = Column(String(500), comment="来源页面")
    created_at = Column(DateTime, default=datetime.now, index=True, comment="发生时间")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "article_id": self.article_id,
            "event_type": self.event_type,
            "ip": self.ip,
            "user_agent": self.user_agent,
            "referer": self.referer,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }

