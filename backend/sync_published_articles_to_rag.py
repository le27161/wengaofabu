# -*- coding: utf-8 -*-
"""将历史已发布新闻批量同步到 KnowledgeHub RAG。

示例：
    cd backend
    python -X utf8 sync_published_articles_to_rag.py --limit 20
    python -X utf8 sync_published_articles_to_rag.py --limit 20 --offset 20

脚本只读取状态为 published 的文章，不修改新闻数据库。重复执行同一文章时，
RAG 使用 article_id 对应的稳定 Chunk ID 覆盖索引，因此可以安全重试。
"""
import argparse
import sys

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量同步历史已发布新闻到 RAG 知识库")
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="本次最多同步多少篇，范围 1~1000，默认 20",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="跳过前多少篇已发布新闻，用于分批继续同步，默认 0",
    )
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error("--limit 必须在 1 到 1000 之间")
    if args.offset < 0:
        parser.error("--offset 不能小于 0")
    return args


def main() -> int:
    args = parse_args()
    # 延迟导入，使 --help 不依赖数据库驱动或项目运行环境。
    from app.database import SessionLocal
    from app.models.article import Article
    from app.services.rag_news_service import (
        RAGNewsServiceError,
        is_rag_enabled,
        sync_published_article,
    )

    if not is_rag_enabled():
        print("RAG 尚未启用：请先在 backend/.env 配置 RAG_ENABLED=true。")
        return 2

    db = SessionLocal()
    try:
        # 固定排序保证 offset 分批执行时顺序稳定；published_at 为空的异常记录排在最后。
        rows = (
            db.query(Article.id)
            .filter(Article.status == "published")
            .order_by(Article.published_at.desc(), Article.id.desc())
            .offset(args.offset)
            .limit(args.limit)
            .all()
        )
        article_ids = [row[0] for row in rows]
    finally:
        db.close()

    if not article_ids:
        print("没有可同步的已发布新闻。")
        return 0

    success_count = 0
    failed_ids: list[int] = []
    print(f"开始同步 {len(article_ids)} 篇已发布新闻（offset={args.offset}）。")

    for index, article_id in enumerate(article_ids, start=1):
        try:
            sync_published_article(article_id)
            success_count += 1
            print(f"[{index}/{len(article_ids)}] article_id={article_id} 同步成功")
        except RAGNewsServiceError as exc:
            failed_ids.append(article_id)
            print(f"[{index}/{len(article_ids)}] article_id={article_id} 同步失败：{exc}")

    print(f"同步完成：成功 {success_count} 篇，失败 {len(failed_ids)} 篇。")
    if failed_ids:
        print("失败文章 ID：" + ", ".join(str(article_id) for article_id in failed_ids))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
