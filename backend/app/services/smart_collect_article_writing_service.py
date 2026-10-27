# -*- coding: utf-8 -*-
"""基于Article关联approved Synthesis生成不落库的Grounded写作建议。"""
import html
import json
import re
from html.parser import HTMLParser
from time import perf_counter

from pydantic import ValidationError
from sqlalchemy.orm import Session, joinedload

from ..models.article import Article
from ..models.smart_collect import SmartCollectArticleSource, SmartCollectEventSynthesis
from ..models.user import User
from ..schemas.article_writing import ArticleWritingResult
from .article_writing_prompt_builder import ArticleWritingContext, ArticleWritingPromptBuilder
from .llm_provider import (
    LLMProvider,
    LLMProviderConfigError,
    LLMProviderEmptyResponseError,
    LLMProviderError,
    LLMProviderTimeoutError,
)
from .smart_collect_synthesis_service import (
    SmartCollectSynthesisDataError,
    SmartCollectSynthesisModelError,
    SmartCollectSynthesisService,
)


class SmartCollectArticleWritingError(Exception):
    message = "AI写作助手生成失败，请稍后重试"


class SmartCollectArticleWritingNotFoundError(SmartCollectArticleWritingError):
    message = "文稿不存在"


class SmartCollectArticleWritingPermissionError(SmartCollectArticleWritingError):
    message = "只能为自己有权编辑的文稿使用AI写作助手"


class SmartCollectArticleWritingStatusError(SmartCollectArticleWritingError):
    message = "当前文稿状态不允许使用AI写作助手"


class SmartCollectArticleWritingUnsupportedError(SmartCollectArticleWritingError):
    message = "当前文稿没有智能采编来源，暂不支持AI写作助手"


class SmartCollectArticleWritingSynthesisStatusError(SmartCollectArticleWritingError):
    message = "文稿关联的AI事件整理版本未确认，不能用于正式写作"


class SmartCollectArticleWritingDataError(SmartCollectArticleWritingError):
    message = "文稿关联的已确认事实资料无效"


class SmartCollectArticleWritingConfigError(SmartCollectArticleWritingError):
    message = "AI写作助手尚未配置"


class SmartCollectArticleWritingTimeoutError(SmartCollectArticleWritingError):
    message = "AI写作助手响应超时，请稍后重试"


class SmartCollectArticleWritingEmptyResponseError(SmartCollectArticleWritingError):
    message = "AI写作助手没有返回内容，请重试"


class SmartCollectArticleWritingJsonError(SmartCollectArticleWritingError):
    message = "AI写作助手返回的JSON无效，请重试"


class SmartCollectArticleWritingSchemaError(SmartCollectArticleWritingError):
    message = "AI写作助手返回结构不符合约定，请重试"


class SmartCollectArticleWritingModelError(SmartCollectArticleWritingError):
    message = "AI写作助手实际模型与项目配置不一致，结果已拒绝"


class SmartCollectArticleWritingSafetyError(SmartCollectArticleWritingError):
    message = "AI写作助手返回内容未通过正文安全校验，结果已拒绝"


