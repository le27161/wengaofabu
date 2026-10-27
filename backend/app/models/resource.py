# -*- coding: utf-8 -*-
"""资源管理模型：编辑器/管理员上传的图片、视频等素材"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from ..database import Base


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True, comment="资源ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="上传者ID")
    filename = Column(String(255), comment="原始文件名")
    stored_name = Column(String(255), unique=True, comment="服务器存储文件名")
    url = Column(String(255), comment="访问URL")
    file_type = Column(String(50), comment="文件类型（如 image/png）")
    file_size = Column(Integer, default=0, comment="文件大小（字节）")
    # 存储位置：local 本地服务器 / oss 对象存储（S3 兼容）；删除资源时据此决定删本地文件还是 OSS 对象
    storage = Column(String(10), nullable=False, default="local", server_default="local", comment="存储位置（local/oss）")
    created_at = Column(DateTime, default=datetime.now, comment="上传时间")

    uploader = relationship("User", foreign_keys=[user_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "uploader_name": self.uploader.nickname or self.uploader.username if self.uploader else "",
            "filename": self.filename,
            "url": self.url,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "storage": self.storage,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }

