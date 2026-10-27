# -*- coding: utf-8 -*-
"""智能采编模型：搜索任务、全局新闻线索、任务关系及人工事件分组。"""
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import relationship

from ..database import Base


class SmartCollectTask(Base):
    """一次由编辑或管理员发起的采编搜索任务。"""

    __tablename__ = "smart_collect_tasks"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }

    id = Column(Integer, primary_key=True, index=True, comment="采编任务ID")
    creator_id = Column(
        Integer,
        nullable=True,
        index=True,
        comment="任务创建人ID；旧users表为MyISAM，暂以逻辑关联兼容",
    )
    query = Column(String(200), nullable=False, comment="新闻搜索主题")
    time_range = Column(String(10), nullable=False, comment="时间范围：day/week/month/year")
    max_results = Column(Integer, nullable=False, comment="请求的最大结果数")
    status = Column(String(20), nullable=False, default="running", index=True, comment="running/completed/failed")
    result_count = Column(Integer, nullable=False, default=0, comment="实际保存的任务线索数")
    credits_used = Column(Integer, nullable=False, default=0, comment="Tavily 本次搜索消耗额度")
    error_message = Column(String(500), nullable=True, comment="可安全展示的失败原因")
    created_at = Column(DateTime, nullable=False, default=datetime.now, index=True, comment="任务创建时间")
    finished_at = Column(DateTime, nullable=True, comment="任务完成或失败时间")

    # 真实项目的users表是MyISAM，InnoDB无法建立跨引擎外键；
    # 这里保留ORM只读关系，三张智能采编新表之间仍使用数据库真实外键。
    creator = relationship(
        "User",
        primaryjoin="foreign(SmartCollectTask.creator_id) == User.id",
        viewonly=True,
    )
    clue_links = relationship(
        "SmartCollectTaskClue",
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SmartCollectTaskClue.rank",
    )
    events = relationship(
        "SmartCollectEvent",
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SmartCollectEvent.id",
    )

    def to_dict(self, include_items: bool = False) -> dict:
        """序列化任务；详情接口按需加入本次任务发现的新闻。"""
        data = {
            "id": self.id,
            "creator_id": self.creator_id,
            "creator_name": (
                (self.creator.nickname or self.creator.username)
                if self.creator
                else "已删除用户"
            ),
            "query": self.query,
            "time_range": self.time_range,
            "max_results": self.max_results,
            "status": self.status,
            "result_count": self.result_count,
            "credits_used": self.credits_used,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }
        if include_items:
            data["items"] = [link.to_result_dict() for link in self.clue_links]
        return data


