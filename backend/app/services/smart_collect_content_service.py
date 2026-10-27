# -*- coding: utf-8 -*-
"""事件来源正文准备：数据库快照、事务外提取、通用清洗和逐条保存。"""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import html
import re

from sqlalchemy.exc import SQLAlchemyError
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
from .content_provider import ContentProvider, ContentProviderError, ContentProviderResult
from .smart_collect_event_service import SmartCollectEventNotFoundError
from .smart_collect_service import SmartCollectTaskNotFoundError


MIN_CONTENT_LENGTH = 200
GENERIC_CONTENT_NOISE = frozenset(
    {
        "首页",
        "主页",
        "网站首页",
        "导航",
        "菜单",
        "搜索",
        "登录",
        "注册",
        "退出登录",
        "分享",
        "分享到",
        "更多",
        "广告",
        "返回顶部",
        "上一篇",
        "下一篇",
        "相关阅读",
        "相关推荐",
        "热门推荐",
        "隐私政策",
        "服务条款",
        "使用条款",
        "网站地图",
        "订阅",
        "home",
        "menu",
        "search",
        "login",
        "log in",
        "sign in",
        "register",
        "sign up",
        "share",
        "more",
        "advertisement",
        "privacy policy",
        "terms of use",
        "site map",
        "sitemap",
        "subscribe",
        "skip to content",
    }
)


class SmartCollectContentNotFoundError(Exception):
    message = "新闻正文不存在或尚未准备"


class SmartCollectContentPersistenceError(Exception):
    message = "新闻正文保存失败，请稍后重试"


@dataclass(frozen=True)
class ContentClueSnapshot:
    """网络调用使用的普通Python数据，不携带Session或ORM对象。"""

    clue_id: int
    rank: int
    title: str
    source: str
    url: str
    stored_status: str | None
    stored_content: str | None


@dataclass(frozen=True)
class PreparedContent:
    status: str
    content: str | None
    content_hash: str | None
    error_message: str | None


