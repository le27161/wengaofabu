# -*- coding: utf-8 -*-
"""分发渠道接口：渠道增删改查 + 渠道 RSS（最近7天勾选本渠道的已发布文稿）"""
from datetime import datetime, timedelta
from email.utils import format_datetime
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..core.deps import require_roles
from ..database import get_db
from ..models.article import Article, article_channels
from ..models.channel import Channel
from ..schemas.channel import ChannelIn

router = APIRouter(prefix="/channels", tags=["分发渠道"])


def _channel_counts(db: Session, status_filter=None) -> dict:
    """统计每个渠道下的已发布文稿数量"""
    query = (
        db.query(article_channels.c.channel_id, func.count(article_channels.c.article_id))
        .join(Article, Article.id == article_channels.c.article_id)
    )
    if status_filter:
        query = query.filter(Article.status == status_filter)
    return dict(query.group_by(article_channels.c.channel_id).all())


@router.get("", summary="渠道列表（写稿勾选用，仅启用渠道）")
def public_channels(db: Session = Depends(get_db)):
    channels = db.query(Channel).filter(Channel.status == "active").order_by(Channel.sort_order).all()
    counts = _channel_counts(db, "published")
    return {"items": [c.to_dict(counts.get(c.id, 0)) for c in channels]}


@router.get("/manage", summary="后台渠道管理列表（含停用渠道与文稿数）")
def manage_channels(db: Session = Depends(get_db), admin=Depends(require_roles("admin"))):
    channels = db.query(Channel).order_by(Channel.sort_order).all()
    counts = _channel_counts(db)
    return {"items": [c.to_dict(counts.get(c.id, 0)) for c in channels]}


@router.post("", summary="创建渠道")
def create_channel(body: ChannelIn, db: Session = Depends(get_db), admin=Depends(require_roles("admin"))):
    if db.query(Channel).filter(Channel.slug == body.slug).first():
        raise HTTPException(400, "渠道标识已存在")
    channel = Channel(
        name=body.name,
        slug=body.slug,
        description=body.description,
        sort_order=body.sort_order,
        status=body.status,
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return {"message": "创建成功", "channel": channel.to_dict()}


@router.put("/{channel_id}", summary="编辑渠道")
def update_channel(channel_id: int, body: ChannelIn, db: Session = Depends(get_db), admin=Depends(require_roles("admin"))):
    channel = db.get(Channel, channel_id)
    if not channel:
        raise HTTPException(404, "渠道不存在")
    if db.query(Channel).filter(Channel.slug == body.slug, Channel.id != channel_id).first():
        raise HTTPException(400, "渠道标识已存在")
    # 基础渠道保护：标识与状态不可更改（保证所有文稿始终包含可用门户渠道）
    if channel.is_default:
        if body.slug != channel.slug:
            raise HTTPException(400, "基础渠道标识不可更改")
        if body.status != "active":
            raise HTTPException(400, "基础渠道不能停用")
    channel.name = body.name
    channel.slug = body.slug
    channel.description = body.description
    channel.sort_order = body.sort_order
    channel.status = body.status
    db.commit()
    db.refresh(channel)
    return {"message": "保存成功", "channel": channel.to_dict()}


@router.delete("/{channel_id}", summary="删除渠道（基础渠道禁止删除）")
def delete_channel(channel_id: int, db: Session = Depends(get_db), admin=Depends(require_roles("admin"))):
    channel = db.get(Channel, channel_id)
    if not channel:
        raise HTTPException(404, "渠道不存在")
    if channel.is_default:
        raise HTTPException(400, "基础渠道不能删除，所有文稿默认分发到该渠道")
    db.delete(channel)
    db.commit()
    return {"message": "删除成功"}


@router.get("/{channel_id}/rss", summary="渠道 RSS（最近7天勾选本渠道的已发布文稿）")
def channel_rss(channel_id: int, db: Session = Depends(get_db)):
    """生成 RSS 2.0 XML，供第三方平台订阅导入；只包含最近7天发布且勾选了本渠道的文稿。"""
    channel = db.get(Channel, channel_id)
    if not channel or channel.status != "active":
        raise HTTPException(404, "渠道不存在或已停用")

    since = datetime.now() - timedelta(days=7)
    articles = (
        db.query(Article)
        .join(article_channels, Article.id == article_channels.c.article_id)
        .filter(
            article_channels.c.channel_id == channel_id,
            Article.status == "published",
            Article.published_at >= since,
        )
        .order_by(Article.published_at.desc())
        .all()
    )

    base_url = settings.BASE_URL.rstrip("/")
    rss_url = f"{base_url}/api/channels/{channel_id}/rss"
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "<channel>",
        f"<title>{escape(channel.name)} - 文稿发布</title>",
        f"<link>{escape(base_url)}</link>",
        f"<description>{escape(channel.description or '文稿发布系统分发渠道')}</description>",
        f"<lastBuildDate>{format_datetime(datetime.now().astimezone())}</lastBuildDate>",
        f'<atom:link href="{escape(rss_url)}" rel="self" type="application/rss+xml"/>',
    ]
    for a in articles:
        item_link = f"{base_url}/article/{a.id}"
        description = a.content or a.summary or ""
        # 内容为 HTML，用 CDATA 包裹；转义可能的 CDATA 结束符避免破坏 XML
        description_cdata = description.replace("]]>", "]]]]><![CDATA[>")
        lines.append("<item>")
        lines.append(f"<title>{escape(a.title)}</title>")
        lines.append(f"<link>{escape(item_link)}</link>")
        lines.append(f'<guid isPermaLink="false">article-{a.id}</guid>')
        lines.append(f"<pubDate>{format_datetime(a.published_at.astimezone())}</pubDate>")
        if a.author:
            lines.append(f"<author>{escape(a.author.nickname or a.author.username)}</author>")
        lines.append(f"<category>{escape(channel.name)}</category>")
        lines.append(f"<description><![CDATA[{description_cdata}]]></description>")
        lines.append("</item>")
    lines.append("</channel>")
    lines.append("</rss>")

    return Response(content="\n".join(lines), media_type="application/rss+xml; charset=utf-8")
