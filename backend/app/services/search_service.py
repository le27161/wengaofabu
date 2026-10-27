# -*- coding: utf-8 -*-
"""Tavily 新闻搜索服务：外部调用、基础清洗、异常归类和统一结果转换。"""
import html
import math
import re
from urllib.parse import urlparse

import httpx

from ..schemas.smart_collect import SearchResult, SmartCollectSearchResponse

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
SNIPPET_MAX_LENGTH = 300

# 仅过滤独占一行、语义明确的通用网页控件文字，避免针对具体网站写规则。
GENERIC_NOISE_LABELS = frozenset(
    {
        "首页",
        "主页",
        "网站首页",
        "返回首页",
        "导航",
        "菜单",
        "搜索",
        "登录",
        "注册",
        "登录/注册",
        "关于我们",
        "联系我们",
        "隐私政策",
        "服务条款",
        "使用条款",
        "网站地图",
        "订阅",
        "分享",
        "分享到",
        "更多",
        "广告",
        "返回顶部",
        "home",
        "menu",
        "search",
        "login",
        "log in",
        "sign in",
        "register",
        "sign up",
        "about us",
        "contact us",
        "privacy policy",
        "terms of use",
        "site map",
        "sitemap",
        "subscribe",
        "share",
        "more",
        "advertisement",
        "skip to content",
    }
)


class SearchServiceError(Exception):
    """可安全返回给前端的搜索服务异常基类。"""

    status_code = 502
    message = "搜索服务暂时不可用，请稍后重试"


class SearchConfigError(SearchServiceError):
    status_code = 503
    message = "搜索服务尚未配置，请联系管理员"


class SearchAuthError(SearchServiceError):
    status_code = 502
    message = "搜索服务认证失败，请联系管理员"


class SearchTimeoutError(SearchServiceError):
    status_code = 504
    message = "搜索服务响应超时，请稍后重试"


class SearchRateLimitError(SearchServiceError):
    status_code = 429
    message = "搜索请求过于频繁，请稍后重试"


class SearchQuotaError(SearchServiceError):
    status_code = 503
    message = "搜索服务额度不足，请联系管理员"


class SearchUpstreamError(SearchServiceError):
    """Tavily 网络、服务或响应格式异常。"""


