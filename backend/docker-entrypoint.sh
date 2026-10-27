#!/bin/sh
# 后端容器启动入口：
#   1) 等待 MySQL 可连（最多 60 秒，配合 compose 中 mysql 服务的启动顺序）
#   2) 执行幂等初始化 init_db.py（建库/建表/兼容迁移/种子数据）
#   3) 启动 uvicorn（沿用 CMD 或 docker run 传入的命令）
set -e

if [ -n "$DB_HOST" ]; then
  echo "[entrypoint] 等待 MySQL（$DB_HOST:$DB_PORT）..."
  i=0
  until python -c "import os,sys,pymysql; pymysql.connect(host=os.environ.get('DB_HOST',''),port=int(os.environ.get('DB_PORT','3306')),user=os.environ.get('DB_USER','root'),password=os.environ.get('DB_PASSWORD',''),connect_timeout=3); sys.exit(0)"; do
    i=$((i + 1))
    if [ "$i" -ge 30 ]; then
      echo "[entrypoint] MySQL 未在 60 秒内就绪，继续启动服务（首次建库可能失败，请检查数据库）"
      break
    fi
    echo "[entrypoint] 等待 MySQL...（第 ${i} 次）"
    sleep 2
  done
  echo "[entrypoint] MySQL 已就绪"
fi

echo "[entrypoint] 执行 init_db.py（幂等，可重复执行）"
python init_db.py || echo "[entrypoint] 警告：init_db.py 执行失败，请检查数据库连接/账号权限"

echo "[entrypoint] 启动服务: $*"
exec "$@"
