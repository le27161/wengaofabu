# Docker 部署指南（国内镜像加速）

前后端分离部署：**前端（Nginx）→ 后端（FastAPI）→ 你已有的 MySQL**，一个 `docker compose up` 即可拉起。
镜像内已配置国内加速：pip（清华源）、apt（清华源）、npm（npmmirror）。

## 一、文件清单

| 文件 | 作用 |
| --- | --- |
| `backend/Dockerfile` | 后端镜像：Python 3.10.20 + FastAPI +（可选）AI 依赖 |
| `backend/docker-entrypoint.sh` | 启动入口：等待 MySQL → 幂等 `init_db.py` → uvicorn |
| `backend/.dockerignore` | 排除 `.env`/`uploads`/日志等，避免敏感文件进镜像 |
| `frontend/Dockerfile` | 前端镜像：Node 构建 + Nginx 托管（多阶段） |
| `frontend/nginx.conf` | Nginx：SPA 路由 + `/api`、`/static` 反代到后端 |
| `frontend/.dockerignore` | 排除 node_modules / dist |
| `docker-compose.yml` | 编排：backend + frontend（**使用已有 MySQL，不内置数据库**） |

## 二、快速开始

```bash
# 1. 准备环境变量（可选，不建 .env 则用 compose 内默认值）
#    在项目根目录创建 .env，按需覆盖：
cat > .env <<'EOF'
# 生产务必修改
SECRET_KEY=请改成随机长字符串
# 你已有的 MySQL 连接信息（必填）
DB_HOST=你的MySQL地址
DB_PORT=3306
DB_USER=root
DB_PASSWORD=你的数据库密码
DB_NAME=wengaofabu
BASE_URL=http://你的域名或IP

# 可选：AI 阅读功能（OpenAI 兼容接口，全文总结/划词分析/关键词提取）
AI_API_BASE=https://api.openai.com/v1
AI_API_KEY=你的APIKey
AI_MODEL=gpt-4o
AI_TIMEOUT=60

# 可选：Dify 工作流（init_db.py 会登记 4 个默认工作流，Key 可在这里统一配置）
DIFY_API_BASE=http://你的Dify服务/v1
DIFY_API_KEY=app-xxx

# 可选：Tavily 新闻搜索 / Grounded 事件整理 LLM
TAVILY_API_KEY=你的TavilyKey
LLM_API_KEY=你的LLMKey
EOF

# 2. 构建并启动（首次构建会下载依赖，耗时较长）
docker compose up -d --build

# 3. 查看状态与日志
docker compose ps
docker compose logs -f backend

# 4. 访问
#    前端：http://服务器IP/（80 端口）
#    后端接口文档：http://服务器IP:8000/docs（若未对外映射 8000 则通过 docker exec 查看）
```

> 注意：如果启动时使用了 `docker compose -p 项目名 up -d`，之后所有 compose 命令
> **必须保持一致带 `-p 项目名`**（如 `docker compose -p wgfb build backend`），
> 否则会按目录名创建另一套项目/网络，导致 frontend 解析不到 `backend` 而 502。
> 也可先 `export COMPOSE_PROJECT_NAME=wgfb` 再执行普通 compose 命令。

种子账号（由 `init_db.py` 创建）：管理员 `admin/admin123`、编辑 `editor/editor123`、用户 `user/user123`。

## 三、镜像体积与 AI 依赖

- 后端默认安装 **CPU 版 torch + transformers + sentence-transformers**（embedding/分类/向量化需要），镜像较大（数 GB）。
- 不需要 AI 功能时可跳过以大幅减小镜像：

```bash
docker compose build --build-arg INSTALL_AI_DEPS=false backend
```

- torch 包约 190MB，首次构建时若一直停在 `install_ai_deps.py --cpu` 是在下载，不是死机；
  构建日志会显示 pip 下载进度条。项目默认已使用阿里云 PyTorch 镜像；如需换其它源：

```bash
# 项目根目录 .env 覆盖后重新构建
TORCH_INDEX_URL=https://你选的镜像源
docker compose build backend
```

