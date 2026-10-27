# -*- coding: utf-8 -*-
"""LLM Provider抽象及OpenAI兼容实现；供应商协议只存在于本模块。"""
from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class LLMProviderResult:
    """供应商无关的模型响应和安全用量元数据。"""

    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class LLMProvider(Protocol):
    async def generate(self, system_message: str, user_message: str) -> LLMProviderResult:
        """生成一次结果；业务层不感知具体URL或供应商响应结构。"""


class LLMProviderError(Exception):
    """模型网络、认证、限流或响应结构异常；只保留安全诊断元数据。"""

    def __init__(self, status_code: int | None = None):
        super().__init__()
        self.status_code = status_code


class LLMProviderConfigError(LLMProviderError):
    """模型配置缺失。"""


class LLMProviderTimeoutError(LLMProviderError):
    """模型调用超时。"""


class LLMProviderEmptyResponseError(LLMProviderError):
    """模型没有返回可解析文本。"""


class OpenAICompatibleLLMProvider:
    """使用Chat Completions JSON Object模式的OpenAI兼容Provider。"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 90,
        client: httpx.AsyncClient | None = None,
    ):
        self.api_key = api_key.strip()
        self.base_url = base_url.strip().rstrip("/")
        self.model = model.strip()
        self.timeout = max(1.0, min(float(timeout), 180.0))
        self.client = client

    @property
    def endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    async def generate(self, system_message: str, user_message: str) -> LLMProviderResult:
        if not self.api_key or not self.base_url or not self.model:
            raise LLMProviderConfigError
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            "response_format": {"type": "json_object"},
            # Qwen3.7 Plus默认开启思考；关闭后稳定返回JSON Object。
            "enable_thinking": False,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            if self.client is not None:
                response = await self.client.post(
                    self.endpoint,
                    json=payload,
                    headers=headers,
                )
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.endpoint,
                        json=payload,
                        headers=headers,
                    )
        except httpx.TimeoutException:
            raise LLMProviderTimeoutError from None
        except httpx.RequestError:
            raise LLMProviderError from None

        if response.status_code in (408, 504):
            raise LLMProviderTimeoutError(status_code=response.status_code)
        if response.status_code >= 400:
            raise LLMProviderError(status_code=response.status_code)
        try:
            data = response.json()
            message = data["choices"][0]["message"]
            content = message.get("content")
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise LLMProviderError from None
        if not isinstance(content, str) or not content.strip():
            raise LLMProviderEmptyResponseError

        usage = data.get("usage") if isinstance(data, dict) else None
        usage = usage if isinstance(usage, dict) else {}
        response_model = data.get("model") if isinstance(data, dict) else None
        return LLMProviderResult(
            text=content.strip(),
            model=response_model if isinstance(response_model, str) else self.model,
            input_tokens=self._optional_int(usage.get("prompt_tokens")),
            output_tokens=self._optional_int(usage.get("completion_tokens")),
            total_tokens=self._optional_int(usage.get("total_tokens")),
        )

    @staticmethod
    def _optional_int(value) -> int | None:
        return value if type(value) is int and value >= 0 else None
