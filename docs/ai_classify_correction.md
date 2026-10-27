# AI 分类纠正数据集规格

> 状态：已确认（2026-08-14）

## 1. 目标

AI 智能分类结果不准确时，写手可在 AI 协作台手动纠正分类。纠正记录（标题 + 正文 + 模型分类 + 纠正分类）持久化入库，
供后续提取高质量数据集进行模型二次训练；纠正后的分类立即应用到当前文稿（自动选中对应栏目）。
后台提供数据集管理页面与 JSON 导出。

## 2. 数据结构

新建表 `ai_corrections`（AI 分类纠正数据集）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | INT PK AUTO_INCREMENT | 记录ID |
| user_id | INT FK users.id | 提交纠正的用户 |
| article_id | INT NULL | 关联文稿ID（可选，写稿场景下为当前文稿） |
| title | VARCHAR(200) | 文稿标题（训练样本的 text 字段） |
| content | TEXT | 文稿正文（纯文本 content_source，训练样本正文） |
| model_category | VARCHAR(50) | AI 模型原始分类（中文名） |
| corrected_category | VARCHAR(50) | 用户纠正后的分类（中文名） |
| created_at | DATETIME | 提交时间 |

表由 `Base.metadata.create_all` 自动创建（重启后端或执行 `python init_db.py`，幂等）。

## 3. 接口契约

### 3.1 提交纠正（登录用户）

`POST /api/ai/assist/corrections`

- 权限：登录用户（`get_current_user`）
- 请求体：
  ```json
  {
    "title": "文稿标题",
    "content": "正文纯文本",
    "model_category": "游戏",
    "corrected_category": "科学",
    "article_id": 123
  }
  ```
- 校验：title、corrected_category 必填非空；content 可空
- 响应（200）：`{"message": "纠正已记录", "id": 1}`

### 3.2 数据集列表（管理员）

`GET /api/admin/ai-corrections`

- 参数：keyword（标题/纠正分类模糊）、page、page_size
- 响应：`{"items": [...], "total": n, "page": p, "page_size": s}`

### 3.3 数据集导出（管理员）

`GET /api/admin/ai-corrections/export`

- 参数：`start_date`（开始日期 YYYY-MM-DD，可选）、`end_date`（结束日期 YYYY-MM-DD，可选）；
  不传时导出全量，传了则按提交时间（created_at）过滤区间（含首尾当天）
- 返回 JSON 数组（含 id/title/content/model_category/corrected_category/created_at），
  Content-Disposition 下载为 `ai_corrections.json`，供二次训练直接使用

## 4. 前端交互

### 4.1 AI 协作台（写稿页）

- AI 智能分类结果区新增「纠正」能力：显示模型分类 + 栏目下拉（可多选）+ 「纠正」按钮
- 点击纠正：提交记录到数据集；成功后把纠正栏目自动选中到当前文稿（category_ids），并提示「已纠正并选中栏目」
- 纠正提交独立于模型任务，不阻塞轮询流程

### 4.2 后台数据集页面

- 菜单「用户与数据」→「AI 分类纠正」，路由 `/admin/ai-corrections`
- 表格：ID / 标题 / 正文预览 / 模型分类 / 纠正分类 / 提交人 / 时间
- 工具栏：标题搜索 + 「导出 JSON」按钮（下载训练数据集）
- 导出支持选择开始/结束日期，只导出区间内样本；不选日期仍为全量导出
- 遵循后台现有表格样式（admin-card / table-toolbar / admin-tables.css）

## 5. 成功标准

1. 写手在 AI 协作台可对分类结果提交纠正，纠正后当前文稿自动选中纠正栏目
2. `ai_corrections` 表正确落库标题/正文/模型分类/纠正分类/用户
3. 后台数据集页面可分页查看、搜索、导出全量 JSON
4. 未登录提交纠正被 401；非管理员访问后台接口被 403
5. `smoke_test.py` 增加提交纠正 + 后台列表/导出断言

## 6. 不做的事

- 不做模型二次训练（仅沉淀数据集，训练流程由后续独立任务处理）
- 不自动回填历史错误样本（仅从纠正功能产生新数据）
