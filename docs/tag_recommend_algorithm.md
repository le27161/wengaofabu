# 标签关联文章推荐算法设计文档

> 版本：v1.0 | 日期：2026-08-16 | 作者：算法工程师

---

## 一、算法概述

### 1.1 输入与输出

| 项目 | 说明 |
|------|------|
| 输入 | 用户鼠标悬浮标签时传入的标签名称（如 `"住房消费"`） |
| 输出 | 一篇推荐文章（超链接），附带刷新按钮可切换下一篇 |
| 优先级 | 本地数据库 > 外部权威来源 |

### 1.2 核心流程

```
用户悬浮标签 → 输入标签名称
      │
      ▼
┌─────────────────────────────────┐
│  阶段一：本地数据库匹配（优先）    │
│  - 语义相似度 + 标题权重 + 主题集中度 │
│  - 综合评分 ≥ 0.6 阈值            │
│  - 返回 Top-2，展示1篇+刷新按钮    │
└──────────┬──────────────────────┘
           │ 达标文章数 = 0？
           ▼ 是
┌─────────────────────────────────┐
│  阶段二：外部权威来源检索（兜底）   │
│  - 限定 .gov / .edu / 知名标准组织  │
│  - 搜索策略：标签+限定词            │
│  - 按 相关性+时效性 综合排序        │
└─────────────────────────────────┘
```

---

## 二、阶段一：本地数据库匹配（优先）

### 2.1 数据源

基于现有 `articles` 表，利用以下字段：

| 字段 | 用途 |
|------|------|
| `title`（标题） | 标题权重匹配（高权重） |
| `content_source`（纯文本正文） | 语义相似度 + 主题集中度计算 |
| `summary`（摘要） | 辅助参与语义匹配 |
| `status` | 过滤，仅匹配 `published` 状态的文稿 |

同时利用现有 `article_main_tags` 表（文章主关键词）和 `article_sub_tags` 表（前置知识链标签）作为候选文章池的快速预筛选条件。

### 2.2 综合评分模型

综合相关度 `Score(tag, article)` 由三个维度加权求和，公式如下：

```
Score = α × Sim(tag, article) + β × TitleBoost(tag, article) + γ × TopicFocus(tag, article)
```

| 维度 | 权重 | 符号 | 说明 |
|------|------|------|------|
| 语义相似度 | 0.40 | α | 标签与文章内容的向量语义相似度 |
| 标题权重 | 0.30 | β | 标题中匹配标签的额外加分 |
| 主题集中度 | 0.30 | γ | 主题一致性与关键词段落分布质量 |

三权重之和为 1.0，可根据实际效果调优。

---

### 2.3 维度一：语义相似度 `Sim(tag, article)`（权重 40%）

#### 2.3.1 推荐方案：Sentence-BERT 向量嵌入

**离线圈选（批量处理）**：

1. 对所有已发布文章（`status = "published"`）的 `content_source` 字段，使用 Sentence-BERT 模型（如 `paraphrase-multilingual-MiniLM-L12-v2`）生成文档级向量嵌入。
2. 向量维度 384，存储到 `articles` 表新增字段 `embedding`（`JSON` 类型，存储浮点数列表）。
3. 当文章新增或内容更新时，触发异步任务重新生成嵌入。

**在线查询**：

1. 将输入标签使用同一模型编码为向量 `v_tag`。
2. 对候选文章池中的每篇文章，计算余弦相似度：

```
cos_sim(v_tag, v_article) = (v_tag · v_article) / (||v_tag|| × ||v_article||)
```

3. 余弦相似度值域为 `[-1, 1]`，归一化到 `[0, 1]`：

```
Sim = (cos_sim + 1) / 2
```

#### 2.3.2 降级方案：TF-IDF 加权余弦相似度

当 Sentence-BERT 模型不可用时（如部署环境限制），降级为 TF-IDF 方案：

1. **离线构建 TF-IDF 矩阵**：对所有已发布文章的 `content_source` 进行 jieba 分词，构建 TF-IDF 向量矩阵（使用 `sklearn.feature_extraction.text.TfidfVectorizer`）。
2. **在线查询**：将标签文本同样经 jieba 分词后，使用同一 Vectorizer 变换为 TF-IDF 向量，与文章矩阵计算余弦相似度。
3. **定期重建**：每天凌晨通过定时任务重建 TF-IDF 矩阵，以反映新增文章。

#### 2.3.3 候选文章池预筛选

为减少全表扫描开销，先在数据库层面预筛选：

