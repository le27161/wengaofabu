# -*- coding: utf-8 -*-
"""用户个性化推荐文章算法（四段式：向量召回 KNN + 精排预留 + 热门兜底）

整体链路（详见 docs/article_recommend_spec.md）：
    ① 离线冷数据：全部文稿已由 embedding_service 向量化写入 article_embeddings 表。
        本模块首次调用时惰性全量载入进程内存，之后按 source_hash 增量同步——
        新写/编辑的文稿向量化后无需重启进程即可被召回。
    ② 在线召回：登录且观看历史 >= 20 篇时，取最近 20 篇观看文稿，
        优先从进程内存缓存读取它们的已入库向量（避免重复调用模型），
        仅缓存缺失时才现场向量化并回填；按观看时长加权平均得到用户向量
        （L2 归一化），再与内存中全部已发布文稿向量做点积
        （双方归一化后点积即余弦相似度），KNN 取 top-50。
    ③ 在线精排：_rerank() 目前原样透传 top-50，后续在此接入排序模型
        （特征工程 → 模型打分 → 重排）。
    ④ 探索位：从与用户向量差距最大的候选池中选 1 篇放在列表末尾，
        避免"信息茧房"（8 篇 = 7 篇相似 + 1 篇探索）；
    ⑤ 兜底：过滤已观看与不感兴趣后，候选不足时按热度榜补齐，
        最终返回 limit 篇（默认 8）。

用户画像不足时的通用推荐（未登录 / 观看历史 < 20 篇）：
    base = 0.30*栏目偏好分 + 0.40*新鲜度 + 0.30*热度
    score = base * (0.75 + 0.5 * rand)
    贪心选取时，同栏目已选 k 篇会使该栏目剩余候选得分乘 0.8 ** k（分类多样性）。

设计要点：
    - 每次请求对相似度/热度做随机扰动，保证不同用户、不同请求结果尽量不同；
    - 用户向量优先读内存缓存，缓存缺失的文稿才调模型向量化，并回填表与缓存；
    - 向量模型模块级单例常驻内存，首次调用加载较慢，之后秒级推理；
    - 向量化/模型加载异常自动回退通用推荐，不阻断接口；
    - 除 _compute_user_vector（可能回填缺失向量，幂等 upsert）外，
      其余辅助函数只读数据库、无副作用，可在任意请求会话中安全复用。
"""
import math
import random
import threading
from collections import defaultdict
from datetime import datetime

import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from ..models.article import Article, article_categories
from ..models.article_embedding import ArticleEmbedding
from ..models.interaction import UserAction
from ..models.user import User
from ..models.view_history import ViewHistory
from .embedding_service import MODEL_VERSION, build_article_text, hash_source_text, upsert_embedding


# ---------- 常量 ----------

# 向量召回所需的最小观看历史条数（不足则走通用推荐）。
# 调小：更快进入个性化；调大：画像更稳定，但新用户更久享受不到向量召回。
MIN_HISTORY_FOR_VECTOR = 20
# 在线召回 KNN 取稿数量（精排前的粗排池）。
# 精排接入后建议保持 50 左右：太小召回不足，太大精排成本上升。
RECALL_TOP_K = 50
# 探索候选池大小：与用户向量相似度最低的 N 篇，用于"反信息茧房"探索位
EXPLORE_POOL_SIZE = 10
# 推荐结果最大条数（接口层 Query(le=20) 已约束，这里对内部调用兜底）。
MAX_LIMIT = 20

