# -*- coding: utf-8 -*-
"""文章关键词接口：基于 article_main_tags / article_sub_tags 双表读写

- 关键词来自数据库预存，前端直接读取展示，无需手动触发 AI。
- 新文章入库时 AI 自动提取并写入双表（见 articles.py 的 create_article）。
- 保留 POST 接口供管理员手动重新提取。
"""
import asyncio
import re
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.deps import get_current_user
from ..database import get_db
from ..models.article import Article
from ..models.article_tags import ArticleMainTag, ArticleSubTag
from ..models.user import User
from ..services.ai_service import extract_keywords_via_ai, explain_tag_streaming, AIServiceError
from ..services.settings_service import get_setting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/articles", tags=["文稿关键词"])


def _build_keywords_response(main_tags: list[ArticleMainTag]) -> list[dict]:
    """从双表数据构建前端需要的 keywords 响应格式

    sort_order 规则：1 最靠近主标签，N 最远。
    关系已按 sort_order ASC 排序，前端需要由远到近展示，故反转。
    """
    result = []
    for mt in main_tags:
        sub_names = [st.tag_name for st in reversed(mt.sub_tags)]
        chain = sub_names + [mt.tag_name]
        result.append({
            "id": mt.id,
            "keyword": mt.tag_name,
            "category": mt.category,
            "chain": chain,
            "sub_tags": [
                {"id": st.id, "tag_name": st.tag_name, "sort_order": st.sort_order}
                for st in mt.sub_tags
            ],
        })
    return result


def _delete_article_keywords(db: Session, article_id: int) -> None:
    """删除文章已有的主/副关键词（正文变更后重新提取前调用）"""
    sub_ids = (
        db.query(ArticleSubTag.id)
        .join(ArticleMainTag)
        .filter(ArticleMainTag.article_id == article_id)
        .subquery()
    )
    db.query(ArticleSubTag).filter(ArticleSubTag.id.in_(sub_ids)).delete(synchronize_session=False)
    db.query(ArticleMainTag).filter(ArticleMainTag.article_id == article_id).delete()


def extract_and_save_keywords(article_id: int, content: str, replace: bool = False) -> list[dict]:
    """提取文章关键词并写入双表（供 articles.py 后台任务调用）

    返回前端可直接使用的 keywords 列表；失败时只记日志不抛异常。
    内部创建独立 session，避免后台任务 session 生命周期问题。
    """
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        if not content or not content.strip():
            return []
        try:
            ai_result = asyncio.run(_extract_with_retry(content))
        except Exception as e:
            logger.warning(f"关键词提取失败（文章 {article_id}）：{e}")
            return []

        category = ai_result.get("category", "")
        main_tags_data = ai_result.get("main_tags", [])
        if not main_tags_data:
            logger.info(f"文章 {article_id} 无有效主标签，跳过写入")
            return []

        if replace and main_tags_data:
            _delete_article_keywords(db, article_id)

        result = []
        for i, kw in enumerate(main_tags_data):
            tag_name = kw.get("name", "")
            if not tag_name:
                continue
            main_tag = ArticleMainTag(
                article_id=article_id,
                tag_name=tag_name,
                category=category,
                sort_order=i,
            )
            db.add(main_tag)
            db.flush()  # 获取 main_tag.id

            prerequisites = kw.get("prerequisites", [])
            for j, pre in enumerate(prerequisites):
                sub_tag = ArticleSubTag(
                    main_tag_id=main_tag.id,
                    tag_name=pre,
                    sort_order=len(prerequisites) - j,  # 1=最靠近主标签，N=最远
                )
                db.add(sub_tag)

            result.append({
                "id": main_tag.id,
                "keyword": main_tag.tag_name,
                "category": category,
                "chain": prerequisites + [main_tag.tag_name],
                "sub_tags": [
                    {"id": -1, "tag_name": pre, "sort_order": j + 1}
                    for j, pre in enumerate(prerequisites)
                ],
            })

        db.commit()
        logger.info(f"关键词提取成功（文章 {article_id}）：{len(result)} 个主关键词，分类：{category}")
        return result
    finally:
        db.close()


def extract_keywords_by_article_id(article_id: int, replace: bool = False) -> list[dict]:
    """按文稿 ID 读取正文后异步提取关键词（供智能采编/Excel 导入等后台任务调用）"""
    from ..database import SessionLocal
    from ..models.article import Article
    from ..services.text_utils import strip_html

    db = SessionLocal()
    try:
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            return []
        content = article.content_source or strip_html(article.content or "")
    finally:
        db.close()
    return extract_and_save_keywords(article_id, content, replace=replace)


async def _extract_with_retry(content: str, max_retries: int = 2) -> dict:
    """带重试的 AI 关键词提取，返回 {"category": "...", "main_tags": [...]}"""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return await extract_keywords_via_ai(content)
        except AIServiceError as e:
            last_error = e
            if attempt < max_retries:
                await asyncio.sleep(2)
    raise last_error


