# -*- coding: utf-8 -*-
"""AI 大模型调用服务：直接通过 OpenAI 兼容 API 调用大模型

支持所有 OpenAI 兼容接口（DeepSeek、Groq、硅基流动、通义千问等）。
配置在 .env 中设置 AI_API_BASE / AI_API_KEY / AI_MODEL / AI_TIMEOUT。
"""
import json
import re
import httpx
import asyncio

from ..config import settings


class AIServiceError(Exception):
    """AI 调用异常（中文提示）"""


def _final_answer_only(content: str) -> str:
    """移除模型混入的思考标签，仅保留可以展示给用户的最终内容。"""
    if not isinstance(content, str):
        return ""
    return re.sub(r"<think>[\s\S]*?</think>\s*", "", content, flags=re.IGNORECASE).strip()


class AIService:
    """AI 大模型 HTTP 客户端"""

    def __init__(self):
        if not settings.AI_API_KEY or settings.AI_API_KEY == "sk-your-api-key-here":
            raise AIServiceError("未配置 AI_API_KEY，请在 .env 中填写你的 API Key")
        self.api_base = settings.AI_API_BASE.rstrip("/")
        self.api_key = settings.AI_API_KEY
        self.model = settings.AI_MODEL
        self.timeout = settings.AI_TIMEOUT

    def _build_url(self):
        return f"{self.api_base}/chat/completions"

    def _build_headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 2000) -> str:
        """调用大模型聊天接口（异步），返回 assistant 回复文本"""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        # 使用 httpx.Timeout 显式控制各阶段超时：连接 30s，读取 300s，写入 60s
        timeout = httpx.Timeout(connect=30.0, read=float(self.timeout), write=60.0, pool=30.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(self._build_url(), json=payload, headers=self._build_headers())
        except httpx.TimeoutException:
            raise AIServiceError(f"AI 调用超时（{self.timeout}s），请检查网络或调大 AI_TIMEOUT")
        except httpx.RequestError as e:
            raise AIServiceError(f"无法连接 AI 服务：{e}")

        if resp.status_code != 200:
            detail = resp.text
            try:
                detail = resp.json().get("error", {}).get("message", resp.text)
            except Exception:
                pass
            raise AIServiceError(f"AI 返回错误（HTTP {resp.status_code}）：{detail}")

        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise AIServiceError("AI 返回为空，未生成任何内容")
        msg = choices[0].get("message", {})
        # 优先取 content，若无则回退到 reasoning_content（部分模型将回答放在此字段）
        # reasoning_content 是模型内部思考过程，不能作为正式回答展示。
        content = _final_answer_only(msg.get("content") or "")
        if not content:
            # 打印完整响应结构用于调试
            raise AIServiceError(f"AI 返回消息为空，原始响应结构：keys={list(data.keys())}, choices[0] keys={list(choices[0].keys())}, msg keys={list(msg.keys())}")
        return content

    def chat_stream(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 800):
        """流式调用大模型，逐个 yield delta 文本片段"""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        # 流式超时：连接 30s，读取 300s（流式响应可能较慢），写入 60s
        timeout = httpx.Timeout(connect=30.0, read=float(self.timeout), write=60.0, pool=30.0)
        try:
            with httpx.Client(timeout=timeout) as client:
                with client.stream("POST", self._build_url(), json=payload, headers=self._build_headers()) as resp:
                    if resp.status_code != 200:
                        detail = resp.text
                        try:
                            detail = resp.json().get("error", {}).get("message", resp.text)
                        except Exception:
                            pass
                        raise AIServiceError(f"AI 流式调用失败（HTTP {resp.status_code}）：{detail}")
                    for line in resp.iter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]  # 去掉 "data: " 前缀
                        if data_str.strip() == "[DONE]":
                            return
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            # 优先取 content，若无则回退到 reasoning_content（deepseek-v4-flash 等模型将回答放在此字段）
                            # 流式场景同样忽略 reasoning_content，只发送正式回答。
                            content = _final_answer_only(delta.get("content") or "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
        except httpx.TimeoutException:
            raise AIServiceError(f"AI 流式调用超时（{self.timeout}s）")
        except httpx.RequestError as e:
            raise AIServiceError(f"无法连接 AI 服务：{e}")


# ── 关键词提取提示词 ──

KEYWORD_SYSTEM_PROMPT = """你是一名新闻文章文本分类与知识标签提取专家。你必须严格遵守以下规则，不得补充、猜测或编造文章中未出现或无法直接推断的事实。

## 一、分类（必选且仅选一项）
从以下十类中选择唯一类别：
金融、房地产、股票、教育、科学、社会、政治、运动、游戏、娱乐。

## 二、主标签（main_tags）提取规则
1. 主标签必须是文章标题或正文中**原样直接出现**的专业术语、机制、方法、制度、事件概念或领域概念。
2. 不得改写、概括、补充或猜测。若文章未提及任何可作主标签的概念，则输出空数组 []。
3. 主标签数量：1～6个，精简为原则，宁缺毋滥。
4. 下列内容**绝不可**作为主标签（除非文章明确在解释某个以它们命名的专业概念）：
   - 地名、学校、公司、人物、机构、国家、货币
   - 普通物品、口号、省份、常识词汇
   - 标题泛词（如"新闻""报道""今天"）
   - 新闻主体（如"某公司宣布…"中的"某公司"）
   - 常识内容：比如"空调""遥控器"等生活常识名词
   - 地点、人物、机构等非知识性词汇

## 三、副标签（prerequisites）提取规则（每个主标签对应一个数组）
1. 副标签是**理解该主标签所需的前置知识**，必须严格构成一条**递推学习链**：
   - 第1个最基础，后续每个副标签建立在前一个之上，最后一个最接近主标签。
   - 例如：主标签"RNN" → 副标签 ["机器学习", "深度学习", "人工神经网络（ANN）"]
     （先懂机器学习→再懂深度学习→再懂ANN→最后理解RNN）
   - 副标签选取也要遵守主标签的选取规则（除"原样出现"外，副标签可以是未出现的通用前置知识）

2. 副标签**可以是文章未出现**的通用前置知识，但必须逐层强关联，不可并列或无关。
3. 每个主标签的副标签数量：0～5个。若无法形成递推链，则输出空数组 []。
4. 禁止出现：
   - 与主标签相同或同义的标签
   - 常识性知识（例如"穿越火线"的主标签无需副标签"游戏"）
   - 地点、人物、机构等非知识性词汇
   - 为凑数而添加的弱关联标签

## 四、输出格式
只返回一个合法的 JSON 对象，不要 Markdown、解释或额外字段。格式固定为：
{"category":"科学","main_tags":[{"name":"RNN","prerequisites":["机器学习","深度学习","人工神经网络（ANN）"]}]}

若没有主标签，则返回 {"category":"社会","main_tags":[]}

## 五、重要原则
- 所有标签必须源自文章内容，不得臆造。
- 关联性必须极强，若无法联想则不强联。
- 主标签和副标签均为知识性概念，拒绝常识或泛化词汇。"""


async def extract_keywords_via_ai(content: str) -> dict:
    """调用 AI 大模型提取文章分类、主标签及前置知识链

    返回格式：{"category": "科学", "main_tags": [{"name": "RNN", "prerequisites": [...]}]}
    """
    ai = AIService()
    user_prompt = f"Article content:\n---\n{content[:8000]}\n---"

    raw = await ai.chat(
        messages=[
            {"role": "system", "content": KEYWORD_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        max_tokens=4000,
    )

    raw = raw.strip()
    # 去掉 markdown 代码块
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # 兜底：尝试从文本中提取 JSON 对象
        match = re.search(r'\{[\s\S]*"main_tags"[\s\S]*\}', raw)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                data = {"category": "社会", "main_tags": []}
        else:
            data = {"category": "社会", "main_tags": []}

    # 规范化输出
    if not isinstance(data, dict):
        data = {"category": "社会", "main_tags": []}
    if not isinstance(data.get("main_tags"), list):
        data["main_tags"] = []
    if not isinstance(data.get("category"), str) or not data["category"].strip():
        data["category"] = "社会"

    return data


# ── 标签解释 ──

EXPLAIN_TAG_SYSTEM_PROMPT = """你是知识渊博的讲师，面向非专业人士通俗解释术语。

你的全部回答只能包含解释正文本身。从用户给出的术语第一个字开始写起，结尾自然结束。不得有任何前缀、后缀、旁白、说明或自我提醒。

解释结构：定义 → 核心原理 → 实际应用，顺序固定。
关键术语用粗体标注（中文粗体为 **术语**）。
字数根据概念复杂程度自然控制在50~300字之间，无需提及字数。
语言通俗，多用生活类比，严禁堆砌术语。
以下内容一旦出现在回答中即视为违规：
任何思考、反思、自问自答（如“我们需要…”“我们来看…”“注意…”）。
任何对任务要求的复述、解释或确认（如“按定义→原理→应用”“总字数…”）。
任何标题、编号、分隔符、括号说明。
任何与解释本身无关的元语言（包括“好的”“下面开始”“我的回答是”等）。
回答必须从术语的释义直接开篇，例如用户问“以旧换新”，你的回答第一句话必须是“以旧换新是指……”或类似直接解释，不得有任何铺垫。
若你输出任何非解释性文字，即视为严重错误。现在开始，只输出解释。
"""

# 元文本前缀匹配：仅匹配 AI 可能输出的"自言自语/格式说明/任务确认"类纯元文本
# 注意：不要匹配解释正文中的合法关键词（如"核心原理""实际应用""定义"等）
_META_PREFIX_RE = re.compile(
    r'^\s*('
    r'好的[，,]\s*下面是|好的[，,]\s*我来|好的[，,]\s*让我|'
    r'下面是.*解释|以下.*解释|我来.*解释|让我.*解释|'
    r'按照.*要求[，,]|根据.*指示[，,]|'
    r'字数.*[0-9]+.*[0-9]+|控制.*[0-9]+.*字|'
    r'格式[：:]\s*定义|结构[：:]\s*定义|'
    r'我们.*(?:需要|来|要).*(?:解释|说明|按照|输出).*[：:]|'
    r'注意[：:]\s*$|注意[：:]\s*[\n\r]|'
    r'回答[：:]|解释[：:]|答案[：:]'
    r')',
    re.IGNORECASE
)


def _strip_meta_prefix(text: str) -> str:
    """从文本开头移除纯元文本前缀（AI 自言自语/格式确认），保留正文

    与旧版不同：只匹配位于开头的纯元文本句子，不匹配正文中的关键词。
    例如 "好的，下面是解释：撞击羽流是指..." → 移除前缀 → "撞击羽流是指..."
    但 "撞击羽流是指...核心原理是..." → 不做任何移除
    """
    stripped = _META_PREFIX_RE.sub('', text, count=1).strip()
    # 如果移除后为空，说明整段都是元文本，返回原始文本的 fallback
    if not stripped:
        stripped = text.strip()
    return stripped


def explain_tag_streaming(tag: str):
    """流式解释单个标签：逐块输出，首块到达时过滤元文本前缀

    改进：不再缓存全部内容，而是边收边发。
    前 80 个字符作为"前缀缓冲区"用于元文本检测，之后直接透传。
    """
    ai = AIService()
    buffer = ""          # 前缀缓冲区，用于元文本检测
    buffer_sent = False  # 是否已发送过缓冲内容

    for chunk in ai.chat_stream(
        messages=[
            {"role": "system", "content": EXPLAIN_TAG_SYSTEM_PROMPT},
            {"role": "user", "content": tag},
        ],
        temperature=0.5,
        max_tokens=400,
    ):
        if not buffer_sent:
            buffer += chunk
            # 缓冲区足够大或收到换行/句号时，尝试发送
            if len(buffer) >= 80 or '\n' in buffer or '。' in buffer:
                clean = _strip_meta_prefix(buffer)
                if clean:
                    yield clean
                buffer_sent = True
                buffer = ""
        else:
            yield chunk

    # 兜底：如果 AI 始终没返回足够内容，尝试发送缓冲区
    if not buffer_sent and buffer.strip():
        clean = _strip_meta_prefix(buffer)
        if clean:
            yield clean

    # 如果全程无内容，返回一个兜底提示（避免前端展示空白）
    if not buffer_sent and not buffer.strip():
        # 说明 AI 返回了空内容
        yield f"「{tag}」的解释暂未生成，请稍后重试。"