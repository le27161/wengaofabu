# 文稿发布系统（前后台分离）

一个面向内容编辑场景的文稿发布平台：前台类似新闻门户（栏目浏览、文章详情、点赞/收藏/转发、搜索），后台提供编辑写稿、二级审核、栏目/用户/资源管理、门户配置与数据统计。

本仓库只提交源码、配置模板和轻量示例资源。真实环境配置（`backend/.env`）、模型权重、上传文件、日志和依赖缓存不应提交；请使用自己的数据库、密钥和模型文件。

## 技术栈

| 端 | 技术 |
| --- | --- |
| 后端 | Python FastAPI + SQLAlchemy + PyMySQL + JWT |
| 前端 | Vue 3 + Vite + Pinia + Vue Router + Element Plus + ECharts |
| 数据库 | MySQL（utf8mb4） |

## 目录结构

```text
wengaofabu/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── models/          # SQLAlchemy 数据模型（用户/栏目/文稿/审核/资源/埋点/门户模块）
│   │   ├── schemas/         # Pydantic 请求/响应校验
│   │   ├── routers/         # 接口路由（认证/用户/栏目/文稿/审核/互动/资源/门户/埋点/统计）
│   │   ├── core/            # JWT、权限依赖、分页工具
│   │   ├── services/        # 埋点记录、Dify 工作流调用等公共服务
│   │   ├── config.py        # 数据库/密钥/上传等配置
│   │   ├── database.py      # 数据库引擎与会话
│   │   └── main.py          # 应用入口
│   ├── init_db.py           # 自动建库（若不存在）+ 建表 + 兼容迁移 + 种子数据/系统配置（幂等）
│   ├── smoke_test.py        # 接口冒烟测试（可重复运行）
│   ├── run.py               # 开发启动脚本
│   └── requirements.txt
├── frontend/                # Vue 3 前端
│   ├── src/
│   │   ├── layouts/         # 门户布局 / 后台布局
│   │   ├── views/portal/    # 首页、栏目、详情、搜索、登录、注册、收藏
│   │   ├── views/admin/     # 仪表盘、文稿、审核、栏目、用户、资源、门户设置、统计
│   │   ├── components/      # 文章卡片、资源选择器
│   │   ├── api/             # Axios 封装与接口定义
│   │   ├── stores/          # Pinia 认证状态
│   │   ├── router/          # 路由与权限守卫
│   │   └── styles/          # 设计令牌与全局样式
│   ├── vite.config.js       # 开发代理（/api、/static → :8000）
│   └── package.json
└── README.md
```

## 快速启动

### 1. 后端

```bash
cd backend
python -m pip install -r requirements.txt
python install_ai_deps.py    # 安装 AI 依赖（torch/transformers），自动检测 GPU，无 GPU 自动装 CPU 版
python init_db.py        # 自动建库（若不存在）+ 建表 + 兼容迁移 + 种子账号/栏目/系统配置，幂等可重复执行
python run.py            # 启动 http://localhost:8000，接口文档 /docs
```
> 模型权重不随源码上传，首次运行前请按下方“模型权重文件”准备目录和文件。
> 本地启动数据库，之后修改backend的.env文件中的配置，数据库改成自己的，相关的线上大模型自己拿一下key。Tavily有免费的key用，一个月1000次
> 项目低耦合，dify不配置也可以用，但是ai协作台相关不能用，自己搭建dify之后可以导入根目录下的dify工作流，最后在后台配置

> `init_db.py` 会先检查 MySQL 服务器上是否存在 `wengaofabu` 数据库，不存在则自动创建
> （utf8mb4，完整支持中文与 emoji），随后建表、做表结构兼容迁移，并写入种子数据与系统配置。
> 若 MySQL 账号没有建库权限，请先手动执行：
> `CREATE DATABASE wengaofabu DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;`
> 请从有权使用的模型来源或已有备份获取权重，并核对模型配置与分类标签是否匹配。

### 2. 前端

```bash
cd frontend
npm install
npm run dev              # 启动 http://localhost:5173
```

开发模式下前端通过 Vite 代理访问后端，无需额外配置跨域。

## AI 依赖安装（torch / transformers）

`requirements.txt` 只包含 FastAPI 等基础依赖，**不含 torch / transformers**——
这两个库体积大且区分 GPU / CPU 版本，由 `install_ai_deps.py` 按机器环境自动选择安装。

### 自动安装（推荐）

```bash
cd backend
python install_ai_deps.py
```

