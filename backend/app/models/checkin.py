# -*- coding: utf-8 -*-
"""签到日志模型：记录用户每日签到获得的积分

唯一约束 (user_id, checkin_date) 保证每自然日最多签到一次，
即使前端并发双击，数据库层面也会兜底拒绝重复签到。
"""
from datetime import datetime

from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, String, UniqueConstraint,
)

from ..database import Base


class CheckinLog(Base):
    __tablename__ = "checkin_logs"
    __table_args__ = (
        UniqueConstraint("user_id", "checkin_date", name="uq_checkin_user_date"),
    )

    id = Column(Integer, primary_key=True, index=True, comment="签到记录ID")
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="签到用户ID",
    )
    checkin_date = Column(String(10), nullable=False, index=True, comment="签到日期（YYYY-MM-DD）")
    points = Column(Integer, nullable=False, comment="本次获得积分")
    created_at = Column(DateTime, default=datetime.now, comment="签到时间")
