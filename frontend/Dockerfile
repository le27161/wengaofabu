# ============================================================
# 文稿发布系统 - 前端镜像（Node 构建 + Nginx 托管）
# 构建：cd frontend && docker build -t wgxt-frontend:latest .
# Nginx 将 /api、/static 反向代理到后端服务 backend:8000（见 nginx.conf）
# ============================================================
FROM node:20-alpine AS build
WORKDIR /app
# npm 国内加速（npmmirror）
RUN npm config set registry https://registry.npmmirror.com
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
ENV TZ=Asia/Shanghai
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