```sql
-- 预筛选：标签存在于 article_main_tags 中的文章，或标签相关的分类文章
SELECT DISTINCT a.*
FROM articles a
LEFT JOIN article_main_tags mt ON a.id = mt.article_id
WHERE a.status = 'published'
  AND (
    mt.tag_name = :tag_name                          -- 主关键词精确匹配
    OR a.title LIKE CONCAT('%', :tag_name, '%')      -- 标题包含标签
    OR a.content_source LIKE CONCAT('%', :tag_name, '%')  -- 正文包含标签
  )
```

仅在候选池中计算向量相似度，大幅降低计算量。

---

### 2.4 维度二：标题权重 `TitleBoost(tag, article)`（权重 30%）

标题中的匹配远比正文中的匹配更有价值。设计如下计分规则：

#### 2.4.1 分层计分

| 匹配级别 | 条件 | 得分 |
|----------|------|------|
| 精确匹配 | 标签作为完整短语出现在标题中 | 1.00 |
| 分词匹配（全部） | 标签分词后所有词均在标题中出现 | 0.80 |
| 分词匹配（部分） | 标签分词后至少 50% 的词在标题中出现 | 0.50 |
| 无匹配 | 标题中无任何标签分词命中 | 0.00 |

#### 2.4.2 实现细节

```python
def title_boost(tag: str, title: str) -> float:
    """计算标签在标题中的匹配得分"""
    # 精确匹配
    if tag in title:
        return 1.0

    # jieba 分词
    tag_words = set(jieba.lcut(tag))
    # 过滤停用词
    tag_words = {w for w in tag_words if w not in STOP_WORDS and len(w) > 1}
    if not tag_words:
        return 0.0

    title_words = set(jieba.lcut(title))
    matched = tag_words & title_words

    if len(matched) == len(tag_words):
        return 0.8
    elif len(matched) >= len(tag_words) * 0.5:
        return 0.5
    return 0.0
```

---

### 2.5 维度三：主题集中度 `TopicFocus(tag, article)`（权重 30%）

主题集中度衡量两个关键指标：**关键词在段落间的自然分布** 和 **文章整体主题与标签含义的一致性**。

#### 2.5.1 段落级关键词密度

将正文按段落（`\n\n` 或 HTML `<p>` 标签）切分，计算：

```
段落命中率 = 包含标签关键词的段落数 / 总段落数
```

要求段落命中率 ≥ 0.2（即至少 20% 的段落自然涉及该标签），否则视为偶然提及。

```python
def paragraph_hit_rate(tag: str, content: str) -> float:
    """计算标签在段落中的分布率"""
    paragraphs = [p.strip() for p in re.split(r'\n\n|<p>|<br>', content) if p.strip()]
    if len(paragraphs) < 3:
        return 0.0

    tag_words = set(jieba.lcut(tag))
    hit_count = 0
    for para in paragraphs:
        if any(w in para for w in tag_words):
            hit_count += 1

    return hit_count / len(paragraphs)
```

#### 2.5.2 主题一致性（零样本分类）

利用零样本分类模型（如 `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`）判断文章是否与标签主题一致：

1. 对文章摘要（或前 512 字符）构建假设：
   - `"这篇文章的主题是{tag}"`（正例）
   - `"这篇文章与{tag}无关"`（负例）
2. 模型输出 entailment 概率作为主题一致性得分 `topic_consistency ∈ [0, 1]`。

#### 2.5.3 综合

```
TopicFocus = 0.5 × paragraph_hit_rate + 0.5 × topic_consistency
```

---

### 2.6 阈值与排序

- **综合评分阈值**：`Score ≥ 0.60`
- 只有超过阈值的文章才视为"相关"
- 按 `Score` 降序排列，取前 2 篇
- 首次展示第 1 篇，页面提供**刷新按钮**，用户点击后展示第 2 篇（若仅 1 篇达标则刷新按钮置灰）

---

## 三、阶段二：外部权威来源检索（兜底）

当本地达标文章数量为 0 时触发。

### 3.1 检索范围限定

仅检索以下权威来源：

| 类型 | 域名模式 | 示例 |
|------|----------|------|
| 政府网站 | `*.gov.cn` | 中国政府网、各部委官网 |
| 教育机构 | `*.edu.cn` | 高校、研究机构 |
| 官方媒体 | 人民日报、新华社、央视网 | `people.com.cn`、`xinhuanet.com`、`cctv.com` |
| 国际标准组织 | ISO、W3C、IEEE | `iso.org`、`w3.org`、`ieee.org` |
| 行业权威 | 央行、证监会、银保监会 | `pbc.gov.cn`、`csrc.gov.cn` |

