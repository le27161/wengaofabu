# -*- coding: utf-8 -*-
"""文稿发布系统 - FastAPI 入口

启动：cd backend && python run.py
接口文档：http://localhost:8000/docs
"""
import os
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import Base, engine, ensure_database, ensure_schema_compat
from .routers import (
    admin_behavior, articles, auth, categories, channels, comments, dify, events, history,
    interactions, keywords, points, portal, resources, reviews, settings as settings_router, stats, tags, users, ai_assist,
    embeddings, preferences, smart_collect, ai_news,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时自动建库（若不存在）、建表并做表结构兼容检查（表结构变更请重新执行 python init_db.py）"""
    ensure_database()
    Base.metadata.create_all(bind=engine)
    ensure_schema_compat()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    yield


app = FastAPI(
    title="文稿发布系统 API",
    description="前后台分离的文稿发布系统：门户浏览 + 编辑写作 + 二级审核 + 用户互动 + 埋点统计",
    version="1.0.0",
    lifespan=lifespan,
)

# 跨域：前后台分离部署时前端地址需加入 allow_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 上传文件静态访问：http://localhost:8000/static/xxx.png
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.UPLOAD_DIR), name="static")

# 统一 /api 前缀挂载各模块路由
api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(admin_behavior.router)
api_router.include_router(users.router)
api_router.include_router(categories.router)
api_router.include_router(channels.router)
api_router.include_router(articles.router)
api_router.include_router(reviews.router)
api_router.include_router(interactions.router)
api_router.include_router(resources.router)
api_router.include_router(portal.router)
api_router.include_router(events.router)
api_router.include_router(preferences.router)
api_router.include_router(history.router)
api_router.include_router(comments.router)
api_router.include_router(comments.admin_router)
api_router.include_router(points.router)
api_router.include_router(points.admin_router)
api_router.include_router(stats.router)
api_router.include_router(settings_router.router)
api_router.include_router(dify.router)
api_router.include_router(ai_assist.router)
api_router.include_router(ai_assist.admin_router)
api_router.include_router(ai_assist.admin_corrections_router)
api_router.include_router(keywords.router)
api_router.include_router(tags.router)
api_router.include_router(embeddings.router)
api_router.include_router(smart_collect.router)
api_router.include_router(ai_news.router)
app.include_router(api_router)


@app.get("/", tags=["健康检查"])
def root():
    return {"app": "文稿发布系统", "docs": "/docs", "status": "ok"}
