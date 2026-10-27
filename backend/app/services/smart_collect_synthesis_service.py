# -*- coding: utf-8 -*-
"""事件AI整理：证据、模型、校验、版本持久化与人工确认。"""
import json
from datetime import datetime
from time import perf_counter

from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..models.smart_collect import (
    NewsClueContent,
    SmartCollectEvent,
    SmartCollectEventSynthesis,
)
from ..models.user import User
from ..schemas.smart_collect import (
    EventEvidencePack,
    EventEvidenceSnapshotItem,
    EventSynthesisResult,
)
from .event_synthesis_prompt_builder import EventSynthesisPromptBuilder
from .llm_provider import (
    LLMProvider,
    LLMProviderConfigError,
    LLMProviderEmptyResponseError,
    LLMProviderError,
    LLMProviderTimeoutError,
)
from .smart_collect_evidence_service import (
    GroundingValidationError,
    SmartCollectEvidenceService,
    validate_event_synthesis_grounding,
)
from .smart_collect_event_service import SmartCollectEventNotFoundError
from .smart_collect_service import SmartCollectTaskNotFoundError


class SmartCollectSynthesisError(Exception):
    message = "AI事件整理失败，请稍后重试"


class SmartCollectSynthesisConfigError(SmartCollectSynthesisError):
    message = "AI事件整理服务尚未配置"


class SmartCollectSynthesisTimeoutError(SmartCollectSynthesisError):
    message = "AI事件整理响应超时，请稍后重试"


class SmartCollectSynthesisEmptyResponseError(SmartCollectSynthesisError):
    message = "AI事件整理没有返回内容，请重试"


class SmartCollectSynthesisJsonError(SmartCollectSynthesisError):
    message = "AI事件整理返回的JSON无效，请重试"


class SmartCollectSynthesisSchemaError(SmartCollectSynthesisError):
    message = "AI事件整理返回结构不符合约定，请重试"


class SmartCollectSynthesisGroundingError(SmartCollectSynthesisError):
    message = "AI事件整理引用了无效来源，结果已拒绝"


class SmartCollectSynthesisNoEvidenceError(SmartCollectSynthesisError):
    message = "当前事件没有有效正文证据，请先准备事件材料"


class SmartCollectSynthesisNotFoundError(SmartCollectSynthesisError):
    message = "AI事件整理版本不存在"


class SmartCollectSynthesisConflictError(SmartCollectSynthesisError):
    message = "AI事件整理版本状态冲突"


class SmartCollectSynthesisPersistenceError(SmartCollectSynthesisError):
    message = "AI事件整理结果保存失败，请稍后重试"


class SmartCollectSynthesisDataError(SmartCollectSynthesisError):
    message = "AI事件整理历史数据无效"


class SmartCollectSynthesisModelError(SmartCollectSynthesisError):
    message = "AI事件整理实际模型与项目配置不一致，结果未保存"