### 3.2 搜索策略

#### 3.2.1 查询构造

将标签关键词与限定词组合，生成多条搜索查询：

```
查询1: "{标签} 定义"
查询2: "{标签} 官方解读"
查询3: "{标签} 最新政策"
查询4: "{标签} site:gov.cn"
查询5: "{标签} 最新动态"
```

#### 3.2.2 搜索结果评分

对每条搜索结果，计算综合外部得分：

```
ExtScore = 0.5 × Relevance(title, snippet, tag) + 0.5 × Recency(publish_date)
```

**相关性 `Relevance`**：

- 标题包含标签精确短语：`1.0`
- 标题包含标签分词：`0.7`
- 摘要包含标签精确短语：`0.5`
- 摘要包含标签分词：`0.3`

**时效性 `Recency`**：

```
Recency = max(0, 1 - (当前日期 - 发布日期).days / 730)
```

即两年内的文章按线性衰减，超过两年的文章时效性为 0。

### 3.3 返回

取 `ExtScore` 最高且发布时间最近的一篇，返回格式：

```
[文章标题](外部链接) — 来自权威来源
```

---

## 四、防弱匹配机制

### 4.1 核心原则

> 严格禁止因关键词出现一次就判定相关。关键词必须**主题性**出现，而非偶然提及。

### 4.2 多层防护

#### 第一层：段落命中率门槛

如 2.5.1 所述，要求标签关键词在至少 20% 的段落中出现。一句话中偶然提到即被排除。

#### 第二层：主题一致性验证

如 2.5.2 所述，通过零样本分类验证文章主题是否与标签一致。若 entailment 概率 < 0.5，直接判定为不相关。

#### 第三层：歧义词库消歧

建立 `disambiguation_dict`，对可能产生歧义的标签进行上下文消歧：

```python
DISAMBIGUATION_DICT = {
    "苹果": {
        "fruit": ["水果", "种植", "口感", "品种", "果园"],
        "company": ["iPhone", "iOS", "Mac", "Apple", "库克", "苹果公司"],
    },
    "小米": {
        "food": ["粮食", "谷物", "种植", "营养"],
        "company": ["手机", "MIUI", "雷军", "智能家居", "生态链"],
    },
    "病毒": {
        "biology": ["感染", "细胞", "免疫", "病原体", "RNA"],
        "computer": ["恶意软件", "木马", "杀毒", "网络安全", "勒索"],
    },
    # ... 更多歧义词条
}
```

消歧逻辑：在文章上下文中统计各义项的特征词命中数，选择命中最多的义项。若该义项与标签的上下文意图不一致，则排除该文章。

#### 第四层：综合阈值兜底

即使前三层全部通过，最终仍需 `Score ≥ 0.60` 才算达标。单一维度高分无法弥补其他维度的不足。

---

## 五、返回格式规范

### 5.1 本地文章

```json
{
  "source": "local",
  "items": [
    {
      "id": 123,
      "title": "住房消费新政解读：公积金贷款额度提升",
      "url": "/article/123",
      "score": 0.87,
      "summary": "近日住建部发布住房消费相关新政..."
    },
    {
      "id": 456,
      "title": "住房消费市场趋势分析",
      "url": "/article/456",
      "score": 0.72,
      "summary": "2025年住房消费呈现三大趋势..."
    }
  ],
  "total": 2,
  "current_index": 0,
  "has_next": true
}
```

前端渲染：

```
相关推荐：住房消费

┌──────────────────────────────────────────────┐
│  📄 住房消费新政解读：公积金贷款额度提升       │
│  近日住建部发布住房消费相关新政...            │
│  [查看详情]                        [🔄 换一篇] │
└──────────────────────────────────────────────┘
```

### 5.2 外部文章

```json
{
  "source": "external",
  "items": [
    {
      "title": "住房消费的定义与政策框架",
      "url": "https://www.mohurd.gov.cn/policy/2025/xxx.html",
      "source_name": "住房和城乡建设部",
      "score": 0.81,
      "published_at": "2025-12-01"
    }
  ],
  "total": 1,
  "current_index": 0,
  "has_next": false,
  "note": "本地暂无相关文章，以下推荐来自权威来源"
}
```

前端渲染：

```
相关推荐：住房消费

┌──────────────────────────────────────────────┐
│  🔗 住房消费的定义与政策框架                  │
│  来源：住房和城乡建设部 | 来自权威来源         │
│  [查看原文]                                   │
└──────────────────────────────────────────────┘
```

### 5.3 无结果