# 通用推荐：新鲜度指数衰减天数。fresh = exp(-age_days / 30)，
# 发布 30 天内的文章衰减明显（7 天约 0.79，30 天约 0.37），越新分数越高。
FRESH_DECAY_DAYS = 30
# 通用推荐：热度评分中各类互动的加权系数（不同行为价值不同）：
# 浏览 1、点赞 3、收藏 5、转发 2——收藏最难、价值最高，浏览最易、权重最低。
HOT_WEIGHTS = {
    "view_count": 1,
    "like_count": 3,
    "favorite_count": 5,
    "share_count": 2,
}
# 通用推荐基础分权重：新+热合计 0.7，略高于个性化 0.3，
# 保证"最新最热权重稍高"的业务诉求；三者之和恒为 1。
W_PREF, W_FRESH, W_HOT = 0.30, 0.40, 0.30
# 通用推荐随机扰动：score = base * (0.75 + 0.5 * rand)，rand ∈ [0,1)，
# 即最终得分在 base 的 75%~125% 之间浮动，保证每次结果不同又不至于全随机。
NOISE_MIN, NOISE_SPAN = 0.75, 0.50
# 通用推荐分类多样性惩罚底数：同栏目已选 k 篇后，该栏目候选得分乘 0.8 ** k，
# 贪心选取时避免 8 篇推荐全来自同一栏目。
DIVERSITY_DECAY = 0.8
# 向量召回相似度随机扰动：sim * (0.9 + 0.2 * rand)，
# 扰动范围 ±10%，仅轻微改变召回集边缘与排序，不影响整体相似性语义。
KNN_NOISE_MIN, KNN_NOISE_SPAN = 0.90, 0.20
# 用户向量观看时长加权系数：权重 = 1 + watch_seconds / 600。
# 看满 10 分钟权重翻倍、30 分钟（系统上限）约 4 倍——看得越久，该篇对用户画像
# 的贡献越大；后续可替换为时间衰减或注意力池化。
WATCH_SECONDS_NORM = 600.0


# ---------- 向量内存缓存（冷数据 + 增量同步） ----------

# 进程内存向量缓存：article_id -> {"hash": source_hash, "vector": np.ndarray}
# - 内存占用：512 维 float32 ≈ 2KB/篇，1 万篇约 20MB，量级可控；
# - 生命周期：进程存活期间常驻，后端重启后首次向量推荐自动重建；
# - 缓存的是全部文稿向量（含未发布），KNN 召回时再按 published 过滤，
#   便于后续扩展"相关推荐"等复用同一份内存矩阵。
_EMBEDDING_CACHE: dict[int, dict] = {}
# 缓存读写锁：FastAPI 多线程并发时保护缓存的原子性（DB 查询是请求级 Session，
# 可在锁内安全执行；加锁仅防止重复全量加载/并发写脏）。
_EMBEDDING_CACHE_LOCK = threading.Lock()


def _sync_embedding_cache(db: Session) -> None:
    """将 article_embeddings 同步到进程内存（线程安全）。

    首次调用：全量加载所有文稿向量到内存（冷加载）。
    后续调用：只比对 (article_id, source_hash) 轻量元数据（不读向量列），
    仅加载新增或源文本（标题+分类）变化的行，并清理已删除文稿的缓存——
    因此新写/编辑的文稿只要完成向量化入库，下一次推荐自动进入内存，无需重启。

    调用方注意：本函数在锁内执行 DB 查询，属于轻量同步（每次只查 id/hash 两列，
    仅变化行读向量列），可在每个向量推荐请求中安全调用。
    """
    with _EMBEDDING_CACHE_LOCK:
        meta = db.query(ArticleEmbedding.article_id, ArticleEmbedding.source_hash).all()
        meta_map = {aid: h for aid, h in meta}

        if not _EMBEDDING_CACHE:
            # 冷加载：全量读向量列（512 维 float32 约 2KB/篇，量级可控）
            rows = db.query(ArticleEmbedding).all()
            for row in rows:
                _EMBEDDING_CACHE[row.article_id] = {
                    "hash": row.source_hash,
                    "vector": np.frombuffer(row.embedding, dtype="<f4").copy(),
                }
            return

        # 增量：只加载新增或源文本（标题+分类）变化的文稿向量
        changed_ids = [
            aid
            for aid, h in meta_map.items()
            if aid not in _EMBEDDING_CACHE or _EMBEDDING_CACHE[aid]["hash"] != h
        ]
        if changed_ids:
            rows = (
                db.query(ArticleEmbedding)
                .filter(ArticleEmbedding.article_id.in_(changed_ids))
                .all()
            )
            for row in rows:
                _EMBEDDING_CACHE[row.article_id] = {
                    "hash": row.source_hash,
                    "vector": np.frombuffer(row.embedding, dtype="<f4").copy(),
                }
        # 清理已删除文稿的缓存，避免内存无限膨胀
        stale = set(_EMBEDDING_CACHE) - set(meta_map)
        for aid in stale:
            _EMBEDDING_CACHE.pop(aid, None)


