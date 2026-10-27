# AI 协作台异步任务化改造规格

> 状态：已确认（2026-08-14，按推荐版实施）

## 1. 目标

将 AI 协作台 5 个 AI 功能接口（AI 智能分类 / AI 生成摘要 / AI 多维度审核 / AI 内容校验 / AI 文稿打分）
从"同步阻塞返回"改为"异步任务 + 轮询"模式，为后续接入真实模型调用（如 Dify 工作流，耗时可达数十秒至数分钟）
铺平道路，避免 HTTP 长连接、网关超时、页面刷新丢结果、线程池被长任务占满等问题。

改造后接口契约不变（入参仍为标题/摘要/正文/栏目），前端统一走"提交任务 → 轮询状态 → 回写结果"。
当前任务执行体仍为占位假逻辑（秒级完成），后续接入真实 AI 时只需替换执行器内部函数，前端与接口契约无需改动。

## 2. 数据结构

新建表 `ai_tasks`（AI 任务执行表），与 `ai_call_logs`（调用记录表）职责分离：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | INT PK AUTO_INCREMENT | 任务ID |
| user_id | INT FK users.id | 发起任务用户 |
| feature_type | INT | 功能类型，数字含义与 ai_call_logs 一致：1=AI分类 2=AI生成摘要 3=AI多维度审核 4=AI内容校验 5=AI文稿打分 |
| status | VARCHAR(16) | 任务状态：pending→running→success / failed |
| input_params | JSON | 调用入参（标题/摘要/正文/栏目ID） |
| result_data | JSON NULL | 成功时的业务返回数据（即原接口 data） |
| error_message | VARCHAR(500) NULL | 失败原因 |
| created_at | DATETIME | 任务提交时间 |
| started_at | DATETIME NULL | 任务开始执行时间 |
| finished_at | DATETIME NULL | 任务完成时间 |

表由 `Base.metadata.create_all` 自动创建（重启后端或执行 `python init_db.py` 即可，幂等）。

## 3. 接口契约（前缀 /api/ai/assist）

### 3.1 提交任务（原 5 个功能接口改为提交任务）

`POST /api/ai/assist/classify`、`/summary`、`/review`、`/check`、`/score`

- 权限：登录用户（`get_current_user`），与原一致
- 请求体：不变（`AIAssistIn`：title / summary / content / category_ids）
- 响应（200）：
  ```json
  { "message": "AI 任务已提交", "task_id": 123, "status": "pending" }
  ```
- 语义：入参校验通过后立即落库返回，任务交由后台线程池执行，接口不等待模型结果

### 3.2 查询任务状态

`GET /api/ai/assist/tasks/{task_id}`

- 权限：登录用户；仅任务发起人本人或管理员可查
- 响应（200）：
  ```json
  {
    "task_id": 123,
    "feature_type": 1,
    "feature_name": "AI 分类",
    "status": "success",
    "result": { "category_name": "时政" },
    "error": null,
    "created_at": "2026-08-14 10:00:00",
    "finished_at": "2026-08-14 10:00:01"
  }
  ```
- 状态取值：pending / running / success / failed；`result` 仅在 success 时非空
- 非本人且非管理员：403；任务不存在：404

## 4. 后端执行模型

- 模块级 `ThreadPoolExecutor(max_workers=4)`（可经环境变量调大），任务提交后 `submit` 执行
- 执行器内自建数据库 Session（不可复用请求级 Session），流程：
  1. 任务置 running + started_at
  2. 调用功能执行函数（当前为占位假实现，后续在此处接入真实模型 / Dify 工作流）
  3. 成功：写 result_data，status=success，finished_at，并向 `ai_call_logs` 写一条调用记录（复用 `log_ai_call`）
  4. 失败：写 error_message，status=failed，finished_at；同时写一条带错误信息的调用记录，保证后台可追溯
- 执行函数为纯函数式 `dispatch(feature_type, inputs) -> dict`，与路由解耦，便于将来替换为真实实现

## 5. 前端交互

- `frontend/src/api/index.js`：5 个提交方法保持原名（返回 task_id），新增 `getAiTask(taskId)`
- `AIAssistDrawer.vue`：点击按钮 → 提交任务 → 每 2 秒轮询一次任务状态（上限 5 分钟）→
  成功后按原逻辑回写（分类自动选中栏目、摘要回写输入框、审核/校验/打分渲染结果）；
  失败或超时给出中文提示；关闭弹窗时清理定时器，避免泄漏
- 各功能按钮 loading 状态与原来一致（提交后置 true，完成后置 false）

## 6. 成功标准

1. 5 个接口提交后立即返回 task_id（秒级），不等待假实现结果
2. 轮询接口能查到 pending → running → success 全链路，success 后 result 与原来假实现返回一致
3. 未登录提交被 401 拒绝；普通用户查他人任务被 403 拒绝
4. 每次成功执行后 `ai_call_logs` 多一条记录，后台"AI 调用记录"页面数据完整
5. 前端写稿页 AI 协作台功能表现与改造前一致（分类/摘要回写、审核/校验/打分展示）
6. `backend/smoke_test.py` 增加对应断言并可重复运行

## 7. 不做的事

- 不新增后台任务管理页面（沿用现有"AI 调用记录"页面；任务表为内部执行载体）
- 不引入 Celery / Redis 队列（当前单机场景线程池足够，接口契约已预留升级空间）
- 不改动 ai_call_logs 表结构
