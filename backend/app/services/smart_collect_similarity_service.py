# -*- coding: utf-8 -*-
"""同一采编任务内新闻线索之间的只读语义相似度分析。

该服务不修改任何数据，只用于给编辑提供“哪两条新闻内容最像”的判断参考。
算法流程：
1. 从 smart_collect_task_clues + news_clues 读取当前任务全部线索（标题+摘要）；
2. 用 multilingual-e5-small 一次批量生成归一化 passage 向量；
3. 任意两条线索计算点积（即余弦相似度），得到 n*(n-1)/2 个不重复 pair；
4. 按相似度降序返回前 limit 条。
"""
from dataclasses import dataclass
import math

from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..models.smart_collect import NewsClue, SmartCollectTask, SmartCollectTaskClue
from ..models.user import User
from .embedding_service import EmbeddingServiceError, PassageEmbedder
from .smart_collect_service import SmartCollectTaskNotFoundError


@dataclass(frozen=True)
class SimilarityClueSnapshot:
    """模型线程使用的普通Python快照，不携带Session或ORM对象。

    因为 Embedding 推理可能耗时，需要在读取完数据后立即结束数据库事务；
    后续只传递本快照，避免多线程共用 Session 导致关联对象失效。
    """

    clue_id: int
    rank: int
    title: str
    source: str
    text: str

    def to_public_dict(self) -> dict:
        return {
            "clue_id": self.clue_id,
            "rank": self.rank,
            "title": self.title,
            "source": self.source,
        }


class SmartCollectSimilarityService:
    """读取任务线索、批量Embedding并计算不重复的i<j相似pair。

    特性：
    - 只读操作，不写 semantic_score、不改线索、不建事件；
    - 权限与任务详情一致：管理员可看全部，编辑只能看自己创建的任务；
    - 每次请求都会重新计算，不依赖缓存，保证最新线索参与分析。
    """

    def __init__(self, embedding_service: PassageEmbedder):
        self.embedding_service = embedding_service

    @staticmethod
    def _build_clue_text(title: str, snippet: str) -> str:
        """拼接线索的语义被编码文本：标题+摘要，没有摘要时只用标题。

        与采编任务评分时的文本规则保持一致，
        避免同一条新闻因文本拼装不同得到不稳定的向量。
        """
        clean_title = title.strip()
        clean_snippet = snippet.strip()
        return f"{clean_title}\n{clean_snippet}" if clean_snippet else clean_title

    @classmethod
    def _load_snapshot(
        cls,
        db: Session,
        task_id: int,
        user: User,
    ) -> tuple[str, list[SimilarityClueSnapshot]]:
        """加载任务及其全部线索，并转成无Session快照。

        权限规则：admin 可读任何任务；editor 只能读自己创建的任务。
        读取完成后立即 db.rollback()，释放连接和事务，
        确保后续模型推理在数据库事务外执行。
        """
        try:
            task = db.get(SmartCollectTask, task_id)
            if not task or (user.role != "admin" and task.creator_id != user.id):
                raise SmartCollectTaskNotFoundError

            rows = (
                db.query(
                    SmartCollectTaskClue.clue_id.label("clue_id"),
                    SmartCollectTaskClue.rank.label("rank"),
                    NewsClue.title.label("title"),
                    NewsClue.source.label("source"),
                    NewsClue.snippet.label("snippet"),
                )
                .join(NewsClue, NewsClue.id == SmartCollectTaskClue.clue_id)
                .filter(SmartCollectTaskClue.task_id == task_id)
                .order_by(SmartCollectTaskClue.rank, SmartCollectTaskClue.clue_id)
                .all()
            )
            snapshots = [
                SimilarityClueSnapshot(
                    clue_id=row.clue_id,
                    rank=row.rank,
                    title=row.title,
                    source=row.source,
                    text=cls._build_clue_text(row.title, row.snippet),
                )
                for row in rows
            ]
            return task.query, snapshots
        finally:
            # SQLAlchemy读取会自动开启事务；模型推理前必须结束并归还连接。
            db.rollback()

    @staticmethod
    def _validate_embeddings(embeddings, expected_count: int) -> list[list[float]]:
        """校验批量结果：数量、维度、有限数值都必须合法。

        如果模型返回数量不对或包含 NaN/Inf，
        直接引发 EmbeddingServiceError，避免用坏数据计算出假相似度。
        """
        if len(embeddings) != expected_count:
            raise EmbeddingServiceError
        vectors: list[list[float]] = []
        dimension: int | None = None
        for embedding in embeddings:
            try:
                values = [float(value) for value in embedding]
            except (TypeError, ValueError):
                raise EmbeddingServiceError from None
            if not values or any(not math.isfinite(value) for value in values):
                raise EmbeddingServiceError
            if dimension is None:
                dimension = len(values)
            elif len(values) != dimension:
                raise EmbeddingServiceError
            vectors.append(values)
        return vectors

    @staticmethod
    def _dot_product(left: list[float], right: list[float]) -> float:
        """计算两个归一化向量的点积（即余弦相似度）。

        EmbeddingService 已在 encode 时 normalize_embeddings=True，
        所以这里直接点积就等价于余弦相似度，
        并把浮点计算产生的小越界成本裁断到 [-1,1]。
        """
        score = sum(a * b for a, b in zip(left, right))
        if not math.isfinite(score):
            raise EmbeddingServiceError
        # 归一化向量理论上处于[-1, 1]，仅截断浮点计算产生的极小越界。
        return max(-1.0, min(1.0, score))

    async def analyze(
        self,
        db: Session,
        task_id: int,
        user: User,
        limit: int = 10,
    ) -> dict:
        """执行一次完整的任务内线索相似度分析。

        1. 读取线索快照（权限无法通过时返回 404，不泄露任务是否存在）；
        2. 线索不足 2 条时直接返回空数组，不调用模型；
        3. 一次批量生成全部 passage 向量，避免逐条调用模型；
        4. 穷举组合计算点积，按相似度降序，同分时用 rank/clue_id 稳定排序；
        5. 只返回前 limit 条，不保存任何结果。
        """
        if not 1 <= limit <= 50:
            raise ValueError("limit必须在1到50之间")

        query, clues = self._load_snapshot(db, task_id, user)
        clue_count = len(clues)
        pair_count = clue_count * (clue_count - 1) // 2
        if clue_count < 2:
            return {
                "task_id": task_id,
                "query": query,
                "clue_count": clue_count,
                "pair_count": pair_count,
                "items": [],
            }

        # 只向线程传递普通字符串；一次调用批量生成当前任务全部新闻向量。
        embeddings = await run_in_threadpool(
            self.embedding_service.embed_passages,
            [clue.text for clue in clues],
        )
        vectors = self._validate_embeddings(embeddings, clue_count)

        pairs = []
        for left_index, left in enumerate(clues):
            for right_index in range(left_index + 1, clue_count):
                right = clues[right_index]
                pairs.append(
                    {
                        "left": left.to_public_dict(),
                        "right": right.to_public_dict(),
                        "similarity_score": self._dot_product(
                            vectors[left_index],
                            vectors[right_index],
                        ),
                    }
                )

        pairs.sort(
            key=lambda pair: (
                -pair["similarity_score"],
                pair["left"]["rank"],
                pair["right"]["rank"],
                pair["left"]["clue_id"],
                pair["right"]["clue_id"],
            )
        )
        return {
            "task_id": task_id,
            "query": query,
            "clue_count": clue_count,
            "pair_count": pair_count,
            "items": pairs[:limit],
        }
