# -*- coding: utf-8 -*-
"""初始化数据库：自动建库（若不存在）+ 建表 + 表结构兼容迁移 + 写入种子数据

用法：在 backend 目录下执行 python init_db.py
"""
import json
import os

from app.database import Base, engine, SessionLocal, ensure_database, ensure_schema_compat
from app.models import (  # noqa: F401
    user, category, channel, article, article_embedding, review, resource, portal, event, interaction,
    anonymous_action, preference, system_setting, dify_workflow, view_history, ai_call, ai_task,
    ai_correction, article_keyword, article_tags, comment, checkin, smart_collect,
)
from app.core.security import hash_password
from app.models.user import User
from app.models.category import Category
from app.models.channel import Channel
from app.models.article import article_categories
from app.models.portal import PortalModule
from app.models.system_setting import SystemSetting
from app.models.dify_workflow import DifyWorkflow


def seed():
    """写入种子数据（幂等：已存在则跳过）"""
    db = SessionLocal()
    try:
        # 1. 初始化账号：admin/admin123（管理员）、editor/editor123（编辑）、user/user123（普通用户）
        if not db.query(User).filter(User.username == "admin").first():
            db.add(User(username="admin", password_hash=hash_password("admin123"),
                        nickname="系统管理员", role="admin", status="active"))
        if not db.query(User).filter(User.username == "editor").first():
            db.add(User(username="editor", password_hash=hash_password("editor123"),
                        nickname="演示编辑", role="editor", status="active",
                        bio="负责科技、文化等栏目的稿件写作。"))
        if not db.query(User).filter(User.username == "user").first():
            db.add(User(username="user", password_hash=hash_password("user123"),
                        nickname="演示用户", role="user", status="active"))

        # 2. 默认栏目：10 个分类（原 6 个旧栏目不再创建，老库中残留且未被引用时自动清理）
        demo_categories = [
            ("finance", "金融", "金融资讯与市场分析", 0),
            ("realty", "房产", "房产政策与楼市动态", 1),
            ("stocks", "股票", "股市行情与投资观察", 2),
            ("education", "教育", "教育政策与校园资讯", 3),
            ("science", "科学", "前沿科学与技术进展", 4),
            ("society", "社会", "社会新闻与民生话题", 5),
            ("politics", "政治", "时政要闻与政策解读", 6),
            ("sports", "运动", "体育赛事与运动健康", 7),
            ("game", "游戏", "游戏行业与电竞资讯", 8),
            ("entertainment", "娱乐", "影视音乐与文娱动态", 9),
        ]
        for slug, name, desc, sort in demo_categories:
            cat = db.query(Category).filter(Category.slug == slug).first()
            if not cat:
                db.add(Category(slug=slug, name=name, description=desc, sort_order=sort))
            elif not cat.description:
                # 已存在但缺描述的栏目（如历史数据）补上默认说明，不动名称/排序
                cat.description = desc

        # 清理旧默认栏目：原 6 个栏目若在旧库残留且未被文稿引用则删除；
        # 仍被引用时保留并提示，避免破坏已发布文稿的分类关联
        old_default_slugs = ["shizheng", "jingji", "keji", "wenhua", "tiyu", "shehui"]
        for slug in old_default_slugs:
            old_cat = db.query(Category).filter(Category.slug == slug).first()
            if old_cat:
                refs = db.query(article_categories).filter(
                    article_categories.c.category_id == old_cat.id
                ).count()
                if refs == 0:
                    db.delete(old_cat)
                    print(f"已清理旧默认栏目：{slug}")
                else:
                    print(f"旧栏目 {slug} 仍被 {refs} 篇文稿引用，保留未删除")

        # 3. 默认分发渠道：门户（基础渠道，所有文稿默认包含且不可移除）
        if not db.query(Channel).filter(Channel.slug == "portal").first():
            db.add(Channel(
                name="门户",
                slug="portal",
                description="前台门户基础渠道，所有文稿默认分发，不可移除",
                is_default=True,
                status="active",
                sort_order=0,
            ))

        # 4. 默认门户模块：首页轮播图（空数据，管理员可在后台配置）
        if not db.query(PortalModule).filter(PortalModule.module_key == "banner").first():
            db.add(PortalModule(module_key="banner", title="首页轮播",
                                content=[], enabled=True))
        if not db.query(PortalModule).filter(PortalModule.module_key == "notice").first():
            db.add(PortalModule(module_key="notice", title="站内公告",
                                content="欢迎使用文稿发布系统！", enabled=True))
        if not db.query(PortalModule).filter(PortalModule.module_key == "recommend").first():
            db.add(PortalModule(module_key="recommend", title="个性化推荐",
                                content={}, enabled=True))

        # 5. 默认后台配置：自动审核开关（默认关闭，管理员可在后台「系统设置」中开启）
        if not db.query(SystemSetting).filter(SystemSetting.config_key == "auto_review").first():
            db.add(SystemSetting(
                config_key="auto_review",
                config_value="false",
                value_type="bool",
                description="开启后，文稿提交审核即自动通过两级审核并发布，无需人工审核",
            ))
        if not db.query(SystemSetting).filter(SystemSetting.config_key == "portal_theme").first():
            db.add(SystemSetting(
                config_key="portal_theme",
                config_value="editorial",
                value_type="string",
                description="前台门户主题：editorial 经典编辑 / cyber 赛博霓虹 / comic 漫画波普",
            ))
        if not db.query(SystemSetting).filter(SystemSetting.config_key == "site_grayscale").first():
            db.add(SystemSetting(
                config_key="site_grayscale",
                config_value="false",
                value_type="bool",
                description="哀悼灰度模式：开启后前台门户全站显示为黑白（用于名人逝世等场景）",
            ))
        if not db.query(SystemSetting).filter(SystemSetting.config_key == "splash_enabled").first():
            db.add(SystemSetting(
                config_key="splash_enabled",
                config_value="true",
                value_type="bool",
                description="登录后是否播放 3D 地球开屏动画；关闭后直接进入门户首页",
            ))
        # 6. 积分系统配置：每日签到积分范围（默认 1~5，管理员可在系统设置调整）
        if not db.query(SystemSetting).filter(SystemSetting.config_key == "signin_min_points").first():
            db.add(SystemSetting(
                config_key="signin_min_points",
                config_value="1",
                value_type="int",
                description="每日签到最小积分",
            ))
        if not db.query(SystemSetting).filter(SystemSetting.config_key == "signin_max_points").first():
            db.add(SystemSetting(
                config_key="signin_max_points",
                config_value="5",
                value_type="int",
                description="每日签到最大积分",
            ))
        # 7. 注册策略：是否允许用户注册为编辑写手（关闭后编辑账号仅可后台创建）
        if not db.query(SystemSetting).filter(SystemSetting.config_key == "register_editor_enabled").first():
            db.add(SystemSetting(
                config_key="register_editor_enabled",
                config_value="true",
                value_type="bool",
                description="允许用户注册为编辑写手；关闭后编辑账号仅可后台创建",
            ))
        if not db.query(SystemSetting).filter(SystemSetting.config_key == "portal_ai_reading_enabled").first():
            db.add(SystemSetting(
                config_key="portal_ai_reading_enabled",
                config_value="true",
                value_type="bool",
                description="门户 AI 阅读功能总开关：控制 AI 全文总结、划词分析、核心术语知识链的显示",
            ))
        # 8. AI 知识库（在线配置）：AI 分类强兜底的关键词 → 分类映射，后台系统设置可在线修改
        if not db.query(SystemSetting).filter(SystemSetting.config_key == "ai_knowledge_base").first():
            db.add(SystemSetting(
                config_key="ai_knowledge_base",
                config_value=json.dumps({
                            "斯塔默": {"title": "英国首相", "category": "政治"},
                            "米莱": {"title": "阿根廷总统", "category": "政治"},
                            "元勋": {"title": "两弹元勋", "category": "政治"},
                            "普京": {"title": "普京", "category": "政治"},
                            "高市早苗": {"title": "高市早苗", "category": "政治"},
                            "泰勒·斯威夫特": {"title": "歌手", "category": "娱乐"}
                }, ensure_ascii=False),
                value_type="json",
                description="AI 知识库（关键词→分类强兜底）：JSON 对象，键为关键词，值为 {title, category}",
            ))

        # 9. Dify 工作流登记：默认登记四个业务工作流（幂等，按 name 唯一）
        # 真实 API Key 不写入脚本，仅从环境变量读取；留空时初始化后到后台补充
        default_dify_api_base = os.getenv("DIFY_API_BASE", "http://192.168.14.216:8080/v1").strip()
        default_dify_api_key = os.getenv("DIFY_API_KEY", "").strip()
        dify_workflow_seeds = [
            {
                "name": "article_summary",
                "description": "用来生成文稿摘要",
                "input_schema": {"title": "", "context": ""},
            },
            {
                "name": "article_neirong",
                "description": "这个是用来做ai内容校验的",
                "input_schema": {"last_llm": "", "now_text": "", "old_text": ""},
            },
            {
                "name": "article_weidu",
                "description": "这个工作流是用来进行文稿维度审核的",
                "input_schema": {"original_text": ""},
            },
            {
                "name": "article_pingfen",
                "description": "这个是文稿评分的工作流",
                "input_schema": {"article_title": "", "article_content": ""},
            },
        ]
        for wf in dify_workflow_seeds:
            if not db.query(DifyWorkflow).filter(DifyWorkflow.name == wf["name"]).first():
                db.add(DifyWorkflow(
                    name=wf["name"],
                    api_base=default_dify_api_base,
                    api_key=default_dify_api_key,
                    description=wf["description"],
                    input_schema=wf["input_schema"],
                    enabled=True,
                    timeout=3600,
                ))

        db.commit()
        print("种子数据写入完成。")
        print("管理员账号: admin / admin123")
        print("编辑账号:   editor / editor123")
        print("用户账号:   user / user123")
    finally:
        db.close()


if __name__ == "__main__":
    print("正在检查/创建数据库 ...")
    ensure_database()
    print("正在创建数据表 ...")
    Base.metadata.create_all(bind=engine)
    print("正在检查表结构兼容性 ...")
    ensure_schema_compat()
    print("数据表创建完成。")
    seed()