```json
{
  "source": "none",
  "items": [],
  "total": 0,
  "message": "暂未找到与「住房消费」相关的推荐内容"
}
```

---

## 六、系统架构设计

### 6.1 后端新增模块

```
backend/app/
├── services/
│   └── tag_recommend_service.py    # 推荐算法核心服务（新增）
├── routers/
│   └── tags.py                     # 标签推荐接口路由（新增）
├── models/
│   └── disambiguation.py           # 歧义词库模型（新增）
└── core/
    └── tag_recommend_config.py     # 推荐参数配置（新增）
```

### 6.2 数据库变更

#### articles 表新增字段

```sql
ALTER TABLE articles ADD COLUMN embedding JSON NULL COMMENT '文档向量嵌入（384维浮点数列表）';
ALTER TABLE articles ADD COLUMN embedding_updated_at DATETIME NULL COMMENT '向量嵌入更新时间';
```

#### 新增歧义词库表

```sql
CREATE TABLE disambiguation_dict (
    id INT PRIMARY KEY AUTO_INCREMENT,
    keyword VARCHAR(50) NOT NULL COMMENT '歧义关键词',
    sense VARCHAR(20) NOT NULL COMMENT '义项标识（如 fruit/company）',
    sense_label VARCHAR(50) NOT NULL COMMENT '义项中文名',
    feature_words JSON NOT NULL COMMENT '特征词列表',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_keyword_sense (keyword, sense)
) COMMENT '歧义词库';
```

### 6.3 接口设计

#### GET `/api/tags/{tag_name}/recommend`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `tag_name` | path | 是 | 标签名称（URL 编码） |
| `index` | query | 否 | 已展示文章索引，默认 0（请求下一篇时传 1） |
| `page_size` | query | 否 | 单次返回数量，默认 1 |

#### 响应示例

见第五章返回格式规范。

### 6.4 离线任务

| 任务 | 频率 | 说明 |
|------|------|------|
| 向量嵌入批量生成 | 新文章入库时（异步） | 对 `content_source` 生成 Sentence-BERT 嵌入 |
| TF-IDF 矩阵重建 | 每天凌晨 2:00 | 当 Sentence-BERT 不可用时启用 |
| 歧义词库更新 | 按需手动维护 | 通过管理后台增删改 |

---

## 七、参数配置与调优

### 7.1 可调参数

```python
# tag_recommend_config.py

# 综合评分权重（α + β + γ = 1.0）
ALPHA = 0.40   # 语义相似度
BETA  = 0.30   # 标题权重
GAMMA = 0.30   # 主题集中度

# 阈值
SCORE_THRESHOLD = 0.60       # 综合评分达标线
PARAGRAPH_HIT_RATE_MIN = 0.20  # 段落命中率最低要求
TOPIC_CONSISTENCY_MIN = 0.50   # 主题一致性最低要求

# 外部检索
EXT_SEARCH_MAX_RESULTS = 10   # 外部检索最大结果数
EXT_RECENCY_DAYS = 730        # 时效性衰减周期（天）

# 召回
MAX_CANDIDATE_ARTICLES = 200  # 候选池最大文章数
MAX_RECOMMEND_COUNT = 2       # 单次推荐返回篇数
```

### 7.2 调优策略

1. **A/B 测试框架**：在后台管理界面增加参数配置页，支持动态调整权重与阈值。
2. **点击率监控**：埋点记录推荐文章的展示与点击数据，通过 `event_logs` 表分析推荐效果。
3. **周期性评估**：每月对推荐结果进行人工抽样评估，校准参数。

---

## 八、与现有系统的集成点

| 现有模块 | 集成方式 |
|----------|----------|
| `article_main_tags` / `article_sub_tags` | 作为候选池预筛选条件，标签精确匹配快速过滤 |
| `ai_service.py` | 复用现有 Dify 工作流，可选用于标签语义扩展 |
| `keywords.py` 的 `explain_tag` | 推荐面板中嵌入"查看标签解释"链接 |
| `event_service.py` | 埋点记录推荐点击事件 |
| 前端 `ArticleDetailView.vue` | 关键词悬浮面板中嵌入推荐区域 |

---

## 九、实现路线图

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| Phase 1 | TF-IDF + 标题权重 + 段落命中率（快速上线，无需模型） | P0 |
| Phase 2 | 歧义词库 + 主题一致性零样本分类 | P1 |
| Phase 3 | Sentence-BERT 向量嵌入替换 TF-IDF | P2 |
| Phase 4 | 外部权威来源检索 | P2 |
| Phase 5 | 参数调优面板 + A/B 测试 | P3 |

