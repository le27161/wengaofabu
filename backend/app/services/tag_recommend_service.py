# -*- coding: utf-8 -*-
"""标签关联文章推荐服务 — Phase 1：TF-IDF + 标题权重 + 段落命中率
   Phase 2：外部权威来源检索（兜底）

核心算法：
  综合评分 Score = 0.40×语义相似度(TF-IDF) + 0.30×标题权重 + 0.30×主题集中度(段落命中率)
  阈值 0.60，达标文章返回 Top-2，前端展示 1 篇 + 刷新按钮切换。
  本地无结果时，触发外部权威来源检索（.gov / .edu / 官方媒体）。
"""
import re
import time
import logging
from datetime import datetime
from urllib.parse import quote

from sqlalchemy.orm import Session

from ..models.article import Article
from ..models.article_tags import ArticleMainTag

logger = logging.getLogger(__name__)

# ── 评分权重 ──
ALPHA = 0.40   # 语义相似度
BETA  = 0.30   # 标题权重
GAMMA = 0.30   # 主题集中度

# ── 阈值 ──
SCORE_THRESHOLD = 0.60          # 综合评分达标线
PARAGRAPH_HIT_RATE_MIN = 0.20   # 段落命中率最低要求
MAX_CANDIDATES = 50             # 候选池最大文章数（不宜过大，TF-IDF 计算随文章数增长）
MAX_RECOMMEND = 5               # 单次最多返回篇数（站内+权威+百度百科）

# ── 停用词表 ──
STOP_WORDS = set([
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "什么",
    "怎么", "哪", "吗", "啊", "吧", "呢", "哦", "嗯", "还", "但", "可以",
    "被", "把", "从", "对", "与", "及", "或", "等", "其", "为", "所",
    "而", "以", "之", "于", "则", "并", "且", "因", "此", "能", "将",
    "已", "又", "再", "才", "更", "最", "只", "各", "每", "该", "来",
    "中", "后", "前", "下", "内", "外", "时", "里", "让", "向", "给",
    "用", "让", "请", "向", "使", "如", "让", "通过", "进行", "没有",
    "目前", "一个", "一些", "一种", "这个", "相关", "主要", "包括",
    "还是", "只是", "一般", "比较", "需要", "可能", "应该", "可以",
    "不同", "很多", "非常", "其中", "其他", "以及", "之间", "一些",
])


def _tokenize(text: str, max_len: int = 3000) -> str:
    """jieba 分词后用空格连接，过滤停用词和单字。
       对长文本自动截断前 max_len 字符，避免全量分词超时。"""
    import jieba
    if len(text) > max_len:
        text = text[:max_len]
    words = jieba.lcut(text)
    return " ".join([w for w in words if w.strip() and w not in STOP_WORDS and len(w) > 1])


def _title_boost(tag: str, title: str) -> float:
    """标题匹配得分：精确匹配 1.0 → 分词全匹配 0.8 → 部分匹配 0.5 → 无匹配 0.0"""
    import jieba
    if not title:
        return 0.0
    if tag in title:
        return 1.0

    tag_words = set(jieba.lcut(tag)) - STOP_WORDS
    tag_words = {w for w in tag_words if len(w) > 1}
    if not tag_words:
        return 0.0

    title_words = set(jieba.lcut(title))
    matched = tag_words & title_words

    if len(matched) == len(tag_words):
        return 0.8
    elif len(matched) >= len(tag_words) * 0.5:
        return 0.5
    return 0.0


def _paragraph_hit_rate(tag: str, content: str) -> float:
    """段落命中率：标签关键词在至少 20% 的段落中自然出现。
       长文本截断前 5000 字符，避免全量遍历超时。"""
    import jieba
    if not content:
        return 0.0

    # 截断长文本以加速
    if len(content) > 5000:
        content = content[:5000]

    paragraphs = [p.strip() for p in re.split(r'\n\n|\n|<p>|<br>|<br/>', content) if len(p.strip()) > 20]
    if len(paragraphs) < 3:
        return 0.0

    tag_words = set(jieba.lcut(tag)) - STOP_WORDS
    tag_words = {w for w in tag_words if len(w) > 1}
    if not tag_words:
        return 0.0

    hit = sum(1 for p in paragraphs if any(w in p for w in tag_words))
    return hit / len(paragraphs)


