# -*- coding: utf-8 -*-
"""FastAPI 依赖：获取当前用户、角色权限校验、客户端 IP 提取"""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """解析请求头中的 Bearer Token，返回当前登录用户"""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录，请先登录")
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录凭证无效或已过期")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    if user.status == "frozen":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已被冻结，请联系管理员")
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """可选登录依赖：未携带 Token 时返回 None（用于公开但可带用户身份的接口）"""
    if credentials is None:
        return None
    return get_current_user(credentials=credentials, db=db)


def require_roles(*roles: str):
    """角色权限依赖：用户角色必须属于 roles 列表之一"""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "没有权限执行此操作")
        return user

    return checker


def get_client_ip(request: Request) -> str:
    """获取客户端 IP（兼容反向代理的 X-Forwarded-For）"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""