---

## 十、附录：TF-IDF 快速实现伪代码

作为 Phase 1 最小可行方案，以下为 TF-IDF 方案的核心伪代码：

```python
# tag_recommend_service.py（Phase 1 核心逻辑）

import jieba
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re

# 停用词表
STOP_WORDS = set(["的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
                  "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
                  "没有", "看", "好", "自己", "这"])

# 歧义词库
DISAMBIGUATION = {
    "苹果": {
        "fruit": ["水果", "种植", "口感", "品种", "果园", "甜", "红富士"],
        "company": ["iPhone", "iOS", "Mac", "Apple", "库克", "苹果公司", "手机"],
    },
    # ... 更多词条
}


def tokenize(text: str) -> str:
    """jieba 分词后用空格连接"""
    words = jieba.lcut(text)
    return " ".join([w for w in words if w.strip() and w not in STOP_WORDS])


def compute_tfidf_score(tag: str, articles: list[dict]) -> list[dict]:
    """TF-IDF 方案：计算标签与文章池的余弦相似度"""
    if not articles:
        return []

    # 构建语料：标签 + 所有文章正文
    corpus = [tokenize(tag)] + [tokenize(a["content_source"] or "") for a in articles]
    vectorizer = TfidfVectorizer(max_features=5000, sublinear_tf=True)
    tfidf_matrix = vectorizer.fit_transform(corpus)

    tag_vec = tfidf_matrix[0]
    article_vecs = tfidf_matrix[1:]

    sims = cosine_similarity(tag_vec, article_vecs).flatten()

    for i, a in enumerate(articles):
        a["tfidf_sim"] = float(sims[i])
    return articles


def title_boost(tag: str, title: str) -> float:
    """标题匹配得分"""
    if tag in title:
        return 1.0
    tag_words = set(jieba.lcut(tag)) - STOP_WORDS
    title_words = set(jieba.lcut(title))
    if not tag_words:
        return 0.0
    matched = tag_words & title_words
    if len(matched) == len(tag_words):
        return 0.8
    elif len(matched) >= len(tag_words) * 0.5:
        return 0.5
    return 0.0


def paragraph_hit_rate(tag: str, content: str) -> float:
    """段落命中率"""
    paragraphs = [p.strip() for p in re.split(r'\n\n|\n|<p>|<br>|<br/>', content) if len(p.strip()) > 20]
    if len(paragraphs) < 3:
        return 0.0
    tag_words = set(jieba.lcut(tag)) - STOP_WORDS
    hit = sum(1 for p in paragraphs if any(w in p for w in tag_words))
    return hit / len(paragraphs)


def disambiguate(tag: str, content: str) -> str | None:
    """消歧：返回文章所属义项，若与标签目标义项不符则返回 None"""
    if tag not in DISAMBIGUATION:
        return "default"  # 无需消歧

    senses = DISAMBIGUATION[tag]
    scores = {}
    for sense_name, features in senses.items():
        scores[sense_name] = sum(1 for f in features if f in content)

    if not scores:
        return None

    best_sense = max(scores, key=scores.get)
    return best_sense


def compute_composite_score(tag: str, article: dict) -> float:
    """综合评分"""
    ALPHA, BETA, GAMMA = 0.40, 0.30, 0.30

    sim = article.get("tfidf_sim", 0.0)
    tb = title_boost(tag, article.get("title", ""))
    phr = paragraph_hit_rate(tag, article.get("content_source", ""))
    # Phase 1 暂用段落命中率作为主题集中度的近似
    topic = phr

    return ALPHA * sim + BETA * tb + GAMMA * topic


def recommend_by_tag(tag: str, db, threshold: float = 0.60) -> list[dict]:
    """主入口：根据标签推荐文章"""
    # 1. 从数据库预筛选候选文章
    candidates = db.query(Article).filter(
        Article.status == "published",
        Article.content_source.isnot(None),
        Article.content_source != "",
    ).limit(200).all()

    # 2. 转为字典列表
    articles = [
        {
            "id": a.id,
            "title": a.title,
            "content_source": a.content_source,
            "summary": a.summary or "",
        }
        for a in candidates
    ]

    if not articles:
        return []

    # 3. TF-IDF 相似度计算
    articles = compute_tfidf_score(tag, articles)

    # 4. 综合评分
    for a in articles:
        a["score"] = compute_composite_score(tag, a)

    # 5. 过滤 + 排序
    qualified = [a for a in articles if a["score"] >= threshold]
    qualified.sort(key=lambda x: x["score"], reverse=True)

    return qualified[:2]
```