def _get_candidates(db: Session, tag: str) -> list[dict]:
    """从数据库预筛选候选文章池：已发布 + 有纯文本内容

    使用 jieba 分词扩展候选池：
      1. 精确匹配标签的文章（article_main_tags 中 tag_name == tag）
      2. 用 jieba 分词后，标题或正文包含任一分词的已发布文章
      3. 合并去重，按发布时间倒序
    """
    import jieba

    # ── 精确匹配：标签名完全一致的已发布文章 ──
    exact_ids = set()
    exact_rows = (
        db.query(Article.id, Article.title, Article.content_source, Article.summary)
        .join(ArticleMainTag, Article.id == ArticleMainTag.article_id)
        .filter(
            Article.status == "published",
            Article.content_source.isnot(None),
            Article.content_source != "",
            ArticleMainTag.tag_name == tag,
        )
        .all()
    )
    for row in exact_rows:
        exact_ids.add(row.id)

    candidates = []
    for row in exact_rows:
        candidates.append({
            "id": row.id,
            "title": row.title or "",
            "content_source": row.content_source or "",
            "summary": row.summary or "",
        })

    # ── 补充：jieba 分词后按语义匹配扩展候选池 ──
    remaining = MAX_CANDIDATES - len(candidates)
    if remaining > 0:
        # jieba 分词，过滤停用词和单字
        tag_words = [w for w in jieba.lcut(tag) if len(w.strip()) > 1 and w.strip() not in STOP_WORDS]
        if not tag_words:
            tag_words = [tag]  # 分词无结果时用原标签兜底

        from sqlalchemy import or_
        conditions = []
        for w in tag_words:
            pattern = f"%{w}%"
            conditions.append(Article.title.contains(pattern))
            conditions.append(Article.content_source.contains(pattern))

        other_rows = (
            db.query(Article.id, Article.title, Article.content_source, Article.summary)
            .filter(
                Article.status == "published",
                Article.id.notin_(exact_ids) if exact_ids else True,
                Article.content_source.isnot(None),
                Article.content_source != "",
            )
            .filter(or_(*conditions))
            .order_by(Article.published_at.desc())
            .limit(remaining)
            .all()
        )
        for row in other_rows:
            candidates.append({
                "id": row.id,
                "title": row.title or "",
                "content_source": row.content_source or "",
                "summary": row.summary or "",
            })

    return candidates


def _compute_tfidf_scores(tag: str, articles: list[dict]) -> None:
    """对候选文章池计算 TF-IDF 余弦相似度，结果写入 article["tfidf_sim"]"""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    if not articles:
        return

    corpus = [_tokenize(tag)] + [_tokenize(a["content_source"]) for a in articles]
    try:
        vectorizer = TfidfVectorizer(
            max_features=2000,      # 降低特征维度以加速计算
            sublinear_tf=True,      # 对数缩放词频
            max_df=0.8,             # 忽略出现在 80%+ 文档中的高频词
            min_df=2,               # 忽略仅出现在 1 篇文档中的罕见词
        )
        tfidf_matrix = vectorizer.fit_transform(corpus)

        tag_vec = tfidf_matrix[0]
        article_vecs = tfidf_matrix[1:]

        sims = cosine_similarity(tag_vec, article_vecs).flatten()
        for i, a in enumerate(articles):
            a["tfidf_sim"] = float(sims[i])
    except Exception:
        # 语料不足以构建 TF-IDF 矩阵 / sklearn 导入失败 / 其他异常时，所有相似度置 0
        for a in articles:
            a["tfidf_sim"] = 0.0


