#!/usr/bin/env bash
# ============================================================================
# 科研助手 Agent 系统 —— 生产环境一键部署脚本（云服务器 / Ubuntu 22.04+）
# 用法（在服务器上，以 root 执行）：
#   sudo bash deploy_server.sh [PROJECT_DIR]
#   PROJECT_DIR 默认 /opt/llm_competition
#
# 前置：
#   1) 已购买云服务器（轻量应用服务器 2核2G 足够，新人价约 ¥70-100/年）
#   2) 已将本项目上传到服务器 PROJECT_DIR（scp / rsync / git clone）
#   3) 云控制台安全组放行 22(SSH) 与 80(HTTP) 入站
#
# 说明：
#   - 后端以 systemd 服务常驻，崩溃/重启自动拉起，无需人为干预
#   - 前端构建为静态包，由 nginx 托管；所有 /api/* 请求反代到 uvicorn
#   - LLM 与 embedding 均走 DashScope 云端 API，服务器无需 GPU
#   - 启动后后端会自动加载 papers/ 下已打包的论文，评委打开即有数据
# ============================================================================
set -euo pipefail

PROJECT_DIR="${1:-/opt/llm_competition}"
BACKEND="$PROJECT_DIR/backend"
FRONTEND="$PROJECT_DIR/frontend"
SERVICE_NAME="llmcompetition"
NGINX_AVAIL="/etc/nginx/sites-available/$SERVICE_NAME"
NGINX_ENABL="/etc/nginx/sites-enabled/$SERVICE_NAME"

# ---- 权限检查 ----
if [[ $EUID -ne 0 ]]; then
  echo "请使用 root 运行：sudo bash $0" >&2
  exit 1
fi

# ---- 项目目录存在性检查 ----
if [[ ! -d "$BACKEND" || ! -d "$FRONTEND" ]]; then
  echo "未找到 $BACKEND 或 $FRONTEND，请先上传项目到 $PROJECT_DIR" >&2
  exit 1
fi

# ---- 读取密钥（优先环境变量，否则交互/自动生成） ----
if [[ -z "${DASHSCOPE_API_KEY:-}" ]]; then
  read -rsp "请输入 DASHSCOPE_API_KEY: " DASHSCOPE_API_KEY
  echo
fi
if [[ -z "$DASHSCOPE_API_KEY" ]]; then
  echo "DASHSCOPE_API_KEY 为空，后端将无法调用大模型，部署中止。" >&2
  exit 1
fi

if [[ -z "${REVIEWER_TOKEN:-}" ]]; then
  REVIEWER_TOKEN="$(python3 -c 'import secrets;print(secrets.token_urlsafe(16))')"
  echo "未提供 REVIEWER_TOKEN，已自动生成：$REVIEWER_TOKEN"
fi

# ---- 公网 IP（仅用于打印提示） ----
PUBLIC_IP="$(curl -s --max-time 5 ifconfig.me || curl -s --max-time 5 icanhazip.com || echo 'YOUR_SERVER_IP')"

echo "==> [1/6] 安装系统依赖与 Node 22 ..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-pip python3-dev build-essential nginx git curl ca-certificates
# Node 22（Vite 8 需要 Node 20+）
if ! command -v node >/dev/null 2>&1 || [[ "$(node -v 2>/dev/null | cut -d. -f1 | tr -d v)" -lt 20 ]]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi

echo "==> [2/6] 构建后端虚拟环境并安装依赖 ..."
cd "$BACKEND"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# 写后端运行环境变量（load_dotenv 会自动读取）
cat > "$BACKEND/.env" <<EOF
DASHSCOPE_API_KEY=$DASHSCOPE_API_KEY
REVIEWER_TOKEN=$REVIEWER_TOKEN
BACKEND_PORT=8000
ALLOW_ORIGINS=*
EOF
echo "已写入 $BACKEND/.env"

echo "==> [3/6] 构建前端静态包 ..."
cd "$FRONTEND"
npm install
npm run build
if [[ ! -d "$FRONTEND/dist" ]]; then
  echo "前端构建失败：未生成 dist/ 目录" >&2
  exit 1
fi

echo "==> [4/6] 注册 systemd 服务（开机自启 + 崩溃自愈） ..."
cat > "/etc/systemd/system/$SERVICE_NAME.service" <<EOF
[Unit]
Description=LLM Competition Backend
After=network.target

[Service]
WorkingDirectory=$BACKEND
ExecStart=$BACKEND/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo "==> [5/6] 配置 nginx 反代 ..."
cat > "$NGINX_AVAIL" <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    root $FRONTEND/dist;
    index index.html;

    # 后端 API：所有请求都在 /api/ 下，rewrite 去掉 /api 前缀转发给 uvicorn
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_read_timeout 300s;
    }

    # 评审只读端点也直接暴露（可选，方便评委直接访问 /reviewer/*）
    location /reviewer/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
    }

    # 静态资源 & Vue Router（history 模式回退）
    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
ln -sf "$NGINX_AVAIL" "$NGINX_ENABL"
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

echo "==> [6/6] 防火墙与就绪检测 ..."
ufw allow 22/tcp >/dev/null 2>&1 || true
ufw allow 80/tcp >/dev/null 2>&1 || true
ufw --force enable >/dev/null 2>&1 || true

sleep 4
if curl -s --max-time 5 "http://127.0.0.1:8000/reviewer/info?token=$REVIEWER_TOKEN" >/dev/null; then
  HEALTH="✓ 后端评审链路正常"
else
  HEALTH="⚠ 后端健康检查未通过，请查 journalctl -u $SERVICE_NAME"
fi

cat <<EOF

============================================================
部署完成 🎉
------------------------------------------------------------
$HEALTH

评委演示地址（公网，评审期间常驻）：
  http://$PUBLIC_IP/
评审只读模式（查看检索/RRF/引用判定/图谱来源）：
  http://$PUBLIC_IP/api/reviewer/info?token=$REVIEWER_TOKEN
  （或 http://$PUBLIC_IP/reviewer/info?token=$REVIEWER_TOKEN）

管理命令：
  查看后端日志 : journalctl -u $SERVICE_NAME -f
  重启后端     : systemctl restart $SERVICE_NAME
  停止演示     : systemctl stop $SERVICE_NAME
  重新部署     : sudo bash $0

注意事项：
  1. 云控制台【安全组】必须放行 80 端口入站，否则外网打不开。
  2. 服务以 systemd 托管，服务器重启/进程崩溃会自动恢复，无需你守着。
  3. 建议把上面的地址+token 复制到比赛系统的"在线演示"栏。
  4. 演示前可在网页上传 Attention Is All You Need v1+v7 触发去重、
     上传互相引用的论文触发引用图谱边、问一个论文里没有的数字触发拒答。
  5. （可选）如需 HTTPS：安装 certbot 后执行
     certbot --nginx -d 你的域名
============================================================
EOF
