# 规格：用户积分系统

## Objective（目标）

为系统引入轻量积分体系，激励用户每日回访：

- 登录用户点击右上角用户菜单（详情信息弹窗）中的「签到」按钮，获得随机积分。
- 每次签到积分范围可配置：默认 1~5，管理员在后台「系统设置」调整（`signin_min_points` / `signin_max_points`）。
- 用户菜单中实时显示当前积分与今日签到状态。
- 后台新增「积分管理」页面：查看每个用户的积分、累计签到次数、最近签到时间，管理员可调整积分（正加负减）。
- 后台表格遵循项目统一的 `admin-tables.css` 表格设计（admin-head / admin-card / status-badge / admin-pager）。

## 业务假设（如与预期不符请指出）

1. **签到每天限一次**（自然日 00:00~23:59:59），防止无限刷积分；次日可再次签到。
2. 管理员调整积分是「增量调整」（输入正数加分、负数扣分），不直接覆盖为固定值；调整后积分不能小于 0。
3. 管理员调整积分不产生签到记录，也不影响签到次数。

## 数据设计

### users 表新增字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| points | INT NOT NULL DEFAULT 0 | 用户当前积分 |

老库由 `init_db.py` 的 `ensure_schema_compat` 幂等补列；新库由模型自动建表。

### checkin_logs 表（新增）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | INT PK AUTO_INCREMENT | 签到记录 ID |
| user_id | INT NOT NULL, FK users.id ON DELETE CASCADE | 签到用户 |
| checkin_date | VARCHAR(10) NOT NULL | 签到日期（YYYY-MM-DD，用于每日一次判定） |
| points | INT NOT NULL | 本次获得积分 |
| created_at | DATETIME | 签到时间 |

唯一约束：`(user_id, checkin_date)`，数据库层面兜底并发重复签到。

### 系统配置（system_settings 新增两条）

| config_key | value_type | 默认值 | 说明 |
| --- | --- | --- | --- |
| signin_min_points | int | 1 | 每日签到最小积分 |
| signin_max_points | int | 5 | 每日签到最大积分 |

后台系统设置页按现有机制自动渲染（int 数字输入）；后端签到接口读取该范围并校验 `min <= max`（配置异常时退化为 1~5）。

## 接口契约

### 1. 我的积分与签到状态（需登录）

`GET /api/points/me`

```json
{ "points": 12, "today_checked_in": false }
```

### 2. 每日签到（需登录，幂等）

`POST /api/points/checkin`

- 今日未签到：随机取 `[min, max]` 闭区间整数积分，写入 `users.points += gained`，插入 `checkin_logs`。
- 今日已签到：返回 400「今日已签到，明天再来吧」，不重复加分（唯一约束兜底并发）。

```json
{ "message": "签到成功，获得 3 积分", "gained": 3, "points": 15, "today_checked_in": true }
```

### 3. 后台积分列表（管理员）

`GET /api/admin/points?keyword=&page=1&page_size=10`

支持按用户名/昵称模糊搜索；按积分降序：

```json
{
  "items": [
    {
      "id": 3,
      "username": "user",
      "nickname": "演示用户",
      "points": 15,
      "checkin_count": 3,
      "last_checkin_at": "2026-08-13 10:00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10
}
```

### 4. 调整积分（管理员）

`PUT /api/admin/points/{user_id}`，body：`{ "delta": 10 }`（正加负减）

- 校验：delta 范围 -100000~100000；调整后积分不小于 0（负数太多则报错）。
- 返回更新后积分：`{ "message": "积分已调整", "points": 25 }`。

## 前端设计

### 门户右上角用户菜单（PortalLayout）

在 el-dropdown 顶部新增两个菜单项：

- 禁用态菜单项「我的积分：N」：实时显示当前积分（读 auth store，签到后更新）。
- 「每日签到」菜单项：未签到可点击；今日已签到时显示「今日已签到」并禁用。签到成功提示「签到成功，获得 X 积分」并刷新积分显示。

### 后台积分管理（/admin/points）

- 侧边栏「用户与数据」分组新增「积分管理」，仅 admin 可见。
- 页面：admin-head（图标 + 标题 + 副标题）→ admin-card（table-toolbar 搜索 + el-table + admin-pager）。
- 表格列：用户（头像 + 昵称 + @账号，cell-media/cell-title）、当前积分、签到次数、最近签到、操作（调整）。
- 调整弹窗：el-dialog 内输入正负调整值（负数扣分），显示调整后预计积分，保存调接口。

## 成功标准

1. 登录用户首次签到获得 1~5 随机积分（受系统设置范围约束），再次签到当天提示已签到。
2. 用户菜单实时显示积分与签到状态，刷新后仍正确。
3. 管理员在系统设置修改签到积分范围后，次日签到按新范围发放。
4. 后台积分管理页可搜索、分页查看用户积分，可正负调整且积分不为负。
5. 未登录调签到/积分接口返回 401；非管理员调后台接口返回 403。
6. `backend/smoke_test.py` 新增积分流程断言全通过；前端 `npm run build` 通过；浏览器 DevTools 验证用户菜单签到与后台积分管理页无报错。

## 边界

- Always：接口边界校验（delta 范围、签到每日一次）、参数化查询、后台页面遵循统一表格样式、中文注释。
- Ask first：增加积分消耗/兑换商城、签到连续天数奖励等新业务。
- Never：积分可为负数、绕过登录直接签到、把签到做成无限刷分。