# ---------- 用户向量 ----------

def _history_count(db: Session, user_id: int) -> int:
    """用户观看历史总条数。

    用于判断是否满足向量召回门槛（>= MIN_HISTORY_FOR_VECTOR）。
    注意：view_history 只在访问文稿详情页时写入，POST /events 埋点不写历史。
    """
    return db.query(func.count(ViewHistory.id)).filter(ViewHistory.user_id == user_id).scalar() or 0


def _user_excluded_ids(db: Session, user: User) -> set[int]:
    """用户已观看与不感兴趣的文稿 id 集合（推荐时排除）。

    - 已观看：view_history 表（详情页访问即记录，重复观看仅更新时间）；
    - 不感兴趣：user_actions 表中 action_type = "dislike" 的记录。
    向量召回与通用推荐共用此函数，保证两条路径的排除语义一致。
    """
    watched = {
        row[0]
        for row in db.query(ViewHistory.article_id).filter(ViewHistory.user_id == user.id).all()
    }
    disliked = {
        row[0]
        for row in db.query(UserAction.article_id).filter(
            UserAction.user_id == user.id, UserAction.action_type == "dislike"
        ).all()
    }
    return watched | disliked


def _compute_user_vector(db: Session, user: User) -> np.ndarray | None:
    """计算用户兴趣向量（最近 20 条观看记录 → 读缓存/补算向量 → 加权平均 → L2 归一化）

    算法步骤：
    1. 按 viewed_at 倒序取最近 MIN_HISTORY_FOR_VECTOR（20）条观看历史；
    2. 优先从进程内存缓存（_EMBEDDING_CACHE）直接读取这 20 篇文稿的已入库向量——
       正常情况下全部命中，全程不调用向量模型，几乎零额外开销；
    3. 缓存缺失的文稿（如当时向量化失败/未入库）才现场用同一个向量模型
       （aiVectorizationModel.predict_fun，BAAI_bge-small-zh，512 维，输出已
       L2 归一化）与同一文本规则（build_article_text："分类1,分类2：标题"）
       向量化，并回填 article_embeddings 表与内存缓存（幂等 upsert），
       下次请求直接命中缓存，避免重复计算；
    4. 按观看时长加权平均（权重 = 1 + watch_seconds/600，看得越久越重要），
       再做一次 L2 归一化，保证与文稿向量同处单位超球面，点积即余弦相似度。

    返回：
    - np.ndarray(512,)：用户兴趣向量；
    - None：观看历史不足 20 条，或 20 篇文稿均无法获得向量（调用方回退通用推荐）。

    扩展点：
    - 若想用注意力池化替代加权平均，可将 weights 替换为 attention 分数
      （如观看时长/时间衰减经过 softmax），其余流程不变。
    - 模型加载失败/向量化异常由调用方（_recommend_by_vector）兜底回退通用推荐。
    - 注意：本函数可能写库（回填缺失向量），是服务内唯一有写操作、会 commit
      的函数；回填数据为幂等派生数据，不影响业务表。
    """
    history = (
        db.query(ViewHistory)
        .filter(ViewHistory.user_id == user.id)
        .order_by(ViewHistory.viewed_at.desc())
        .limit(MIN_HISTORY_FOR_VECTOR)
        .all()
    )
    if len(history) < MIN_HISTORY_FOR_VECTOR:
        return None

    ids = [h.article_id for h in history]
    articles = (
        db.query(Article)
        .options(selectinload(Article.categories))
        .filter(Article.id.in_(ids))
        .all()
    )

    # 生成每篇的向量化文本（与入库文本规则一致），供缓存缺失时补算使用
    texts_by_id = {a.id: build_article_text(a) for a in articles}

    vectors: list[np.ndarray] = []
    weights: list[float] = []
    missing: list[tuple[int, float]] = []  # 缓存缺失的 (article_id, 观看权重)
    for h in history:
        # 观看时长加权：看得越久权重越高（正常 1~4 倍）
        weight = 1.0 + (h.watch_seconds or 0) / WATCH_SECONDS_NORM
        cache_item = _EMBEDDING_CACHE.get(h.article_id)
        if cache_item is not None:
            # 命中内存缓存：直接复用已入库向量，不重复调用模型
            vectors.append(cache_item["vector"])
            weights.append(weight)
        else:
            missing.append((h.article_id, weight))

    # 缓存缺失的文稿：现场向量化并回填表与缓存（正常情况下历史文稿均已向量化，
    # 该分支只在向量化曾失败的文稿上触发；by_id 缺文章时该篇直接跳过）
    pending = [(aid, w) for aid, w in missing if aid in texts_by_id]
    if pending:
        from ..aiVectorizationModel.predict import predict_fun  # 惰性导入：首次调用才加载模型
        new_vectors = predict_fun([texts_by_id[aid] for aid, _ in pending])
        with _EMBEDDING_CACHE_LOCK:
            for (aid, _w), vector in zip(pending, new_vectors):
                source_hash = hash_source_text(texts_by_id[aid])
                _EMBEDDING_CACHE[aid] = {
                    "hash": source_hash,
                    "vector": np.asarray(vector, dtype="<f4").copy(),
                }
        # 回填 article_embeddings 表（幂等 upsert），避免下次 sync 清理缓存后重复补算
        for (aid, _w), vector in zip(pending, new_vectors):
            upsert_embedding(
                db,
                aid,
                vector,
                MODEL_VERSION,
                hash_source_text(texts_by_id[aid]),
            )
        db.commit()
        for aid, weight in pending:
            vectors.append(_EMBEDDING_CACHE[aid]["vector"])
            weights.append(weight)

    if not vectors:
        return None

    # 加权平均后重新 L2 归一化（缓存向量已归一化，平均后需再归一化保持余弦语义）
    user_vec = np.average(vectors, axis=0, weights=weights)
    norm = np.linalg.norm(user_vec)
    return user_vec / norm if norm > 0 else None


