# 规格：下线文稿重新编辑并再次发布

## Objective（目标）

当前文稿发布后只有「下线」「删除」两个操作。新增流程：已下线文稿可被作者/管理员重新编辑，编辑完成后重新提交审核（走既有两级审核），审核通过后再次发布。

## 状态机变更

原：`draft → pending_first → pending_second → published`，发布后可 `offline`。

新：`published → offline →（编辑保存，状态保持 offline）→ pending_first → pending_second → published`

- 编辑保存不改变 offline 状态；只有重新提审才进入审核流。
- 审核驳回时退回 `rejected`（与草稿提审被驳回行为一致），编辑可再改再提。
- 二审通过重新发布时更新 `published_at`（列表排序/展示按最新发布时间）。

## 后端改动

### articles.py

- `EDITABLE_STATUS` 增加 `"offline"`：下线稿允许作者/管理员编辑。
- `submit_article` 允许的源状态从 `("draft", "rejected")` 增加 `"offline"`：下线稿可重新提交审核。
- 权限沿用 `_can_manage`（作者或系统管理员）；下线操作本身仍仅系统管理员。
- 自动审核开关同样适用于下线稿重新提审（开启时提审即重新发布）。

### reviews.py

无需改动：`offline → pending_first` 后自动进入既有审核流，二审通过时已更新 `published_at`。

## 前端改动（ArticleListView.vue）

- `canEdit` / `canSubmit` 判断增加 `row.status === 'offline'`：
  - 已下线行显示「编辑」「提交审核」「删除」；管理员额外可「下线」仅对 published 生效（保持不变）。
- 状态徽章 `offline` 已有（灰色「已下线」），无需新增。
- 编辑页（ArticleEditView）无需改动：`get_article` 对未发布稿的可见性已覆盖作者/管理员，保存走 `update` 接口。

## 成功标准

1. 已发布文稿下线后，列表显示「编辑」「提交审核」按钮（作者本人或管理员）。
2. 下线稿可正常编辑保存（状态仍为已下线）。
3. 重新提审进入待一审；两级审核通过后重新发布，列表状态为已发布、发布时间更新。
4. 重新提审后审核驳回退回编辑（rejected），可再编辑再提。
5. 冒烟测试覆盖完整链路；前端构建通过；DOM 审核列表按钮与状态徽章。

## 边界

- Always：状态机注释同步更新、中文注释、接口校验（非 offline 状态不可走新流程）。
- Never：offline 稿不经审核直接恢复 published；下线权限扩大到编辑。
