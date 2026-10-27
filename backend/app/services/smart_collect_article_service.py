# -*- coding: utf-8 -*-
"""把已确认的事件AI整理转换为现有CMS Article草稿。"""
import re
from html import escape

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..models.smart_collect import (
    NewsClue,
    NewsClueContent,
    SmartCollectArticleSource,
    SmartCollectEventSynthesis,
)
from ..models.user import User
from ..schemas.article import ArticleIn
from ..schemas.smart_collect import EventEvidenceSnapshotItem, EventSynthesisResult
from .article_service import ArticleService
from .smart_collect_evidence_service import SmartCollectEvidenceService
from .smart_collect_event_service import SmartCollectEventNotFoundError
from .smart_collect_service import SmartCollectTaskNotFoundError
from .smart_collect_synthesis_service import (
    SmartCollectSynthesisDataError,
    SmartCollectSynthesisService,
)


class SmartCollectArticleError(Exception):
    message = "创建CMS文稿草稿失败"


class SmartCollectArticleNotFoundError(SmartCollectArticleError):
    message = "AI事件整理版本不存在"


class SmartCollectArticleStatusError(SmartCollectArticleError):
    message = "只有已确认的AI事件整理版本才能创建文稿"


class SmartCollectArticleAlreadyExistsError(SmartCollectArticleError):
    message = "该AI事件整理版本已经创建过文稿"


class SmartCollectArticleValidationError(SmartCollectArticleError):
    message = "AI事件整理内容不符合现有CMS文稿字段规则"


class SmartCollectArticleDataError(SmartCollectArticleError):
    message = "已确认的AI事件整理历史数据无效"


class SmartCollectArticlePersistenceError(SmartCollectArticleError):
    message = "CMS文稿草稿保存失败，请稍后重试"


