# -*- coding: utf-8 -*-
"""人工事件证据包：只读数据库并校验未来LLM引用的来源身份。"""
from hashlib import sha256

from sqlalchemy import and_
from sqlalchemy.orm import Session

from ..models.smart_collect import (
    NewsClue,
    NewsClueContent,
    SmartCollectEvent,
    SmartCollectEventClue,
    SmartCollectTask,
    SmartCollectTaskClue,
)
from ..models.user import User
from ..schemas.smart_collect import EventEvidencePack, EventSynthesisResult
from .smart_collect_content_service import SmartCollectContentService
from .smart_collect_event_service import SmartCollectEventNotFoundError
from .smart_collect_service import SmartCollectTaskNotFoundError


class GroundingValidationError(ValueError):
    """未来模型输出引用了证据包以外的来源，或事实没有来源依据。"""


class SmartCollectEvidenceService:
    """实时构造事件证据包，不联网、不写库、不运行任何模型。"""

    @staticmethod
    def _require_task(db: Session, task_id: int, user: User) -> SmartCollectTask:
        task = db.get(SmartCollectTask, task_id)
        # 编辑访问别人任务仍返回404，避免泄露任务是否存在。
        if not task or (user.role != "admin" and task.creator_id != user.id):
            raise SmartCollectTaskNotFoundError
        return task

    @staticmethod
    def _require_event(db: Session, task_id: int, event_id: int) -> SmartCollectEvent:
        event = (
            db.query(SmartCollectEvent)
            .filter(
                SmartCollectEvent.id == event_id,
                SmartCollectEvent.task_id == task_id,
            )
            .first()
        )
        if event is None:
            raise SmartCollectEventNotFoundError
        return event

    @staticmethod
    def _is_valid_source(row) -> bool:
        """证据只接受有效completed正文，并核对正文哈希没有漂移。"""
        if row.content_status != "completed" or not row.content:
            return False
        if SmartCollectContentService._validate_content(row.content, row.title) is not None:
            return False
        expected_hash = sha256(row.content.encode("utf-8")).hexdigest()
        return row.content_hash == expected_hash

    @classmethod
    def build_evidence_pack(
        cls,
        db: Session,
        task_id: int,
        event_id: int,
        user: User,
    ) -> dict:
        """把数据库行转换成普通Python证据包；finally回滚确保只读事务结束。"""
        try:
            task = cls._require_task(db, task_id, user)
            event = cls._require_event(db, task_id, event_id)
            rows = (
                db.query(
                    SmartCollectEventClue.clue_id.label("clue_id"),
                    SmartCollectTaskClue.rank.label("rank"),
                    NewsClue.title.label("title"),
                    NewsClue.source.label("source"),
                    NewsClue.url.label("url"),
                    NewsClueContent.status.label("content_status"),
                    NewsClueContent.content.label("content"),
                    NewsClueContent.content_hash.label("content_hash"),
                    NewsClueContent.fetched_at.label("fetched_at"),
                )
                .select_from(SmartCollectEventClue)
                .join(
                    SmartCollectTaskClue,
                    and_(
                        SmartCollectTaskClue.task_id == SmartCollectEventClue.task_id,
                        SmartCollectTaskClue.clue_id == SmartCollectEventClue.clue_id,
                    ),
                )
                .join(NewsClue, NewsClue.id == SmartCollectEventClue.clue_id)
                .outerjoin(NewsClueContent, NewsClueContent.clue_id == NewsClue.id)
                .filter(
                    SmartCollectEventClue.task_id == task_id,
                    SmartCollectEventClue.event_id == event_id,
                )
                .order_by(SmartCollectTaskClue.rank, SmartCollectEventClue.clue_id)
                .all()
            )

            sources = []
            for row in rows:
                if not cls._is_valid_source(row):
                    continue
                sources.append(
                    {
                        "clue_id": row.clue_id,
                        "rank": row.rank,
                        "title": row.title,
                        "source": row.source,
                        "url": row.url,
                        "content": row.content,
                        "content_length": len(row.content),
                        "content_hash": row.content_hash,
                        "fetched_at": row.fetched_at,
                    }
                )

            return {
                "task_id": task.id,
                "task_query": task.query,
                "event_id": event.id,
                "event_title": event.title,
                "source_count": len(rows),
                "completed_source_count": len(sources),
                "total_content_length": sum(item["content_length"] for item in sources),
                "sources": sources,
            }
        finally:
            db.rollback()


def validate_event_synthesis_grounding(
    evidence_pack: EventEvidencePack,
    result: EventSynthesisResult,
) -> EventSynthesisResult:
    """确保未来模型的每个事实和冲突只引用当前事件证据中的clue_id。"""
    allowed_ids = {source.clue_id for source in evidence_pack.sources}

    for index, fact in enumerate(result.core_facts, start=1):
        if not fact.text.strip():
            raise GroundingValidationError(f"core_facts[{index}]的text不能为空")
        if not fact.source_clue_ids:
            raise GroundingValidationError(
                f"core_facts[{index}]至少需要一个source_clue_id"
            )
        invalid_ids = sorted(set(fact.source_clue_ids) - allowed_ids)
        if invalid_ids:
            raise GroundingValidationError(
                f"core_facts[{index}]引用了当前事件证据之外的来源：{invalid_ids}"
            )

    for index, conflict in enumerate(result.conflicts, start=1):
        invalid_ids = sorted(set(conflict.source_clue_ids) - allowed_ids)
        if invalid_ids:
            raise GroundingValidationError(
                f"conflicts[{index}]引用了当前事件证据之外的来源：{invalid_ids}"
            )

    return result
