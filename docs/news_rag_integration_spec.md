# 新闻 AI 助手接入规格

## 目标

保持新闻系统与 KnowledgeHub RAG 服务为两个独立 FastAPI 服务，通过 HTTP 实现：

- 新闻发布成功后，将已发布新闻标题、纯文本正文和来源 Metadata 同步到 RAG。
- 新闻下线或删除后，删除 RAG 中对应文章的向量 Chunk。
- 给前端提供 `/api/ai-news/chat`，由新闻后端转发问题到 RAG，避免前端直接暴露 RAG 地址。

## 服务边界

```text
新闻前端 -> 新闻后端 :8000 -> RAG 服务 :8001
                              -> Chroma / Chat Model
```

新闻系统负责用户权限、文章状态和文章 URL；RAG 负责切块、向量检索、精排和生成回答。

## 配置

新增环境变量：

```env
RAG_ENABLED=true
RAG_BASE_URL=http://127.0.0.1:8001
RAG_TIMEOUT=60
```

`RAG_ENABLED=false` 时不调用 RAG，保证未启动 RAG 服务时新闻系统仍可运行。

## 接口契约

### 新闻后端内部调用 RAG

发布/修改：`POST {RAG_BASE_URL}/news/articles/index`

请求字段：`article_id`、`title`、`content`、`category`、`published_at`、`url`。

下线/删除：`DELETE {RAG_BASE_URL}/news/articles/{article_id}`。

### 新闻前端调用新闻后端

`POST /api/ai-news/chat`

请求：

```json
{
  "question": "最近有哪些 AI 新闻？",
  "category": "科技"
}
```

响应：透传 RAG 的 `answer` 和 `sources`，来源包含文章 ID、标题、链接、发布时间。

## 状态机触发点

- `submit_article` 开启自动审核并变为 `published`：提交 RAG 入库任务。
- `review_article` 二审通过并变为 `published`：提交 RAG 入库任务。
- `offline_article` 变为 `offline`：提交 RAG 删除任务。
- `delete_article` 删除数据库记录：提交 RAG 删除任务。

草稿、待审核、驳回状态不进入新闻知识库。

## 失败策略

RAG 调用失败只记录日志，不回滚已经成功的新闻事务；RAG 服务恢复后可通过重新发布/补偿任务重新索引。对用户提问时，RAG 不可用返回 503 和稳定中文提示。

## 历史新闻首次入库

已有的已发布新闻需要运行批量脚本同步，脚本只读取 `published` 文章并按发布时间从新到旧处理：

```powershell
cd backend
python -X utf8 sync_published_articles_to_rag.py --limit 20
```

可通过 `--offset` 分批执行，例如先同步前 20 篇，再同步第 21 到 40 篇：

```powershell
python -X utf8 sync_published_articles_to_rag.py --limit 20 --offset 20
```

脚本要求 `.env` 已设置 `RAG_ENABLED=true`，失败文章 ID 会在最后输出，可单独排查或重试。

## 成功标准

- `RAG_ENABLED=false` 时原有新闻接口行为不变。
- 已发布新闻可通过 `/api/ai-news/chat` 查询，草稿/下线新闻不会被同步回答。
- 发布、下线、删除路由的业务状态机不改变。
- 新增调用有超时，日志不包含 API Key。
- `smoke_test.py` 至少覆盖 AI 新闻助手参数校验和 RAG 不可用时的 503 语义。