# ---------- 向量召回 / 精排 / 兜底 ----------

def _knn_recall(
    db: Session,
    user_vec: np.ndarray,
    k: int,
    explore_k: int = EXPLORE_POOL_SIZE,
) -> tuple[list[int], list[int]]:
    """KNN 余弦相似度召回：取相似度 top-k 与"最不相似"探索候选池。

    输入：
    - user_vec：用户兴趣向量（已 L2 归一化，来自 _compute_user_vector）；
    - k：召回数量（调用方传 RECALL_TOP_K=50）；
    - explore_k：探索候选池大小（默认 EXPLORE_POOL_SIZE=10）。

    输出：
    - top_ids：按相似度降序的文稿 id 列表（含随机扰动），最多 k 个；
    - explore_ids：与用户向量相似度最低的 explore_k 个文稿 id
      （使用原始相似度、不加扰动，保证是真正的"差距最大"），供反信息茧房探索位使用。

    实现说明：
    1. 向量缓存已由 _recommend_by_vector 主流程同步（冷加载或增量更新），
       本函数直接复用 _EMBEDDING_CACHE，不再重复同步；
    2. 只对 status = "published" 的文稿计算相似度（缓存含全部文稿，这里过滤）；
    3. 内存矩阵点积：双方均 L2 归一化，点积即余弦相似度，向量化一次算完；
    4. 相似度乘 0.9~1.1 随机扰动，使每次召回集边缘与顺序略有不同；
    5. np.argsort 分别取 top-k 与最不相似 explore_k，映射回文稿 id。

    边界：若没有任何已发布文稿向量（如尚未跑全量向量化），返回两个空列表，
    由 _recommend_by_vector 的热门兜底补齐。
    """
    published_ids = [
        row[0]
        for row in db.query(Article.id).filter(Article.status == "published").all()
    ]
    ids = [aid for aid in published_ids if aid in _EMBEDDING_CACHE]
    if not ids:
        return [], []
    matrix = np.stack([_EMBEDDING_CACHE[aid]["vector"] for aid in ids])  # (N, 512)
    sims = matrix @ user_vec
    # 探索候选：相似度最低的 explore_k 篇（原始相似度，不扰动）
    explore_order = np.argsort(sims)[:explore_k]
    explore_ids = [ids[i] for i in explore_order]
    # 随机扰动：让每次召回结果/顺序略有不同
    noise = KNN_NOISE_MIN + KNN_NOISE_SPAN * np.random.random(len(ids))
    sims = sims * noise
    top = np.argsort(-sims)[:k]
    return [ids[i] for i in top], explore_ids


