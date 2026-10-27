# 门户首页"为你推荐"区块 规格文档

## 目标

在门户首页开辟"为你推荐"区块，调用已有个性化推荐接口 `GET /api/articles/recommend`
展示推荐文稿；区块开关放在后台门户设置页，且开关关闭后前台不再请求与展示。
样式通过 CSS 变量与主题覆盖兼容 editorial / cyber / comic 三种门户主题。

## 数据结构

复用 `portal_modules` 表（无需建新表），新增模块标识：

| module_key | title | content | enabled |
| --- | --- | --- | --- |
| recommend | 个性化推荐 | `{}`（无内容配置） | 默认 true |

`init_db.py` 幂等写入该种子；老库跑一次初始化脚本即可获得开关。

## 接口契约

### 新增：GET /api/portal/modules/admin（管理员）

返回全部门户模块（含已禁用），供后台设置页展示开关；前台仍走现有
`GET /api/portal/modules`（只返回启用的模块，天然实现"关闭后前台不展示"）。

**成功响应（200）**

```json
{
  "items": [
    {"id": 1, "module_key": "recommend", "title": "个性化推荐", "content": {}, "enabled": true, "updated_at": "..."}
  ]
}
```

非管理员访问返回 403。

### 复用已有接口

- 前台模块读取：`GET /api/portal/modules`（不变）
- 模块开关保存：`PUT /api/portal/modules/{module_key}`（不变，传 `{title, content, enabled}`）
- 个性化推荐数据：`GET /api/articles/recommend?limit=8`（不变，未登录返回通用推荐）

## 前端交互

### 门户首页（HomeView.vue）

- 读取前台启用的模块列表，存在 `module_key == "recommend"` 时才展示区块
- 区块位置：`home__grid`（最新发布/热门排行）之后、栏目分区之前
- 区块标题"为你推荐"，用 `ArticleCard` 网格展示 8 篇推荐文稿（响应式 4→2→1 列）
- 点击卡片进入对应文稿详情页

### 后台门户设置（PortalManageView.vue）

- 新增"个性化推荐"面板：`el-switch` 控制启用/关闭，保存复用模块更新接口
- 读取模块改用新的管理员全量接口，保证模块被关闭后仍能在设置页看到并重新开启

### 主题兼容

- 基础样式全部使用 `tokens.css` 的 CSS 变量（颜色/字体/间距/边框），三主题自动跟随
- `themes.css` 补充 cyber / comic 的区块点缀（霓虹边框、漫画贴纸标题等），
  与现有首页区块风格一致

## 成功标准

1. 开关开启时首页展示"为你推荐"8 篇；关闭后首页不再显示该区块
2. 未登录与登录用户均可看到推荐（登录且历史足量时返回个性化结果）
3. 三种主题下区块样式正常（chrome-devtools DOM 审核）
4. 后台设置页可看到并切换推荐开关（关闭后仍可见）
5. 冒烟测试覆盖新接口权限与模块开关联动