def _compute_composite_score(tag: str, article: dict) -> float:
    """综合评分 = α×TF-IDF + β×标题权重 + γ×段落命中率"""
    sim = article.get("tfidf_sim", 0.0)
    tb = _title_boost(tag, article.get("title", ""))
    phr = _paragraph_hit_rate(tag, article.get("content_source", ""))
    return ALPHA * sim + BETA * tb + GAMMA * phr


def recommend_by_tag(tag: str, db: Session, exclude_article_id: int = None) -> list[dict]:
    """主入口：根据标签推荐文章

    Args:
        tag: 标签名称（如 "住房消费"）
        db: 数据库会话
        exclude_article_id: 排除的文章 ID（当前文章不推荐自身）

    Returns:
        推荐文章列表，最多 2 篇，每篇含 id / title / score / summary / url
    """
    tag = tag.strip()
    if not tag:
        return []

    # 1. 预筛选候选文章
    candidates = _get_candidates(db, tag)
    if not candidates:
        logger.info(f"标签「{tag}」无候选文章")
        return []

    # 1.5 排除当前文章
    if exclude_article_id is not None:
        candidates = [a for a in candidates if a["id"] != exclude_article_id]
        if not candidates:
            logger.info(f"标签「{tag}」排除当前文章后无候选文章")
            return []

    # 2. TF-IDF 相似度计算
    _compute_tfidf_scores(tag, candidates)

    # 3. 综合评分
    for a in candidates:
        a["score"] = _compute_composite_score(tag, a)

    # 4. 过滤 + 排序
    qualified = [a for a in candidates if a["score"] >= SCORE_THRESHOLD]
    qualified.sort(key=lambda x: x["score"], reverse=True)

    result = qualified[:MAX_RECOMMEND]

    # 构造返回格式
    return [
        {
            "id": a["id"],
            "title": a["title"],
            "score": round(a["score"], 4),
            "summary": (a.get("summary") or "")[:200],
            "url": f"/article/{a['id']}",
        }
        for a in result
    ]


# ══════════════════════════════════════════════════════════════════════
# Phase 2：外部权威来源检索（兜底）— 仅限国内权威网站
# ══════════════════════════════════════════════════════════════════════

# 外部检索超时与重试
EXT_SEARCH_TIMEOUT = 3        # 单次搜索超时秒数（缩短以加快失败反馈）
EXT_SEARCH_MAX_RESULTS = 5    # 单次搜索最多取结果数
EXT_SEARCH_TOTAL_BUDGET = 10  # 外部检索总时间预算（秒），超时自动退出
EXT_RECENCY_DAYS = 730        # 时效性衰减周期（天）

