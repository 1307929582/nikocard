#!/usr/bin/env bash

set -euo pipefail

APP_NAME="nikocard"
ENV_FILE=".env"
COMPOSE_CMD=""
SUDO=""

echo "======================================"
echo "   NikoCard 一键部署脚本"
echo "======================================"

if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo &> /dev/null; then
        SUDO="sudo"
    else
        echo "请使用 root 运行，或安装 sudo 后重试。"
        exit 1
    fi
fi

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "[1/4] 安装 Docker..."
    curl -fsSL https://get.docker.com | $SUDO sh
    $SUDO systemctl enable --now docker
else
    echo "[1/4] Docker 已安装 ✓"
fi

# 检查 Docker Compose
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
    echo "[2/4] Docker Compose 已安装 ✓"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
    echo "[2/4] Docker Compose 已安装 ✓"
else
    echo "[2/4] 安装 Docker Compose..."
    $SUDO curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    $SUDO chmod +x /usr/local/bin/docker-compose
    COMPOSE_CMD="docker-compose"
fi
if [ -n "$SUDO" ]; then
    COMPOSE_CMD="$SUDO $COMPOSE_CMD"
fi

# 生成密钥与环境变量
if [ ! -f "$ENV_FILE" ]; then
    echo "[3/4] 生成环境配置..."
    if command -v openssl &> /dev/null; then
        SECRET_KEY="$(openssl rand -hex 32)"
    else
        SECRET_KEY="$(python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
    fi
    cat > "$ENV_FILE" <<EOF
SECRET_KEY=${SECRET_KEY}
APP_PORT=5000
DATA_DIR=./data
GUNICORN_WORKERS=2
GUNICORN_THREADS=4
GUNICORN_TIMEOUT=60
TZ=Asia/Shanghai
EOF
else
    echo "[3/4] 环境配置已存在 ✓"
fi

# 确保持久化目录存在
mkdir -p ./data

# 构建并启动
echo "[4/4] 构建并启动服务..."
$COMPOSE_CMD down 2>/dev/null || true
$COMPOSE_CMD up -d --build

APP_PORT="$(grep -E '^APP_PORT=' "$ENV_FILE" | tail -n1 | cut -d= -f2-)"
APP_PORT="${APP_PORT:-5000}"
SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo ""
echo "======================================"
echo "   部署完成！"
echo "======================================"
echo ""
if [ -n "$SERVER_IP" ]; then
    echo "访问地址: http://${SERVER_IP}:${APP_PORT}"
else
    echo "访问地址: http://<服务器IP>:${APP_PORT}"
fi
echo ""
echo "管理命令:"
echo "  查看日志: $COMPOSE_CMD logs -f"
echo "  停止服务: $COMPOSE_CMD down"
echo "  重启服务: $COMPOSE_CMD restart"
echo ""