- torch CPU 由项目脚本从 PyTorch 官方 CPU 源安装；若服务器访问 `download.pytorch.org` 慢，
  可改为阿里云 PyTorch 镜像（把 `backend/Dockerfile` 中对应 RUN 替换为）：

```dockerfile
# 先装 CPU torch（阿里云镜像），脚本检测到已装会跳过并只装 transformers
RUN pip install torch --index-url https://mirrors.aliyun.com/pytorch-wheels/cpu \
    && python install_ai_deps.py --cpu
```

### 可选：GPU 加速

CPU 版即可跑通；若要 GPU 推理，需使用 NVIDIA 容器运行时（`nvidia-container-toolkit`），
在 `docker-compose.yml` 的 backend 服务加：

```yaml
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

并把 `backend/Dockerfile` 中 AI 依赖改为 `python install_ai_deps.py --gpu`（构建机需能访问 GPU 或改为运行时安装）。

## 四、数据库

- 项目**使用你已有的 MySQL**，不内置数据库容器。连接信息在项目根目录 `.env` 中配置：
  `DB_HOST`（地址）、`DB_PORT`、`DB_USER`、`DB_PASSWORD`、`DB_NAME`（默认 `wengaofabu`）。
- 后端每次启动都会执行幂等 `init_db.py`：
  - 若 `wengaofabu` 库不存在且账号有 CREATE 权限，会自动建库（utf8mb4）；
- 随后建表、兼容迁移、写入种子数据（管理员 `admin/admin123` 等），可安全重复执行。
- 初始化脚本会同时登记 4 个 Dify 工作流（`article_summary` / `article_neirong` /
  `article_weidu` / `article_pingfen`），API Key 优先取 `DIFY_API_KEY` 环境变量；
  未配置时工作流会创建为空 Key，需到后台「Dify 工作流」里补填。
- 若 MySQL 账号没有建库权限，请先手动创建数据库：`CREATE DATABASE wengaofabu DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;`
- 如需把开发环境数据带过来，可用 `mysqldump` 导出后导入该库。

## 五、必须修改的配置（生产）

| 配置 | 位置 | 说明 |
| --- | --- | --- |
| `SECRET_KEY` | `.env` → compose | JWT 签名密钥，必须改成随机长字符串 |
| `DB_PASSWORD` | `.env` → compose | 你已有 MySQL 的数据库密码 |
| `BASE_URL` | `.env` → compose | 静态资源完整 URL 前缀，改为 `http://域名` 或 `http://IP` |
| 端口 | compose `ports` | 如 80 被占用可改为 `8080:80` |
| `AI_API_KEY` | `.env` → compose | AI 阅读功能（全文总结/划词/关键词）的 OpenAI 兼容 Key |
| `DIFY_API_KEY` | `.env` → compose | Dify 工作流统一 Key；未配置则初始化后到后台补填 |

## 六、AI 阅读与 Dify 工作流

- 新增的 AI 全文总结、划词分析、核心术语知识链通过 `AI_API_*` 配置调用 OpenAI 兼容接口，
  未配置 `AI_API_KEY` 时相关按钮会提示不可用，不影响其余门户功能。
- Dify 工作流最长可配置 3600 秒；前端 Nginx 反代已把 `/api`、`/static` 的
  `proxy_read_timeout` / `proxy_send_timeout` 放宽到 3600 秒，避免长工作流被网关掐断。

## 七、数据持久化

- 上传文件：`./uploads` 目录挂载到容器 `/app/uploads`，**不会被容器重建清空**。
## 八、AI 模型权重（如缺少）

- 本地 embedding 模型 `backend/app/multilingual-e5-small` 已在仓库内，随镜像复制。
- 标题分类模型与向量化模型权重不在仓库（见 `backend/app/aimodel/model/`、
  `backend/app/aiVectorizationModel/model/`）。如有权重文件，放到对应目录后重新构建，
  或在 compose 中额外挂载卷。缺失时 AI 分类/向量化功能会报错，其余功能不受影响。

## 九、常用运维命令