# 国内权威来源站点列表（大幅扩展以提高命中率，同时通过 _is_relevant 保证相关性）
AUTHORITATIVE_SITES = [
    # ── 政府 / 教育（最高权威）──
    "gov.cn",          # 中国政府网站（含各部委、地方政府）
    "edu.cn",          # 中国教育机构
    "std.gov.cn",      # 国家标准
    "cas.cn",          # 中科院
    "cae.cn",          # 工程院
    "caas.cn",         # 农科院
    "cma.gov.cn",      # 气象局
    "nsfc.gov.cn",     # 国家自然科学基金委
    # ── 中央级新闻媒体 ──
    "people.com.cn",   # 人民日报
    "xinhuanet.com",   # 新华社
    "cctv.com",        # 央视网
    "cntv.cn",         # 央视频
    "china.com.cn",    # 中国网
    "chinanews.com",   # 中国新闻网
    "gmw.cn",          # 光明网
    "youth.cn",        # 中国青年网
    "ce.cn",           # 中国经济网
    "huanqiu.com",     # 环球网
    "cankaoxiaoxi.com",# 参考消息
    "81.cn",           # 解放军报
    "chinadaily.com.cn", # 中国日报
    "qstheory.cn",     # 求是网
    "cri.cn",          # 国际在线
    "cnr.cn",          # 央广网
    # ── 主流商业新闻门户 ──
    "thepaper.cn",     # 澎湃新闻
    "caixin.com",      # 财新网
    "ifeng.com",       # 凤凰网
    "sina.com.cn",     # 新浪
    "sohu.com",        # 搜狐
    "163.com",         # 网易
    "qq.com",          # 腾讯
    "pengpai.com.cn",  # 澎湃
    "jiemian.com",     # 界面新闻
    "yicai.com",       # 第一财经
    "cls.cn",          # 财联社
    "21jingji.com",    # 21世纪经济报道
    "nbd.com.cn",      # 每经网
    "eastmoney.com",   # 东方财富
    "jrj.com.cn",      # 金融界
    "hexun.com",       # 和讯网
    "stcn.com",        # 证券时报
    "cnstock.com",     # 上海证券报
    "chinatimes.com",  # 华夏时报
    "time-weekly.com", # 时代周报
    "bjd.com.cn",      # 北京日报
    "whb.cn",          # 文汇报
    "takungpao.com",   # 大公报
    "wenweipo.com",    # 文汇网
    # ── 科技 / 学术 / 行业 ──
    "csdn.net",        # CSDN
    "cnblogs.com",     # 博客园
    "51cto.com",       # 51CTO
    "oschina.net",     # 开源中国
    "infoq.cn",        # InfoQ
    "segmentfault.com",# SegmentFault
    "juejin.cn",       # 稀土掘金
    "zhihu.com",       # 知乎
    "cnki.net",        # 中国知网
    "wanfangdata.com.cn", # 万方
    "cqvip.com",       # 维普
    "sciencenet.cn",   # 科学网
    "ckcest.cn",       # 中国工程科技知识中心
    "istic.ac.cn",     # 中国科学技术信息研究所
    "geekbang.org",    # 极客邦
    "tmtpost.com",     # 钛媒体
    "36kr.com",        # 36氪
    "huxiu.com",       # 虎嗅
    "leiphone.com",    # 雷锋网
    "ithome.com",      # IT之家
    "donews.com",      # DoNews
]

# AI 聊天/思考平台黑名单 — 这些域名的内容多为 AI 生成的思考过程，非正式文章
AI_BLACKLIST = [
    "deepseek.com",        # DeepSeek 聊天/思考页
    "chat.deepseek.com",
    "moonshot.cn",         # Kimi
    "kimi.moonshot.cn",
    "doubao.com",          # 豆包
    "yiyan.baidu.com",     # 文心一言
    "tongyi.aliyun.com",   # 通义千问
    "chatglm.cn",          # 智谱清言
    "chat.baidu.com",      # 百度AI
    "yuanbao.tencent.com", # 腾讯元宝
    "xinghuo.xfyun.cn",    # 讯飞星火
    "qianwen.aliyun.com",  # 通义千问
    "poe.com",             # Poe
    "claude.ai",           # Claude
    "chat.openai.com",     # ChatGPT
    "chatgpt.com",
]


def _is_excluded(url: str) -> bool:
    """判断 URL 是否为 AI 聊天/思考平台等非正式来源"""
    if not url:
        return False
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        domain = (parsed.netloc or "").lower()
    except Exception:
        return False
    if not domain:
        return False
    for blocked in AI_BLACKLIST:
        if blocked in domain:
            return True
    return False


def _is_authoritative(url: str) -> bool:
    """判断 URL 是否属于国内权威来源站点"""
    if not url:
        return False
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        domain = (parsed.netloc or "").lower()
    except Exception:
        return False
    if not domain:
        return False
    for site in AUTHORITATIVE_SITES:
        if site in domain:
            return True
    return False


def _ext_relevance_score(tag: str, title: str, snippet: str) -> float:
    """计算外部搜索结果的相关性得分（标题和摘要匹配度）

    标题权重 0.6，摘要权重 0.4
    """
    import jieba
    tag_words = set(jieba.lcut(tag)) - STOP_WORDS
    tag_words = {w for w in tag_words if len(w) > 1}
    if not tag_words:
        return 0.0

    def _word_match(text: str) -> float:
        if not text:
            return 0.0
        text_words = set(jieba.lcut(text))
        matched = tag_words & text_words
        return len(matched) / len(tag_words)

    title_score = _word_match(title)
    # 精确短语匹配加分
    if tag in (title or ""):
        title_score = 1.0

    snippet_score = _word_match(snippet)
    if tag in (snippet or ""):
        snippet_score = max(snippet_score, 0.8)

    return 0.6 * title_score + 0.4 * snippet_score


