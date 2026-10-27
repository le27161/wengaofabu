# ============================================================
# 文稿发布系统 - 后端镜像（FastAPI + Python 3.10.20）
# 构建：cd backend && docker build -t wgxt-backend:latest .
# 说明：
#   - 国内加速：pip 使用清华源，apt 使用清华源，npm 见 frontend/Dockerfile
#   - 默认安装 AI 依赖（torch CPU 版 + transformers/sentence-transformers）；
#     服务器无 AI 需求时可用 --build-arg INSTALL_AI_DEPS=false 大幅减小镜像
#   - GPU 场景见 docs/docker_deploy.md「可选：GPU 加速」
# ============================================================
FROM python:3.10.20-slim-bookworm

# 国内 pip 加速：清华源（torch 由 install_ai_deps.py 单独走官方 CPU 源）
ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# apt 换国内镜像（清华源），安装时区数据与健康检查工具
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g; s|security.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true \
    && apt-get update \
    && apt-get install -y --no-install-recommends tzdata curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先复制 AI 依赖安装脚本，利用 Docker 层缓存（改动少时可复用该层）
COPY install_ai_deps.py ./
ARG INSTALL_AI_DEPS=true
ARG TORCH_INDEX_URL="https://mirrors.aliyun.com/pytorch-wheels/cpu"
RUN if [ "$INSTALL_AI_DEPS" = "true" ]; then python install_ai_deps.py --cpu --torch-index "${TORCH_INDEX_URL:-https://mirrors.aliyun.com/pytorch-wheels/cpu}"; fi

# 基础依赖（清华源加速）
COPY requirements.txt ./
RUN pip install -r requirements.txt

# 复制后端代码（.dockerignore 已排除 .env / uploads / 日志等）
COPY . .

# 启动入口：等待 MySQL → 幂等初始化（建库/建表/种子）→ uvicorn
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
# 防止 Windows 同步过来的脚本带 CRLF 导致 shebang 失效（/bin/sh\r 找不到解释器）
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["docker-entrypoint.sh"]
# 生产不使用 reload；默认 1 个 worker（AI 模型常驻内存，多 worker 会成倍放大内存）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
