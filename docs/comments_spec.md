# 规格：文稿评论功能

## Objective（目标）

为前台文稿详情页增加评论能力，形成"文稿浏览 → 互动评论"的完整闭环：

- 登录用户在文稿详情页底部发表评论，支持回复评论（两级：评论 + 回复）。
- 未登录用户看到评论区但无法发表，界面提示"登录后参与评论"。
- 后台增加"评论管理"页面（侧边栏「用户与数据」分组），管理员可分页查看全部评论、按关键词检索、删除违规评论。
- 评论作者本人可删除自己的评论；管理员可删除任意评论。

## 数据表设计（comments）

由 SQLAlchemy 模型 `backend/app/models/comment.py` 定义，`init_db.py` 通过 `Base.metadata.create_all` 自动建表（新库直接创建，老库 `python init_db.py` 幂等补建）。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | INT PK AUTO_INCREMENT | 评论 ID |
| article_id | INT NOT NULL, FK articles.id ON DELETE CASCADE | 所属文稿 |
| user_id | INT NOT NULL, FK users.id ON DELETE CASCADE | 发表用户 |
| parent_id | INT NULL, FK comments.id ON DELETE CASCADE | 回复的父评论 ID；NULL 表示顶层评论 |
| content | TEXT NOT NULL | 评论内容（**纯文本**，不含 HTML） |
| created_at | DATETIME | 发表时间 |

说明：
- 评论只分两级：`parent_id IS NULL` 为顶层评论，非空为回复；回复不可再回复（前端不展示三级输入框）。
- 删除顶层评论时，其回复随 `ON DELETE CASCADE` 一并删除（避免孤儿回复）。
- 评论内容按纯文本处理：后端对输入做去 HTML 标签 + 长度校验（1~2000 字符），前端用 Vue 插值渲染自动转义，不引入 `v-html`，防存储型 XSS。
- 不做评论审核/敏感词过滤（后续可扩展），不做冗余评论计数字段（列表接口返回 total 即可）。

## 接口契约（/api/comments）

### 1. 获取评论列表（公开）

`GET /api/comments?article_id=1&page=1&page_size=20`

返回顶层评论分页 + 每条的回复列表（回复不分页，按时间正序）：

```json
{
  "items": [
    {
      "id": 1,
      "article_id": 1,
      "user_id": 3,
      "nickname": "演示用户",
      "avatar": "",
      "content": "写得很棒",
      "created_at": "2026-08-12 20:00:00",
      "is_mine": false,
      "is_admin": false,
      "replies": [
        { "id": 2, "article_id": 1, "user_id": 3, "nickname": "演示用户", "avatar": "", "content": "谢谢", "created_at": "2026-08-12 20:05:00", "is_mine": false, "is_admin": false }
      ]
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

- `is_mine`：当前登录用户是否可删（本人）；`is_admin`：管理员可删。未登录时均为 false。
- 文章不存在或未发布返回 404；文章已发布但无评论返回空 items。

### 2. 发表评论 / 回复（需登录）

`POST /api/comments`

请求体：

```json
{ "article_id": 1, "content": "评论内容", "parent_id": null }
```

- `parent_id` 为 null 发表顶层评论；非 null 发表对该评论的回复。
- 校验：content 1~2000 字符；`parent_id` 必须存在且与 `article_id` 属于同一文稿；`parent_id` 对应评论必须是顶层评论（禁止三级回复）。
- 仅允许对**已发布**文稿评论。
- 返回新建评论完整对象（同列表项结构）。

### 3. 删除评论（本人或管理员）

`DELETE /api/comments/{id}`

- 未登录返回 401；非本人且非管理员返回 403。
- 删除顶层评论时级联删除其全部回复；删除回复仅删除该条。
- 成功返回 `{"message": "评论已删除"}`。

### 4. 后台评论列表（管理员）

`GET /api/admin/comments?keyword=&page=1&page_size=10`

返回所有评论（含回复），可按用户名/昵称/评论内容/文稿标题模糊搜索，按时间倒序：

```json
{
  "items": [
    {
      "id": 1,
      "article_id": 1,
      "article_title": "文稿标题",
      "user_id": 3,
      "username": "user",
      "nickname": "演示用户",
      "content": "评论内容",
      "parent_id": null,
      "parent_content": null,
      "created_at": "2026-08-12 20:00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10
}
```

后台删除复用 `DELETE /api/comments/{id}`（管理员权限）。

## 前端设计

### 门户详情页（ArticleDetailView.vue）

在文章互动栏下方、相关推荐之前新增评论区：

- 顶部标题"评论（N）"，N 为列表接口 total。
- 发表区：登录用户显示头像 + 文本域 + "发表评论"按钮；未登录显示提示条"登录后可参与评论"，点击跳转登录页（带 redirect 回本页）。
- 评论列表：昵称、头像、时间、内容（插值渲染）；底部"回复"按钮；自己的评论或管理员显示"删除"按钮（二次确认）。
- 回复交互：点击"回复"在该评论下方展开输入框，发表后追加到对应 `replies` 并更新 total。
- 评论内容用 `<p>`/`<div>` 插值渲染，禁止 v-html。
- 样式遵循门户设计令牌（tokens.css）与主题变量（themes.css），组件不写死颜色。

### 后台评论管理（/admin/comments）

- 侧边栏「用户与数据」分组新增"评论管理"子项，仅 admin 可见。
- 表格列：ID、用户（昵称+账号）、所属文稿、内容（截断 tooltip）、类型（评论/回复）、时间、操作（删除）。
- 顶部搜索框（用户名/昵称/评论内容/文稿标题）+ 分页，风格与用户行为页一致。

## 成功标准

1. 登录用户可对已发布文稿发表评论、回复评论，刷新后仍在。
2. 未登录访问详情页看到评论区，发表按钮被"登录后参与评论"提示替代。
3. 评论作者可删除自己的评论；管理员在后台可检索并删除任意评论（含级联删除回复）。
4. 非法输入（空内容、超长、回复不存在的评论、对未发布文稿评论）被后端拒绝并返回中文错误。
5. 评论内容即使包含 `<script>` 等标签，前台与后台均按纯文本展示，不产生 XSS。
6. `backend/smoke_test.py` 增加评论流程断言且全部通过；前端 `npm run build` 通过；浏览器 DevTools 验证详情页评论区 DOM 与交互无报错。

## 边界

- Always：接口边界校验、参数化查询、评论纯文本渲染、删除二次确认、中文注释。
- Ask first：新增依赖、改变审核状态机、评论审核/敏感词过滤等新业务。
- Never：评论内容 `v-html` 渲染、把用户输入拼进 SQL、绕过登录直接调用发表接口。