def _ext_recency_score(publish_date_str: str) -> float:
    """计算时效性得分：两年内按线性衰减，超过两年为 0"""
    if not publish_date_str:
        return 0.5  # 无日期信息给中性分

    try:
        # 尝试解析常见日期格式
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"):
            try:
                pub_date = datetime.strptime(publish_date_str.strip(), fmt)
                break
            except ValueError:
                continue
        else:
            return 0.5
    except Exception:
        return 0.5

    days_ago = (datetime.now() - pub_date).days
    if days_ago < 0:
        return 1.0  # 未来日期（可能是时区问题）
    return max(0.0, 1.0 - days_ago / EXT_RECENCY_DAYS)


def _search_bing(query: str, max_results: int = EXT_SEARCH_MAX_RESULTS) -> list[dict]:
    """使用 cn.bing.com 搜索（国内可访问），返回 [{title, url, snippet}]"""
    import requests
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("beautifulsoup4 未安装，无法执行搜索")
        return []

    encoded = quote(query)
    url = f"https://cn.bing.com/search?q={encoded}&setlang=zh-cn"

    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            timeout=EXT_SEARCH_TIMEOUT,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"Bing 搜索请求失败：{e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    # 尝试多种 Bing 搜索结果选择器（兼容 HTML 结构变化）
    result_items = soup.select("li.b_algo") or soup.select("ol#b_results li") or soup.select(".b_results li")
    logger.debug(f"Bing 搜索「{query[:50]}...」→ 原始结果 {len(result_items)} 条")

    for li in result_items[:max_results]:
        title_el = li.select_one("h2 a") or li.select_one("h3 a") or li.select_one("a")
        snippet_el = li.select_one(".b_caption p") or li.select_one(".b_algoSlug") or li.select_one("p")
        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        snippet = snippet_el.get_text(strip=True) if snippet_el else ""

        if not href or not title:
            continue

        results.append({
            "title": title,
            "url": href,
            "snippet": snippet,
        })

    logger.info(f"Bing 搜索「{query[:60]}」→ 解析到 {len(results)} 条有效结果")
    return results


def _search_web(query: str, max_results: int = EXT_SEARCH_MAX_RESULTS) -> list[dict]:
    """统一搜索入口：仅使用 cn.bing.com（国内权威来源）"""
    return _search_bing(query, max_results)


def _search_baike(tag: str) -> list[dict]:
    """百度百科搜索：使用完整标签词条直接访问，不进行分词或截断

    规则：
      1. 将完整标签直接 URL 编码后访问 baike.baidu.com/item/{tag}
      2. 若直接访问失败，通过 Bing 搜索 "site:baike.baidu.com {完整标签}"
      3. 验证返回的词条标题必须包含完整标签或其核心分词

    Returns:
        搜索结果列表，每篇含 title / url / snippet
    """
    import requests
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("beautifulsoup4 未安装，无法执行百度百科搜索")
        return [_baike_search_fallback(tag)]

    # 记录完整标签，确保不被截断
    logger.info(f"百度百科搜索：完整标签「{tag}」（长度={len(tag)}）")

    encoded = quote(tag)
    url = f"https://baike.baidu.com/item/{encoded}"

    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            timeout=EXT_SEARCH_TIMEOUT,
            allow_redirects=True,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"百度百科直接访问失败（{e}），通过 Bing 搜索 site:baike.baidu.com「{tag}」")
        return _search_baike_via_bing(tag)

    soup = BeautifulSoup(resp.text, "html.parser")

    # 提取词条标题
    title_el = soup.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else tag

    # 提取摘要
    summary_el = soup.select_one(".lemma-summary") or soup.select_one(".para")
    summary = summary_el.get_text(strip=True) if summary_el else ""

    if not summary:
        paras = soup.select(".para")
        summary = "".join(p.get_text(strip=True) for p in paras[:3])[:300]

    # 排除百度百科首页 / 无词条页 → 走 Bing 兜底
    if not title or title == "百度百科——全球领先的中文百科全书":
        logger.info(f"百度百科无「{tag}」词条，尝试 Bing 搜索")
        return _search_baike_via_bing(tag)

    # 验证词条标题与标签的匹配度
    if not _baike_title_matches(tag, title):
        logger.info(f"百度百科词条标题「{title}」与完整标签「{tag}」不匹配，尝试 Bing 搜索")
        return _search_baike_via_bing(tag)

    logger.info(f"百度百科匹配成功：标签「{tag}」→ 词条「{title}」")
    return [{
        "title": title,
        "url": resp.url,
        "snippet": summary[:200],
    }]


