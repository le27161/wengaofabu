# -*- coding: utf-8 -*-
"""门户 AI 新闻助手：前端只访问新闻后端，由后端转发至独立 RAG 服务。"""
from fastapi import APIRouter, HTTPException

from ..schemas.ai_news import AINewsChatIn
from ..services.rag_news_service import RAGNewsServiceError, ask_news_assistant

router = APIRouter(prefix="/ai-news", tags=["AI 新闻助手"])


@router.post("/chat", summary="向 AI 新闻助手提问")
def chat_with_ai_news(body: AINewsChatIn):
    """只返回 RAG 基于已发布新闻生成的答案和真实来源。"""
    try:
        data = ask_news_assistant(body.question, body.category)
    except RAGNewsServiceError as exc:
        raise HTTPException(503, "AI 新闻助手暂时不可用，请稍后再试") from exc
    return {"message": "AI 新闻助手回答成功", "data": data}
