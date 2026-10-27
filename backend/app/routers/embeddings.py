# -*- coding: utf-8 -*-
"""文稿向量化接口：全量文稿向量化入库（个性化推荐召回链路，见 docs/article_embedding_spec.md）

流程：查询全部文稿(id/标题/分类) → 拼接"分类：标题"文本列表 → 调用
aiVectorizationModel.predict.predict_fun 批量向量化(BAAI_bge-small-zh, 512维)
→ 连同文稿 id 等信息写入 article_embeddings 表。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.deps import require_roles
from ..database import get_db
from ..models.article import Article
from ..models.user import User
from ..services import embedding_service

router = APIRouter(prefix="/embeddings", tags=["文稿向量化"])

# 模型版本统一取 embedding_service.MODEL_VERSION（单篇钩子与全量回填接口共用）


@router.post("/vectorize", summary="全量文稿向量化入库（仅管理员）")
def vectorize_all_articles(db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    """全量向量化并写入 article_embeddings（幂等：已有记录覆盖更新）。

    - 文本拼接规则：多分类用","连接，格式"分类：标题"；无分类时仅用标题
    - 模型在首次调用时加载（aiVectorizationModel.predict 模块级单例，加载后常驻）
    - 一个事务：全部 upsert 成功后统一 commit
    """
    articles = db.query(Article).all()
    if not articles:
        raise HTTPException(404, "没有可向量化的文稿")

    # 1. 组装向量化文本列表（与 articles 顺序一一对应；规则统一见 embedding_service.build_article_text）
    texts = [embedding_service.build_article_text(a) for a in articles]

    # 2. 批量向量化（惰性导入：避免后端启动时就加载模型拖慢启动）
    from ..aiVectorizationModel.predict import predict_fun
    vectors = predict_fun(texts)
    if len(vectors) != len(articles):
        raise HTTPException(500, f"向量化结果数量异常：期望 {len(articles)} 条，实际 {len(vectors)} 条")

    # 3. 逐篇写入 article_embeddings（source_hash 记录本次文本指纹，供后续增量重算判断）
    for article, text, vector in zip(articles, texts, vectors):
        embedding_service.upsert_embedding(
            db,
            article.id,
            vector,
            embedding_service.MODEL_VERSION,
            embedding_service.hash_source_text(text),
        )
    db.commit()

    return {
        "message": f"向量化完成，共写入 {len(articles)} 篇文稿",
        "total": len(articles),
        "model_version": embedding_service.MODEL_VERSION,
        "stats": embedding_service.stats(db),
    }


@router.get("/article/{article_id}", summary="查询文稿向量化信息（仅管理员）")
def get_article_embedding(
    article_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """查询单篇文稿的向量化元信息（不返回向量字节流）；未向量化返回 404"""
    row = embedding_service.get_embedding(db, article_id)
    if not row:
        raise HTTPException(404, "该文稿尚未向量化")
    return {"message": "查询成功", "embedding": row.to_dict()}