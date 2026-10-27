# AI 协作台调用记录与未保存文稿的关联设计（draft_key）

> 状态：已确认（2026-08-16，按推荐方案实施）
> 关联：docs/ai_assist_async.md（异步任务改造）

## 1. 背景与目标

AI 协作台（写稿页）的 5 个 AI 功能（分类/摘要/审核/校验/打分）为异步任务，每次调用都会写入
`ai_tasks`（任务）与 `ai_call_logs`（调用记录）。当前关联字段 `article_id` 在「新建文稿未保存」
时为 NULL——新建文稿只有保存后才会有 ID，导致：

1. 调用记录无法与最终保存的文稿对应（后台「AI 调用记录」页面 article_id 永远为空）；
2. 未保存草稿关闭 AI 协作台再打开时，无法恢复上次结果，进行中的任务也无法续轮询。

目标：
- 新建文稿在保存后，其 AI 任务、调用记录（以及分类纠正样本）能自动回填正式文稿 ID；
- 未保存草稿重开 AI 协作台时能按草稿会话恢复结果 / 继续轮询；
- 不影响智能采编（服务端先建稿再进编辑页，走已有 ID 的编辑路径）等其他业务。

## 2. 数据结构

`ai_tasks`、`ai_call_logs`、`ai_corrections` 三表各新增一列：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| draft_key | VARCHAR(64) NULL，加索引 | 新建文稿保存前的草稿会话标识（前端 UUID）；保存后回填 article_id，draft_key 保留用于追溯 |

- 新库由 `Base.metadata.create_all` 自动创建；老库在 `ensure_schema_compat()` 中幂等补列（同现有 article_id 补列写法）。
- 历史 NULL 记录不回填（无法溯源），后台展示为「未关联文稿」。

## 3. 接口契约

### 3.1 AI 任务提交（5 个接口，入参扩展）

`POST /api/ai/assist/{classify|summary|review|check|score}`

请求体 `AIAssistIn` 增加可选字段：

```json
{ "title": "...", "content": "...", "article_id": null, "draft_key": "uuid-xxx" }
```

- `draft_key`：新建未保存文稿的草稿会话标识；编辑已有文稿时可传可不传。
- 后端 `_create_task` 将 draft_key 一并落库；worker 完成时透传给调用记录。

### 3.2 最近任务查询（恢复上次结果）

`GET /api/ai/assist/tasks/latest?feature_type=1&article_id=..&draft_key=..`

- 有 `article_id`：按 `user_id + feature_type + article_id` 查最近一条（原逻辑）。
- 无 `article_id` 但有 `draft_key`：按 `user_id + feature_type + draft_key AND article_id IS NULL` 查最近一条。
- 两者都无：404（新建未保存且无草稿会话时前端不会调用）。

### 3.3 文稿创建 / 编辑（绑定回填）

`POST /api/articles`、`PUT /api/articles/{id}` 请求体 `ArticleIn` 增加可选 `draft_key`。

创建成功后（同一事务）批量回填：

```
UPDATE ai_tasks      SET article_id = :id WHERE draft_key = :key AND article_id IS NULL
UPDATE ai_call_logs  SET article_id = :id WHERE draft_key = :key AND article_id IS NULL
UPDATE ai_corrections SET article_id = :id WHERE draft_key = :key AND article_id IS NULL
```

- 只回填 `article_id IS NULL` 的行，幂等安全；更新接口同样兜底（防多步保存场景）。
- 编辑接口不传 draft_key 时无副作用（智能采编等既有调用不受影响）。

### 3.4 后台调用记录

`GET /api/admin/ai-calls` 返回项增加 `article_id`，前端「AI 调用记录」页面新增「关联文稿」列
（`#id` / 「未关联」），便于管理员核对绑定结果。

## 4. 前端交互

1. `ArticleEditView.vue`：新建文稿（`!isEdit`）时生成 `form.draft_key`（`crypto.randomUUID()`，
   兜底时间戳随机串）；保存 payload 带上 `draft_key`。编辑已有文稿不生成（isEdit 路径不受影响）。
2. `AIAssistDrawer.vue`：
   - 提交任务 payload 增加 `draft_key: props.form?.draft_key || null`；
   - `restoreLatestResults()` 恢复依据由「必须 form.id」改为 `form.id || form.draft_key`；
   - 分类纠正 `aiCorrectionApi.submit` 同步带 draft_key。
3. `api/index.js`：`latestTask(featureType, articleId, draftKey)` 透传两个可选参数。

## 5. 成功标准

1. 新建文稿（带 draft_key）调用 AI 功能 → 保存草稿后，`ai_tasks/ai_call_logs/ai_corrections`
   对应行的 article_id 自动等于新文稿 ID；
2. 未保存草稿重开 AI 协作台：最近一次成功结果恢复、进行中任务继续轮询、失败可重调；
3. 智能采编生成的文稿走编辑页保存，不受影响（不传 draft_key，行为与原来一致）；
4. 不同用户的记录不串（查询恒带 user_id）；不同草稿用不同 draft_key 不串；
5. `backend/smoke_test.py` 增加对应断言并可重复运行。

## 6. 不做的事

- 不新增后台任务管理页面；不改异步任务执行模型；
- 不回填历史 NULL 记录；不把 draft_key 暴露到门户/前台任何接口。