class SmartCollectArticleService:
    """只做已确认Synthesis到CMS草稿的确定性转换，不调用任何外部服务。"""

    @staticmethod
    def _reader_text(value: str) -> str:
        """正文不展示模型使用的SOURCE编号，即使模型误把编号写进读者字段。"""
        return re.sub(
            r"SOURCE\s*\[\s*\d+\s*]",
            "",
            value,
            flags=re.IGNORECASE,
        ).strip()

    @classmethod
    def _build_content(
        cls,
        result: EventSynthesisResult,
    ) -> str:
        """只把面向读者的整理字段写入正文，审核与追溯数据留在原表。"""
        sections = [
            '<section class="smart-collect-section">',
            "<h2>事件摘要</h2>",
            f"<p>{escape(cls._reader_text(result.summary))}</p>",
            "</section>",
        ]
        if result.core_facts:
            sections.extend([
                '<section class="smart-collect-section">',
                "<h2>核心事实</h2>",
            ])
            sections.append("<ol>")
            for fact in result.core_facts:
                sections.append(f"<li>{escape(cls._reader_text(fact.text))}</li>")
            sections.append("</ol>")
            sections.append("</section>")

        entities = [cls._reader_text(item) for item in result.entities]
        entities = [item for item in entities if item]
        if entities:
            sections.extend([
                '<section class="smart-collect-section">',
                "<h2>涉及主体</h2>",
                f"<p>{escape('；'.join(entities))}</p>",
                "</section>",
            ])

        time_info = [cls._reader_text(item) for item in result.time_info]
        time_info = [item for item in time_info if item]
        if time_info:
            sections.extend([
                '<section class="smart-collect-section">',
                "<h2>时间信息</h2>",
                f"<p>{escape('；'.join(time_info))}</p>",
                "</section>",
            ])
        return "\n".join(sections)

    @classmethod
    def get_editorial_context(cls, db: Session, article) -> dict | None:
        """读取Article编辑页专用的来源与AI审核信息，不复制正文或证据哈希。"""
        link = article.smart_collect_source
        if link is None:
            return None

        synthesis = link.synthesis
        result = SmartCollectSynthesisService.validate_stored_result(synthesis)
        try:
            snapshot = [
                EventEvidenceSnapshotItem.model_validate(item)
                for item in synthesis.evidence_snapshot
            ]
        except (ValidationError, TypeError, ValueError):
            raise SmartCollectSynthesisDataError from None

        clue_ids = [item.clue_id for item in snapshot]
        rows = (
            db.query(NewsClue, NewsClueContent)
            .outerjoin(NewsClueContent, NewsClueContent.clue_id == NewsClue.id)
            .filter(NewsClue.id.in_(clue_ids))
            .all()
            if clue_ids
            else []
        )
        clue_rows = {clue.id: (clue, content) for clue, content in rows}
        sources = []
        for item in snapshot:
            row = clue_rows.get(item.clue_id)
            clue, content = row if row else (None, None)
            sources.append({
                "clue_id": item.clue_id,
                "title": clue.title if clue else "来源线索已不存在",
                "source": clue.source if clue else "",
                "url": clue.url if clue else "",
                "content_status": content.status if content else None,
            })

        return {
            "synthesis_id": synthesis.id,
            "event_id": synthesis.event_id,
            "source_count": len(snapshot),
            "sources": sources,
            "conflicts": [item.model_dump() for item in result.conflicts],
            "insufficient_evidence": list(result.insufficient_evidence),
        }

    @staticmethod
    def _article_info(article) -> dict:
        return {
            "id": article.id,
            "title": article.title,
            "status": article.status,
            "created_at": article.created_at,
        }

    @classmethod
    def create_article(
        cls,
        db: Session,
        task_id: int,
        event_id: int,
        synthesis_id: int,
        user: User,
    ) -> dict:
        """权限、状态、转换、Article和来源关联全部在一次短事务内完成。"""
        try:
            SmartCollectEvidenceService._require_task(db, task_id, user)
            event = SmartCollectEvidenceService._require_event(db, task_id, event_id)
            synthesis = (
                db.query(SmartCollectEventSynthesis)
                .filter(
                    SmartCollectEventSynthesis.id == synthesis_id,
                    SmartCollectEventSynthesis.event_id == event_id,
                )
                .with_for_update()
                .first()
            )
            if synthesis is None:
                raise SmartCollectArticleNotFoundError
            if synthesis.status != "approved":
                raise SmartCollectArticleStatusError
            if synthesis.article_source is not None:
                raise SmartCollectArticleAlreadyExistsError

            result = SmartCollectSynthesisService.validate_stored_result(synthesis)
            try:
                snapshot = [
                    EventEvidenceSnapshotItem.model_validate(item)
                    for item in synthesis.evidence_snapshot
                ]
            except (ValidationError, TypeError, ValueError):
                raise SmartCollectSynthesisDataError from None

            body = ArticleIn(
                title=event.title,
                summary=result.summary,
                content=cls._build_content(result),
                cover_url="",
                category_ids=[],
            )
            article = ArticleService.create_draft(db, user, body)
            db.add(
                SmartCollectArticleSource(
                    article_id=article.id,
                    synthesis_id=synthesis.id,
                )
            )
            db.flush()
            db.commit()
            db.refresh(article)
            return {
                "message": "CMS文稿草稿已创建",
                "synthesis_id": synthesis.id,
                "article": cls._article_info(article),
            }
        except (
            SmartCollectTaskNotFoundError,
            SmartCollectEventNotFoundError,
            SmartCollectArticleNotFoundError,
            SmartCollectArticleStatusError,
            SmartCollectArticleAlreadyExistsError,
        ):
            db.rollback()
            raise
        except SmartCollectSynthesisDataError:
            db.rollback()
            raise SmartCollectArticleDataError from None
        except ValidationError:
            db.rollback()
            raise SmartCollectArticleValidationError from None
        except IntegrityError:
            db.rollback()
            existing = db.query(SmartCollectArticleSource.id).filter_by(
                synthesis_id=synthesis_id
            ).first()
            db.rollback()
            if existing:
                raise SmartCollectArticleAlreadyExistsError from None
            raise SmartCollectArticlePersistenceError from None
        except SQLAlchemyError:
            db.rollback()
            raise SmartCollectArticlePersistenceError from None