def _rerank(candidate_ids: list[int]) -> list[int]:
    """在线精排（预留实现）：目前原样透传 top-50，后续在此接入排序模型。

    后续开发接入点：
    1. 特征工程：对 candidate_ids 中的每篇文稿生成特征，例如
       - 用户特征：观看时长均值、栏目偏好占比、活跃度；
       - 文稿特征：相似度、热度（view/3like/5fav/2share）、新鲜度、
         分类点击率、作者历史表现；
       - 交叉特征：文稿栏目 × 用户栏目偏好。
    2. 模型打分：调用排序模型（LR/GBDT/DNN/LLM 均可）得到每篇的精排分数；
    3. 重排：按精排分数降序返回新的 id 列表（注意保持数量为 RECALL_TOP_K 量级，
       供第四步过滤与兜底）。

    当前实现不改变顺序，保证四段式链路完整可运行。
    """
    return candidate_ids


def _fill_by_hot(db: Session, exclude_ids: set[int], need: int) -> list[int]:
    """热门兜底：按互动热度降序补齐候选（第四步候选不足时调用）。

    输入：
    - exclude_ids：需要排除的文稿 id（已入选候选 + 已观看 + 不感兴趣）；
    - need：还需要补齐的数量（<= 0 直接返回空）。

    输出：热度降序的文稿 id 列表，最多 need 个。

    实现说明：
    - 热度 = view_count + 3*like_count + 5*favorite_count + 2*share_count；
    - 热度同样乘随机扰动，保证兜底结果每次也尽量不同；
    - 只从已发布文稿中补齐，且不会与 exclude_ids 重复。
    """
    if need <= 0:
        return []
    query = db.query(Article).filter(Article.status == "published")
    if exclude_ids:
        query = query.filter(~Article.id.in_(exclude_ids))
    scored = []
    for a in query.all():
        hot = (
            a.view_count * HOT_WEIGHTS["view_count"]
            + a.like_count * HOT_WEIGHTS["like_count"]
            + a.favorite_count * HOT_WEIGHTS["favorite_count"]
            + a.share_count * HOT_WEIGHTS["share_count"]
        )
        # 随机扰动，保证每次补齐结果也尽量不同
        scored.append((a.id, hot * (NOISE_MIN + NOISE_SPAN * random.random())))
    scored.sort(key=lambda item: item[1], reverse=True)
    return [aid for aid, _ in scored[:need]]