class SmartCollectContentService:
    """为人工事件准备可复用正文，不处理分组、AI或文稿创建。"""

    def __init__(self, provider: ContentProvider):
        self.provider = provider

    @staticmethod
    def clean_content(value: str) -> str:
        """通用清洗HTML/Markdown、空白和明显控件文字，不含站点专属规则。"""
        if not isinstance(value, str) or not value.strip():
            return ""

        text = html.unescape(value)
        text = re.sub(
            r"(?is)<(?:script|style|noscript|svg|canvas|nav|header|footer|aside|form)\b[^>]*>.*?</(?:script|style|noscript|svg|canvas|nav|header|footer|aside|form)>",
            " ",
            text,
        )
        text = re.sub(r"(?i)<br\s*/?>", "\n", text)
        text = re.sub(r"(?i)</(?:p|div|article|section|li|h[1-6]|tr)\s*>", "\n", text)
        text = re.sub(r"<[^>]*>", " ", text)
        text = re.sub(r"!\[[^]]*]\([^)]*\)", " ", text)
        text = re.sub(r"\[([^]]+)]\([^)]*\)", r"\1", text)
        text = re.sub(r"`{1,3}([^`]+)`{1,3}", r"\1", text)
        text = re.sub(r"\*{1,2}([^*\n]+)\*{1,2}", r"\1", text)
        text = re.sub(
            r"(?m)^\s*展开剩余\s*(?:\r?\n\s*)?\d+\s*(?:\r?\n\s*)?%\s*$",
            " ",
            text,
        )

        lines: list[str] = []
        previous = None
        for raw_line in text.splitlines():
            line = re.sub(r"^\s{0,3}#{1,6}\s*", "", raw_line)
            line = re.sub(r"^\s*>+\s?", "", line)
            line = re.sub(r"^\s*[-*+]\s+", "", line)
            line = re.sub(r"\s+", " ", line).strip(" |｜\t")
            if not line or re.fullmatch(r"[-=|｜:：\s]{3,}", line):
                continue
            if SmartCollectContentService._is_noise_line(line):
                continue
            if line == previous:
                continue
            lines.append(line)
            previous = line

        cleaned = "\n".join(lines)
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    @staticmethod
    def _normalize_key(value: str) -> str:
        return re.sub(r"[\W_]+", "", value, flags=re.UNICODE).casefold()

    @classmethod
    def _trim_article_bounds(cls, content: str, title: str) -> str:
        """用稳定标题和通用页脚标记裁掉正文前后外壳，不依赖来源网站。"""
        lines = content.splitlines()
        title_key = cls._normalize_key(title)
        if title_key:
            for index, line in enumerate(lines[:40]):
                line_key = cls._normalize_key(line)
                if len(line_key) >= 8 and (
                    title_key.startswith(line_key) or line_key.startswith(title_key)
                ):
                    lines = lines[index:]
                    break

        footer_labels = {
            "关于我们",
            "加入我们",
            "联系我们",
            "版权声明",
            "合作伙伴",
            "网站地图",
            "about us",
            "contact us",
            "上一则",
            "下一则",
            "延伸阅读",
            "相关阅读",
            "相关推荐",
            "热门新闻",
            "热门推荐",
        }
        footer_start = max(0, len(lines) - 40)
        for index in range(footer_start, len(lines)):
            if lines[index].strip().casefold() in footer_labels:
                before = "".join(lines[:index])
                if len(re.sub(r"\s+", "", before)) >= MIN_CONTENT_LENGTH:
                    lines = lines[:index]
                    break
        return "\n".join(lines).strip()

    @classmethod
    def _clean_for_clue(cls, value: str, title: str) -> str:
        return cls._trim_article_bounds(cls.clean_content(value), title)

    @staticmethod
    def _is_noise_line(line: str) -> bool:
        normalized = line.strip(" |｜/\\>›»·•-–—_:：").casefold()
        if normalized in GENERIC_CONTENT_NOISE:
            return True
        if len(line) <= 100 and re.match(
            r"^(?:首页|主页|home)\s*[>›»/|｜·]",
            line,
            re.IGNORECASE,
        ):
            return True
        if len(line) <= 180 and re.search(
            r"(?:版权所有|all rights reserved)",
            line,
            re.IGNORECASE,
        ):
            return True
        if re.fullmatch(r"(?:上一篇|下一篇|相关阅读|相关推荐|热门推荐)(?:\s*[:：].*)?", line):
            return True
        if re.match(
            r"^(?:打开微信.*(?:扫一扫|分享).*|展开剩余\s*\d+\s*%|搜索历史清空|账号登录)$",
            line,
        ):
            return True
        return False

    @classmethod
    def _validate_content(cls, content: str, title: str) -> str | None:
        compact = re.sub(r"\s+", "", content)
        if len(compact) < MIN_CONTENT_LENGTH:
            return f"正文过短或无效，清洗后不足{MIN_CONTENT_LENGTH}字"

        content_key = cls._normalize_key(content)
        title_key = cls._normalize_key(title)
        if title_key and len(content_key.replace(title_key, "")) < MIN_CONTENT_LENGTH // 4:
            return "正文内容基本只有网页标题"

        lead = content[:500].casefold()
        invalid_markers = (
            "404 not found",
            "page not found",
            "access denied",
            "checking your browser",
            "enable javascript",
            "页面不存在",
            "网页不存在",
            "访问被拒绝",
            "访问异常",
            "请完成安全验证",
            "请输入验证码",
        )
        if len(compact) < 2000 and any(marker in lead for marker in invalid_markers):
            return "提取结果疑似错误页或验证码页"
        if len(compact) < 1500 and "cookie" in lead and (
            "privacy" in lead or "consent" in lead or "preferences" in lead
        ):
            return "提取结果疑似只有Cookie提示"
        return None

    @staticmethod
    def _hash_content(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _load_event_snapshot(
        db: Session,
        task_id: int,
        event_id: int,
        user: User,
    ) -> list[ContentClueSnapshot]:
        """读取后立即结束事务，确保网络请求期间不占用数据库连接。"""
        try:
            task = db.get(SmartCollectTask, task_id)
            if not task or (user.role != "admin" and task.creator_id != user.id):
                raise SmartCollectTaskNotFoundError
            event = (
                db.query(SmartCollectEvent.id)
                .filter(
                    SmartCollectEvent.id == event_id,
                    SmartCollectEvent.task_id == task_id,
                )
                .first()
            )
            if event is None:
                raise SmartCollectEventNotFoundError

            rows = (
                db.query(
                    SmartCollectEventClue.clue_id.label("clue_id"),
                    SmartCollectTaskClue.rank.label("rank"),
                    NewsClue.title.label("title"),
                    NewsClue.source.label("source"),
                    NewsClue.url.label("url"),
                    NewsClueContent.status.label("stored_status"),
                    NewsClueContent.content.label("stored_content"),
                )
                .select_from(SmartCollectEventClue)
                .join(
                    SmartCollectTaskClue,
                    (SmartCollectTaskClue.task_id == SmartCollectEventClue.task_id)
                    & (SmartCollectTaskClue.clue_id == SmartCollectEventClue.clue_id),
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
            return [ContentClueSnapshot(**row._mapping) for row in rows]
        finally:
            db.rollback()

    @staticmethod
    def _mark_pending(db: Session, snapshots: list[ContentClueSnapshot]) -> None:
        if not snapshots:
            return
        try:
            ids = [snapshot.clue_id for snapshot in snapshots]
            existing = {
                row.clue_id: row
                for row in (
                    db.query(NewsClueContent)
                    .filter(NewsClueContent.clue_id.in_(ids))
                    .all()
                )
            }
            for snapshot in snapshots:
                row = existing.get(snapshot.clue_id)
                if row is None:
                    row = NewsClueContent(clue_id=snapshot.clue_id)
                    db.add(row)
                row.status = "pending"
                row.content = None
                row.content_hash = None
                row.fetched_at = None
                row.error_message = None
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            raise SmartCollectContentPersistenceError from exc

    @staticmethod
    def _save_result(
        db: Session,
        clue_id: int,
        result: PreparedContent,
        update_fetched_at: bool = True,
    ) -> None:
        """每个来源独立短事务保存，一个互联网失败不影响其他成功正文。"""
        try:
            row = (
                db.query(NewsClueContent)
                .filter(NewsClueContent.clue_id == clue_id)
                .first()
            )
            if row is None:
                row = NewsClueContent(clue_id=clue_id)
                db.add(row)
            row.status = result.status
            row.content = result.content
            row.content_hash = result.content_hash
            row.error_message = result.error_message
            if update_fetched_at:
                row.fetched_at = datetime.now()
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            raise SmartCollectContentPersistenceError from exc

    @classmethod
    def _prepare_result(
        cls,
        snapshot: ContentClueSnapshot,
        provider_result: ContentProviderResult,
    ) -> PreparedContent:
        if provider_result.error_message:
            return PreparedContent(
                status="failed",
                content=None,
                content_hash=None,
                error_message=provider_result.error_message[:500],
            )
        cleaned = cls._clean_for_clue(provider_result.content or "", snapshot.title)
        error = cls._validate_content(cleaned, snapshot.title)
        if error:
            return PreparedContent(
                status="failed",
                content=None,
                content_hash=None,
                error_message=error,
            )
        return PreparedContent(
            status="completed",
            content=cleaned,
            content_hash=cls._hash_content(cleaned),
            error_message=None,
        )

    @staticmethod
    def _build_response(
        db: Session,
        event_id: int,
        snapshots: list[ContentClueSnapshot],
    ) -> dict:
        try:
            ids = [snapshot.clue_id for snapshot in snapshots]
            records = {
                row.clue_id: row
                for row in (
                    db.query(NewsClueContent)
                    .filter(NewsClueContent.clue_id.in_(ids))
                    .all()
                    if ids
                    else []
                )
            }
            items = []
            for snapshot in snapshots:
                record = records.get(snapshot.clue_id)
                status = record.status if record else "pending"
                items.append(
                    {
                        "clue_id": snapshot.clue_id,
                        "title": snapshot.title,
                        "source": snapshot.source,
                        "status": status,
                        "content_length": len(record.content) if record and record.content else 0,
                        "error_message": record.error_message if record else None,
                    }
                )
            return {
                "event_id": event_id,
                "total": len(items),
                "completed": sum(item["status"] == "completed" for item in items),
                "failed": sum(item["status"] == "failed" for item in items),
                "items": items,
            }
        finally:
            db.rollback()

    async def prepare_event(
        self,
        db: Session,
        task_id: int,
        event_id: int,
        user: User,
    ) -> dict:
        snapshots = self._load_event_snapshot(db, task_id, event_id, user)
        candidates = []
        for snapshot in snapshots:
            if snapshot.stored_status == "completed" and snapshot.stored_content:
                locally_cleaned = self._clean_for_clue(
                    snapshot.stored_content,
                    snapshot.title,
                )
                if self._validate_content(locally_cleaned, snapshot.title) is None:
                    if locally_cleaned != snapshot.stored_content:
                        self._save_result(
                            db,
                            snapshot.clue_id,
                            PreparedContent(
                                status="completed",
                                content=locally_cleaned,
                                content_hash=self._hash_content(locally_cleaned),
                                error_message=None,
                            ),
                            update_fetched_at=False,
                        )
                    continue
            candidates.append(snapshot)
        if candidates:
            self._mark_pending(db, candidates)
            try:
                provider_results = await self.provider.extract_batch(
                    [snapshot.url for snapshot in candidates]
                )
            except ContentProviderError as exc:
                provider_results = [
                    ContentProviderResult(url=snapshot.url, error_message=exc.message)
                    for snapshot in candidates
                ]
            if len(provider_results) != len(candidates):
                provider_results = [
                    ContentProviderResult(
                        url=snapshot.url,
                        error_message="正文提取服务返回数量异常",
                    )
                    for snapshot in candidates
                ]
            for snapshot, provider_result in zip(candidates, provider_results):
                prepared = self._prepare_result(snapshot, provider_result)
                self._save_result(db, snapshot.clue_id, prepared)

        return self._build_response(db, event_id, snapshots)

    @staticmethod
    def get_content(db: Session, clue_id: int, user: User) -> dict:
        """只有能通过人工事件访问该线索的用户才能读取完整正文。"""
        try:
            permission_query = (
                db.query(SmartCollectEventClue.clue_id)
                .join(SmartCollectEvent, SmartCollectEvent.id == SmartCollectEventClue.event_id)
                .join(SmartCollectTask, SmartCollectTask.id == SmartCollectEvent.task_id)
                .filter(SmartCollectEventClue.clue_id == clue_id)
            )
            if user.role != "admin":
                permission_query = permission_query.filter(
                    SmartCollectTask.creator_id == user.id
                )
            if permission_query.first() is None:
                raise SmartCollectContentNotFoundError

            row = (
                db.query(NewsClue, NewsClueContent)
                .join(NewsClueContent, NewsClueContent.clue_id == NewsClue.id)
                .filter(NewsClue.id == clue_id)
                .first()
            )
            if row is None:
                raise SmartCollectContentNotFoundError
            clue, content = row
            return {
                "clue_id": clue.id,
                "title": clue.title,
                "source": clue.source,
                "url": clue.url,
                "status": content.status,
                "content": content.content,
                "content_length": len(content.content) if content.content else 0,
                "fetched_at": content.fetched_at,
                "error_message": content.error_message,
            }
        finally:
            db.rollback()
