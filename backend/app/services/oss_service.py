# -*- coding: utf-8 -*-
"""S3 兼容对象存储服务（阿里云 OSS / 腾讯云 COS / MinIO / AWS S3 等）

规则：
- 配置存储在 system_settings.oss_config（json）；endpoint 为空视为未启用，走本地存储。
- 未启用时不 import boto3，零额外依赖开销。
- URL 拼接优先 public_base_url（兼容虚拟主机风格/CDN），否则按路径风格
  endpoint/bucket/key 拼接（兼容 MinIO 默认方式）。
"""
import os
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..services.settings_service import get_setting


def get_oss_config(db: Session) -> Optional[dict]:
    """读取 OSS 配置；endpoint 为空或未配置时返回 None（= 本地模式）"""
    cfg = get_setting(db, "oss_config", default=None)
    if not isinstance(cfg, dict) or not str(cfg.get("endpoint", "")).strip():
        return None
    return {
        "endpoint": str(cfg["endpoint"]).rstrip("/"),
        "bucket": str(cfg.get("bucket", "")).strip(),
        "region": str(cfg.get("region", "")).strip() or "us-east-1",
        "access_key": str(cfg.get("access_key", "")).strip(),
        "secret_key": str(cfg.get("secret_key", "")).strip(),
        "path_prefix": str(cfg.get("path_prefix", "")).strip().strip("/"),
        "public_base_url": str(cfg.get("public_base_url", "")).strip().rstrip("/"),
    }


def _get_client(cfg: dict):
    """懒加载 boto3 S3 客户端（路径风格寻址，兼容 MinIO 等自建存储）"""
    import boto3
    from botocore.client import Config

    return boto3.client(
        "s3",
        endpoint_url=cfg["endpoint"],
        region_name=cfg["region"],
        aws_access_key_id=cfg["access_key"],
        aws_secret_access_key=cfg["secret_key"],
        config=Config(
            s3={"addressing_style": "path"},
            connect_timeout=5,          # 连接失败快速返回，避免长时间阻塞
            read_timeout=30,
            retries={"max_attempts": 2},
        ),
    )


def build_object_url(cfg: dict, key: str) -> str:
    """拼接公网访问 URL：public_base_url 优先，否则 endpoint/bucket/key（路径风格）"""
    base = cfg.get("public_base_url") or f"{cfg['endpoint']}/{cfg['bucket']}"
    return f"{base}/{key}"


def generate_key(cfg: dict, ext: str) -> str:
    """生成对象 key：可选前缀 + 日期 + UUID，避免重名与路径注入"""
    prefix = f"{cfg['path_prefix']}/" if cfg.get("path_prefix") else ""
    return f"{prefix}{datetime.now():%Y%m%d}_{uuid.uuid4().hex}{ext}"


def upload_bytes(cfg: dict, data: bytes, content_type: str, ext: str) -> tuple[str, str]:
    """上传字节流到 OSS，返回 (公网URL, 对象key)；删除对象时需要 key"""
    client = _get_client(cfg)
    key = generate_key(cfg, ext)
    client.put_object(
        Bucket=cfg["bucket"],
        Key=key,
        Body=data,
        ContentType=content_type or "application/octet-stream",
    )
    return build_object_url(cfg, key), key


def delete_object(cfg: dict, key: str) -> None:
    """按 key 删除 OSS 对象（对象不存在时静默忽略）"""
    client = _get_client(cfg)
    try:
        client.delete_object(Bucket=cfg["bucket"], Key=key)
    except Exception:
        # 删除失败不影响主流程（资源记录仍会删除），由运维后续清理
        pass