def _pick_explore(
    db: Session,
    explore_ids: list[int],
    excluded: set[int],
    chosen: set[int],
) -> int | None:
    """从"与用户向量差距最大"的候选池中选 1 篇探索内容（反信息茧房）。

    输入：
    - explore_ids：_knn_recall 返回的相似度最低候选池；
    - excluded：已观看/不感兴趣的文稿 id；
    - chosen：已入选推荐列表的文稿 id（避免与相似内容重复）。

    输出：选中的文稿 id；池子被排除/占用后为空则返回 None（调用方不加探索位）。

    实现说明：先按热度取质量最高的 top-3（探索位虽然与用户偏好差距大，
    但仍是相对热门的文稿，用户不会觉得内容莫名其妙），再从 top-3 里随机抽 1 篇——
    避免固定选热度最高的一篇导致探索位永不变化。
    """
    pool = [aid for aid in explore_ids if aid not in excluded and aid not in chosen]
    if not pool:
        return None
    candidates = db.query(Article).filter(Article.id.in_(pool)).all()
    scored = []
    for a in candidates:
        hot = (
            a.view_count * HOT_WEIGHTS["view_count"]
            + a.like_count * HOT_WEIGHTS["like_count"]
            + a.favorite_count * HOT_WEIGHTS["favorite_count"]
            + a.share_count * HOT_WEIGHTS["share_count"]
        )
        scored.append((a.id, hot))
    scored.sort(key=lambda item: item[1], reverse=True)
    if not scored:
        return None
    # 热度 top-3 内随机：质量有保障，且每次探索位可能不同
    top_n = min(3, len(scored))
    return random.choice(scored[:top_n])[0]


def _recommend_by_vector(db: Session, user: User, limit: int) -> list[Article]:
    """向量召回推荐主流程：用户向量 → KNN top-50 → 精排（预留）→ 过滤 → 探索位 → 兜底。

    执行顺序对应四段式：
    ① 缓存准备：先 _sync_embedding_cache 校验进程内存是否有全量文稿向量——
       无则从 article_embeddings 冷加载，有则按 source_hash 增量同步；
    ② 用户向量：_compute_user_vector 优先读缓存（缺失才补算回填），
       历史不足 20 条返回 None，回退通用推荐；
    ③ 召回：_knn_recall 取 top-50（含相似度随机扰动）+ 探索候选池（最不相似）；
    ④ 精排：_rerank（当前透传，后续接排序模型）；
    ⑤ 过滤：_user_excluded_ids 删除已观看/不感兴趣；
    ⑥ 探索位：_pick_explore 从差距最大的候选里选 1 篇（反信息茧房），
       放在列表最后，占用 1 个名额（8 篇 = 7 篇相似 + 1 篇探索）；
    ⑦ 兜底：相似内容不足 limit-1 时 _fill_by_hot 热门补齐 → 回查 Article 返回。

    异常兜底：用户向量计算抛异常（模型加载失败等）时打印告警并回退通用推荐，
    保证接口在向量链路故障时仍可用。

    返回：最多 limit 篇已发布 Article 对象（顺序即最终展示顺序）。
    """
    # 进入向量链路先保证内存缓存就绪：无则全量载入，有则增量同步
    _sync_embedding_cache(db)
    try:
        #计算用户近20篇文稿的向量
        user_vec = _compute_user_vector(db, user)
    except Exception as e:
        # 模型加载/向量化异常不阻断推荐，回退通用推荐
        print(f"[recommend] 用户向量计算失败，回退通用推荐：{e}")
        return _recommend_general(db, user, limit)
    if user_vec is None:
        return _recommend_general(db, user, limit)

    #使用knn计算用户相似度和所有文稿的余弦相似度
    top_ids, explore_ids = _knn_recall(db, user_vec, RECALL_TOP_K)
    ranked = _rerank(top_ids)  # 精排（预留，目前透传）

    # 第五步：删除已观看与不感兴趣
    excluded = _user_excluded_ids(db, user)
    filtered = [aid for aid in ranked if aid not in excluded]

    # 第六步：探索位——从与用户向量差距最大的候选里选 1 篇，避免"信息茧房"
    explore = _pick_explore(db, explore_ids, excluded, set(filtered))
    similar_limit = limit - 1 if explore is not None else limit

    # 第七步：相似内容不足时用热门兜底（补齐同样排除已看/不喜欢与探索位）
    if len(filtered) < similar_limit:
        filtered = filtered + _fill_by_hot(
            db,
            set(filtered) | excluded | ({explore} if explore is not None else set()),
            similar_limit - len(filtered),
        )

    ids = filtered[:similar_limit]
    if explore is not None:
        ids = ids + [explore]
    articles = db.query(Article).filter(Article.id.in_(ids)).all()
    by_id = {a.id: a for a in articles}
    return [by_id[aid] for aid in ids if aid in by_id]


