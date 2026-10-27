# -*- coding: utf-8 -*-
"""一次性迁移脚本：把存量 OSS 内网图片 URL 替换为公网前缀

背景：早期 OSS/MinIO 配置的 endpoint 是内网地址（如 http://192.168.14.216:9000），
已入库的封面/正文/资源 URL 都是内网地址，公网访问图片会 404/超时。

用法（在 backend 目录执行）：
    python fix_oss_public_urls.py --new-prefix http://wgfb.89cyx.cc:9000 --dry-run
    python fix_oss_public_urls.py --new-prefix http://wgfb.89cyx.cc:9000 \
        --set-public-base http://wgfb.89cyx.cc:9000/wgfb

参数说明：
    --new-prefix        新公网来源前缀（只到协议+域名[:端口]，不含 bucket，如 http://wgfb.89cyx.cc:9000）
    --old-prefix        旧内网前缀，默认 http://192.168.14.216:9000
    --set-public-base   同时更新 OSS 配置的 public_base_url（含 bucket，如 http://wgfb.89cyx.cc:9000/wgfb）
    --dry-run           只统计不写库
"""
import argparse
import json
import sys

from app.database import SessionLocal
from app.models.article import Article
from app.models.portal import PortalModule
from app.models.resource import Resource
from app.models.system_setting import SystemSetting
from app.services.settings_service import get_setting, set_setting


def main() -> int:
    parser = argparse.ArgumentParser(description="修复存量 OSS 内网图片 URL")
    parser.add_argument("--new-prefix", required=True, help="新公网来源前缀，如 http://wgfb.89cyx.cc:9000")
    parser.add_argument("--old-prefix", default="http://192.168.14.216:9000", help="旧内网前缀")
    parser.add_argument("--set-public-base", default="", help="可选：同时把 OSS public_base_url 改为该值（含 bucket）")
    parser.add_argument("--dry-run", action="store_true", help="只统计不写库")
    args = parser.parse_args()

    if not args.new_prefix or args.old_prefix in args.new_prefix:
        print("--new-prefix 不能为空，且不能包含旧前缀")
        return 1

    db = SessionLocal()
    try:
        # 需要替换的字段：封面、资源、正文 HTML、门户模块 JSON
        covers = db.query(Article).filter(Article.cover_url.contains(args.old_prefix)).all()
        resources = db.query(Resource).filter(Resource.url.contains(args.old_prefix)).all()
        contents = db.query(Article).filter(Article.content.contains(args.old_prefix)).all()
        modules = []
        for m in db.query(PortalModule).all():
            raw = json.dumps(m.content, ensure_ascii=False) if m.content is not None else ""
            if args.old_prefix in raw:
                modules.append(m)

        print(f"封面待替换: {len(covers)}")
        print(f"资源待替换: {len(resources)}")
        print(f"正文待替换: {len(contents)}")
        print(f"门户模块待替换: {len(modules)}")

        if args.set_public_base:
            cfg = get_setting(db, "oss_config", default={}) or {}
            cfg["public_base_url"] = args.set_public_base.strip().rstrip("/")
            print(f"OSS public_base_url 将更新为: {cfg['public_base_url']}")

        if args.dry_run:
            print("dry-run：未写入任何数据")
            return 0

        for a in covers:
            a.cover_url = a.cover_url.replace(args.old_prefix, args.new_prefix)
        for r in resources:
            r.url = r.url.replace(args.old_prefix, args.new_prefix)
        for a in contents:
            a.content = a.content.replace(args.old_prefix, args.new_prefix)
        for m in modules:
            raw = json.dumps(m.content, ensure_ascii=False).replace(args.old_prefix, args.new_prefix)
            m.content = json.loads(raw)

        if args.set_public_base:
            cfg = get_setting(db, "oss_config", default={}) or {}
            cfg["public_base_url"] = args.set_public_base.strip().rstrip("/")
            set_setting(
                db,
                "oss_config",
                cfg,
                value_type="json",
                description="S3 兼容对象存储配置（endpoint 为空则上传到本地）",
            )

        db.commit()
        print("迁移完成，已写入数据库")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
