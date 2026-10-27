# -*- coding: utf-8 -*-
"""文章 AI 总结与划选解释服务，不写入数据库。"""
import json
import re

from ..models.article import Article
from ..services.ai_service import AIService, AIServiceError
from ..services.text_utils import strip_html


def _article_text(article: Article) -> str:
    """读取文章可供模型分析的纯文本，并限制长度避免请求过大。"""
    text = article.content_source or strip_html(article.content or "")
    return re.sub(r"\s+", " ", text).strip()[:12000]


def _read_json(raw: str) -> dict:
    """只接受模型返回的 JSON 对象，兼容少数模型附带的代码块。"""
    content = raw.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AIServiceError("AI 返回格式异常，请重新尝试") from exc
    if not isinstance(data, dict):
        raise AIServiceError("AI 返回内容异常，请重新尝试")
    return data


async def summarize_article(article: Article) -> dict:
    """根据当前文章标题和正文生成短总结。"""
    text = _article_text(article)
    if not text:
        raise AIServiceError("文章正文为空，暂时无法生成总结")
    prompt = (
        "你是新闻文章总结助手。只能依据给出的标题和正文总结，不得编造事实、数据或背景。"
        "请只返回合法 JSON：{\"summary\":\"简洁、准确、易读的全文总结\"}。"
        "总结控制在 80 到 220 个汉字。禁止输出思考过程、推理步骤、<think> 标签、标签、Markdown 或其他内容。\n"
        f"标题：{article.title}\n正文：{text}"
    )
    raw = await AIService().chat([
        {"role": "system", "content": "仅输出最终 JSON 答案，禁止展示任何思考过程或推理步骤。"},
        {"role": "user", "content": prompt},
    ], temperature=0.2, max_tokens=500)
    summary = _read_json(raw).get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise AIServiceError("AI 未返回有效总结，请重新尝试")
    return {"summary": summary.strip()[:600]}


async def explain_article_selection(article: Article, selected_text: str) -> dict:
    """解释正文划选内容，拒绝解释不属于当前文章的文本。"""
    text = _article_text(article)
    selection = re.sub(r"\s+", " ", selected_text).strip()
    if not selection or selection not in text:
        raise AIServiceError("划选内容不属于当前文章正文，请重新选择")
    prompt = (
        "你是新闻阅读助手。只能依据给出的标题、正文和划选文字解释划选内容，不得编造。"
        "请只返回合法 JSON：{\"explanation\":\"简短、通俗的解释\"}。"
        "解释控制在 40 到 180 个汉字。禁止输出思考过程、推理步骤、<think> 标签、标签、Markdown 或其他内容。\n"
        f"标题：{article.title}\n正文：{text}\n划选文字：{selection}"
    )
    raw = await AIService().chat([
        {"role": "system", "content": "仅输出最终 JSON 答案，禁止展示任何思考过程或推理步骤。"},
        {"role": "user", "content": prompt},
    ], temperature=0.2, max_tokens=420)
    explanation = _read_json(raw).get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        raise AIServiceError("AI 未返回有效解释，请重新尝试")
    return {"explanation": explanation.strip()[:500]}
