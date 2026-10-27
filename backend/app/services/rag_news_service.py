# -*- coding: utf-8 -*-
"""新闻系统与 KnowledgeHub RAG 服务的 HTTP 集成。

本模块不处理新闻数据库事务，只在文章已成功发布、下线或删除后调用。
调用失败仅记录日志，不能回滚新闻状态机；后续可按 article_id 重试同步。
"""
import logging
from datetime import datetime

import httpx

from ..config import settings
from ..database import SessionLocal
from ..models.article import Article
from .text_utils import strip_html

logger = logging.getLogger(__name__)


class RAGNewsServiceError(Exception):
    """RAG 服务未启用、不可连接或返回异常时抛出。"""


def is_rag_enabled() -> bool:
    """集中判断开关，保证所有业务入口行为一致。"""
    return bool(settings.RAG_ENABLED)


def sync_published_article(article_id: int) -> None:
    """重新打开数据库读取文章并同步到 RAG，适合放进 BackgroundTasks。"""
    if not is_rag_enabled():
        return
    db = SessionLocal()
    try:
        article = db.get(Article, article_id)
        if not article:
            raise RAGNewsServiceError("文稿不存在，无法同步到新闻知识库")
        _sync_article(article)
    finally:
        db.close()


def _sync_article(article: Article) -> None:
    """使用当前 Session 中的文章对象构造入库请求。"""
    if article.status != "published":
        raise RAGNewsServiceError("只有已发布文稿可以同步到新闻知识库")

    content = (article.content_source or strip_html(article.content or "")).strip()
    if not content:
        raise RAGNewsServiceError("文稿正文为空，无法同步到新闻知识库")

    payload = {
        "article_id": str(article.id),
        "title": article.title,
        "content": content,
        "category": _primary_category_name(article),
        "published_at": _format_datetime(article.published_at),
        "url": _article_url(article.id),
    }
    _request("POST", "/news/articles/index", json=payload)
    logger.info("已同步新闻到 RAG，article_id=%s", article.id)


def remove_article_from_rag(article_id: int) -> None:
    """从 RAG 中删除一篇下线或已删除新闻的所有向量 Chunk。"""
    if not is_rag_enabled():
        return
    _request("DELETE", f"/news/articles/{article_id}")
    logger.info("已从 RAG 清理新闻，article_id=%s", article_id)


def ask_news_assistant(question: str, category: str | None = None) -> dict:
    """向独立 RAG 服务提问，返回 answer 和可点击的新闻来源。"""
    if not is_rag_enabled():
        raise RAGNewsServiceError("AI 新闻助手尚未启用")

    payload = {
        "question": question.strip(),
        "category": category.strip() if category else None,
        "retrieve_top_k": 10,
        "top_n": 3,
        "max_distance": 0.45,
    }
    result = _request("POST", "/news/chat", json=payload)
    if not isinstance(result, dict):
        raise RAGNewsServiceError("RAG 服务返回格式异常")
    return result


def sync_published_article_safely(article_id: int) -> None:
    """后台任务入口：RAG 故障不能影响已成功发布的新闻。"""
    try:
        sync_published_article(article_id)
    except RAGNewsServiceError as exc:
        logger.warning("新闻同步 RAG 失败，article_id=%s，原因：%s", article_id, exc)


def remove_article_from_rag_safely(article_id: int) -> None:
    """后台任务入口：清理失败只记录，避免阻塞下线/删除业务。"""
    try:
        remove_article_from_rag(article_id)
    except RAGNewsServiceError as exc:
        logger.warning("新闻从 RAG 清理失败，article_id=%s，原因：%s", article_id, exc)


def _request(method: str, path: str, json: dict | None = None) -> dict:
    url = f"{settings.RAG_BASE_URL.rstrip('/')}{path}"
    try:
        with httpx.Client(timeout=settings.RAG_TIMEOUT) as client:
            response = client.request(method, url, json=json)
    except httpx.TimeoutException:
        raise RAGNewsServiceError(f"RAG 服务调用超时（{settings.RAG_TIMEOUT}s）") from None
    except httpx.RequestError:
        raise RAGNewsServiceError("无法连接 RAG 服务，请检查 RAG_BASE_URL 和服务状态") from None

    if response.status_code >= 400:
        raise RAGNewsServiceError(f"RAG 服务返回 HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError:
        raise RAGNewsServiceError("RAG 服务返回了非 JSON 响应") from None


def _primary_category_name(article: Article) -> str | None:
    """当前 RAG 接口仅支持一个分类，按文章已关联栏目的第一项传递。"""
    return article.categories[0].name if article.categories else None


def _article_url(article_id: int) -> str:
    path = f"/article/{article_id}"
    return f"{settings.NEWS_PUBLIC_BASE_URL.rstrip('/')}{path}" if settings.NEWS_PUBLIC_BASE_URL else path


def _format_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