def _search_baike_via_bing(tag: str) -> list[dict]:
    """通过 Bing 搜索百度百科词条，若仍无结果则返回搜索页链接兜底"""
    raw_results = _search_bing(f'site:baike.baidu.com "{tag}"', 3)
    filtered = [r for r in raw_results if _baike_title_matches(tag, r.get("title", ""))]
    if filtered:
        logger.info(f"百度百科 Bing 兜底成功：标签「{tag}」匹配 {len(filtered)} 条")
        return filtered
    logger.info(f"百度百科 Bing 兜底也未找到「{tag}」，返回搜索页链接作为终极兜底")
    return [_baike_search_fallback(tag)]


def _baike_search_fallback(tag: str) -> dict:
    """终极兜底：返回百度百科搜索页链接，保证用户始终有链接可点"""
    search_url = f"https://baike.baidu.com/search?word={quote(tag)}"
    logger.info(f"百度百科终极兜底：{search_url}")
    return {
        "title": f"「{tag}」- 百度百科",
        "url": search_url,
        "snippet": f"在百度百科中搜索「{tag}」的相关内容",
    }


def _baike_title_matches(tag: str, title: str) -> bool:
    """验证百度百科词条标题是否与标签匹配

    规则（按优先级）：
      1. 完整标签是标题的子串 → 直接通过（精确匹配，最高优先级）
      2. 标签经 jieba 分词后，每个词都必须在标题中出现 → 通过
      3. 以上均不满足 → 不通过
    """
    import jieba

    # 规则1：完整标签精确匹配（最高优先级，不依赖分词）
    if tag in title:
        return True

    # 规则2：去空格标点后的标签在标题中
    clean_tag = re.sub(r'\s+', '', tag)
    if clean_tag and clean_tag in title:
        return True

    # 规则3：jieba 分词后逐词验证
    tag_words = [w for w in jieba.lcut(tag) if len(w.strip()) > 1 and w.strip() not in STOP_WORDS]
    if not tag_words:
        return False

    for w in tag_words:
        if w not in title:
            return False
    return True


def _is_specific_article(url: str) -> bool:
    """判断 URL 是否为具体文章页（非首页 / 栏目页 / 导航页）

    放宽策略：只要不是明显的首页/栏目/导航页，就当作文章页通过。
    配合 _is_relevant 做二次过滤，确保宽松初筛 + 严格相关性。
    """
    if not url:
        return False
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    # 无路径或只有根路径 → 首页
    if not path or path == "":
        return False
    # 明显的栏目页关键词（仅过滤最明显的）
    segment_lower = path.lower()
    obvious_landing = {"index", "home", "default", "main", "login", "register",
                       "search", "sitemap", "category", "tag", "author", "page"}
    segments = [s for s in path.split("/") if s]
    if segments and segments[-1].lower() in obvious_landing:
        return False
    # 路径太短且无数字 → 可能是栏目页（如 /news、/tech）
    if len(segments) == 1 and len(segments[0]) <= 6 and not any(c.isdigit() for c in segments[0]):
        # 但允许含数字的短路径（如 /t12345）和含连字符的（如 /a-b-c）
        if "-" not in segments[0]:
            return False
    return True