class SearchService:
    """通过 Tavily 获取候选新闻，并转换成项目统一格式。"""

    def __init__(
        self,
        api_key: str,
        timeout: float = 15,
        client: httpx.AsyncClient | None = None,
    ):
        self.api_key = api_key.strip()
        self.timeout = timeout
        self.client = client

    async def search(
        self,
        query: str,
        time_range: str,
        max_results: int,
    ) -> SmartCollectSearchResponse:
        """执行一次新闻搜索；不生成答案、不取全文、不保存数据。"""
        if not self.api_key:
            raise SearchConfigError

        payload = {
            "query": query,
            "topic": "news",
            "search_depth": "basic",
            "time_range": time_range,
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
            "include_usage": True,
            "auto_parameters": False,
            "country": "china",
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            if self.client is not None:
                response = await self.client.post(TAVILY_SEARCH_URL, json=payload, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(TAVILY_SEARCH_URL, json=payload, headers=headers)
        except httpx.TimeoutException:
            raise SearchTimeoutError from None
        except httpx.RequestError:
            raise SearchUpstreamError from None

        self._raise_for_status(response)
        try:
            data = response.json()
        except ValueError:
            raise SearchUpstreamError from None

        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            raise SearchUpstreamError

        items = [item for raw in data["results"] if (item := self._convert_result(raw)) is not None]
        credits_used = self._read_credits(data.get("usage"))
        return SmartCollectSearchResponse(
            query=query,
            total=len(items),
            credits_used=credits_used,
            items=items,
        )

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code == 401:
            raise SearchAuthError
        if response.status_code == 429:
            raise SearchRateLimitError
        if response.status_code in (432, 433):
            raise SearchQuotaError
        if response.status_code >= 400:
            raise SearchUpstreamError

    @staticmethod
    def _convert_result(raw) -> SearchResult | None:
        """把一条 Tavily result 转换为项目自己的 SearchResult。"""
        if not isinstance(raw, dict):
            return None

        url = raw.get("url")
        if not isinstance(url, str):
            return None
        url = url.strip()
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return None

        source = parsed.hostname.lower()
        if source.startswith("www."):
            source = source[4:]

        title = SearchService._clean_title(raw.get("title"), fallback=source)
        snippet = SearchService._clean_snippet(raw.get("content"), title=title)

        try:
            score = float(raw.get("score", 0))
        except (TypeError, ValueError):
            score = 0.0
        if not math.isfinite(score) or score < 0 or score > 1:
            score = 0.0

        return SearchResult(
            title=title,
            url=url,
            source=source,
            snippet=snippet,
            search_score=score,
        )

    @staticmethod
    def _clean_title(value, fallback: str) -> str:
        """轻度清理标题格式，不改写标题原意。"""
        if not isinstance(value, str):
            return fallback
        text = html.unescape(value)
        text = re.sub(r"<[^>]*>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        # 只去掉明显的 Markdown、分隔线和项目符号，不剥离正常中文标点。
        text = text.strip("#*_|｜•·~ ")
        text = re.sub(r"^(?:[-–—]\s*){2,}", "", text)
        text = re.sub(r"(?:\s*[-–—]){2,}$", "", text).strip()
        return text or fallback

    @staticmethod
    def _clean_snippet(value, title: str) -> str:
        """清理搜索片段中的网页格式噪声，并限制卡片展示长度。"""
        if not isinstance(value, str) or not value.strip():
            return ""

        text = html.unescape(value)
        # 在去 HTML 标签前保留常见块级换行，便于逐行过滤导航文字。
        text = re.sub(r"(?i)<br\s*/?>", "\n", text)
        text = re.sub(r"(?i)</(?:p|div|li|h[1-6])\s*>", "\n", text)
        text = re.sub(r"<[^>]*>", " ", text)

        lines = []
        for raw_line in text.splitlines():
            line = SearchService._clean_snippet_line(raw_line)
            if line and not SearchService._is_noise_line(line):
                lines.append(line)

        # Tavily 偶尔把网页主标题作为 content 第一行再次返回。
        while lines and SearchService._same_text(lines[0], title):
            lines.pop(0)

        snippet = re.sub(r"\s+", " ", " ".join(lines)).strip()
        snippet = SearchService._strip_title_prefix(snippet, title)
        return SearchService._truncate_snippet(snippet)

    @staticmethod
    def _clean_snippet_line(value: str) -> str:
        """清理一行通用 Markdown 展示符号，保留实际文字。"""
        line = re.sub(r"^\s{0,3}#{1,6}(?:\s+|$)", "", value)
        line = re.sub(r"^\s*>+\s?", "", line)
        line = re.sub(r"^\s*[-*+]\s+", "", line)
        line = re.sub(r"!\[[^]]*]\([^)]*\)", " ", line)
        line = re.sub(r"\[([^]]+)]\([^)]*\)", r"\1", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        return re.sub(r"\s+", " ", line).strip()

    @staticmethod
    def _is_noise_line(line: str) -> bool:
        """识别通用导航、版权和翻页杂项；不依赖具体网站名称。"""
        normalized = line.strip(" |｜/\\>›»·•-–—_:：").casefold()
        if normalized in GENERIC_NOISE_LABELS:
            return True
        if len(line) <= 80 and re.match(r"^(?:首页|主页|home)\s*[>›»/|｜·]", line, re.IGNORECASE):
            return True
        if re.match(r"^(?:上一篇|下一篇|相关阅读|相关推荐|热门推荐)(?:\s*[:：].*)?$", line):
            return True
        if len(line) <= 160 and re.search(r"(?:版权所有|all rights reserved)", line, re.IGNORECASE):
            return True
        return False

    @staticmethod
    def _same_text(left: str, right: str) -> bool:
        """比较标题文字时忽略空白和标点，仅用于判断开头是否重复。"""
        normalize = lambda text: re.sub(r"[\W_]+", "", text, flags=re.UNICODE).casefold()
        left_key = normalize(left)
        return bool(left_key) and left_key == normalize(right)

    @staticmethod
    def _strip_title_prefix(snippet: str, title: str) -> str:
        """清除同一行开头重复的标题，要求标题后存在明显边界。"""
        if not snippet or not title:
            return snippet
        if snippet.casefold().startswith(title.casefold()):
            remainder = snippet[len(title):]
            if not remainder:
                return ""
            if remainder[0].isspace() or remainder[0] in ":：|｜-–—":
                return remainder.lstrip(" \t:：|｜-–—")
        return snippet

    @staticmethod
    def _truncate_snippet(snippet: str, limit: int = SNIPPET_MAX_LENGTH) -> str:
        """片段最多约 300 字，优先在靠近末尾的中文句号处截断。"""
        if len(snippet) <= limit:
            return snippet
        candidate = snippet[: limit - 1]
        boundary = max(candidate.rfind(mark) for mark in "。！？!?；;")
        if boundary >= limit - 80:
            candidate = candidate[: boundary + 1].rstrip()
        return f"{candidate}…"

    @staticmethod
    def _read_credits(usage) -> int:
        if not isinstance(usage, dict):
            return 0
        try:
            credits = int(usage.get("credits", 0))
        except (TypeError, ValueError):
            return 0
        return max(credits, 0)
