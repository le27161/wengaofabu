# -*- coding: utf-8 -*-
"""CMS文稿草稿的共享创建规则；事务提交由调用方统一负责。"""
from sqlalchemy.orm import Session

from ..models.article import Article
from ..models.category import Category
from ..models.channel import Channel
from ..models.user import User
from ..schemas.article import ArticleIn
from .text_utils import strip_html


class ArticleService:
    """集中维护普通创建与智能采编转换共同使用的草稿规则。"""

    @staticmethod
    def apply_categories(
        db: Session,
        article: Article,
        category_ids: list[int],
    ) -> None:
        ids = list(dict.fromkeys(category_ids))
        article.categories = (
            db.query(Category).filter(Category.id.in_(ids)).all() if ids else []
        )

    @staticmethod
    def apply_channels(
        db: Session,
        article: Article,
        channel_ids: list[int],
    ) -> None:
        """重置文稿分发渠道：基础渠道始终包含且不可移除。"""
        default = db.query(Channel).filter(Channel.is_default.is_(True)).first()
        ids = list(dict.fromkeys([*(channel_ids or []), default.id])) if default else list(dict.fromkeys(channel_ids or []))
        channels = db.query(Channel).filter(Channel.id.in_(ids), Channel.status == "active").all() if ids else []
        if default and default not in channels:
            channels.append(default)
        article.channels = channels

    @classmethod
    def create_draft(
        cls,
        db: Session,
        user: User,
        body: ArticleIn,
    ) -> Article:
        """创建但不提交草稿，使上层可把其他关联写入同一事务。"""
        article = Article(
            title=body.title,
            summary=body.summary,
            content=body.content,
            content_source=body.content_source or strip_html(body.content),
            cover_url=body.cover_url,
            author_id=user.id,
            status="draft",
        )
        db.add(article)
        db.flush()
        cls.apply_categories(db, article, body.category_ids)
        cls.apply_channels(db, article, body.channel_ids)
        return article