def _is_relevant(item: dict, tag: str) -> bool:
    """检查外部搜索结果是否与标签相关（标题或摘要包含关键词）"""
    import jieba
    title = (item.get("title") or "").lower()
    snippet = (item.get("snippet") or "").lower()
    text = title + " " + snippet
    tag_lower = tag.lower()

    # 完整标签命中 → 直接通过
    if tag_lower in text:
        return True

    # jieba 分词后至少 50% 的词命中
    tag_words = [w for w in jieba.lcut(tag) if len(w.strip()) > 1 and w.strip() not in STOP_WORDS]
    if not tag_words:
        return False
    hit_count = sum(1 for w in tag_words if w.lower() in text)
    return hit_count >= len(tag_words) * 0.5


def _do_auth_search(query: str, tag: str, results: list[dict], max_results: int = 15) -> bool:
    """执行一次权威搜索，将结果追加到 results 中。返回 True 表示找到结果

    过滤链：AI平台排除 → 权威域名确认 → 文章页判断 → 相关性校验
    前三层宽松，最后一层严格（保证相关性）。
    """
    try:
        raw_results = _search_web(query, max_results)
    except Exception as e:
        logger.warning(f"权威搜索「{query}」失败：{e}")
        return False

    skipped_ai = 0
    skipped_auth = 0
    skipped_article = 0
    skipped_relevant = 0
    count_before = len(results)

    for r in raw_results:
        url = r.get("url", "")
        if _is_excluded(url):
            skipped_ai += 1
            logger.debug(f"排除 AI 平台：{url[:80]}")
            continue
        if not _is_authoritative(url):
            skipped_auth += 1
            continue
        if not _is_specific_article(url):
            skipped_article += 1
            continue
        # ★ 关键：相关性校验，确保搜索结果的标题/摘要与标签相关
        if not _is_relevant(r, tag):
            skipped_relevant += 1
            continue
        results.append({
            "title": r.get("title", ""),
            "url": url,
            "snippet": r.get("snippet", ""),
        })

    added = len(results) - count_before
    logger.info(
        f"权威搜索「{query[:60]}」: 原始 {len(raw_results)} 条, "
        f"AI排除 {skipped_ai} 条, 非权威 {skipped_auth} 条, "
        f"非文章页 {skipped_article} 条, 不相关 {skipped_relevant} 条, "
        f"新增 {added} 条"
    )

    return added > 0


