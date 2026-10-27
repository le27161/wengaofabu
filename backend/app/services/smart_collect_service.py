# -*- coding: utf-8 -*-
"""智能采编任务服务：任务状态、URL精确去重和MySQL持久化。"""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import math
from urllib.parse import unquote_plus, urlsplit, urlunsplit

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload
from starlette.concurrency import run_in_threadpool

from ..models.smart_collect import NewsClue, SmartCollectTask, SmartCollectTaskClue
from ..models.user import User
from ..schemas.smart_collect import SmartCollectSearchRequest, SmartCollectSearchResponse
from .embedding_service import EmbeddingScorer, EmbeddingServiceError
from .search_service import SearchService, SearchServiceError

TRACKING_QUERY_NAMES = frozenset({"fbclid", "gclid"})


class UrlNormalizationError(ValueError):
    """URL无法安全标准化。"""


class SmartCollectPersistenceError(Exception):
    """可安全返回给前端的任务持久化异常。"""

    message = "采编任务保存失败，请稍后重试"


class SmartCollectTaskNotFoundError(Exception):
    """任务不存在，或当前编辑无权得知该任务是否存在。"""

    message = "采编任务不存在"


class SmartCollectTaskClueNotFoundError(Exception):
    """指定新闻不属于该次采编任务。"""

    message = "任务新闻线索不存在"


class SmartCollectRelevanceForbiddenError(Exception):
    """当前用户角色不能执行人工标注。"""

    message = "无权修改人工相关性标签"


class PreparedClueChanged(Exception):
    """Embedding期间线索被其他任务写入或删除，需要重新读取并计算。"""


@dataclass(frozen=True)
class PreparedClue:
    """事务外评分所需的稳定快照，不携带Session或ORM对象。"""

    existing_clue_id: int | None
    title: str
    snippet: str
    url: str
    normalized_url: str
    url_hash: str
    source: str
    search_score: float
    rank: int


@dataclass(frozen=True)
class TaskExecutionInput:
    """后台执行需要的任务快照，不携带请求Session或ORM对象。"""

    query: str
    time_range: str
    max_results: int


def normalize_url(url: str) -> str:
    """保守标准化URL，只移除明确无业务意义的跟踪信息。"""
    if not isinstance(url, str) or not url.strip():
        raise UrlNormalizationError("URL不能为空")

    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError as exc:
        raise UrlNormalizationError("URL格式无效") from exc

    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"} or not parts.hostname:
        raise UrlNormalizationError("只支持HTTP或HTTPS URL")
    if parts.username is not None or parts.password is not None:
        raise UrlNormalizationError("URL不能包含用户认证信息")

    host = parts.hostname.rstrip(".").encode("idna").decode("ascii").lower()
    host_display = f"[{host}]" if ":" in host else host
    if port is not None and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host_display}:{port}"
    else:
        netloc = host_display

    path = parts.path or "/"
    # 根路径保持一个斜杠；非根路径仅去末尾斜杠，不合并中间的双斜杠。
    trimmed_path = path.rstrip("/")
    if path != "/" and trimmed_path:
        path = trimmed_path

    query_parts = []
    for position, raw_part in enumerate(parts.query.split("&")):
        if not raw_part:
            continue
        raw_name = raw_part.partition("=")[0]
        try:
            name_key = unquote_plus(raw_name).casefold()
        except (UnicodeDecodeError, ValueError):
            name_key = raw_name.casefold()
        if name_key.startswith("utm_") or name_key in TRACKING_QUERY_NAMES:
            continue
        query_parts.append((name_key, position, raw_part))

    # Python排序是稳定的：同名参数仍保持原来的先后顺序。
    query_parts.sort(key=lambda item: item[0])
    normalized_query = "&".join(item[2] for item in query_parts)
    return urlunsplit((scheme, netloc, path, normalized_query, ""))


def hash_normalized_url(normalized_url: str) -> str:
    """对UTF-8标准化URL计算固定64位十六进制SHA-256。"""
    return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()


