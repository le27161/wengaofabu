# -*- coding: utf-8 -*-
"""正文提取Provider：屏蔽第三方接口结构，向业务层返回统一结果。"""
from dataclasses import dataclass
from typing import Protocol

import httpx


TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"


@dataclass(frozen=True)
class ContentProviderResult:
    """一个URL的统一正文提取结果。"""

    url: str
    content: str | None = None
    title: str | None = None
    error_message: str | None = None


class ContentProvider(Protocol):
    async def extract_batch(self, urls: list[str]) -> list[ContentProviderResult]:
        """批量提取URL，并按输入顺序返回一一对应的结果。"""


class ContentProviderError(Exception):
    message = "正文提取服务暂时不可用"


class ContentProviderConfigError(ContentProviderError):
    message = "正文提取服务尚未配置"


class ContentProviderTimeoutError(ContentProviderError):
    message = "正文提取服务响应超时"


class ContentProviderAuthError(ContentProviderError):
    message = "正文提取服务认证失败"


class ContentProviderQuotaError(ContentProviderError):
    message = "正文提取服务额度不足"


class TavilyContentProvider:
    """Tavily Extract实现；Router和业务Service不感知其原始JSON结构。"""

    def __init__(
        self,
        api_key: str,
        timeout: float = 15,
        client: httpx.AsyncClient | None = None,
    ):
        self.api_key = api_key.strip()
        self.timeout = max(1.0, min(float(timeout), 60.0))
        self.client = client

    async def extract_batch(self, urls: list[str]) -> list[ContentProviderResult]:
        if not urls:
            return []
        if not self.api_key:
            raise ContentProviderConfigError

        payload = {
            "urls": urls,
            "extract_depth": "basic",
            "include_images": False,
            "format": "markdown",
            "timeout": self.timeout,
            "include_usage": False,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            if self.client is not None:
                response = await self.client.post(
                    TAVILY_EXTRACT_URL,
                    json=payload,
                    headers=headers,
                )
            else:
                async with httpx.AsyncClient(timeout=self.timeout + 5) as client:
                    response = await client.post(
                        TAVILY_EXTRACT_URL,
                        json=payload,
                        headers=headers,
                    )
        except httpx.TimeoutException:
            raise ContentProviderTimeoutError from None
        except httpx.RequestError:
            raise ContentProviderError from None

        self._raise_for_status(response)
        try:
            data = response.json()
        except ValueError:
            raise ContentProviderError from None
        if not isinstance(data, dict):
            raise ContentProviderError

        successes = self._read_successes(data.get("results"))
        failures = self._read_failures(data.get("failed_results"))
        results = []
        for url in urls:
            if url in successes:
                results.append(successes[url])
            elif url in failures:
                results.append(failures[url])
            else:
                results.append(
                    ContentProviderResult(
                        url=url,
                        error_message="正文提取服务未返回该来源",
                    )
                )
        return results

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code in (401, 403):
            raise ContentProviderAuthError
        if response.status_code in (429, 432, 433):
            raise ContentProviderQuotaError
        if response.status_code >= 400:
            raise ContentProviderError

    @staticmethod
    def _read_successes(value) -> dict[str, ContentProviderResult]:
        results: dict[str, ContentProviderResult] = {}
        if not isinstance(value, list):
            return results
        for item in value:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            content = item.get("raw_content")
            if not isinstance(url, str) or not url.strip():
                continue
            results[url.strip()] = ContentProviderResult(
                url=url.strip(),
                content=content if isinstance(content, str) else None,
                title=item.get("title") if isinstance(item.get("title"), str) else None,
            )
        return results

    @classmethod
    def _read_failures(cls, value) -> dict[str, ContentProviderResult]:
        results: dict[str, ContentProviderResult] = {}
        if not isinstance(value, list):
            return results
        for item in value:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not isinstance(url, str) or not url.strip():
                continue
            raw_error = item.get("error") or item.get("error_message")
            message = cls._safe_error_message(raw_error)
            results[url.strip()] = ContentProviderResult(
                url=url.strip(),
                error_message=message,
            )
        return results

    @staticmethod
    def _safe_error_message(value) -> str:
        if not isinstance(value, str) or not value.strip():
            return "该来源正文提取失败"
        message = " ".join(value.split())[:300]
        return f"该来源正文提取失败：{message}"
