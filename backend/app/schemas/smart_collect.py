# -*- coding: utf-8 -*-
"""智能采编搜索、任务列表与任务详情的请求响应 Schema。"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SmartCollectSearchRequest(BaseModel):
    """第一阶段新闻搜索请求。"""

    query: str = Field(min_length=1, description="新闻搜索主题")
    time_range: Literal["day", "week", "month", "year"] = Field(
        default="week",
        description="新闻时间范围",
    )
    max_results: int = Field(default=10, ge=1, le=10, description="最大结果数量")

    @field_validator("query", mode="before")
    @classmethod
    def strip_query(cls, value):
        """先清理首尾空白，让只包含空格的主题也不能通过校验。"""
        return value.strip() if isinstance(value, str) else value


class SearchResult(BaseModel):
    """项目自己的统一搜索结果，不直接暴露 Tavily 原始数据。"""

    title: str
    url: str
    source: str
    snippet: str
    search_score: float


class SmartCollectSearchResponse(BaseModel):
    """智能采编新闻搜索响应。"""

    query: str
    total: int = Field(ge=0)
    credits_used: int = Field(ge=0)
    items: list[SearchResult]


TaskStatus = Literal["running", "completed", "failed"]
RelevanceLabel = Literal[0, 1, 2]
ContentStatus = Literal["pending", "completed", "failed"]


class SmartCollectTaskItem(BaseModel):
    """任务列表中的一行。"""

    id: int
    creator_id: int | None
    creator_name: str
    query: str
    time_range: Literal["day", "week", "month", "year"]
    max_results: int
    status: TaskStatus
    result_count: int = Field(ge=0)
    credits_used: int = Field(ge=0)
    error_message: str | None
    created_at: datetime
    finished_at: datetime | None


class SmartCollectTaskResult(BaseModel):
    """某次任务保存的一条新闻及其当次搜索上下文。"""

    clue_id: int
    title: str
    url: str
    source: str
    snippet: str
    search_score: float
    semantic_score: float | None = None
    relevance_label: RelevanceLabel | None = None
    rank: int = Field(ge=1)
    created_at: datetime


class SmartCollectTaskDetail(SmartCollectTaskItem):
    """任务详情，新闻按当次 Tavily 排名返回。"""

    items: list[SmartCollectTaskResult]


class SmartCollectTaskCreateResponse(BaseModel):
    message: str
    task_id: int = Field(gt=0)
    status: Literal["running"]
    created_at: datetime


class SmartCollectTaskListResponse(BaseModel):
    items: list[SmartCollectTaskItem]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class SmartCollectRelevanceUpdateRequest(BaseModel):
    """人工相关性标签；NULL表示取消标注。"""

    relevance_label: RelevanceLabel | None

    @field_validator("relevance_label", mode="before")
    @classmethod
    def validate_relevance_label(cls, value):
        """拒绝Pydantic对布尔值、浮点数或字符串的隐式整数转换。"""
        if value is None:
            return None
        if type(value) is not int or value not in {0, 1, 2}:
            raise ValueError("relevance_label只允许0、1、2或null")
        return value


class SmartCollectRelevanceUpdateResponse(BaseModel):
    message: str
    task_id: int
    clue_id: int
    relevance_label: RelevanceLabel | None


class SmartCollectEvaluationLabelCounts(BaseModel):
    """三个固定人工标签的数量，JSON中保持0/1/2键名。"""

    model_config = ConfigDict(populate_by_name=True)

    label_0: int = Field(alias="0", ge=0)
    label_1: int = Field(alias="1", ge=0)
    label_2: int = Field(alias="2", ge=0)


class SmartCollectEvaluationScoreStat(BaseModel):
    count: int = Field(ge=0)
    average: float | None
    minimum: float | None
    maximum: float | None


class SmartCollectEvaluationSemanticScoreStat(SmartCollectEvaluationScoreStat):
    null_count: int = Field(ge=0)


class SmartCollectEvaluationSearchStats(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    label_0: SmartCollectEvaluationScoreStat = Field(alias="0")
    label_1: SmartCollectEvaluationScoreStat = Field(alias="1")
    label_2: SmartCollectEvaluationScoreStat = Field(alias="2")


class SmartCollectEvaluationSemanticStats(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    label_0: SmartCollectEvaluationSemanticScoreStat = Field(alias="0")
    label_1: SmartCollectEvaluationSemanticScoreStat = Field(alias="1")
    label_2: SmartCollectEvaluationSemanticScoreStat = Field(alias="2")


class SmartCollectEvaluationAgreementStat(BaseModel):
    correct: int = Field(ge=0)
    incorrect: int = Field(ge=0)
    ties: int = Field(ge=0)
    total: int = Field(ge=0, description="不含tie的有效pair数")
    rate: float | None = Field(default=None, ge=0, le=1)


class SmartCollectEvaluationRankingAgreement(BaseModel):
    search_score: SmartCollectEvaluationAgreementStat
    semantic_score: SmartCollectEvaluationAgreementStat


class SmartCollectEvaluationSummary(BaseModel):
    total_labeled: int = Field(ge=0)
    label_counts: SmartCollectEvaluationLabelCounts
    search_score_stats: SmartCollectEvaluationSearchStats
    semantic_score_stats: SmartCollectEvaluationSemanticStats
    ranking_agreement: SmartCollectEvaluationRankingAgreement


class SmartCollectEvaluationOutlier(BaseModel):
    task_id: int
    query: str
    clue_id: int
    rank: int = Field(ge=1)
    title: str
    source: str
    search_score: float
    semantic_score: float | None
    relevance_label: RelevanceLabel


class SmartCollectEvaluationOutliers(BaseModel):
    semantic_label_0_high: list[SmartCollectEvaluationOutlier]
    semantic_label_2_low: list[SmartCollectEvaluationOutlier]
    search_label_0_high: list[SmartCollectEvaluationOutlier]
    search_label_2_low: list[SmartCollectEvaluationOutlier]


class SmartCollectSimilarityClue(BaseModel):
    """相似度对中的单条新闻线索（只读快照，不含正文/评分）。

    前端只展示线索身份信息；具体相似度由 Pair 的 similarity_score 给出。
    """
    clue_id: int  # 新闻线索唯一ID（news_clues.id）
    rank: int = Field(ge=1)  # 线索在本次采编任务中的搜索排名，从1开始
    title: str  # 新闻标题
    source: str  # 来源域名（如 xinhuanet.com）


class SmartCollectSimilarityPair(BaseModel):
    """一对新闻线索的语义相似度结果。

    - left/right：按“搜索排名升序”固定左小右大，避免同一对重复返回；
    - similarity_score：[-1,1]，由归一化向量点积得到，越接近1表示语义越相似。
    """
    left: SmartCollectSimilarityClue  # 排名较小的一条线索
    right: SmartCollectSimilarityClue  # 排名较大的一条线索
    similarity_score: float = Field(ge=-1, le=1)  # 归一化向量余弦相似度


class SmartCollectSimilarityResponse(BaseModel):
    """同一采编任务内新闻线索两两相似度分析的响应。"""
    task_id: int  # 采编任务ID
    query: str  # 本次采编任务的新闻主题
    clue_count: int = Field(ge=0)  # 参与分析的线索数量
    pair_count: int = Field(ge=0)  # 理论两两组合数 = n*(n-1)/2
    items: list[SmartCollectSimilarityPair]  # 按相似度从高到低返回，最多 limit 条


class SmartCollectEventClueItem(BaseModel):
    """事件详情中的任务线索快照。"""

    clue_id: int
    rank: int = Field(ge=1)
    title: str
    source: str
    search_score: float
    semantic_score: float | None
    relevance_label: RelevanceLabel | None
    content_status: ContentStatus | None = None
    content_length: int = Field(default=0, ge=0)


class SmartCollectEventDetail(BaseModel):
    id: int
    task_id: int
    title: str
    clue_count: int = Field(ge=0)
    clues: list[SmartCollectEventClueItem]
    created_at: datetime
    updated_at: datetime


class SmartCollectEventListResponse(BaseModel):
    task_id: int
    query: str
    events: list[SmartCollectEventDetail]
    ungrouped_clues: list[SmartCollectEventClueItem]


def _validate_clue_ids(value, minimum: int) -> list[int]:
    """事件接口只接受去重后的正整数线索ID，避免隐式类型转换。"""
    if not isinstance(value, list):
        raise ValueError("clue_ids必须是数组")
    if len(value) < minimum:
        raise ValueError(f"至少选择{minimum}条线索")
    if len(value) > 20:
        raise ValueError("一次最多处理20条线索")
    if any(type(clue_id) is not int or clue_id <= 0 for clue_id in value):
        raise ValueError("clue_ids只能包含正整数")
    if len(value) != len(set(value)):
        raise ValueError("clue_ids不能重复")
    return value


class SmartCollectEventCreateRequest(BaseModel):
    """编辑手工创建事件；一条可靠任务线索即可先建立事件。"""

    title: str = Field(min_length=1, max_length=200)
    clue_ids: list[int]

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("clue_ids", mode="before")
    @classmethod
    def validate_clue_ids(cls, value):
        return _validate_clue_ids(value, minimum=1)


class SmartCollectEventUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value):
        return value.strip() if isinstance(value, str) else value


class SmartCollectEventAddCluesRequest(BaseModel):
    clue_ids: list[int]

    @field_validator("clue_ids", mode="before")
    @classmethod
    def validate_clue_ids(cls, value):
        return _validate_clue_ids(value, minimum=1)


class SmartCollectEventMutationResponse(BaseModel):
    message: str
    event: SmartCollectEventDetail


class SmartCollectEventDeleteResponse(BaseModel):
    message: str


class SmartCollectContentPrepareItem(BaseModel):
    clue_id: int
    title: str
    source: str
    status: ContentStatus
    content_length: int = Field(ge=0)
    error_message: str | None


class SmartCollectContentPrepareResponse(BaseModel):
    event_id: int
    total: int = Field(ge=0)
    completed: int = Field(ge=0)
    failed: int = Field(ge=0)
    items: list[SmartCollectContentPrepareItem]


class SmartCollectContentDetail(BaseModel):
    clue_id: int
    title: str
    source: str
    url: str
    status: ContentStatus
    content: str | None
    content_length: int = Field(ge=0)
    fetched_at: datetime | None
    error_message: str | None


class EventEvidenceSource(BaseModel):
    """未来LLM可以引用的一份已完成、哈希有效的新闻正文。"""

    clue_id: int = Field(gt=0)
    rank: int = Field(ge=1)
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)
    url: str = Field(min_length=1)
    content: str = Field(min_length=1)
    content_length: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    fetched_at: datetime | None


class EventEvidencePack(BaseModel):
    """某个人工事件的实时证据包，是未来事件整理唯一允许读取的事实来源。"""

    task_id: int = Field(gt=0)
    task_query: str = Field(min_length=1)
    event_id: int = Field(gt=0)
    event_title: str = Field(min_length=1)
    source_count: int = Field(ge=0)
    completed_source_count: int = Field(ge=0)
    total_content_length: int = Field(ge=0)
    sources: list[EventEvidenceSource]

    @model_validator(mode="after")
    def validate_totals(self):
        if self.completed_source_count != len(self.sources):
            raise ValueError("completed_source_count必须等于sources数量")
        if self.completed_source_count > self.source_count:
            raise ValueError("有效正文数量不能超过事件成员数量")
        if self.total_content_length != sum(item.content_length for item in self.sources):
            raise ValueError("total_content_length必须等于所有正文长度之和")
        return self


def _validate_source_ids(value, minimum: int) -> list[int]:
    if not isinstance(value, list) or len(value) < minimum:
        raise ValueError(f"source_clue_ids至少需要{minimum}个来源")
    if any(type(clue_id) is not int or clue_id <= 0 for clue_id in value):
        raise ValueError("source_clue_ids只能包含正整数")
    if len(value) != len(set(value)):
        raise ValueError("source_clue_ids不能重复")
    return value


class CoreFact(BaseModel):
    text: str = Field(min_length=1)
    source_clue_ids: list[int]

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("source_clue_ids", mode="before")
    @classmethod
    def validate_source_ids(cls, value):
        return _validate_source_ids(value, minimum=1)


class EvidenceConflict(BaseModel):
    description: str = Field(min_length=1)
    source_clue_ids: list[int]

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("source_clue_ids", mode="before")
    @classmethod
    def validate_source_ids(cls, value):
        return _validate_source_ids(value, minimum=2)


def _validate_string_list(value, field_name: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{field_name}必须是非空字符串数组")
    return [item.strip() for item in value]


class EventSynthesisResult(BaseModel):
    """未来Grounded LLM必须返回的精简结构；当前阶段只定义、不生成。"""

    summary: str = Field(min_length=1)
    core_facts: list[CoreFact] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    time_info: list[str] = Field(default_factory=list)
    conflicts: list[EvidenceConflict] = Field(default_factory=list)
    insufficient_evidence: list[str] = Field(default_factory=list)

    @field_validator("summary", mode="before")
    @classmethod
    def strip_summary(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("entities", "time_info", "insufficient_evidence", mode="before")
    @classmethod
    def validate_string_lists(cls, value, info):
        return _validate_string_list(value, info.field_name)


class EventSynthesisPrompt(BaseModel):
    """未来模型调用的输入契约，系统规则与来源材料必须分开传递。"""

    system_message: str = Field(min_length=1)
    user_message: str = Field(min_length=1)


class EventEvidenceSnapshotItem(BaseModel):
    """持久化证据身份，以及读取时核对到的当前正文哈希。"""

    clue_id: int = Field(gt=0)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_content_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    content_changed: bool = False


class SmartCollectSynthesisArticleInfo(BaseModel):
    """已由AI整理版本创建的CMS草稿信息。"""

    id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    status: str = Field(min_length=1)
    created_at: datetime


class SmartCollectSynthesisSummary(BaseModel):
    """AI事件整理历史列表项；不重复传输完整模型结果。"""

    id: int = Field(gt=0)
    event_id: int = Field(gt=0)
    version: int = Field(gt=0)
    status: Literal["generated", "approved", "rejected"]
    requested_model: str = Field(min_length=1)
    actual_model: str = Field(min_length=1)
    source_count: int = Field(ge=1)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    elapsed_ms: int = Field(ge=0)
    created_by: int | None = Field(default=None, gt=0)
    created_at: datetime
    reviewed_by: int | None = Field(default=None, gt=0)
    reviewed_at: datetime | None = None
    article: SmartCollectSynthesisArticleInfo | None = None


class SmartCollectSynthesisResponse(SmartCollectSynthesisSummary):
    """已持久化且重新通过Pydantic校验的AI事件整理详情。"""

    event_title: str = Field(min_length=1)
    total_content_length: int = Field(ge=1)
    output_content_length: int = Field(ge=1)
    # 兼容3D-1B前端字段；值始终等于actual_model/elapsed_ms。
    model: str = Field(min_length=1)
    duration_ms: int = Field(ge=0)
    result: EventSynthesisResult
    evidence_snapshot: list[EventEvidenceSnapshotItem] = Field(min_length=1)


class SmartCollectSynthesisListResponse(BaseModel):
    """单个人工事件的全部AI整理版本，按版本倒序返回。"""

    event_id: int = Field(gt=0)
    items: list[SmartCollectSynthesisSummary] = Field(default_factory=list)


class SmartCollectArticleCreateResponse(BaseModel):
    """已确认AI整理转换为CMS草稿后的响应。"""

    message: str = Field(min_length=1)
    synthesis_id: int = Field(gt=0)
    article: SmartCollectSynthesisArticleInfo