class SmartCollectTaskService:
    """编排一次可持久化采编任务；第三方搜索细节仍由SearchService负责。"""

    def __init__(self, search_service: SearchService, embedding_service: EmbeddingScorer):
        self.search_service = search_service
        self.embedding_service = embedding_service

    @staticmethod
    def create_running_task(
        db: Session,
        creator: User,
        body: SmartCollectSearchRequest,
    ) -> dict:
        """只创建并提交running任务，绝不等待搜索、Embedding或结果保存。"""
        task = SmartCollectTask(
            creator_id=creator.id,
            query=body.query,
            time_range=body.time_range,
            max_results=body.max_results,
            status="running",
            result_count=0,
            credits_used=0,
        )
        try:
            db.add(task)
            db.flush()
            created = {
                "task_id": task.id,
                "status": task.status,
                "created_at": task.created_at,
            }
            db.commit()
            return created
        except SQLAlchemyError as exc:
            db.rollback()
            raise SmartCollectPersistenceError from exc

    @staticmethod
    def _load_execution_input(db: Session, task_id: int) -> TaskExecutionInput:
        """后台按ID加载稳定输入，返回前结束只读事务并归还连接。"""
        try:
            task = db.get(SmartCollectTask, task_id)
            if not task or task.status != "running":
                raise SmartCollectPersistenceError("任务状态不允许执行")
            return TaskExecutionInput(
                query=task.query,
                time_range=task.time_range,
                max_results=task.max_results,
            )
        finally:
            db.rollback()

    async def process_task(self, db: Session, task_id: int) -> None:
        """在独立Session中执行Task ID对应的完整采编流程。"""
        execution = self._load_execution_input(db, task_id)
        try:
            response = await self.search_service.search(
                execution.query,
                execution.time_range,
                execution.max_results,
            )
        except SearchServiceError as exc:
            self._mark_failed(db, task_id, exc.message)
            raise

        try:
            await self._score_and_persist_with_retry(
                db,
                task_id,
                execution.query,
                response,
            )
        except EmbeddingServiceError as exc:
            self._mark_failed(db, task_id, exc.message)
            raise
        except SmartCollectPersistenceError:
            self._mark_failed(db, task_id, SmartCollectPersistenceError.message)
            raise

    async def execute(
        self,
        db: Session,
        creator: User,
        body: SmartCollectSearchRequest,
    ) -> SmartCollectTask:
        """兼容服务层调用：创建running任务后在当前Session中执行至终态。"""
        created = self.create_running_task(db, creator, body)
        await self.process_task(db, created["task_id"])
        task = self.get_task(db, created["task_id"])
        if task is None:
            raise SmartCollectPersistenceError
        return task

    async def _score_and_persist_with_retry(
        self,
        db: Session,
        task_id: int,
        topic: str,
        response: SmartCollectSearchResponse,
    ) -> None:
        """读取稳定文本后在事务外评分；唯一约束竞争时整批重读并重算一次。"""
        for attempt in range(2):
            try:
                candidates = self._prepare_clues_for_embedding(db, task_id, response)
                clue_texts = [self._build_clue_text(row.title, row.snippet) for row in candidates]
                scores = (
                    await run_in_threadpool(self.embedding_service.score_batch, topic, clue_texts)
                    if clue_texts
                    else []
                )
                semantic_scores = self._validate_semantic_scores(scores, len(candidates))
                self._persist_results_once(db, task_id, response, candidates, semantic_scores)
                return
            except (IntegrityError, PreparedClueChanged) as exc:
                db.rollback()
                if attempt == 1:
                    raise SmartCollectPersistenceError from exc
            except EmbeddingServiceError:
                db.rollback()
                raise
            except SQLAlchemyError as exc:
                db.rollback()
                raise SmartCollectPersistenceError from exc

    @staticmethod
    def _deduplicate_batch(response: SmartCollectSearchResponse) -> list[dict]:
        """按标准化URL做批内精确去重，保留最先出现的排名和分数。"""
        unique_rows: list[dict] = []
        seen_by_hash: dict[str, str] = {}
        for rank, item in enumerate(response.items, start=1):
            try:
                normalized_url = normalize_url(item.url)
            except UrlNormalizationError:
                continue
            url_hash = hash_normalized_url(normalized_url)
            seen_url = seen_by_hash.get(url_hash)
            if seen_url is not None:
                if seen_url != normalized_url:
                    raise SmartCollectPersistenceError("检测到URL哈希冲突")
                continue
            seen_by_hash[url_hash] = normalized_url
            unique_rows.append(
                {
                    "item": item,
                    "rank": rank,
                    "normalized_url": normalized_url,
                    "url_hash": url_hash,
                }
            )
        return unique_rows

    def _prepare_clues_for_embedding(
        self,
        db: Session,
        task_id: int,
        response: SmartCollectSearchResponse,
    ) -> list[PreparedClue]:
        """只读解析现有线索并复制文本快照，返回前结束当前数据库事务。"""
        try:
            task = db.get(SmartCollectTask, task_id)
            if not task or task.status != "running":
                raise SmartCollectPersistenceError("任务状态不允许保存结果")

            unique_rows = self._deduplicate_batch(response)
            hashes = [row["url_hash"] for row in unique_rows]
            existing_clues = (
                db.query(NewsClue).filter(NewsClue.url_hash.in_(hashes)).all()
                if hashes
                else []
            )
            clues_by_hash = {clue.url_hash: clue for clue in existing_clues}
            candidates: list[PreparedClue] = []

            for row in unique_rows:
                item = row["item"]
                clue = clues_by_hash.get(row["url_hash"])
                if clue is not None:
                    if clue.normalized_url != row["normalized_url"]:
                        raise SmartCollectPersistenceError("检测到URL哈希冲突")
                    existing_clue_id = clue.id
                    title = clue.title
                    snippet = clue.snippet
                else:
                    existing_clue_id = None
                    title = item.title
                    snippet = item.snippet

                candidates.append(
                    PreparedClue(
                        existing_clue_id=existing_clue_id,
                        title=title,
                        snippet=snippet,
                        url=item.url,
                        normalized_url=row["normalized_url"],
                        url_hash=row["url_hash"],
                        source=item.source,
                        search_score=item.search_score,
                        rank=row["rank"],
                    )
                )
            return candidates
        finally:
            # SQLAlchemy查询会自动开启事务；模型推理前必须归还连接并结束事务。
            db.rollback()

    @staticmethod
    def _build_clue_text(title: str, snippet: str) -> str:
        """标题始终在前，空snippet时不追加空行或占位文字。"""
        clean_title = title.strip()
        clean_snippet = snippet.strip()
        return f"{clean_title}\n{clean_snippet}" if clean_snippet else clean_title

    @staticmethod
    def _validate_semantic_scores(scores, expected_count: int) -> list[float]:
        """验证Fake或真实服务的输出，防止数量错位或非法值入库。"""
        try:
            values = [float(score) for score in scores]
        except (TypeError, ValueError):
            raise EmbeddingServiceError from None
        if len(values) != expected_count:
            raise EmbeddingServiceError
        if any(not math.isfinite(score) or score < -1 or score > 1 for score in values):
            raise EmbeddingServiceError
        return values

    def _persist_results_once(
        self,
        db: Session,
        task_id: int,
        response: SmartCollectSearchResponse,
        candidates: list[PreparedClue],
        semantic_scores: list[float],
    ) -> None:
        """短事务原子写入缺失线索、关联、双分数和任务完成状态。"""
        task = (
            db.query(SmartCollectTask)
            .filter(SmartCollectTask.id == task_id)
            .with_for_update()
            .first()
        )
        if not task or task.status != "running":
            raise SmartCollectPersistenceError("任务状态不允许保存结果")

        hashes = [row.url_hash for row in candidates]
        existing_clues = (
            db.query(NewsClue).filter(NewsClue.url_hash.in_(hashes)).all()
            if hashes
            else []
        )
        clues_by_hash = {clue.url_hash: clue for clue in existing_clues}
        now = datetime.now()
        resolved_clues: list[NewsClue] = []

        for row in candidates:
            clue = clues_by_hash.get(row.url_hash)
            if clue is not None:
                # SHA-256碰撞概率极低，但仍核对原文，绝不错误合并两条URL。
                if clue.normalized_url != row.normalized_url:
                    raise SmartCollectPersistenceError("检测到URL哈希冲突")
                # Embedding期间若另一任务先写入了不同文本，必须整批重读并重算。
                if clue.title != row.title or clue.snippet != row.snippet:
                    raise PreparedClueChanged
                # 保守策略：旧线索正文信息全部不覆盖，只记录本次再次发现时间。
                clue.updated_at = now
                resolved_clues.append(clue)
                continue

            # 快照中的旧线索若被并发删除，不能拿旧文本创建新线索，需重新解析。
            if row.existing_clue_id is not None:
                raise PreparedClueChanged
            clue = NewsClue(
                title=row.title,
                url=row.url,
                normalized_url=row.normalized_url,
                url_hash=row.url_hash,
                source=row.source,
                snippet=row.snippet,
                first_seen_at=now,
                updated_at=now,
            )
            db.add(clue)
            clues_by_hash[row.url_hash] = clue
            resolved_clues.append(clue)

        # 新线索需要先拿到数据库ID，之后才能填写关联表的clue_id。
        db.flush()
        for row, clue, semantic_score in zip(candidates, resolved_clues, semantic_scores):
            db.add(
                SmartCollectTaskClue(
                    task_id=task_id,
                    clue_id=clue.id,
                    search_score=row.search_score,
                    semantic_score=semantic_score,
                    rank=row.rank,
                    created_at=now,
                )
            )

        task.status = "completed"
        task.result_count = len(candidates)
        task.credits_used = response.credits_used
        task.error_message = None
        task.finished_at = now
        db.commit()

    @staticmethod
    def _mark_failed(db: Session, task_id: int, message: str) -> None:
        """失败状态单独提交，保证搜索或保存失败后历史任务仍可查看。"""
        db.rollback()
        try:
            task = db.get(SmartCollectTask, task_id)
            if task and task.status == "running":
                task.status = "failed"
                task.result_count = 0
                task.error_message = str(message)[:500]
                task.finished_at = datetime.now()
                db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            raise SmartCollectPersistenceError from exc

    @staticmethod
    def get_task(db: Session, task_id: int) -> SmartCollectTask | None:
        """加载任务、创建人及线索详情，支持页面刷新后重新查看。"""
        return (
            db.query(SmartCollectTask)
            .options(
                joinedload(SmartCollectTask.creator),
                selectinload(SmartCollectTask.clue_links).joinedload(SmartCollectTaskClue.clue),
            )
            .filter(SmartCollectTask.id == task_id)
            .first()
        )

    @staticmethod
    def update_relevance_label(
        db: Session,
        task_id: int,
        clue_id: int,
        user: User,
        relevance_label: int | None,
    ) -> SmartCollectTaskClue:
        """只更新任务关联上的人工判断，不触发搜索、Embedding或线索改写。"""
        if user.role not in {"editor", "admin"}:
            raise SmartCollectRelevanceForbiddenError
        if relevance_label not in {None, 0, 1, 2}:
            raise ValueError("relevance_label只允许0、1、2或NULL")

        try:
            task = db.get(SmartCollectTask, task_id)
            if not task or (user.role != "admin" and task.creator_id != user.id):
                raise SmartCollectTaskNotFoundError

            link = db.get(
                SmartCollectTaskClue,
                {"task_id": task_id, "clue_id": clue_id},
            )
            if link is None:
                raise SmartCollectTaskClueNotFoundError

            link.relevance_label = relevance_label
            db.commit()
            db.refresh(link)
            return link
        except (
            SmartCollectTaskNotFoundError,
            SmartCollectTaskClueNotFoundError,
            SmartCollectRelevanceForbiddenError,
        ):
            db.rollback()
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise SmartCollectPersistenceError from exc
