# -*- coding: utf-8 -*-
"""模型包：集中导入所有模型，确保 Base.metadata 能发现全部表"""
from .user import User
from .category import Category
from .channel import Channel, article_channels
from .article import Article, article_categories
from .article_embedding import ArticleEmbedding
from .review import ArticleReview
from .resource import Resource
from .portal import PortalModule
from .event import EventLog
from .interaction import UserAction
from .preference import UserPreference
from .anonymous_action import AnonymousAction
from .system_setting import SystemSetting
from .dify_workflow import DifyWorkflow
from .view_history import ViewHistory
from .ai_call import AICallLog
from .ai_task import AITask
from .ai_correction import AICorrection
from .article_keyword import ArticleKeyword
from .article_tags import ArticleMainTag, ArticleSubTag
from .comment import Comment
from .checkin import CheckinLog
from .smart_collect import (
    NewsClue,
    NewsClueContent,
    SmartCollectArticleSource,
    SmartCollectEvent,
    SmartCollectEventClue,
    SmartCollectEventSynthesis,
    SmartCollectTask,
    SmartCollectTaskClue,
)

__all__ = [
    "User", "Category", "Article", "article_categories", "ArticleReview",
    "Channel", "article_channels",
    "Resource", "PortalModule", "EventLog", "UserAction", "UserPreference", "AnonymousAction",
    "SystemSetting", "DifyWorkflow", "ViewHistory", "AICallLog", "AITask", "AICorrection",
    "Comment", "CheckinLog", "ArticleEmbedding",
    "ArticleKeyword",
    "ArticleMainTag", "ArticleSubTag",
    "SmartCollectTask", "NewsClue", "NewsClueContent", "SmartCollectTaskClue",
    "SmartCollectArticleSource", "SmartCollectEvent", "SmartCollectEventClue",
    "SmartCollectEventSynthesis",
]
