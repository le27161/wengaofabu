# 文稿预览功能规格（后台管理 / 审核页面）

## 目标

在「文稿管理」与「审核管理」页面中，点击列表里文稿的封面或标题，可在页面右侧弹出抽屉，预览该文稿的完整详情（封面、标题、作者、栏目、状态、数据、正文等），方便管理人员在编辑 / 审核前快速浏览内容，无需跳转或打开编辑页。

## 交互设计

- 触发方式：
  - 文稿管理页：点击「文稿」列中的封面缩略图或标题，打开右侧预览抽屉。
  - 审核管理页：
    - 「待一审」「待二审」列表：点击标题列打开预览抽屉。
    - 「审核记录」列表：点击「文稿」列标题打开预览抽屉。
- 展示形态：右侧抽屉（Element Plus `el-drawer`），宽度 560px，内容可滚动；复用前台文稿详情的正文排版样式（`.article-content`）。
- 预览内容：封面大图（无封面时显示占位块）、标题、状态徽章、作者 / 栏目 / 更新时间、浏览 / 点赞 / 收藏 / 转发数据、摘要（有则展示）、正文 HTML。
- 不改变现有业务：预览为只读操作，不触发审核、不修改数据；点击审核按钮的原有流程不变。

## 数据契约

复用现有接口 `GET /api/articles/{id}`（`articleApi.detail`），无需新增后端接口。

返回字段（`include_content=True`）：

| 字段 | 说明 |
| --- | --- |
| id / title | 文稿 ID / 标题 |
| cover_url | 封面图地址（可为空） |
| status | 状态（draft/pending_first/pending_second/published/rejected/offline） |
| author_name | 作者昵称或用户名 |
| categories | 栏目列表（name） |
| summary | 摘要（可为空） |
| content | 正文 HTML |
| view_count / like_count / favorite_count / share_count | 浏览 / 点赞 / 收藏 / 转发 |
| created_at / updated_at / published_at | 时间字段 |

权限沿用详情接口：未发布文稿仅作者、系统管理员（admin）、审核管理员（moderator）可见；后台两个页面均满足该条件。

## 前端改动

1. 新增组件 `frontend/src/components/ArticlePreviewDrawer.vue`：
   - `v-model:visible` 控制抽屉开关，`articleId` 指定预览文稿；
   - 打开时调用 `articleApi.detail(articleId)` 加载，含加载中 / 失败提示；
   - 关闭时清空详情，避免残留。
2. `frontend/src/views/admin/ArticleListView.vue`：封面与标题包装为可点击元素（键盘可聚焦），点击调用 `openPreview(row)`。
3. `frontend/src/views/admin/ReviewView.vue`：
   - 待一审 / 待二审：标题列改为可点击文本（保留溢出省略），点击打开预览；
   - 审核记录：`article_title` 列改为可点击文本，点击用 `row.article_id` 打开预览。

## 样式约束

- 遵循设计令牌（`tokens.css`）与现有表格样式（`admin-tables.css` 的 `cell-thumb`、`cell-title`、`status-badge` 等类）。
- 正文区复用全局 `.article-content` 排版（与前台详情一致），不新增"AI 审美"样式。
- 预览抽屉顶部保留关闭按钮，内容区滚动。

## 成功标准

- 两个页面均可通过点击封面 / 标题打开右侧预览，内容完整、正文 HTML 正确渲染。
- 预览为只读，不触发任何业务副作用（不写观看历史之外的状态变更）。
- 审核弹窗原有功能不受影响。
- 前端无控制台报错，键盘可访问（标题 / 封面可 Tab 聚焦、Enter 触发）。
