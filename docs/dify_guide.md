# Dify 工作流接入指南

本文面向开发者，说明如何把项目（文稿发布系统）与 [Dify](https://dify.ai) 工作流对接：
环境变量预留、数据库登记、统一调用服务，以及如何把 Dify 工作流接入现有业务。

## 1. 整体设计

```
业务代码（如文稿发布后生成摘要）
        │  run_workflow(db, inputs, name="article_summary")
        ▼
services/dify_service.py   ← 统一封装 Dify /workflows/run 接口（阻塞模式）
        │
        ├── 数据库 dify_workflows 表（后台 /api/dify/workflows 管理，可登记多个工作流）
        └── 兜底 .env 的 DIFY_API_BASE / DIFY_API_KEY / DIFY_TIMEOUT
        │
        ▼
Dify 平台（云端 https://api.dify.ai/v1 或自建地址）
```

配置来源优先级：**数据库按 name/id 指定的工作流 > 数据库第一条启用记录 > 环境变量**。

## 2. 在 Dify 平台准备接入信息

1. 登录 Dify 控制台，进入目标应用（Workflow 类型）；
2. 右上角「发布」后，点击「访问 API」；
3. 在「API 密钥」页签点击「创建密钥」，得到形如 `app-xxxxxxxx` 的 **API Key**；
4. 「API 服务器」处即为 **API Base URL**：
   - 云端：`https://api.dify.ai/v1`
   - 自建部署：`http(s)://你的域名/v1`
5. 查看工作流需要哪些输入变量（开始节点定义的变量名），调用时放入 `inputs`。

Dify 官方工作流接口（阻塞模式）：

```
POST {api_base}/workflows/run
Headers: Authorization: Bearer {api_key}
Body:
{
  "inputs": { "title": "..." },   // 工作流开始节点的输入变量
  "response_mode": "blocking",    // blocking 阻塞返回 / streaming 流式
  "user": "dify-user"             // 调用方用户标识
}
```

成功返回 `data.outputs` 即为工作流输出；失败返回 `data.error` 或非 200 状态码。

## 3. 环境变量配置（推荐先用这个跑通）

编辑 `backend/.env`：

```ini
DIFY_API_BASE=https://api.dify.ai/v1
DIFY_API_KEY=app-xxxxxxxx
DIFY_TIMEOUT=30
```

对应读取代码在 `backend/app/config.py`，改动后重启后端生效。

## 4. 数据库登记工作流（多工作流管理）

后台提供了「Dify 工作流」管理页面（管理员登录 → 侧边栏 → Dify 工作流），
支持列表、新增、编辑、删除与试运行，无需写代码即可完成配置登记。

表 `dify_workflows`（新建，`python init_db.py` 或后端启动时自动建表）：

| 字段 | 说明 |
| --- | --- |
| `id` | 工作流ID |
| `name` | 业务标识（唯一），如 `article_summary`、`ai_review` |
| `api_base` | Dify API 地址 |
| `api_key` | Dify 应用 API Key |
| `description` | 用途说明 |
| `input_schema` | 输入参数说明（JSON），供开发查阅 |
| `enabled` | 是否启用 |
| `timeout` | 调用超时（秒） |

管理接口（仅管理员，API Key 默认脱敏显示）：

```
GET    /api/dify/workflows               列表
POST   /api/dify/workflows               登记
PUT    /api/dify/workflows/{id}          编辑
DELETE /api/dify/workflows/{id}          删除
POST   /api/dify/workflows/{id}/run      试运行（body: {"inputs": {...}}）
```

登记示例：

```json
POST /api/dify/workflows
{
  "name": "article_summary",
  "api_base": "https://api.dify.ai/v1",
  "api_key": "app-xxxxxxxx",
  "description": "生成文稿摘要",
  "input_schema": { "title": "文章标题", "content": "正文内容" },
  "enabled": true,
  "timeout": 60
}
```

## 5. 在业务代码中调用 Dify 工作流

统一入口 `run_workflow()`（`backend/app/services/dify_service.py`），无需关心 HTTP 细节：

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.dify_service import DifyError, run_workflow

router = APIRouter(prefix="/demo", tags=["Dify 接入示例"])


@router.post("/ai-summary/{article_id}", summary="示例：调用 Dify 生成文稿摘要")
def ai_summary(article_id: int, db: Session = Depends(get_db)):
    from ..models.article import Article

    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "文稿不存在")

    try:
        # 按登记名称调用；未登记时兜底走 .env 配置
        data = run_workflow(
            db,
            inputs={"title": article.title, "content": article.content},
            name="article_summary",  # 对应 dify_workflows.name
        )
    except DifyError as e:
        raise HTTPException(502, str(e)) from None

    summary = (data.get("outputs") or {}).get("summary", "")
    return {"message": "AI 摘要生成成功", "summary": summary}
```

## 6. 把 Dify 接入现有业务（二次开发建议）

推荐接几个天然适合的节点，改动都集中在对应路由文件：

| 业务场景 | 触发点 | 建议工作流 |
| --- | --- | --- |
| 文稿发布后生成摘要 | `articles.py` 二审通过 / 自动审核发布 | 摘要生成工作流 |
| 提审前内容预审 | `submit_article` 提审时 | 内容合规检查工作流 |
| 智能配图/标签 | 创建或编辑文稿保存时 | 标签/封面生成工作流 |
| 后台问答助手 | 新增客服路由 | Chatflow 应用 |

接入示例（在 `articles.py` 的 `submit_article` 中调用预审，失败不阻断提审）：

```python
# 提审时异步预审：Dify 不可用不阻塞正常提审流程
try:
    data = run_workflow(db, inputs={"title": article.title, "content": article.content}, name="content_precheck")
    # data["outputs"] 可落库或仅记录日志
except DifyError:
    pass
```

> 注意：Dify 调用属于外部 IO，正式环境建议放入后台任务（如 FastAPI BackgroundTasks
> 或 Celery），避免拖慢主接口响应。

## 7. 开发新的 Dify 调用接口（扩展步骤）

1. 在 Dify 平台建好工作流并获取 API Key；
2. 通过 `/api/dify/workflows` 登记（或直接填 `.env`）；
3. 在 `backend/app/services/dify_service.py` 追加需要的封装方法（如流式调用）；
4. 在对应业务路由（如 `articles.py`）中调用 `run_workflow()`；
5. 需要独立接口就在 `backend/app/routers/` 新建路由并在 `main.py` 挂载。

## 8. 安全与注意事项

- **API Key 不要下发到前端**，后端管理接口列表默认脱敏（只显示后 4 位）；
- `.env` 已被 `.gitignore` 忽略，不要在仓库中提交真实 Key；
- 生产环境数据库中的 Key 建议加密存储（可用环境变量注入代替库内明文）；
- 默认阻塞模式有超时保护（`timeout`），流式模式（SSE）如需支持请在服务层扩展；
- 调用前先在工作流「开始」节点确认输入变量名，与 `inputs` 键一一对应；
- 试运行接口 `POST /api/dify/workflows/{id}/run` 可直接验证连通性与输出结构。
