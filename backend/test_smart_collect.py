# -*- coding: utf-8 -*-
"""智能采编第一阶段测试：不访问真实 Tavily，不消耗 API 额度。"""
import json
import unittest

import httpx
from pydantic import ValidationError

from app.schemas.smart_collect import SmartCollectSearchRequest
from app.services.search_service import SearchService, SearchTimeoutError


class SmartCollectSchemaTests(unittest.TestCase):
    def test_query_cannot_be_blank(self):
        with self.assertRaises(ValidationError):
            SmartCollectSearchRequest(query="   ")

    def test_max_results_must_be_between_one_and_twenty(self):
        for invalid_value in (0, 21):
            with self.subTest(max_results=invalid_value), self.assertRaises(ValidationError):
                SmartCollectSearchRequest(query="OpenAI", max_results=invalid_value)


class SearchServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_normal_results_are_converted_to_project_format(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["Authorization"], "Bearer test-key")
            payload = json.loads(request.content.decode("utf-8"))
            self.assertEqual(payload["topic"], "news")
            self.assertIs(payload["include_answer"], False)
            self.assertIs(payload["include_raw_content"], False)
            self.assertEqual(payload["country"], "china")
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": " OpenAI 发布新模型 ",
                            "url": "https://www.openai.com/news/model",
                            "content": " 新闻内容片段 ",
                            "score": 0.88,
                            "raw_content": "不应传给前端",
                        }
                    ],
                    "usage": {"credits": 1},
                },
                request=request,
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await SearchService("test-key", client=client).search("OpenAI", "week", 20)

        self.assertEqual(result.query, "OpenAI")
        self.assertEqual(result.total, 1)
        self.assertEqual(result.credits_used, 1)
        self.assertEqual(
            result.items[0].model_dump(),
            {
                "title": "OpenAI 发布新模型",
                "url": "https://www.openai.com/news/model",
                "source": "openai.com",
                "snippet": "新闻内容片段",
                "search_score": 0.88,
            },
        )

    async def test_empty_results_are_a_normal_response(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"results": [], "usage": {"credits": 1}}, request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await SearchService("test-key", client=client).search("冷门主题", "day", 5)

        self.assertEqual(result.total, 0)
        self.assertEqual(result.items, [])
        self.assertEqual(result.credits_used, 1)

    async def test_tavily_timeout_is_converted_to_safe_error(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("simulated timeout", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(SearchTimeoutError):
                await SearchService("test-key", client=client).search("OpenAI", "week", 10)


class SearchCleaningTests(unittest.TestCase):
    @staticmethod
    def convert(title, content):
        return SearchService._convert_result(
            {
                "title": title,
                "url": "https://news.example.com/article/1",
                "content": content,
                "score": 0.8,
            }
        )

    def test_normal_chinese_content_is_preserved(self):
        content = "新华社北京8月13日电，相关机构今天发布了最新消息，行业正在关注后续进展。"
        item = self.convert("行业发布最新消息", content)
        self.assertEqual(item.snippet, content)

    def test_markdown_headings_and_navigation_are_cleaned(self):
        item = self.convert(
            "新模型正式发布",
            "首页\n## 行业动态\n### 新模型亮相\n正文介绍了模型的主要能力。\n隐私政策",
        )
        self.assertEqual(item.snippet, "行业动态 新模型亮相 正文介绍了模型的主要能力。")

    def test_repeated_title_at_start_is_removed(self):
        item = self.convert(
            "OpenAI 发布新模型",
            "## OpenAI 发布新模型\nOpenAI 今天公布了模型能力和开放计划。",
        )
        self.assertEqual(item.snippet, "OpenAI 今天公布了模型能力和开放计划。")

    def test_long_content_is_truncated(self):
        item = self.convert("长篇新闻", "这是正常中文内容，" * 80)
        self.assertLessEqual(len(item.snippet), 300)
        self.assertTrue(item.snippet.endswith("…"))

    def test_empty_content_does_not_raise(self):
        for content in (None, "", "   "):
            with self.subTest(content=content):
                item = self.convert("空内容新闻", content)
                self.assertEqual(item.snippet, "")

    def test_title_receives_only_light_format_cleaning(self):
        item = self.convert(" &nbsp; |  OpenAI&nbsp; 发布\n新模型  | ", "正文")
        self.assertEqual(item.title, "OpenAI 发布 新模型")


if __name__ == "__main__":
    unittest.main()