# ---------- 通用推荐 ----------

def _build_user_preference(db: Session, user: User | None) -> dict[int, float]:
    """构建用户栏目偏好画像：最近 20 条观看记录中各栏目出现占比（0~1）。

    返回 {category_id: 占比}，例如用户 20 条历史中 8 条属于游戏栏目，
    则 game 的偏好分 = 0.4。仅用于通用推荐（历史不足 20 篇时的轻量画像）；
    向量召回分支不使用此画像（直接用向量相似度）。
    """
    if user is None:
        return {}
    history = (
        db.query(ViewHistory)
        .filter(ViewHistory.user_id == user.id)
        .order_by(ViewHistory.viewed_at.desc())
        .limit(MIN_HISTORY_FOR_VECTOR)
        .all()
    )
    if not history:
        return {}
    ids = [h.article_id for h in history]
    rows = (
        db.query(article_categories.c.article_id, article_categories.c.category_id)
        .filter(article_categories.c.article_id.in_(ids))
        .all()
    )
    counts: dict[int, int] = defaultdict(int)
    for _, category_id in rows:
        counts[category_id] += 1
    total = len(ids) or 1
    return {cid: cnt / total for cid, cnt in counts.items()}


def _collect_category_map(db: Session, article_ids: list[int]) -> dict[int, list[int]]:
    """一次性查询文稿-栏目映射，避免逐篇加载关系造成 N+1 查询。

    返回 {article_id: [category_id, ...]}；未命中任何栏目的文稿不在结果中，
    调用方按空列表处理（偏好分为 0、多样性惩罚为 1）。
    """
    if not article_ids:
        return {}
    rows = (
        db.query(article_categories.c.article_id, article_categories.c.category_id)
        .filter(article_categories.c.article_id.in_(article_ids))
        .all()
    )
    mapping: dict[int, list[int]] = defaultdict(list)
    for article_id, category_id in rows:
        mapping[article_id].append(category_id)
    return mapping


