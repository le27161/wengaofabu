# -*- coding: utf-8 -*-
"""文本工具：HTML 正文 → 纯文本（供 content_source 兜底、搜索、AI 调用入参等使用）"""
import re


def strip_html(html: str) -> str:
    """去掉 HTML 标签与常见实体，返回压缩空白后的纯文本；空值返回空字符串"""
    if not html:
        return ""
    text = re.sub(r"<[^>]*>", "", html)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    return re.sub(r"\s+", " ", text).strip()
