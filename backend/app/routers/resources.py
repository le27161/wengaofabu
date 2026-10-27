# -*- coding: utf-8 -*-
"""资源管理接口：上传、列表、删除（素材供文稿封面/正文引用）"""
import os
import uuid
from datetime import datetime
from io import BytesIO

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from ..config import settings
from ..core.deps import get_current_user, require_roles
from ..core.pagination import paginate
from ..database import get_db
from ..models.resource import Resource
from ..models.user import User
from ..schemas.resource import ResourceUrlIn
from ..services.oss_service import delete_object, get_oss_config
from ..services.storage_service import save_bytes

router = APIRouter(prefix="/resources", tags=["资源"])

# 允许上传的文件类型
ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
    "video/mp4", "video/webm",
    "audio/mpeg", "application/pdf",
}

# 通过链接上传仅允许图片类型
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"}

# content-type → 文件扩展名（部分站点会返回 image/jpg 等非标准类型，统一归一化）
CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}


@router.post("/upload", summary="上传资源文件（图片/视频/PDF）")
async def upload_resource(
    file: UploadFile = File(..., description="上传的文件"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"不支持的文件类型：{file.content_type}")

    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(400, f"文件过大，最大允许 {settings.MAX_UPLOAD_SIZE // 1024 // 1024}MB")
    if not data:
        raise HTTPException(400, "文件为空")

    # 按存储配置分流：OSS 或本地
    ext = os.path.splitext(file.filename or "")[1].lower()
    # 读配置在主线程（Session 线程不安全），字节写入/上传放线程池避免阻塞事件循环
    oss_cfg = get_oss_config(db)
    stored_name, url, storage = await run_in_threadpool(
        save_bytes, oss_cfg, data, file.content_type, ext,
    )

    resource = Resource(
        user_id=user.id,
        filename=file.filename or stored_name,
        stored_name=stored_name,
        url=url,
        file_type=file.content_type,
        file_size=len(data),
        storage=storage,
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return {"message": "上传成功", "resource": resource.to_dict()}


@router.post("/upload-by-url", summary="通过图片链接下载并入库（仅图片）")
async def upload_resource_by_url(
    body: ResourceUrlIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """根据线上图片链接下载图片，保存到资源库（与本地上传走同一套存储与记录）。

    注意：生产环境如开放给非可信用户，建议在此处增加内网地址/SSRF 防护
    （例如拒绝 127.0.0.1、10.x、192.168.x 等内网段），当前演示项目仅做协议与类型限制。
    """
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "仅支持 http/https 的图片链接")

    # 流式下载到内存：限制总大小（与本地上传一致 20MB），随后按 OSS/本地配置统一入库
    data_buf = BytesIO()
    total = 0
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            async with client.stream("GET", url) as resp:
                if resp.status_code != 200:
                    raise HTTPException(400, f"链接无法访问（HTTP {resp.status_code}）")
                content_type = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
                # 部分站点不返回 content-type，按 URL 后缀兜底判断
                if content_type not in ALLOWED_IMAGE_TYPES:
                    ext_from_url = os.path.splitext(url.split("?")[0])[1].lower()
                    ext_to_type = {
                        ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg",
                        ".png": "image/png",
                        ".gif": "image/gif",
                        ".webp": "image/webp",
                        ".svg": "image/svg+xml",
                    }
                    content_type = ext_to_type.get(ext_from_url, "")
                if content_type not in ALLOWED_IMAGE_TYPES:
                    raise HTTPException(400, "链接内容不是支持的图片格式（jpg/png/gif/webp/svg）")

                ext = CONTENT_TYPE_EXT.get(content_type, ".jpg")
                async for chunk in resp.aiter_bytes(64 * 1024):
                    total += len(chunk)
                    if total > settings.MAX_UPLOAD_SIZE:
                        raise HTTPException(400, f"图片过大，最大允许 {settings.MAX_UPLOAD_SIZE // 1024 // 1024}MB")
                    data_buf.write(chunk)
                if total == 0:
                    raise HTTPException(400, "下载内容为空")
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(408, "下载超时，请确认链接可访问") from None
    except httpx.RequestError as e:
        raise HTTPException(400, f"下载失败：{e}") from None

    # 按存储配置分流：OSS 或本地（读配置在主线程，上传/写文件在线程池）
    oss_cfg = get_oss_config(db)
    stored_name, url_stored, storage = await run_in_threadpool(
        save_bytes, oss_cfg, data_buf.getvalue(), content_type, ext,
    )

    # 原始文件名优先取链接最后一段，取不到则用日期命名
    url_path = url.split("?")[0].rstrip("/")
    original_name = os.path.basename(url_path) or f"网络图片{datetime.now():%Y%m%d}"
    resource = Resource(
        user_id=user.id,
        filename=original_name,
        stored_name=stored_name,
        url=url_stored,
        file_type=content_type,
        file_size=total,
        storage=storage,
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return {"message": "链接图片已下载并入库", "resource": resource.to_dict()}


@router.get("", summary="资源列表（管理员看全部，其他人看自己的）")
def list_resources(
    keyword: str | None = Query(default=None),
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Resource)
    if user.role != "admin":
        query = query.filter(Resource.user_id == user.id)
    if keyword:
        query = query.filter(Resource.filename.like(f"%{keyword}%"))
    query = query.order_by(Resource.id.desc())
    rows, total = paginate(query, page, page_size)
    return {"items": [r.to_dict() for r in rows], "total": total, "page": page, "page_size": page_size}


@router.delete("/{resource_id}", summary="删除资源（上传者或管理员）")
def delete_resource(resource_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    resource = db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(404, "资源不存在")
    if user.role != "admin" and resource.user_id != user.id:
        raise HTTPException(403, "只能删除自己上传的资源")

    # 按存储位置删除物理文件：OSS 删对象，本地删 uploads 内文件
    if resource.storage == "oss":
        oss_cfg = get_oss_config(db)
        if oss_cfg:
            delete_object(oss_cfg, resource.stored_name)
        # OSS 配置已被清空时无法删除远端对象，跳过并保留资源记录删除
    else:
        file_path = os.path.abspath(os.path.join(settings.UPLOAD_DIR, resource.stored_name))
        upload_dir = os.path.abspath(settings.UPLOAD_DIR)
        if os.path.commonpath([file_path, upload_dir]) == upload_dir and os.path.isfile(file_path):
            os.remove(file_path)

    db.delete(resource)
    db.commit()
    return {"message": "删除成功"}

