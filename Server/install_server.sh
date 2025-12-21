#!/bin/bash
set -e  # 遇到错误立即退出

# 可调整的变量
INSTALL_DIR="/opt/fail2bansync"
VENV_DIR="${INSTALL_DIR}/venv"  # 虚拟环境目录
SERVER_USER="fail2bansync"
SERVER_FILE="https://gitea.yxliu.cc/gift95/fail2ban-sync/raw/branch/main/Server/server.py"
DASHBOARD_TEMPLATE="https://gitea.yxliu.cc/gift95/fail2ban-sync/raw/branch/main/Server/templates/dashboard.html"
LOGIN_TEMPLATE="https://gitea.yxliu.cc/gift95/fail2ban-sync/raw/branch/main/Server/templates/login.html"
SERVICE_NAME="fail2bansync-server"
PYTHON_BIN="${VENV_DIR}/bin/python3"  # 虚拟环境Python路径
PIP_BIN="${VENV_DIR}/bin/pip3"        # 虚拟环境pip路径

echo "==== Fail2BanSync 服务器安装器（带Python虚拟环境） ===="
echo "安装目录: $INSTALL_DIR"
echo "虚拟环境: $VENV_DIR"
echo "系统用户: $SERVER_USER"
echo

# 1. 安装系统依赖（包含python3-venv）
echo "=== 1/8 安装系统基础依赖 ==="
sudo apt update
sudo apt install -y python3 python3-venv curl openssl
echo "系统依赖安装完成"

# 2. 创建专用用户（如不存在）
echo -e "\n=== 2/8 创建系统用户 ==="
if ! id "$SERVER_USER" &>/dev/null; then
    sudo useradd -r -s /bin/false "$SERVER_USER"
    echo "已创建用户: $SERVER_USER"
else
    echo "用户 $SERVER_USER 已存在，跳过创建"
fi

# 3. 创建目录结构
echo -e "\n=== 3/8 创建安装目录 ==="
sudo mkdir -p "$INSTALL_DIR/templates"
sudo chown -R "$SERVER_USER:$SERVER_USER" "$INSTALL_DIR"
echo "安装目录已创建: $INSTALL_DIR"

# 4. 下载核心文件
echo -e "\n=== 4/8 下载server.py ==="
if ! sudo curl -s -f -o "$INSTALL_DIR/server.py" "$SERVER_FILE"; then
    echo "错误: 下载server.py失败!"
    exit 1
fi
sudo chown "$SERVER_USER:$SERVER_USER" "$INSTALL_DIR/server.py"
sudo chmod +x "$INSTALL_DIR/server.py"
echo "server.py 下载完成并设置执行权限"

echo -e "\n=== 5/8 下载模板文件 ==="
# 下载dashboard.html
if ! sudo curl -s -f -o "$INSTALL_DIR/templates/dashboard.html" "$DASHBOARD_TEMPLATE"; then
    echo "错误: 下载dashboard.html失败!"
    exit 1
fi
# 下载login.html
if ! sudo curl -s -f -o "$INSTALL_DIR/templates/login.html" "$LOGIN_TEMPLATE"; then
    echo "错误: 下载login.html失败!"
    exit 1
fi
sudo chown -R "$SERVER_USER:$SERVER_USER" "$INSTALL_DIR/templates"
echo "模板文件下载完成"

# 5. 创建配置文件（如不存在）
echo -e "\n=== 6/8 创建配置文件 ==="
if [ ! -f "$INSTALL_DIR/serverconfig.ini" ]; then
    sudo tee "$INSTALL_DIR/serverconfig.ini" >/dev/null <<EOF
[DEFAULT]
# 初始封禁时间
bantime = 10m
# 是否启用递增封禁时间
bantime.increment = true
# 递增因子
bantime.factor = 3
# 最大封禁时间
bantime.maxtime = 5w
# IP保留在known状态的时间
known_duration = 48h
# IP保留在allowed状态的时间
allowed_duration = 2m

[api_tokens]
# 客户端令牌配置
client1 = $(openssl rand -hex 32)
client2 = $(openssl rand -hex 32)
client3 = $(openssl rand -hex 32)
client4 = $(openssl rand -hex 32)
client5 = $(openssl rand -hex 32)
client6 = $(openssl rand -hex 32)
client7 = $(openssl rand -hex 32)
client8 = $(openssl rand -hex 32)
client9 = $(openssl rand -hex 32)
EOF
    sudo chown "$SERVER_USER:$SERVER_USER" "$INSTALL_DIR/serverconfig.ini"
    echo "配置文件已创建: $INSTALL_DIR/serverconfig.ini"
else
    echo "配置文件已存在，跳过创建"
fi

# 6. 创建并配置Python虚拟环境
echo -e "\n=== 7/8 创建Python虚拟环境并安装依赖 ==="
# 创建虚拟环境
sudo -u "$SERVER_USER" python3 -m venv "$VENV_DIR"
echo "虚拟环境已创建: $VENV_DIR"

# 升级pip并安装依赖（使用虚拟环境的pip）
sudo -u "$SERVER_USER" "$PIP_BIN" install --upgrade pip
sudo -u "$SERVER_USER" "$PIP_BIN" install flask flask_httpauth flask_compress
echo "依赖包安装完成: flask, flask_httpauth, flask_compress"

# 7. 创建Systemd服务文件（使用虚拟环境Python）
echo -e "\n=== 8/8 创建Systemd服务 ==="
sudo tee /etc/systemd/system/${SERVICE_NAME}.service >/dev/null <<EOF
[Unit]
Description=Fail2BanSync API服务器
After=network.target
StartLimitInterval=60
StartLimitBurst=5

[Service]
Type=simple
User=$SERVER_USER
Group=$SERVER_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$PYTHON_BIN $INSTALL_DIR/server.py
Restart=on-failure
RestartSec=3
StandardOutput=append:/var/log/fail2bansync-server.log
StandardError=append:/var/log/fail2bansync-server.log
# 限制资源（可选）
LimitNOFILE=1024
LimitNPROC=512

[Install]
WantedBy=multi-user.target
EOF

# 创建日志文件并设置权限
sudo touch /var/log/fail2bansync-server.log
sudo chown "$SERVER_USER:$SERVER_USER" /var/log/fail2bansync-server.log

# 重新加载systemd并重启服务
sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo -e "\n==== 安装完成! ===="
echo "✅ Fail2BanSync服务器已配置为Systemd服务: $SERVICE_NAME"
echo "📋 状态检查命令: sudo systemctl status $SERVICE_NAME"
echo "📜 日志查看命令: tail -f /var/log/fail2bansync-server.log"
echo "⚙️  配置文件: $INSTALL_DIR/serverconfig.ini"
echo "🌐 虚拟环境: $VENV_DIR"
echo -e "\n如果需要更新server.py，重新运行本脚本即可自动覆盖并重启服务"