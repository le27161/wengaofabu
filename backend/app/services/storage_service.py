# -*- coding: utf-8 -*-
"""文件存储服务：按 OSS 配置分流保存字节流（本地 uploads/ 或 S3 兼容对象存储）

资源上传与批量导入的封面下载共用此函数，保证存储位置与 URL 规则一致。
"""
import os
import uuid
from datetime import datetime

from fastapi import HTTPException

from ..config import settings
from ..services.oss_service import upload_bytes


def save_bytes(oss_cfg, data: bytes, content_type: str, ext: str) -> tuple[str, str, str]:
    """按 OSS 配置分流保存文件，返回 (stored_name, url, storage)。

    - 已配置 OSS：上传到对象存储，URL 为公网地址；上传失败明确报错，不回退本地。
    - 未配置：维持本地 uploads/ 存储。
    """
    if oss_cfg:
        try:
            url, key = upload_bytes(oss_cfg, data, content_type, ext)
        except Exception as e:
            raise HTTPException(502, f"对象存储上传失败，请检查 OSS 配置：{e}") from None
        return key, url, "oss"

    # 本地存储：UUID 重命名，避免重名与路径注入
    stored_name = f"{datetime.now():%Y%m%d}_{uuid.uuid4().hex}{ext}"
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(os.path.join(settings.UPLOAD_DIR, stored_name), "wb") as f:
        f.write(data)
    return stored_name, f"{settings.BASE_URL}/static/{stored_name}", "local"