```bash
docker compose ps                 # 查看状态
docker compose logs -f backend    # 后端日志
docker compose logs -f frontend   # 前端/Nginx 日志
docker compose exec backend python init_db.py   # 手动重新初始化（幂等）
docker compose restart backend    # 重启后端
docker compose down               # 停止并删除容器（数据卷保留）
docker compose down -v            # 停止并删除容器+匿名卷（慎用；uploads 在宿主机目录不受影响）
```

## 十、域名与 HTTPS

- **DNS 解析**：把域名 A 记录指向服务器公网 IP；云安全组/防火墙放行 80（HTTPS 再放行 443）。
- **BASE_URL**：项目根目录 `.env` 里改为 `BASE_URL=https://你的域名`，影响上传文件、
  静态资源和 RSS 等返回的完整 URL。
- **Nginx server_name**：`frontend/nginx.conf` 的 `server_name _;` 可改为你的域名；
  配置在镜像内，改后需重新构建前端镜像（`docker compose up -d --build frontend`）。
- **HTTPS**：推荐用证书（如 Let's Encrypt）或云负载均衡做 SSL 终结；若在容器 Nginx 做，
  需增加 443 监听、证书挂载与 80→443 跳转；若用宿主机 Nginx/Caddy 反代，
  把 80/443 转发到 frontend 容器即可，项目内无需再改。
- **对象存储**：如果配置了 OSS 且 `public_base_url` 有值，则域名以 OSS 配置为准。

### 无公网 IP：内网穿透

- 服务器没有公网 IP 时，只需把 **frontend 容器监听的 80 端口**穿透出去
  （frp / ngrok / natfrp / Cloudflare Tunnel 等），映射到本机 `127.0.0.1:80` 即可。
- `/api`、`/static` 由容器内 Nginx 在 Docker 内网转发到 `backend:8000`，
  **后端 8000 端口不需要穿透**，也不要暴露到公网。
- `BASE_URL` 填穿透工具给你的公网地址，例如 `https://xxx.natfrp.com` 或
  `https://你的域名`（若公网地址带端口则一起写上）。
- 如需从外网直接访问后端 `/docs` 调试，可临时穿透 8000，用完即关，不建议长期开放。

#### 域名与穿透端口

- DNS 只负责把域名解析到 IP，**不携带端口**。若公网入口是 `38.22.95.20:8080`，
  解析 `A` 记录后需访问 `http://wgfb.89cyx.cc:8080` 才会命中该服务。
- 想去掉端口（直接用 `http://wgfb.89cyx.cc`），需在公网主机 `38.22.95.20` 上
  用 Nginx/Caddy 把 80 端口反代到 `127.0.0.1:8080`，或把 frp 改为 HTTP 域名模式
  （`frps` 开启 `vhost_http_port=80`，客户端用 `type=http` + `custom_domains=wgfb.89cyx.cc`）。
- 域名选择确定后，把 `.env` 的 `BASE_URL` 改为最终用户访问地址
  （如 `http://wgfb.89cyx.cc:8080` 或 `https://wgfb.89cyx.cc`），再重启后端容器生效。

#### frp HTTP 模式样例

frps（公网机 `38.22.95.20`，TOML 格式）：

```toml
bindPort = 7000
vhostHTTPPort = 80
auth.method = "token"
auth.token = "换成你的token"
```

frpc（内网机，TOML 格式；`localPort` 填你本地前端实际监听端口）：

```toml
serverAddr = "38.22.95.20"
serverPort = 7000
auth.token = "换成你的token"

[[proxies]]
name = "xiangmu_http"
type = "http"
localIP = "127.0.0.1"
localPort = 8080
customDomains = ["wgfb.89cyx.cc"]
```

- HTTP 模式下不需要 `remote_port`，公网入口统一走 `vhostHTTPPort`（示例为 80）；
  frps 按请求的域名（Host）把流量转发到对应 frpc。
- 原配置里的 `[xiangmu_udp]` 可删除，HTTP 网站不需要 UDP 代理。
- 域名 A 记录仍为 `wgfb.89cyx.cc -> 38.22.95.20`，解析生效后直接访问
  `http://wgfb.89cyx.cc` 即可（无需带 8080 端口）。