def search_external(tag: str) -> list[dict]:
    """外部检索入口：权威网站优先，百度百科始终在最后

    核心目标：在权威网站找到与标签强相关的文章。
    搜索策略（多轮，带总时间预算）：
      1. 宽泛搜索：引号精确 + 限定词（新闻/研究/解读）
      2. 站点限定搜索：针对 gov.cn / 主流新闻 / 科技站点
      3. jieba 分词扩展搜索（仅当分词 >= 2 个词时触发）
      4. 百度百科兜底（始终在最后）

    总时间预算 EXT_SEARCH_TOTAL_BUDGET 秒，超时自动退出，保证前端不超时。
    """
    import jieba

    tag = tag.strip()
    if not tag:
        return []

    auth_results = []
    MAX_AUTH = 4          # 权威来源最多 4 条
    start_time = time.time()

    def _budget_left() -> float:
        """剩余时间预算（秒），<=0 表示已超时"""
        return EXT_SEARCH_TOTAL_BUDGET - (time.time() - start_time)

    def _has_budget() -> bool:
        return _budget_left() > 0

    # ══════════════════════════════════════════════════════════════
    # 第一轮：宽泛搜索（精选 5 个高价值查询）
    # ══════════════════════════════════════════════════════════════
    broad_queries = [
        f'"{tag}"',                # 引号精确匹配（相关性最高，优先）
        f'{tag} 新闻',              # 新闻限定
        f'{tag} 研究',              # 学术/技术限定
        f'{tag} 解读',              # 政策/概念限定
        tag,                       # 纯标签（Bing 自然排序，覆盖面最广）
    ]
    logger.info(f"【权威搜索-宽泛】标签「{tag}」，共 {len(broad_queries)} 个查询")
    for q in broad_queries:
        if len(auth_results) >= MAX_AUTH or not _has_budget():
            break
        _do_auth_search(q, tag, auth_results, max_results=20)
        time.sleep(0.15)

    # ══════════════════════════════════════════════════════════════
    # 第二轮：站点限定搜索（精选 6 个高命中率站点）
    # ══════════════════════════════════════════════════════════════
    if len(auth_results) < MAX_AUTH and _has_budget():
        site_queries = [
            f'{tag} site:gov.cn',
            f'{tag} site:people.com.cn',
            f'{tag} site:xinhuanet.com',
            f'{tag} site:thepaper.cn',
            f'{tag} site:csdn.net',
            f'{tag} site:zhihu.com',
        ]
        logger.info(f"【权威搜索-站点】标签「{tag}」，共 {len(site_queries)} 个查询")
        for q in site_queries:
            if len(auth_results) >= MAX_AUTH or not _has_budget():
                break
            _do_auth_search(q, tag, auth_results, max_results=10)
            time.sleep(0.15)

    # ══════════════════════════════════════════════════════════════
    # 第三轮：jieba 分词扩展搜索（仅当分词 >= 2 且有剩余预算）
    # ══════════════════════════════════════════════════════════════
    if len(auth_results) < MAX_AUTH and _has_budget():
        tag_words = [w for w in jieba.lcut(tag) if len(w.strip()) > 1 and w.strip() not in STOP_WORDS]
        if tag_words and len(tag_words) >= 2:
            core_words = tag_words[:3]
            expanded = " ".join(core_words)
            logger.info(f"【权威搜索-扩展】jieba 分词「{tag}」→ 核心词「{expanded}」")
            expanded_queries = [
                expanded,
                f'{expanded} site:gov.cn',
            ]
            for q in expanded_queries:
                if len(auth_results) >= MAX_AUTH or not _has_budget():
                    break
                _do_auth_search(q, tag, auth_results, max_results=15)
                time.sleep(0.15)

    elapsed = time.time() - start_time
    logger.info(f"权威搜索「{tag}」耗时 {elapsed:.1f}s，找到 {len(auth_results)} 条")

    # ══════════════════════════════════════════════════════════════
    # 第四轮：百度百科兜底（始终作为最后一条）
    # ══════════════════════════════════════════════════════════════
    logger.info(f"【百度百科兜底】获取百度百科结果「{tag}」")
    try:
        baike_results = _search_baike(tag)
    except Exception as e:
        logger.warning(f"百度百科搜索异常：{e}")
        baike_results = []

    # 构建最终结果
    final_results = []
    seen_urls = set()

    for r in auth_results[:MAX_AUTH]:
        url = r.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        final_results.append({
            "title": r.get("title", ""),
            "url": url,
            "summary": r.get("snippet", "")[:200],
            "source_name": "权威来源",
        })

    if baike_results:
        r = baike_results[0]
        url = r.get("url", "")
        if url not in seen_urls:
            final_results.append({
                "title": r.get("title", ""),
                "url": url,
                "summary": r.get("snippet", "")[:200],
                "source_name": "百度百科",
            })

    if not final_results:
        baike_url = baike_results[0].get("url", "") if baike_results else ""
        final_results.append({
            "title": baike_results[0].get("title", "") if baike_results else f"百度百科-「{tag}」",
            "url": baike_url or f"https://baike.baidu.com/search?word={quote(tag)}",
            "summary": baike_results[0].get("snippet", "")[:200] if baike_results else f"在百度百科中搜索「{tag}」",
            "source_name": "百度百科",
        })

    logger.info(
        f"外部检索完成「{tag}」: 权威 {len(auth_results)} 条 + 百科 {len(baike_results)} 条, "
        f"最终 {len(final_results)} 条, 总耗时 {time.time() - start_time:.1f}s"
    )
    return final_results