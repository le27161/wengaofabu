# 国风山水画主题（shan_shui）规格

## 目标

为门户新增一套「山水墨韵」主题：宣纸米白底、墨色文字、朱砂钤印、赭金装裱线，
搭配宋体/行书字体，营造国风山水卷轴感。参考 `info/61-shan-shui.html` 的水墨长卷设计。

## 影响范围

- 后端：`backend/app/routers/portal.py` 的 `PORTAL_THEMES` 登记 `shan-shui`。
- 前端：
  - `frontend/src/layouts/PortalLayout.vue`：body 主题类清理加入 `theme-shan-shui`。
  - `frontend/src/styles/themes.css`：新增 `.theme-shan-shui` 令牌与组件覆盖块。
  - `frontend/src/views/admin/ThemeManageView.vue`：新增主题卡片与预览色。
  - `frontend/src/views/admin/SettingsView.vue`：门户主题下拉新增选项。
- 数据/接口：无新增表、无新增接口；沿用现有 `portal_theme` 配置。

## 设计令牌

- 纸色：`#f7f1e3`（正文）、`#efe5d0`（次级纸面）、`#f2ead9`（页面底色）。
- 墨色：`#2b2620`（主文字）、`#5c5246`（次级）、`#8a7e6d`（弱化）。
- 朱砂：`#b3342a`（主强调）、`#f5ddd5`（柔和底）。
- 赭金：`#a8843c`、装裱金线 `#c9a86a`。
- 字体：标题 `Zhi Mang Xing / Ma Shan Zheng / Noto Serif SC`，正文 `Noto Serif SC / Songti SC`。

## 前端交互

- 主题切换仍走系统设置/后台主题页，选择「山水墨韵」后门户全局换肤。
- 组件不改变结构与接口，只通过 CSS 变量与主题覆盖块换肤。
- 浮层（用户菜单、关键词解释、AI 助手）通过 `body.theme-shan-shui` 同步换肤。

## 成功标准

- 门户首页、栏目页、文章详情页、评论/关键词/AI 阅读功能均可在该主题下正常使用。
- 后台主题页与系统设置可切换到该主题并持久化。
- `npm run build` 通过；控制台无样式相关报错。
