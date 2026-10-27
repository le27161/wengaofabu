# -*- coding: utf-8 -*-
"""数据库引擎与会话管理（SQLAlchemy + PyMySQL），含自动建库工具"""
import re

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import text

from .config import settings

# 连接串：使用 utf8mb4 以完整支持中文与 emoji
DATABASE_URL = (
    f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}?charset=utf8mb4"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,     # 取连接前先 ping，避免断线后拿到失效连接
    pool_recycle=3600,      # 连接 1 小时回收，防止 MySQL wait_timeout 断开
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _server_engine():
    """创建不指定数据库的服务器级连接（用于建库等管理操作）"""
    server_url = (
        f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/?charset=utf8mb4"
    )
    return create_engine(server_url, pool_pre_ping=True)


def ensure_database() -> None:
    """初始化数据库：若目标库不存在则自动创建（utf8mb4），已存在则跳过（幂等）。

    注意：需要 MySQL 账号具备 CREATE DATABASE 权限；若权限不足，
    可手动执行：
      CREATE DATABASE wengaofabu DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    """
    # 校验库名，防止特殊字符注入到 CREATE DATABASE 语句中
    if not re.fullmatch(r"[A-Za-z0-9_]+", settings.DB_NAME):
        raise ValueError(f"数据库名不合法: {settings.DB_NAME}")

    server = _server_engine()
    try:
        with server.connect() as conn:
            exists = conn.execute(
                text("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = :name"),
                {"name": settings.DB_NAME},
            ).scalar()
            if not exists:
                conn.execute(
                    text(
                        f"CREATE DATABASE `{settings.DB_NAME}` "
                        "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    )
                )
                print(f"数据库 {settings.DB_NAME} 创建成功")
            else:
                print(f"数据库 {settings.DB_NAME} 已存在，跳过创建")
    finally:
        server.dispose()


def ensure_schema_compat() -> None:
    """幂等兼容迁移：只做表结构变更（补列/改列），重复执行无副作用。

    注意：不再做存量数据回填/修复（曾用于 content_source 回填、摘要 HTML 剥离、嵌套 <p> 还原），因为这些批量 UPDATE 会触发 articles.updated_at 自动刷新；历史数据如需修复请由业务侧按需处理。
    """
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT IS_NULLABLE FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'article_reviews' "
                "AND COLUMN_NAME = 'reviewer_id'"
            )
        ).first()
        if row and str(row[0]).upper() != "YES":
            conn.execute(text("ALTER TABLE article_reviews MODIFY COLUMN reviewer_id INT NULL"))
            print("已迁移：article_reviews.reviewer_id 允许为空（支持系统自动审核）")

    # 幂等新增 articles.city 同城搜索字段（老库补列，重复执行无副作用）
    with engine.begin() as conn:
        city_col = conn.execute(
            text(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'articles' "
                "AND COLUMN_NAME = 'city'"
            )
        ).first()
        if not city_col:
            conn.execute(
                text(
                    "ALTER TABLE articles ADD COLUMN city VARCHAR(50) NULL "
                    "COMMENT '城市（同城搜索），如 深圳' AFTER cover_url"
                )
            )
            print("已迁移：articles.city 列新增成功（同城搜索）")

    # 幂等新增 view_history 观看时长字段（老库补列，重复执行无副作用）
    with engine.begin() as conn:
        for col, ddl in (
            ("watch_seconds", "ALTER TABLE view_history ADD COLUMN watch_seconds INT NOT NULL DEFAULT 0"),
            ("watch_count", "ALTER TABLE view_history ADD COLUMN watch_count INT NOT NULL DEFAULT 0"),
        ):
            exists = conn.execute(
                text(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'view_history' AND COLUMN_NAME = :col"
                ),
                {"col": col},
            ).first()
            if not exists:
                conn.execute(text(ddl))
                print(f"已迁移：view_history.{col} 新增成功")

    # 幂等新增 articles.content_source 纯文本字段，并从已有 content 剥离 HTML 回填
    with engine.begin() as conn:
        exists = conn.execute(
            text(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'articles' AND COLUMN_NAME = 'content_source'"
            )
        ).first()
        if not exists:
            conn.execute(
                text(
                    "ALTER TABLE articles ADD COLUMN content_source TEXT NULL "
                    "COMMENT '正文纯文本（无HTML标签）'"
                )
            )
            print("已迁移：articles.content_source 新增成功")

    # 幂等新增 users.points 积分字段（老库补列，重复执行无副作用）
    with engine.begin() as conn:
        exists = conn.execute(
            text(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'points'"
            )
        ).first()
        if not exists:
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN points INT NOT NULL DEFAULT 0 "
                    "COMMENT '用户积分'"
                )
            )
            print("已迁移：users.points 新增成功")

    # 幂等新增 resources.storage 存储位置字段（local/oss，老库补列）
    with engine.begin() as conn:
        exists = conn.execute(
            text(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'resources' AND COLUMN_NAME = 'storage'"
            )
        ).first()
        if not exists:
            conn.execute(
                text(
                    "ALTER TABLE resources ADD COLUMN storage VARCHAR(10) NOT NULL DEFAULT 'local' "
                    "COMMENT '存储位置（local/oss）'"
                )
            )
            print("已迁移：resources.storage 新增成功")

    # 智能采编：老库兼容语义相关度与人工标签字段（新库由create_all直接创建）
    with engine.begin() as conn:
        semantic_score_column = conn.execute(
            text(
                "SELECT 1 FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = 'smart_collect_task_clues' "
                "AND COLUMN_NAME = 'semantic_score'"
            )
        ).first()
        if not semantic_score_column:
            conn.execute(
                text(
                    "ALTER TABLE smart_collect_task_clues "
                    "ADD COLUMN semantic_score FLOAT NULL "
                    "COMMENT '该新闻相对于本次采编主题的语义相关度' "
                    "AFTER search_score"
                )
            )
            print("已迁移：smart_collect_task_clues.semantic_score 允许为空")

        relevance_label_column = conn.execute(
            text(
                "SELECT 1 FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = 'smart_collect_task_clues' "
                "AND COLUMN_NAME = 'relevance_label'"
            )
        ).first()
        if not relevance_label_column:
            conn.execute(
                text(
                    "ALTER TABLE smart_collect_task_clues "
                    "ADD COLUMN relevance_label SMALLINT NULL "
                    "COMMENT '人工相关性：0明显偏题，1一般相关，2明显相关，NULL未标注' "
                    "AFTER semantic_score"
                )
            )
            print("已迁移：smart_collect_task_clues.relevance_label 允许为空")

        # 新库由create_all直接创建事件表；这里兼容可能已存在但缺少业务唯一索引的表。
        event_clue_table = conn.execute(
            text(
                "SELECT 1 FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = 'smart_collect_event_clues'"
            )
        ).first()
        if event_clue_table:
            task_clue_unique = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = 'smart_collect_event_clues' "
                    "AND INDEX_NAME = 'uq_smart_collect_event_clues_task_clue' "
                    "AND NON_UNIQUE = 0"
                )
            ).first()
            if not task_clue_unique:
                conn.execute(
                    text(
                        "ALTER TABLE smart_collect_event_clues "
                        "ADD UNIQUE INDEX uq_smart_collect_event_clues_task_clue "
                        "(task_id, clue_id)"
                    )
                )
                print("已迁移：同一采编任务的一条线索最多属于一个人工事件")

        content_table = conn.execute(
            text(
                "SELECT 1 FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = 'news_clue_contents'"
            )
        ).first()
        if content_table:
            content_clue_unique = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = 'news_clue_contents' "
                    "AND INDEX_NAME = 'uq_news_clue_contents_clue_id' "
                    "AND NON_UNIQUE = 0"
                )
            ).first()
            if not content_clue_unique:
                conn.execute(
                    text(
                        "ALTER TABLE news_clue_contents "
                        "ADD UNIQUE INDEX uq_news_clue_contents_clue_id (clue_id)"
                    )
                )
                print("已迁移：每条新闻线索最多保存一份可复用正文")



    # AI协作台：任务与调用记录绑定文稿ID（老库补列，避免新建文稿恢复旧结果）
    with engine.begin() as conn:
        for table_name in ("ai_tasks", "ai_call_logs"):
            exists = conn.execute(
                text(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = 'article_id'"
                ),
                {"t": table_name},
            ).first()
            if not exists:
                conn.execute(
                    text(
                        f"ALTER TABLE {table_name} ADD COLUMN article_id INT NULL "
                        "COMMENT '关联文稿ID'"
                    )
                )
                print(f"已迁移：{table_name}.article_id 新增成功")

    # AI协作台：任务/调用记录/纠正样本增加 draft_key（新建文稿保存前关联草稿会话，保存后回填 article_id）
    with engine.begin() as conn:
        for table_name in ("ai_tasks", "ai_call_logs", "ai_corrections"):
            exists = conn.execute(
                text(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = 'draft_key'"
                ),
                {"t": table_name},
            ).first()
            if not exists:
                conn.execute(
                    text(
                        f"ALTER TABLE {table_name} ADD COLUMN draft_key VARCHAR(64) NULL "
                        "COMMENT '草稿会话标识：新建文稿未保存时关联AI记录，保存后回填article_id'"
                    )
                )
                print(f"已迁移：{table_name}.draft_key 新增成功")


def get_db():
    """FastAPI 依赖：每个请求一个数据库会话，请求结束自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