class NewsClue(Base):
    """平台发现的一篇外部新闻；第一版仅按标准化 URL 全局去重。"""

    __tablename__ = "news_clues"
    __table_args__ = (
        UniqueConstraint("url_hash", name="uq_news_clues_url_hash"),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id = Column(Integer, primary_key=True, index=True, comment="新闻线索ID")
    title = Column(String(500), nullable=False, comment="首次发现时的标题")
    url = Column(Text, nullable=False, comment="首次发现时的原始URL")
    normalized_url = Column(Text, nullable=False, comment="用于精确去重的标准化URL")
    # 唯一约束本身会生成索引，无需再建一份重复的普通索引。
    url_hash = Column(String(64), nullable=False, comment="标准化URL的SHA-256")
    source = Column(String(255), nullable=False, default="", comment="首次发现时的来源域名")
    snippet = Column(Text, nullable=False, default="", comment="首次发现时的清洗后内容片段")
    first_seen_at = Column(DateTime, nullable=False, default=datetime.now, index=True, comment="首次发现时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="最近再次发现时间")

    task_links = relationship(
        "SmartCollectTaskClue",
        back_populates="clue",
        passive_deletes=True,
    )
    event_links = relationship(
        "SmartCollectEventClue",
        back_populates="clue",
        passive_deletes=True,
    )
    content_record = relationship(
        "NewsClueContent",
        back_populates="clue",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class SmartCollectTaskClue(Base):
    """任务与新闻的关联；自动分数、人工标签和排名都只属于本次任务。"""

    __tablename__ = "smart_collect_task_clues"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }

    task_id = Column(
        Integer,
        ForeignKey("smart_collect_tasks.id", ondelete="CASCADE"),
        primary_key=True,
        comment="采编任务ID",
    )
    clue_id = Column(
        Integer,
        ForeignKey("news_clues.id", ondelete="CASCADE"),
        primary_key=True,
        comment="新闻线索ID",
    )
    search_score = Column(Float, nullable=False, default=0, comment="该新闻在本次任务中的Tavily搜索相关度")
    semantic_score = Column(
        Float,
        nullable=True,
        comment="该新闻相对于本次采编主题的语义相关度",
    )
    relevance_label = Column(
        SmallInteger,
        nullable=True,
        comment="人工相关性：0明显偏题，1一般相关，2明显相关，NULL未标注",
    )
    rank = Column(Integer, nullable=False, comment="该新闻在本次任务中的原始排名")
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="本次任务发现时间")

    task = relationship("SmartCollectTask", back_populates="clue_links")
    clue = relationship("NewsClue", back_populates="task_links")

    def to_result_dict(self) -> dict:
        """把关联信息和稳定的新闻线索组合成任务详情项。"""
        return {
            "clue_id": self.clue_id,
            "title": self.clue.title,
            "url": self.clue.url,
            "source": self.clue.source,
            "snippet": self.clue.snippet,
            "search_score": self.search_score,
            "semantic_score": self.semantic_score,
            "relevance_label": self.relevance_label,
            "rank": self.rank,
            "created_at": self.created_at,
        }


class SmartCollectEvent(Base):
    """编辑在单个采编任务上下文中人工确认的新闻事件组。"""

    __tablename__ = "smart_collect_events"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }

    id = Column(Integer, primary_key=True, index=True, comment="人工事件ID")
    task_id = Column(
        Integer,
        ForeignKey("smart_collect_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属采编任务ID",
    )
    title = Column(String(200), nullable=False, comment="编辑手工填写的事件标题")
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        comment="最后修改时间",
    )

    task = relationship("SmartCollectTask", back_populates="events")
    clue_links = relationship(
        "SmartCollectEventClue",
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    syntheses = relationship(
        "SmartCollectEventSynthesis",
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SmartCollectEventSynthesis.version",
    )


class SmartCollectEventClue(Base):
    """人工事件与新闻线索的任务内关联。"""

    __tablename__ = "smart_collect_event_clues"
    __table_args__ = (
        # task_id保留事件分组的业务上下文，并在数据库层防止同任务重复分组。
        UniqueConstraint(
            "task_id",
            "clue_id",
            name="uq_smart_collect_event_clues_task_clue",
        ),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    event_id = Column(
        Integer,
        ForeignKey("smart_collect_events.id", ondelete="CASCADE"),
        primary_key=True,
        comment="人工事件ID",
    )
    clue_id = Column(
        Integer,
        ForeignKey("news_clues.id", ondelete="CASCADE"),
        primary_key=True,
        comment="新闻线索ID",
    )
    task_id = Column(
        Integer,
        ForeignKey("smart_collect_tasks.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属采编任务ID，用于任务内唯一约束",
    )
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="加入事件时间")

    event = relationship("SmartCollectEvent", back_populates="clue_links")
    clue = relationship("NewsClue", back_populates="event_links")


class SmartCollectEventSynthesis(Base):
    """一次通过Schema和Grounding校验的事件AI整理版本。"""

    __tablename__ = "smart_collect_event_syntheses"
    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "version",
            name="uq_smart_collect_event_syntheses_event_version",
        ),
        CheckConstraint(
            "status IN ('generated', 'approved', 'rejected')",
            name="ck_smart_collect_event_syntheses_status",
        ),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id = Column(Integer, primary_key=True, index=True, comment="AI事件整理版本ID")
    event_id = Column(
        Integer,
        ForeignKey("smart_collect_events.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属人工事件ID",
    )
    version = Column(Integer, nullable=False, comment="事件内从1递增的版本号")
    status = Column(
        String(20),
        nullable=False,
        default="generated",
        index=True,
        comment="generated/approved/rejected",
    )
    requested_model = Column(String(100), nullable=False, comment="请求的模型名称")
    actual_model = Column(String(100), nullable=False, comment="供应商实际返回的模型名称")
    result_json = Column(JSON, nullable=False, comment="完整EventSynthesisResult JSON")
    evidence_snapshot = Column(
        JSON,
        nullable=False,
        comment="生成时证据快照，仅保存clue_id和content_hash",
    )
    source_count = Column(Integer, nullable=False, comment="生成时有效SOURCE数量")
    total_content_length = Column(Integer, nullable=False, comment="生成时输入正文字符数")
    output_content_length = Column(Integer, nullable=False, comment="模型原始输出字符数")
    input_tokens = Column(Integer, nullable=True, comment="供应商报告的输入Token")
    output_tokens = Column(Integer, nullable=True, comment="供应商报告的输出Token")
    total_tokens = Column(Integer, nullable=True, comment="供应商报告的总Token")
    elapsed_ms = Column(Integer, nullable=False, comment="模型调用耗时毫秒")
    # users表是MyISAM，延续SmartCollectTask.creator_id的逻辑关联方式。
    created_by = Column(Integer, nullable=True, index=True, comment="生成人用户ID")
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="生成时间")
    reviewed_by = Column(Integer, nullable=True, comment="确认或废弃操作用户ID")
    reviewed_at = Column(DateTime, nullable=True, comment="确认或废弃时间")

    event = relationship("SmartCollectEvent", back_populates="syntheses")
    article_source = relationship(
        "SmartCollectArticleSource",
        back_populates="synthesis",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class SmartCollectArticleSource(Base):
    """CMS文稿与已确认AI整理版本之间的最小来源关联。"""

    __tablename__ = "smart_collect_article_sources"
    __table_args__ = (
        UniqueConstraint(
            "article_id",
            name="uq_smart_collect_article_sources_article",
        ),
        UniqueConstraint(
            "synthesis_id",
            name="uq_smart_collect_article_sources_synthesis",
        ),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id = Column(Integer, primary_key=True, index=True, comment="智能采编文稿来源关联ID")
    article_id = Column(
        Integer,
        nullable=False,
        comment="CMS文稿逻辑关联ID；旧articles表为MyISAM，无法建立跨引擎外键",
    )
    synthesis_id = Column(
        Integer,
        ForeignKey("smart_collect_event_syntheses.id", ondelete="CASCADE"),
        nullable=False,
        comment="已确认AI事件整理版本ID",
    )
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="关联创建时间")

    article = relationship(
        "Article",
        primaryjoin="foreign(SmartCollectArticleSource.article_id) == Article.id",
        back_populates="smart_collect_source",
    )
    synthesis = relationship("SmartCollectEventSynthesis", back_populates="article_source")


class NewsClueContent(Base):
    """新闻线索的可复用正文提取结果，与搜索发现信息分表保存。"""

    __tablename__ = "news_clue_contents"
    __table_args__ = (
        UniqueConstraint("clue_id", name="uq_news_clue_contents_clue_id"),
        CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="ck_news_clue_contents_status",
        ),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id = Column(Integer, primary_key=True, index=True, comment="正文记录ID")
    clue_id = Column(
        Integer,
        ForeignKey("news_clues.id", ondelete="CASCADE"),
        nullable=False,
        comment="新闻线索ID，每条线索最多一份正文",
    )
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="pending/completed/failed",
    )
    # MySQL使用LONGTEXT；SQLite测试环境继续使用通用Text。
    content = Column(
        Text().with_variant(LONGTEXT(), "mysql"),
        nullable=True,
        comment="最终清洗后的新闻正文",
    )
    content_hash = Column(String(64), nullable=True, comment="清洗正文的SHA-256")
    fetched_at = Column(DateTime, nullable=True, comment="最近一次正文获取完成时间")
    error_message = Column(String(500), nullable=True, comment="最近一次失败的安全提示")
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="记录创建时间")
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        comment="记录更新时间",
    )

    clue = relationship("NewsClue", back_populates="content_record")