def _recommend_general(db: Session, user: User | None, limit: int) -> list[Article]:
    """通用推荐：新鲜度 + 热度 + 随机扰动 + 分类多样性。

    适用场景：未登录用户，或登录但观看历史不足 20 篇的新用户。

    评分公式（详见模块 docstring）：
        base = 0.30*栏目偏好分 + 0.40*新鲜度 + 0.30*热度
        score = base * (0.75 + 0.5 * rand)
    其中新鲜度按发布天数指数衰减、热度在候选集内 min-max 归一化、
    偏好分取文章所属栏目中用户偏好最高的栏目权重。

    选取策略：按 score 贪心选取，同栏目已选 k 篇后该栏目剩余候选得分乘 0.8 ** k，
    保证 8 篇推荐覆盖多个栏目；登录用户先排除已观看/不感兴趣。

    返回：最多 limit 篇已发布 Article 对象。
    """
    #查询已发布的文稿
    query = db.query(Article).filter(Article.status == "published")
    #排除用户已观看与不感兴趣的文稿
    if user is not None:
        excluded = _user_excluded_ids(db, user)
        if excluded:
            query = query.filter(~Article.id.in_(excluded))
    #剩下的文稿
    candidates = query.all()
    if not candidates:
        return []
    #拿去文稿的id
    article_ids = [a.id for a in candidates]
    #查询文稿和栏目的对应关系
    category_map = _collect_category_map(db, article_ids)
    #根据用户观看记录构建用户画像，如果没登录就是空
    pref = _build_user_preference(db, user)
    #获取当前时间
    now = datetime.now()
    # 热度 min-max 归一化（候选集内）
    #循环每一篇文稿，利用里面的点赞、分享、观看时长、转发信息进行归一化处理
    # 各项指标权重如下：浏览 1、点赞 3、收藏 5、转发 2——收藏最难、价值最高，浏览最易、权重最低。
    hot_raw = [
        a.view_count * HOT_WEIGHTS["view_count"]
        + a.like_count * HOT_WEIGHTS["like_count"]
        + a.favorite_count * HOT_WEIGHTS["favorite_count"]
        + a.share_count * HOT_WEIGHTS["share_count"]
        for a in candidates
    ]
    hot_max = max(hot_raw) if hot_raw else 0
    hot_min = min(hot_raw) if hot_raw else 0
    hot_span = hot_max - hot_min

    #创建每篇文稿的得分空数组，往里面填
    scored: list[tuple[Article, float]] = []
    # 创建一个文稿-分数的zip后面取着用
    for article, raw_hot in zip(candidates, hot_raw):
        # 新鲜度：指数衰减，距发布越久权重越低
        #创建时间、发布时间二选一
        published = article.published_at or article.created_at
        #计算上面时间和现在的差值
        age_days = max(0, (now - published).days)
        #根据差值计算新鲜度
        fresh = math.exp(-age_days / FRESH_DECAY_DAYS)
        # 热度归一化
        hot = (raw_hot - hot_min) / hot_span if hot_span > 0 else 0.0
        # 偏好分：文章所属栏目中用户偏好最高的权重
        pref_score = max(
            (pref.get(cid, 0.0) for cid in category_map.get(article.id, [])),
            default=0.0,
        )
        base = W_PREF * pref_score + W_FRESH * fresh + W_HOT * hot
        score = base * (NOISE_MIN + NOISE_SPAN * random.random())
        scored.append((article, score))

    # 贪心选取 + 分类多样性惩罚：同栏目已选 k 篇后，该栏目剩余候选降权
    #已经选的文稿列表
    selected: list[Article] = []
    # 已经选的文稿的所属分类列表
    selected_by_category: dict[int, int] = defaultdict(int)
    #limit写的选8篇，len(scored)为选了多少篇
    for _ in range(min(limit, len(scored))):
        def effective(item: tuple[Article, float]) -> float:
            article, score = item
            cats = category_map.get(article.id, [])
            hit = max((selected_by_category.get(cid, 0) for cid in cats), default=0)
            #通用推荐分类多样性惩罚底数
            return score * (DIVERSITY_DECAY ** hit)

        best = max(scored, key=effective)
        scored.remove(best)
        selected.append(best[0])
        for cid in category_map.get(best[0].id, []):
            selected_by_category[cid] += 1

    return selected


# ---------- 入口 ----------

def recommend_articles(db: Session, user: User | None, limit: int) -> list[Article]:
    """个性化推荐入口（路由层 user_recommend_articles 调用）。

    参数：
    - db: 请求级数据库会话（get_db 注入，只读，无 commit）；
    - user: 可选登录用户（get_optional_user 注入，未登录为 None）；
    - limit: 期望返回的推荐数量（1~20，内部会兜底截断到 MAX_LIMIT）。

    路由分发规则：
    - 登录且观看历史 >= 20 篇 → _recommend_by_vector（向量召回四段式）；
    - 否则 → _recommend_general（通用推荐）。

    返回：最多 limit 篇已发布 Article 对象；无任何候选时返回空列表，
    由路由层转成 HTTP 400。
    """
    limit = max(1, min(int(limit), MAX_LIMIT))
    if user is not None and _history_count(db, user.id) >= MIN_HISTORY_FOR_VECTOR:
        return _recommend_by_vector(db, user, limit)
    return _recommend_general(db, user, limit)
