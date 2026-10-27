# Design — 文稿发布系统（门户前台）

本文件是前台门户的锁定设计系统。后续对门户页面的任何改版先读本文件，
不要每页重新发明一套主题。后台页面不在此系统范围内（沿用既有 token）。

## Genre
editorial（新闻编辑风）

## Macrostructure family
- 首页（Home）：**Front Page 头版** —— 报头 masthead + 头条主稿 + 双栏索引 + 栏目分区
- 栏目/搜索/收藏（Category / Search / Favorites）：**Catalogue 目录页** —— 规则线标题 + 纵向文稿列表
- 文章详情（Article Detail）：**Long Document 长文** —— 标题块 + 衬线正文 + 吸顶相关推荐
- 登录/注册（Login / Register）：**Form 极简表单** —— 无重阴影，规则线卡片

## Theme
沿用品牌色（ui-ux-pro-max 验证：新闻编辑风 / Newsreader+Roboto）：
- `--color-paper`   oklch(100% 0 0)                版面纸
- `--color-paper-2` oklch(98.5% 0.002 257)         次级底
- `--color-ink`     oklch(27.8% 0.03 257)          正文墨色
- `--color-ink-2`   oklch(55.6% 0.03 257)          次级文字
- `--color-rule`    oklch(93.2% 0.01 257)          细分隔线
- `--color-accent`  oklch(54.9% 0.19 264)          链接蓝（品牌 #2563EB）
- `--color-accent-2` oklch(64.5% 0.17 29)          头版橙（品牌 #F97316）
- `--color-focus`   oklch(54.9% 0.19 264)          焦点环

## Typography
- Display: Newsreader 600/700, style normal, 标题中文回退宋体系
- Body:    Roboto 400/500, style normal
- Display tracking: -0.02em；正文行高 1.6–1.75
- Type scale anchor: `--text-display: clamp(2.25rem, 5vw + 1rem, 3.5rem)`

## Spacing
4pt 命名刻度（`--space-*` 已在 tokens.css），页面必须使用命名 token。

## Motion
- Easings: `--ease-out: cubic-bezier(0.16, 1, 0.3, 1)` 等，禁止默认 ease
- Reveal pattern: none（编辑页面不做滚动渐显）
- Reduced-motion fallback: opacity-only ≤ 150ms

## Microinteractions stance
- silent success（不用庆祝式弹窗）
- hover 150–250ms；focus 即时显示焦点环
- 只动 transform/opacity，不动布局属性

## CTA voice
- 主 CTA：实底品牌蓝（`--color-accent`），半径 6px，最小触控 44px
- 次 CTA：文字/描边，下划线强调

## Per-page allowances
- 首页 MAY 使用图片头条（真实封面或管理员轮播，不允许伪造素材）
- 其余页面 typography only

## What pages MUST share
- 报头品牌字标（文稿发布 + 方形标记）
- 强调色与位置（≤ 5% 视口面积）
- Display + Body 字体
- CTA 声音（按钮圆角/内边距节奏）
- 章节标题节奏（衬线标题 + 规则线 + 栏目标签）

## What pages MAY differ on
- 页面宏观结构（头版 / 目录 / 长文 / 表单）
- Hero 头版区块的排列

## Exports

### tokens.css
已直接落地在 `frontend/src/styles/tokens.css`，门户新 token（`--text-*` / `--ease-*` /
`--dur-*` / `--size-*`）与既有 token 并存，后台页面继续使用既有 token 不受影响。