脚本会先检测本机是否有 NVIDIA GPU：

- **有 GPU**：从 PyTorch 官方 CUDA 索引安装 GPU 版 torch（默认 `cu124`），推理快；
- **无 GPU**：从 PyTorch 官方 CPU 索引安装 CPU 版 torch，体积小、无需 CUDA 驱动，
  普通电脑也能正常运行（模型推理稍慢，但功能完整）。

常用参数：

```bash
python install_ai_deps.py --cpu            # 强制安装 CPU 版
python install_ai_deps.py --gpu            # 强制安装 GPU 版
python install_ai_deps.py --cuda cu121     # 指定 CUDA 版本（仅 GPU 场景）
python install_ai_deps.py --dry-run        # 只查看检测结果与安装计划，不实际安装
```

### 手动安装

**无 GPU 的电脑（CPU 版，重点）：**

```bash
cd backend
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install transformers
```

**有 NVIDIA GPU 的电脑（CUDA 版）：**

```bash
cd backend
pip install torch --index-url https://download.pytorch.org/whl/cu124
pip install transformers
```

> 提示：CPU 版 torch 从 PyPI 默认源也能装，但建议使用上面的官方 CPU 索引，
> 安装包更小且不会附带 CUDA 运行库。

### 模型权重文件

AI 分类与文稿向量化依赖本地模型权重文件（已加入 `.gitignore`，不入库），
需要手动放置到以下目录：

```text
backend/app/aimodel/model/bert-base-chinese/        # AI 分类模型（HuggingFace 格式 + model.safetensors）
backend/app/aimodel/model/bert_model.pt             # AI 分类微调权重（PyTorch 格式）
backend/app/aiVectorizationModel/model/vectorization-model/  # 文稿向量化模型（model.safetensors）
```

权重文件在 GPU 机器上保存时张量为 CUDA 格式，代码已通过 `map_location=device`
兼容无 GPU 机器（自动映射到 CPU），无需额外处理。

### 验证安装

```bash
python -c "import torch, transformers; print(torch.__version__, torch.cuda.is_available()); print(transformers.__version__)"
```

## 种子账号

| 角色 | 账号 | 密码 |
| --- | --- | --- |
| 管理员 | admin | admin123 |
| 编辑 | editor | editor123 |
| 普通用户 | user | user123 |

## 角色与权限

| 角色 | 能力 |
| --- | --- |
| 普通用户 | 浏览门户、搜索、点赞、收藏、转发（均写埋点日志） |
| 编辑 | 在多个栏目下写作稿件、提交审核、管理自己的资源；后台仅可见「文稿管理 / 资源管理」 |
| 管理员 | 全部：栏目增删改、二级审核、用户管理（创建账号/冻结/改角色）、资源管理、门户模块配置、数据统计 |

## 文稿审核流程（二级审核）

```text
草稿 draft → 提交 → 待一审 pending_first
  → 一审通过 → 待二审 pending_second → 二审通过 → 已发布 published
  → 任意一级驳回 → 已驳回 rejected（编辑修改后可重新提交）
```

- 一级、二级审核均需管理员操作，每次审核写入 `article_reviews` 记录（审核人、级别、动作、意见）。
- 二审通过后自动写入 `published_at` 并对前台可见。
- 管理员可将已发布文稿下线（offline）。
- 后台「系统设置 → 自动审核」开启后，编辑提审即自动通过一审、二审并直接发布，
  审核记录中审核人显示「系统自动审核」，无需人工操作。

## 数据库表说明

| 表 | 说明 |
| --- | --- |
| users | 用户表（role: user/editor/admin；status: active/frozen 冻结） |
| categories | 栏目表（名称、标识、简介、排序、启用/隐藏） |
| articles | 文稿表（标题、摘要、正文、封面、审核状态、互动计数） |
| article_categories | 文稿-栏目多对多关联 |
| article_reviews | 审核记录（一级/二级、通过/驳回、审核人、意见） |
| user_actions | 点赞/收藏记录（用户-文稿-行为唯一约束，防止重复） |
| event_logs | 埋点日志（观看/点赞/收藏/转发 + IP/UA/来源页） |
| resources | 上传资源（图片/视频/PDF），文稿封面从此处选择 |
| portal_modules | 门户模块（首页轮播 banner、站内公告 notice 等，管理员配置） |
| system_settings | 后台系统配置（键值对：config_key 唯一，value_type 支持 string/int/bool/json，当前含自动审核开关 auto_review） |
| dify_workflows | Dify 工作流登记（API 地址、Key、输入参数说明；供业务调用 Dify 工作流） |