# ── 公开接口 ──

@router.get("/{article_id}/keywords", summary="获取文章关键词")
def get_keywords(
    article_id: int,
    db: Session = Depends(get_db),
):
    """获取已提取的文章关键词及前置知识链（公开接口，无需登录）

    数据来源：article_main_tags + article_sub_tags 双表。
    """
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(404, "文稿不存在")
    if not get_setting(db, "portal_ai_reading_enabled", default=True):
        raise HTTPException(403, "门户 AI 阅读功能已关闭")

    main_tags = (
        db.query(ArticleMainTag)
        .filter(ArticleMainTag.article_id == article_id)
        .order_by(ArticleMainTag.sort_order)
        .all()
    )

    if not main_tags:
        return {"keywords": [], "message": "该文稿暂无关键词"}

    return {"keywords": _build_keywords_response(main_tags)}


@router.get("/{article_id}/keywords/explain", summary="流式解释标签")
def explain_tag(
    article_id: int,
    tag: str = Query(..., description="要解释的标签名称"),
):
    """流式返回 AI 对某个标签的通俗解释（SSE 格式，无需登录）"""
    db = next(get_db())
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(404, "文稿不存在")
    if not get_setting(db, "portal_ai_reading_enabled", default=True):
        raise HTTPException(403, "门户 AI 阅读功能已关闭")

    def generate():
        try:
            for chunk in explain_tag_streaming(tag):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except AIServiceError as e:
            yield f"data: [ERROR] {e}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── 管理接口（需登录）──

@router.post("/{article_id}/keywords", summary="手动重新提取关键词（管理员）")
async def manual_extract_keywords(
    article_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """手动触发 AI 重新提取关键词并写入双表。先删除旧数据再生成。"""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(404, "文稿不存在")

    # 使用纯文本内容
    content = article.content_source
    if not content:
        from ..services.text_utils import strip_html
        content = strip_html(article.content or "")
    if not content or not content.strip():
        raise HTTPException(400, "文稿内容为空，无法提取关键词")

    # 删除旧数据（子标签通过 join 主标签表删除）
    sub_ids = db.query(ArticleSubTag.id).join(ArticleMainTag).filter(
        ArticleMainTag.article_id == article_id
    ).subquery()
    db.query(ArticleSubTag).filter(ArticleSubTag.id.in_(sub_ids)).delete(synchronize_session=False)
    db.query(ArticleMainTag).filter(ArticleMainTag.article_id == article_id).delete()

    try:
        ai_result = await _extract_with_retry(content)
    except AIServiceError as e:
        db.commit()  # 提交删除操作
        raise HTTPException(500, f"AI 关键词提取失败：{e}")

    category = ai_result.get("category", "")
    main_tags_data = ai_result.get("main_tags", [])
    if not main_tags_data:
        db.commit()
        return {"message": "AI 未提取到有效关键词", "keywords": []}

    saved = []
    for i, kw in enumerate(main_tags_data):
        tag_name = kw.get("name", "")
        if not tag_name:
            continue
        main_tag = ArticleMainTag(
            article_id=article_id,
            tag_name=tag_name,
            category=category,
            sort_order=i,
        )
        db.add(main_tag)
        db.flush()

        prerequisites = kw.get("prerequisites", [])
        for j, pre in enumerate(prerequisites):
            db.add(ArticleSubTag(
                main_tag_id=main_tag.id,
                tag_name=pre,
                sort_order=len(prerequisites) - j,  # 1=最靠近主标签，N=最远
            ))

        saved.append({
            "id": main_tag.id,
            "keyword": main_tag.tag_name,
            "category": category,
            "chain": prerequisites + [main_tag.tag_name],
            "sub_tags": [
                {"id": -1, "tag_name": pre, "sort_order": j + 1}
                for j, pre in enumerate(prerequisites)
            ],
        })

    db.commit()

    return {
        "message": f"成功提取 {len(saved)} 个关键词（分类：{category}）",
        "keywords": saved,
    }


@router.delete("/{article_id}/keywords", summary="删除文章关键词")
def delete_keywords(
    article_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除文章的所有关键词（需要登录）"""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(404, "文稿不存在")

    deleted_sub = (
        db.query(ArticleSubTag)
        .filter(ArticleSubTag.id.in_(
            db.query(ArticleSubTag.id).join(ArticleMainTag).filter(
                ArticleMainTag.article_id == article_id
            ).subquery()
        ))
        .delete(synchronize_session=False)
    )
    deleted_main = (
        db.query(ArticleMainTag)
        .filter(ArticleMainTag.article_id == article_id)
        .delete()
    )
    db.commit()
    return {"message": f"已删除 {deleted_main} 个主关键词和 {deleted_sub} 个分支关键词"}