class _AllowlistHTMLSanitizer(HTMLParser):
    """仅保留编辑器可接受的基础结构标签，删除全部属性和危险节点内容。"""

    ALLOWED_TAGS = {"p", "h2", "strong", "ul", "ol", "li", "blockquote"}
    BLOCKED_CONTENT_TAGS = {
        "script",
        "style",
        "iframe",
        "object",
        "embed",
        "svg",
        "math",
        "template",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.open_tags: list[str] = []
        self.blocked_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        normalized = tag.casefold()
        if self.blocked_depth:
            self.blocked_depth += 1
            return
        if normalized in self.BLOCKED_CONTENT_TAGS:
            self.blocked_depth = 1
            return
        if normalized in self.ALLOWED_TAGS:
            self.parts.append(f"<{normalized}>")
            self.open_tags.append(normalized)

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.blocked_depth:
            self.blocked_depth -= 1
            return
        normalized = tag.casefold()
        if normalized not in self.open_tags:
            return
        while self.open_tags:
            current = self.open_tags.pop()
            self.parts.append(f"</{current}>")
            if current == normalized:
                break

    def handle_data(self, data: str) -> None:
        if not self.blocked_depth:
            self.parts.append(html.escape(data, quote=False))

    def get_html(self) -> str:
        while self.open_tags:
            self.parts.append(f"</{self.open_tags.pop()}>")
        return "".join(self.parts).strip()


class SmartCollectArticleWritingService:
    """权限和approved事实检查先于唯一一次模型调用；结果只返回、不持久化。"""

    EDITABLE_STATUSES = {"draft", "rejected"}
    INTERNAL_MARKERS = (
        re.compile(r"SOURCE\s*\[", re.IGNORECASE),
        re.compile(r"参考来源", re.IGNORECASE),
        re.compile(r"Evidence\s*Hash", re.IGNORECASE),
        re.compile(r"模型信息", re.IGNORECASE),
        re.compile(r"Token", re.IGNORECASE),
        re.compile(r"耗时", re.IGNORECASE),
        re.compile(r"AI\s*审核提示", re.IGNORECASE),
        re.compile(r"编辑注意事项", re.IGNORECASE),
        re.compile(r"来源冲突", re.IGNORECASE),
        re.compile(r"证据不足", re.IGNORECASE),
    )

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    @staticmethod
    def _load_context(
        db: Session,
        article_id: int,
        user: User,
    ) -> ArticleWritingContext:
        """读取后立即结束只读事务，外部模型调用期间不占用数据库连接。"""
        try:
            article = db.get(Article, article_id)
            if article is None:
                raise SmartCollectArticleWritingNotFoundError
            if user.role != "admin" and article.author_id != user.id:
                raise SmartCollectArticleWritingPermissionError
            if article.status not in SmartCollectArticleWritingService.EDITABLE_STATUSES:
                raise SmartCollectArticleWritingStatusError

            link = (
                db.query(SmartCollectArticleSource)
                .options(
                    joinedload(SmartCollectArticleSource.synthesis).joinedload(
                        SmartCollectEventSynthesis.event
                    )
                )
                .filter(SmartCollectArticleSource.article_id == article_id)
                .first()
            )
            if link is None or link.synthesis is None:
                raise SmartCollectArticleWritingUnsupportedError
            synthesis = link.synthesis
            if synthesis.status != "approved":
                raise SmartCollectArticleWritingSynthesisStatusError
            if synthesis.event is None:
                raise SmartCollectArticleWritingDataError
            try:
                result = SmartCollectSynthesisService.validate_stored_result(synthesis)
            except SmartCollectSynthesisDataError:
                raise SmartCollectArticleWritingDataError from None
            return ArticleWritingContext(
                article_id=article.id,
                article_title=article.title,
                event_title=synthesis.event.title,
                synthesis_id=synthesis.id,
                synthesis_version=synthesis.version,
                source_count=synthesis.source_count,
                synthesis_result=result,
            )
        finally:
            db.rollback()

    @staticmethod
    def _parse_result(raw_text: str) -> ArticleWritingResult:
        """严格接受单个JSON对象；Markdown围栏和夹带说明均视为失败。"""
        text = raw_text.strip()
        if text.startswith("```"):
            raise SmartCollectArticleWritingJsonError
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            raise SmartCollectArticleWritingJsonError from None
        if not isinstance(data, dict):
            raise SmartCollectArticleWritingSchemaError
        try:
            return ArticleWritingResult.model_validate(data)
        except ValidationError:
            raise SmartCollectArticleWritingSchemaError from None

    @classmethod
    def _sanitize_html(cls, value: str) -> str:
        parser = _AllowlistHTMLSanitizer()
        try:
            parser.feed(value)
            parser.close()
        except (ValueError, TypeError):
            raise SmartCollectArticleWritingSafetyError from None
        sanitized = parser.get_html()
        visible_text = html.unescape(re.sub(r"<[^>]+>", "", sanitized)).strip()
        if not visible_text:
            raise SmartCollectArticleWritingSafetyError
        return sanitized

    @classmethod
    def _validate_reader_fields(
        cls,
        result: ArticleWritingResult,
        requested_model: str,
        actual_model: str,
    ) -> ArticleWritingResult:
        if re.search(r"<[^>]+>", result.title) or re.search(r"<[^>]+>", result.summary):
            raise SmartCollectArticleWritingSafetyError
        sanitized_html = cls._sanitize_html(result.content_html)
        combined = "\n".join([result.title, result.summary, sanitized_html])
        if "```" in combined or any(pattern.search(combined) for pattern in cls.INTERNAL_MARKERS):
            raise SmartCollectArticleWritingSafetyError
        lowered = combined.casefold()
        for model_name in {requested_model.strip(), actual_model.strip()}:
            if model_name and model_name.casefold() in lowered:
                raise SmartCollectArticleWritingSafetyError
        return result.model_copy(update={"content_html": sanitized_html})

    async def generate(
        self,
        db: Session,
        article_id: int,
        user: User,
    ) -> dict:
        context = self._load_context(db, article_id, user)
        prompt = ArticleWritingPromptBuilder.build(context)
        started = perf_counter()
        try:
            provider_result = await self.provider.generate(
                prompt.system_message,
                prompt.user_message,
            )
        except LLMProviderConfigError:
            raise SmartCollectArticleWritingConfigError from None
        except LLMProviderTimeoutError:
            raise SmartCollectArticleWritingTimeoutError from None
        except LLMProviderEmptyResponseError:
            raise SmartCollectArticleWritingEmptyResponseError from None
        except LLMProviderError:
            raise SmartCollectArticleWritingError from None
        elapsed_ms = int(round((perf_counter() - started) * 1000))

        requested_model = str(
            getattr(self.provider, "model", "") or provider_result.model
        ).strip()
        actual_model = provider_result.model.strip()
        try:
            SmartCollectSynthesisService._validate_model_identity(
                requested_model,
                actual_model,
            )
        except SmartCollectSynthesisModelError:
            raise SmartCollectArticleWritingModelError from None

        result = self._parse_result(provider_result.text)
        result = self._validate_reader_fields(result, requested_model, actual_model)
        return {
            "article_id": context.article_id,
            "synthesis_id": context.synthesis_id,
            "synthesis_version": context.synthesis_version,
            "approved_core_fact_count": len(context.synthesis_result.core_facts),
            "requested_model": requested_model,
            "actual_model": actual_model,
            "model": actual_model,
            "elapsed_ms": elapsed_ms,
            "input_tokens": provider_result.input_tokens,
            "output_tokens": provider_result.output_tokens,
            "total_tokens": provider_result.total_tokens,
            "result": result,
        }