class SmartCollectSynthesisService:
    """模型计算在事务外执行；只把通过校验的结果短事务新增为版本。"""

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    @staticmethod
    def _unwrap_json_text(value: str) -> str:
        """只兼容完整JSON或完整Markdown代码围栏，不从自然语言中猜JSON。"""
        text = value.strip()
        if not text.startswith("```"):
            return text
        lines = text.splitlines()
        if (
            len(lines) < 3
            or lines[0].strip().casefold() not in {"```", "```json"}
            or lines[-1].strip() != "```"
        ):
            raise SmartCollectSynthesisJsonError
        return "\n".join(lines[1:-1]).strip()

    @classmethod
    def _parse_result(cls, raw_text: str) -> EventSynthesisResult:
        try:
            data = json.loads(cls._unwrap_json_text(raw_text))
        except (json.JSONDecodeError, SmartCollectSynthesisJsonError):
            raise SmartCollectSynthesisJsonError from None
        if not isinstance(data, dict):
            raise SmartCollectSynthesisSchemaError
        try:
            return EventSynthesisResult.model_validate(data)
        except ValidationError:
            raise SmartCollectSynthesisSchemaError from None

    @staticmethod
    def _validate_model_identity(requested_model: str, actual_model: str) -> None:
        """正式Qwen调用不得被其他供应商模型静默替代。"""
        requested = requested_model.strip()
        actual = actual_model.strip()
        if not requested or not actual:
            raise SmartCollectSynthesisModelError
        if requested.casefold() == "qwen3.7-plus" and not actual.casefold().startswith(
            "qwen3.7-plus"
        ):
            raise SmartCollectSynthesisModelError

    @staticmethod
    def validate_stored_result(row: SmartCollectEventSynthesis) -> EventSynthesisResult:
        """数据库JSON不能被盲目信任，每次读取都重新执行Pydantic校验。"""
        try:
            return EventSynthesisResult.model_validate(row.result_json)
        except (ValidationError, TypeError, ValueError):
            raise SmartCollectSynthesisDataError from None

    @classmethod
    def _summary_dict(cls, row: SmartCollectEventSynthesis) -> dict:
        cls.validate_stored_result(row)
        article = row.article_source.article if row.article_source else None
        return {
            "id": row.id,
            "event_id": row.event_id,
            "version": row.version,
            "status": row.status,
            "requested_model": row.requested_model,
            "actual_model": row.actual_model,
            "source_count": row.source_count,
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
            "total_tokens": row.total_tokens,
            "elapsed_ms": row.elapsed_ms,
            "created_by": row.created_by,
            "created_at": row.created_at,
            "reviewed_by": row.reviewed_by,
            "reviewed_at": row.reviewed_at,
            "article": (
                {
                    "id": article.id,
                    "title": article.title,
                    "status": article.status,
                    "created_at": article.created_at,
                }
                if article
                else None
            ),
        }

    @classmethod
    def _detail_dict(
        cls,
        db: Session,
        row: SmartCollectEventSynthesis,
        event_title: str,
    ) -> dict:
        result = cls.validate_stored_result(row)
        try:
            stored_snapshot = [
                EventEvidenceSnapshotItem.model_validate(item)
                for item in row.evidence_snapshot
            ]
        except (ValidationError, TypeError, ValueError):
            raise SmartCollectSynthesisDataError from None

        clue_ids = [item.clue_id for item in stored_snapshot]
        current_hashes = dict(
            db.query(NewsClueContent.clue_id, NewsClueContent.content_hash)
            .filter(NewsClueContent.clue_id.in_(clue_ids))
            .all()
        )
        snapshot = []
        for item in stored_snapshot:
            current_hash = current_hashes.get(item.clue_id)
            snapshot.append(
                {
                    "clue_id": item.clue_id,
                    "content_hash": item.content_hash,
                    "current_content_hash": current_hash,
                    "content_changed": current_hash != item.content_hash,
                }
            )

        return {
            **cls._summary_dict(row),
            "event_title": event_title,
            "total_content_length": row.total_content_length,
            "output_content_length": row.output_content_length,
            "model": row.actual_model,
            "duration_ms": row.elapsed_ms,
            "result": result,
            "evidence_snapshot": snapshot,
        }

    @classmethod
    def _persist_valid_result(
        cls,
        db: Session,
        evidence: EventEvidencePack,
        user: User,
        requested_model: str,
        actual_model: str,
        result: EventSynthesisResult,
        raw_output: str,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
        elapsed_ms: int,
    ) -> dict:
        """短事务新增版本；唯一约束解决并发版本号竞争，不重复调用模型。"""
        snapshot = [
            {"clue_id": source.clue_id, "content_hash": source.content_hash}
            for source in evidence.sources
        ]
        for _attempt in range(3):
            try:
                SmartCollectEvidenceService._require_task(db, evidence.task_id, user)
                event = SmartCollectEvidenceService._require_event(
                    db,
                    evidence.task_id,
                    evidence.event_id,
                )
                latest_version = (
                    db.query(func.max(SmartCollectEventSynthesis.version))
                    .filter(SmartCollectEventSynthesis.event_id == evidence.event_id)
                    .scalar()
                    or 0
                )
                row = SmartCollectEventSynthesis(
                    event_id=evidence.event_id,
                    version=latest_version + 1,
                    status="generated",
                    requested_model=requested_model,
                    actual_model=actual_model,
                    result_json=result.model_dump(mode="json"),
                    evidence_snapshot=snapshot,
                    source_count=evidence.completed_source_count,
                    total_content_length=evidence.total_content_length,
                    output_content_length=len(raw_output),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    elapsed_ms=elapsed_ms,
                    created_by=user.id,
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                return cls._detail_dict(db, row, event.title)
            except IntegrityError:
                db.rollback()
                continue
            except (SmartCollectTaskNotFoundError, SmartCollectEventNotFoundError):
                db.rollback()
                raise
            except SQLAlchemyError:
                db.rollback()
                raise SmartCollectSynthesisPersistenceError from None
        raise SmartCollectSynthesisPersistenceError

    async def synthesize(
        self,
        db: Session,
        task_id: int,
        event_id: int,
        user: User,
    ) -> dict:
        evidence = EventEvidencePack.model_validate(
            SmartCollectEvidenceService.build_evidence_pack(
                db,
                task_id,
                event_id,
                user,
            )
        )
        if not evidence.sources:
            raise SmartCollectSynthesisNoEvidenceError

        prompt = EventSynthesisPromptBuilder.build(evidence)
        started = perf_counter()
        try:
            provider_result = await self.provider.generate(
                prompt.system_message,
                prompt.user_message,
            )
        except LLMProviderConfigError:
            raise SmartCollectSynthesisConfigError from None
        except LLMProviderTimeoutError:
            raise SmartCollectSynthesisTimeoutError from None
        except LLMProviderEmptyResponseError:
            raise SmartCollectSynthesisEmptyResponseError from None
        except LLMProviderError:
            raise SmartCollectSynthesisError from None
        elapsed_ms = int(round((perf_counter() - started) * 1000))

        result = self._parse_result(provider_result.text)
        try:
            validate_event_synthesis_grounding(evidence, result)
        except GroundingValidationError:
            raise SmartCollectSynthesisGroundingError from None

        requested_model = str(
            getattr(self.provider, "model", "") or provider_result.model
        ).strip()
        actual_model = provider_result.model.strip()
        self._validate_model_identity(requested_model, actual_model)
        return self._persist_valid_result(
            db,
            evidence,
            user,
            requested_model,
            actual_model,
            result,
            provider_result.text,
            provider_result.input_tokens,
            provider_result.output_tokens,
            provider_result.total_tokens,
            elapsed_ms,
        )

    @classmethod
    def list_syntheses(
        cls,
        db: Session,
        task_id: int,
        event_id: int,
        user: User,
    ) -> dict:
        try:
            SmartCollectEvidenceService._require_task(db, task_id, user)
            SmartCollectEvidenceService._require_event(db, task_id, event_id)
            rows = (
                db.query(SmartCollectEventSynthesis)
                .filter(SmartCollectEventSynthesis.event_id == event_id)
                .order_by(SmartCollectEventSynthesis.version.desc())
                .all()
            )
            return {
                "event_id": event_id,
                "items": [cls._summary_dict(row) for row in rows],
            }
        finally:
            db.rollback()

    @classmethod
    def get_synthesis(
        cls,
        db: Session,
        task_id: int,
        event_id: int,
        synthesis_id: int,
        user: User,
    ) -> dict:
        try:
            SmartCollectEvidenceService._require_task(db, task_id, user)
            event = SmartCollectEvidenceService._require_event(db, task_id, event_id)
            row = (
                db.query(SmartCollectEventSynthesis)
                .filter(
                    SmartCollectEventSynthesis.id == synthesis_id,
                    SmartCollectEventSynthesis.event_id == event_id,
                )
                .first()
            )
            if row is None:
                raise SmartCollectSynthesisNotFoundError
            return cls._detail_dict(db, row, event.title)
        finally:
            db.rollback()

    @classmethod
    def _review(
        cls,
        db: Session,
        task_id: int,
        event_id: int,
        synthesis_id: int,
        user: User,
        target_status: str,
    ) -> dict:
        try:
            SmartCollectEvidenceService._require_task(db, task_id, user)
            event = (
                db.query(SmartCollectEvent)
                .filter(
                    SmartCollectEvent.id == event_id,
                    SmartCollectEvent.task_id == task_id,
                )
                .with_for_update()
                .first()
            )
            if event is None:
                raise SmartCollectEventNotFoundError
            row = (
                db.query(SmartCollectEventSynthesis)
                .filter(
                    SmartCollectEventSynthesis.id == synthesis_id,
                    SmartCollectEventSynthesis.event_id == event_id,
                )
                .first()
            )
            if row is None:
                raise SmartCollectSynthesisNotFoundError

            if target_status == "approved":
                if row.status != "generated":
                    raise SmartCollectSynthesisConflictError
                approved = (
                    db.query(SmartCollectEventSynthesis.id)
                    .filter(
                        SmartCollectEventSynthesis.event_id == event_id,
                        SmartCollectEventSynthesis.status == "approved",
                        SmartCollectEventSynthesis.id != row.id,
                    )
                    .first()
                )
                if approved:
                    raise SmartCollectSynthesisConflictError
            elif target_status == "rejected":
                # 允许编辑显式废弃旧approved，之后再选择新版本；绝不静默替换。
                if row.status not in {"generated", "approved"}:
                    raise SmartCollectSynthesisConflictError
            else:
                raise ValueError("unsupported synthesis status")

            row.status = target_status
            row.reviewed_by = user.id
            row.reviewed_at = datetime.now()
            db.commit()
            db.refresh(row)
            return cls._detail_dict(db, row, event.title)
        except (
            SmartCollectTaskNotFoundError,
            SmartCollectEventNotFoundError,
            SmartCollectSynthesisNotFoundError,
        ):
            db.rollback()
            raise
        except SmartCollectSynthesisConflictError:
            db.rollback()
            raise
        except SQLAlchemyError:
            db.rollback()
            raise SmartCollectSynthesisPersistenceError from None

    @classmethod
    def approve(
        cls,
        db: Session,
        task_id: int,
        event_id: int,
        synthesis_id: int,
        user: User,
    ) -> dict:
        return cls._review(db, task_id, event_id, synthesis_id, user, "approved")

    @classmethod
    def reject(
        cls,
        db: Session,
        task_id: int,
        event_id: int,
        synthesis_id: int,
        user: User,
    ) -> dict:
        return cls._review(db, task_id, event_id, synthesis_id, user, "rejected")
