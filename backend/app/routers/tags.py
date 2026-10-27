# -*- coding: utf-8 -*-
"""标签推荐接口：根据标签名称推荐关联文章（公开接口，无需登录）

GET /api/tags/{tag_name}/recommend
  - 本地数据库优先，综合评分 ≥ 0.60 的文章
  - 权威网站补充（gov.cn、人民网、新华网等）
  - 百度百科始终在最后一条兜底
  - 最多返回 5 条
"""
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.tag_recommend_service import recommend_by_tag, search_external
from ..services.settings_service import get_setting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tags", tags=["标签推荐"])


@router.get("/{tag_name}/recommend", summary="标签推荐关联文章")
def get_tag_recommend(
    tag_name: str,
    exclude_article_id: int = Query(None, description="排除的文章 ID（当前文章不推荐自身）"),
    db: Session = Depends(get_db),
):
    """根据标签名称推荐关联文章（公开接口）

    返回最多 5 条，站内文章在前，权威来源次之，百度百科在最后。
    返回格式：
    {
      "tag": "住房消费",
      "items": [
        {
          "id": 123,              // 本地文章有 id，external 无此字段
          "title": "文章标题",
          "score": 0.87,          // 本地文章有 score
          "summary": "摘要...",
          "url": "/article/123",
          "source": "local"       // local | authority | baike
        }
      ],
      "total": 5,
      "message": ""
    }
    """
    combined = []

    if not get_setting(db, "portal_ai_reading_enabled", default=True):
        raise HTTPException(403, "门户 AI 阅读功能已关闭")

    # ── 第一优先级：本地数据库匹配 ──
    try:
        local_items = recommend_by_tag(tag_name, db, exclude_article_id=exclude_article_id)
    except Exception as e:
        logger.error(f"本地推荐异常（标签「{tag_name}」）：{e}")
        local_items = []

    for item in local_items:
        combined.append({
            **item,
            "source": "local",
        })

    # ── 第二优先级：外部权威来源检索（百度百科在最后）──
    try:
        ext_items = search_external(tag_name)
    except Exception as e:
        logger.error(f"外部检索异常：{e}")
        ext_items = []

    seen_urls = {item.get("url", "") for item in combined}
    for item in ext_items:
        url = item.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        combined.append({
            "title": item["title"],
            "url": item["url"],
            "summary": item.get("summary", ""),
            "source": "baike" if item.get("source_name") == "百度百科" else "authority",
        })

    MAX_TOTAL = 5
    combined = combined[:MAX_TOTAL]

    if combined:
        source_types = list(set(item.get("source", "") for item in combined))
        return {
            "tag": tag_name,
            "items": combined,
            "total": len(combined),
            "message": "",
        }

    return {
        "tag": tag_name,
        "items": [],
        "total": 0,
        "message": f"暂未找到与「{tag_name}」相关的推荐内容",
    }