## 主要接口一览

公共：`POST /api/auth/register|login`、`GET /api/categories`、`GET /api/articles`、`GET /api/articles/{id}`、`GET /api/portal/modules`、`POST /api/events`（埋点）

门户主题：读取（公开）`GET /api/portal/theme`；切换（管理员）`PUT /api/portal/theme`（body: `{"theme": "editorial|cyber|comic"}`）

互动（需登录）：`POST/DELETE /api/interactions/like|favorite`、`POST /api/interactions/share`、`GET /api/interactions/status|favorites`

编辑：`POST/PUT /api/articles`、`POST /api/articles/{id}/submit`、`GET /api/articles/mine`、资源上传/删除

管理员：栏目 CRUD、用户管理（含冻结）、二级审核 `POST /api/reviews`、门户模块配置、统计接口 `GET /api/stats/*`、
系统配置 `GET/POST /api/settings`、`PUT/DELETE /api/settings/{key}`（如自动审核开关 auto_review）、
Dify 工作流 `GET/POST /api/dify/workflows`、`PUT/DELETE /api/dify/workflows/{id}`、试运行 `POST /api/dify/workflows/{id}/run`

完整接口定义见后端启动后的 [Swagger 文档](http://localhost:8000/docs)。

## 门户主题切换

- 后台「门户主题」页可切换前台风格：经典编辑（editorial，默认）/ 赛博霓虹（cyber）/ 漫画波普（comic）；
- 换肤范围：首页、栏目页、搜索/收藏、文章详情页；登录页与后台页面保持经典风格；
- 实现原理：`frontend/src/styles/themes.css` 的 `.theme-*` 覆盖设计令牌（CSS 变量），门户组件全部引用
  `var(--*)` 自动跟随，业务逻辑零改动；
- 扩充新风格：在 `backend/app/routers/portal.py` 的 `PORTAL_THEMES` 登记 key，并在
  `themes.css` 新增 `.theme-<key>` 覆盖块，再在后台主题页 `ThemeManageView.vue` 的 `themes` 数组加卡片。

## Dify 工作流接入（预留）

- 环境变量预留：`DIFY_API_BASE`（API 地址）、`DIFY_API_KEY`（应用 Key）、`DIFY_TIMEOUT`（超时秒数），在 `backend/.env` 配置；
- 多工作流登记：表 `dify_workflows`（后台 `/api/dify/workflows` 管理），业务代码统一走
  `app/services/dify_service.py` 的 `run_workflow(db, inputs, name=...)` 调用；
- 配置优先级：数据库指定工作流 > 数据库启用记录 > 环境变量；
- 详细接入步骤、Dify 平台取 Key 流程、业务接入示例见 [docs/dify_guide.md](docs/dify_guide.md)。

## 埋点与统计

- 进入文稿详情页自动上报 `view` 埋点并累加浏览量；
- 点赞/收藏/转发在互动接口内部同步写入 `event_logs`，同时维护文稿计数；
- 统计页（后台 → 数据统计）提供：数据概览、行为趋势折线图、栏目数据、用户活跃、Top 文稿、埋点明细查询；
- 对应接口：`/api/stats/overview`、`trends`、`articles`、`categories`、`user-activity`、`events`，便于二次开发快速取数。

## 二次开发指引

- 后端新增接口：在 `app/routers/` 下新建或扩展路由，于 `app/main.py` 挂载；模型在 `app/models/` 中定义后执行 `python init_db.py`（或手动迁移）。
- 前端新增页面：在 `src/views/` 下创建组件，并在 `src/router/index.js` 注册路由；接口统一在 `src/api/index.js` 维护。
- 设计规范：颜色/字体/间距等设计令牌集中在 `src/styles/tokens.css`，遵循新闻门户编辑风（主色 `#2563EB`、强调橙 `#F97316`、Newsreader+Roboto）。
- 生产部署注意：
  1. 修改 `backend/app/config.py` 中的 `SECRET_KEY`，通过环境变量覆盖数据库密码；
  2. 将 `BASE_URL` 改为实际域名，保证上传资源 URL 可访问；
  3. 后端 `uploads/` 目录需持久化；`allow_origins` 收紧为前端实际域名；
  4. 编辑器正文按 HTML 保存，正式环境建议接入富文本编辑器（如 wangEditor）并增加 XSS 过滤（如 bleach）。
