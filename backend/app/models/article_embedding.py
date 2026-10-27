# -*- coding: utf-8 -*-
"""文稿向量模型：存储文稿"标题+分类"的向量化结果，供个性化推荐召回使用

设计要点（详见 docs/article_embedding_spec.md）：
- 独立于 articles 表：向量是派生数据，有自己的模型版本/重算生命周期；
  分表避免 db.query(Article) 默认全列加载时把向量 BLOB 一起拖进内存
- article_id 既是主键也是外键（级联删除）：一篇文稿恰好一条向量，删文稿自动清理
- embedding 以 float32 小端字节流存储（512 维约 2KB），
  读写辅助函数见 services/embedding_service.py（pack_vector/unpack_vector）
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String

from ..database import Base


class ArticleEmbedding(Base):
    __tablename__ = "article_embeddings"

    # article_id 作主键：一对一关系，同时外键级联删除（删文稿自动清向量）
    article_id = Column(
        Integer,
        ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
        comment="文稿ID（一对一，级联删除）",
    )
    embedding = Column(LargeBinary, nullable=False, comment="向量：float32小端字节流")
    dim = Column(Integer, nullable=False, comment="向量维度（如512）")
    # 模型版本：换嵌入模型/文本配方时 bump 版本并全量重算，旧行由 upsert 覆盖
    model_version = Column(String(50), nullable=False, index=True, comment="嵌入模型版本，如 bge-small-zh-v1")
    # 源文本哈希：标题+分类未变化时跳过重算（见 embedding_service.upsert_embedding 用法）
    source_hash = Column(String(64), nullable=False, comment="源文本（标题+分类）SHA-256哈希")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="最近一次向量化时间")

    def to_dict(self, include_vector: bool = False) -> dict:
        """序列化为字典；向量字节流默认不返回（需经 embedding_service.unpack_vector 解码后使用）"""
        data = {
            "article_id": self.article_id,
            "dim": self.dim,
            "model_version": self.model_version,
            "source_hash": self.source_hash,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
        if include_vector:
            data["embedding"] = self.embedding
        return data