# -*- coding: utf-8 -*-
"""智能采编人工事件分组服务：只管理事件及任务内线索关联。"""
from datetime import datetime

from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
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
from .smart_collect_service import SmartCollectTaskNotFoundError


class SmartCollectEventNotFoundError(Exception):
    message = "人工事件不存在"


class SmartCollectEventClueNotFoundError(Exception):
    message = "该线索不在当前人工事件中"


class SmartCollectEventValidationError(Exception):
    """请求中的线索不属于当前任务。"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class SmartCollectEventConflictError(Exception):
    """线索已被当前任务中的人工事件占用。"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class SmartCollectEventPersistenceError(Exception):
    message = "人工事件保存失败，请稍后重试"


class SmartCollectEventService:
    """人工事件CRUD及任务内线索归属校验，不触发任何搜索或模型计算。"""

    @staticmethod
    def _normalize_title(title: str) -> str:
        clean_title = title.strip() if isinstance(title, str) else ""
        if not clean_title or len(clean_title) > 200:
            raise SmartCollectEventValidationError("事件标题不能为空且最多200个字符")
        return clean_title

    @staticmethod
    def _normalize_clue_ids(clue_ids: list[int], minimum: int) -> list[int]:
        if (
            not isinstance(clue_ids, list)
            or len(clue_ids) < minimum
            or len(clue_ids) > 20
            or any(type(clue_id) is not int or clue_id <= 0 for clue_id in clue_ids)
            or len(clue_ids) != len(set(clue_ids))
        ):
            raise SmartCollectEventValidationError(
                f"线索ID必须是去重后的正整数列表，数量为{minimum}到20条"
            )
        return clue_ids

    @staticmethod
    def _require_task(db: Session, task_id: int, user: User) -> SmartCollectTask:
        task = db.get(SmartCollectTask, task_id)
        # 编辑访问别人任务沿用详情页404策略，避免泄露任务是否存在。
        if not task or (user.role != "admin" and task.creator_id != user.id):
            raise SmartCollectTaskNotFoundError
        return task

    @staticmethod
    def _require_event(
        db: Session,
        task_id: int,
        event_id: int,
    ) -> SmartCollectEvent:
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
    def _require_task_clues(
        db: Session,
        task_id: int,
        clue_ids: list[int],
    ) -> None:
        existing_ids = {
            clue_id
            for (clue_id,) in (
                db.query(SmartCollectTaskClue.clue_id)
                .filter(
                    SmartCollectTaskClue.task_id == task_id,
                    SmartCollectTaskClue.clue_id.in_(clue_ids),
                )
                .all()
            )
        }
        missing_ids = sorted(set(clue_ids) - existing_ids)
        if missing_ids:
            joined = "、".join(str(clue_id) for clue_id in missing_ids)
            raise SmartCollectEventValidationError(
                f"线索 {joined} 不属于当前采编任务"
            )

    @staticmethod
    def _require_ungrouped_clues(
        db: Session,
        task_id: int,
        clue_ids: list[int],
    ) -> None:
        occupied = (
            db.query(
                SmartCollectEventClue.clue_id,
                SmartCollectEventClue.event_id,
            )
            .filter(
                SmartCollectEventClue.task_id == task_id,
                SmartCollectEventClue.clue_id.in_(clue_ids),
            )
            .order_by(SmartCollectEventClue.clue_id)
            .all()
        )
        if occupied:
            details = "、".join(
                f"线索{row.clue_id}（事件{row.event_id}）" for row in occupied
            )
            raise SmartCollectEventConflictError(
                f"{details} 已被分组，不能重复加入或自动移动"
            )

    @staticmethod
    def _clue_item(row) -> dict:
        return {
            "clue_id": row.clue_id,
            "rank": row.rank,
            "title": row.title,
            "source": row.source,
            "search_score": row.search_score,
            "semantic_score": row.semantic_score,
            "relevance_label": row.relevance_label,
            "content_status": row.content_status,
            "content_length": int(row.content_length or 0),
        }

    @classmethod
    def _load_clue_rows(cls, db: Session, task_id: int):
        return (
            db.query(
                SmartCollectEventClue.event_id.label("event_id"),
                SmartCollectTaskClue.clue_id.label("clue_id"),
                SmartCollectTaskClue.rank.label("rank"),
                NewsClue.title.label("title"),
                NewsClue.source.label("source"),
                SmartCollectTaskClue.search_score.label("search_score"),
                SmartCollectTaskClue.semantic_score.label("semantic_score"),
                SmartCollectTaskClue.relevance_label.label("relevance_label"),
                NewsClueContent.status.label("content_status"),
                func.char_length(NewsClueContent.content).label("content_length"),
            )
            .select_from(SmartCollectTaskClue)
            .join(NewsClue, NewsClue.id == SmartCollectTaskClue.clue_id)
            .outerjoin(NewsClueContent, NewsClueContent.clue_id == NewsClue.id)
            .outerjoin(
                SmartCollectEventClue,
                and_(
                    SmartCollectEventClue.task_id == SmartCollectTaskClue.task_id,
                    SmartCollectEventClue.clue_id == SmartCollectTaskClue.clue_id,
                ),
            )
            .filter(SmartCollectTaskClue.task_id == task_id)
            .order_by(SmartCollectTaskClue.rank, SmartCollectTaskClue.clue_id)
            .all()
        )

    @classmethod
    def _load_event_list(cls, db: Session, task: SmartCollectTask) -> dict:
        events = (
            db.query(SmartCollectEvent)
            .filter(SmartCollectEvent.task_id == task.id)
            .order_by(SmartCollectEvent.created_at, SmartCollectEvent.id)
            .all()
        )
        clues_by_event: dict[int, list[dict]] = {event.id: [] for event in events}
        ungrouped_clues: list[dict] = []
        for row in cls._load_clue_rows(db, task.id):
            item = cls._clue_item(row)
            if row.event_id is None:
                ungrouped_clues.append(item)
            else:
                clues_by_event.setdefault(row.event_id, []).append(item)

        return {
            "task_id": task.id,
            "query": task.query,
            "events": [
                {
                    "id": event.id,
                    "task_id": event.task_id,
                    "title": event.title,
                    "clue_count": len(clues_by_event.get(event.id, [])),
                    "clues": clues_by_event.get(event.id, []),
                    "created_at": event.created_at,
                    "updated_at": event.updated_at,
                }
                for event in events
            ],
            "ungrouped_clues": ungrouped_clues,
        }

    @classmethod
    def _load_event_detail(cls, db: Session, task_id: int, event_id: int) -> dict:
        task = db.get(SmartCollectTask, task_id)
        event_list = cls._load_event_list(db, task)
        for event in event_list["events"]:
            if event["id"] == event_id:
                return event
        raise SmartCollectEventNotFoundError

    @classmethod
    def list_events(cls, db: Session, task_id: int, user: User) -> dict:
        """返回已有事件与全部未分组TaskClue；只读后立即结束事务。"""
        try:
            task = cls._require_task(db, task_id, user)
            return cls._load_event_list(db, task)
        finally:
            db.rollback()

    @classmethod
    def create_event(
        cls,
        db: Session,
        task_id: int,
        user: User,
        title: str,
        clue_ids: list[int],
    ) -> dict:
        """事件和全部成员一次提交；任何校验或写入失败都不留下空事件。"""
        try:
            title = cls._normalize_title(title)
            clue_ids = cls._normalize_clue_ids(clue_ids, minimum=1)
            cls._require_task(db, task_id, user)
            cls._require_task_clues(db, task_id, clue_ids)
            cls._require_ungrouped_clues(db, task_id, clue_ids)

            event = SmartCollectEvent(task_id=task_id, title=title)
            db.add(event)
            db.flush()
            db.add_all(
                [
                    SmartCollectEventClue(
                        event_id=event.id,
                        task_id=task_id,
                        clue_id=clue_id,
                    )
                    for clue_id in clue_ids
                ]
            )
            db.commit()
            detail = cls._load_event_detail(db, task_id, event.id)
            db.rollback()
            return detail
        except (SmartCollectTaskNotFoundError, SmartCollectEventValidationError):
            db.rollback()
            raise
        except SmartCollectEventConflictError:
            db.rollback()
            raise
        except IntegrityError as exc:
            db.rollback()
            raise SmartCollectEventConflictError(
                "所选线索已被当前任务中的其他事件占用，请刷新后重试"
            ) from exc
        except SQLAlchemyError as exc:
            db.rollback()
            raise SmartCollectEventPersistenceError from exc

    @classmethod
    def rename_event(
        cls,
        db: Session,
        task_id: int,
        event_id: int,
        user: User,
        title: str,
    ) -> dict:
        try:
            title = cls._normalize_title(title)
            cls._require_task(db, task_id, user)
            event = cls._require_event(db, task_id, event_id)
            event.title = title
            event.updated_at = datetime.now()
            db.commit()
            detail = cls._load_event_detail(db, task_id, event_id)
            db.rollback()
            return detail
        except (
            SmartCollectTaskNotFoundError,
            SmartCollectEventNotFoundError,
            SmartCollectEventValidationError,
        ):
            db.rollback()
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise SmartCollectEventPersistenceError from exc

    @classmethod
    def add_clues(
        cls,
        db: Session,
        task_id: int,
        event_id: int,
        user: User,
        clue_ids: list[int],
    ) -> dict:
        try:
            clue_ids = cls._normalize_clue_ids(clue_ids, minimum=1)
            cls._require_task(db, task_id, user)
            event = cls._require_event(db, task_id, event_id)
            cls._require_task_clues(db, task_id, clue_ids)
            cls._require_ungrouped_clues(db, task_id, clue_ids)
            db.add_all(
                [
                    SmartCollectEventClue(
                        event_id=event_id,
                        task_id=task_id,
                        clue_id=clue_id,
                    )
                    for clue_id in clue_ids
                ]
            )
            event.updated_at = datetime.now()
            db.commit()
            detail = cls._load_event_detail(db, task_id, event_id)
            db.rollback()
            return detail
        except (
            SmartCollectTaskNotFoundError,
            SmartCollectEventNotFoundError,
            SmartCollectEventValidationError,
            SmartCollectEventConflictError,
        ):
            db.rollback()
            raise
        except IntegrityError as exc:
            db.rollback()
            raise SmartCollectEventConflictError(
                "所选线索已被当前任务中的其他事件占用，请刷新后重试"
            ) from exc
        except SQLAlchemyError as exc:
            db.rollback()
            raise SmartCollectEventPersistenceError from exc

    @classmethod
    def remove_clue(
        cls,
        db: Session,
        task_id: int,
        event_id: int,
        clue_id: int,
        user: User,
    ) -> None:
        try:
            cls._require_task(db, task_id, user)
            event = cls._require_event(db, task_id, event_id)
            link = (
                db.query(SmartCollectEventClue)
                .filter(
                    SmartCollectEventClue.event_id == event_id,
                    SmartCollectEventClue.task_id == task_id,
                    SmartCollectEventClue.clue_id == clue_id,
                )
                .first()
            )
            if link is None:
                raise SmartCollectEventClueNotFoundError
            db.delete(link)
            event.updated_at = datetime.now()
            db.commit()
        except (
            SmartCollectTaskNotFoundError,
            SmartCollectEventNotFoundError,
            SmartCollectEventClueNotFoundError,
        ):
            db.rollback()
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise SmartCollectEventPersistenceError from exc

    @classmethod
    def delete_event(
        cls,
        db: Session,
        task_id: int,
        event_id: int,
        user: User,
    ) -> None:
        """只删除事件及关联行，绝不删除NewsClue或TaskClue。"""
        try:
            cls._require_task(db, task_id, user)
            event = cls._require_event(db, task_id, event_id)
            db.delete(event)
            db.commit()
        except (SmartCollectTaskNotFoundError, SmartCollectEventNotFoundError):
            db.rollback()
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise SmartCollectEventPersistenceError from exc
