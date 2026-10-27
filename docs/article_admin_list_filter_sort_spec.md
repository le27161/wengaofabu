# 后台文稿列表：栏目筛选 + 服务端排序 规格

> 状态：已确认（2026-08-14）

## 1. 目标

后台"文稿管理"页查询条件增加栏目（可选），表格支持按数据字段排序（服务端排序，分页数据全局有序）。

## 2. 接口契约（均为可选参数，向后兼容）

`GET /api/articles/admin` 与 `GET /api/articles/mine` 新增：

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| category_id | int | 无 | 按栏目筛选（admin 原已有；mine 新增） |
| sort_by | str | updated_at | 白名单：updated_at / created_at / published_at / view_count / like_count / favorite_count / share_count，非法值 422 |
| sort_order | str | desc | asc / desc，非法值 422 |

mine 同时补上 keyword（标题/摘要模糊匹配），与页面工具栏对齐。

## 3. 前端交互

- 工具栏新增"全部栏目"下拉（categoryApi.list 加载，可清空，change 即查询）
- 浏览/点赞/收藏/转发/更新时间 五列支持点击列头排序（sortable="custom"，第三击清空恢复默认 updated_at 降序）
- 排序与筛选变更均回到第 1 页

## 4. 成功标准

- [x] smoke_test：栏目筛选结果全部命中该栏目；view_count 降序有序；非法 sort_by 返回 422
- [x] 前端 Vite 编译通过；DevTools 验证列头排序箭头与请求参数