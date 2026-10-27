# -*- coding: utf-8 -*-
"""新闻 RAG 接入的本地单元测试，不连接真实 RAG 或模型服务。"""
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.schemas.ai_news import AINewsChatIn
from app.services.rag_news_service import RAGNewsServiceError, ask_news_assistant


class AINewsSchemaTests(unittest.TestCase):
    def test_question_cannot_be_blank(self):
        with self.assertRaises(ValidationError):
            AINewsChatIn(question="")

    def test_question_and_category_are_kept(self):
        body = AINewsChatIn(question="最近有哪些科技新闻？", category="科技")
        self.assertEqual(body.question, "最近有哪些科技新闻？")
        self.assertEqual(body.category, "科技")


class RAGNewsServiceTests(unittest.TestCase):
    @patch("app.services.rag_news_service.settings")
    def test_disabled_rag_returns_stable_error(self, mock_settings):
        mock_settings.RAG_ENABLED = False
        with self.assertRaisesRegex(RAGNewsServiceError, "尚未启用"):
            ask_news_assistant("最近有哪些新闻？")


if __name__ == "__main__":
    unittest.main()
