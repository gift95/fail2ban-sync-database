#!/bin/bash

# 可调整的变量:
INSTALL_DIR="/opt/fail2bansync"
SERVER_USER="fail2bansync"
SERVER_FILE="https://github.com/gift95/fail2ban-sync-database/raw/refs/heads/main/Server/server.py"
# 模板文件URL
DASHBOARD_TEMPLATE="https://github.com/gift95/fail2ban-sync-database/raw/refs/heads/main/Server/templates/dashboard.html"
LOGIN_TEMPLATE="https://github.com/gift95/fail2ban-sync-database/raw/refs/heads/main/Server/templates/login.html"
SERVICE_NAME="fail2bansync-server"

echo "==== Fail2BanSync 服务器安装器 ===="
echo "安装目录: $INSTALL_DIR"
echo "系统用户: $SERVER_USER"
echo

# 1. 安装Python和pip
sudo apt update
sudo apt install -y python3 python3-pip

# 2. 创建用户（如不存在）
if ! id "$SERVER_USER" &>/dev/null; then
    sudo useradd -r -s /bin/false "$SERVER_USER"
fi

# 3. 创建安装目录和templates子目录
sudo mkdir -p "$INSTALL_DIR"
sudo mkdir -p "$INSTALL_DIR/templates"
sudo chown -R "$SERVER_USER":"$SERVER_USER" "$INSTALL_DIR"

# 4. 从远程URL下载server.py（强制覆盖）
echo "正在从远程服务器下载server.py..."
if ! sudo curl -s -f -o "$INSTALL_DIR/server.py" "$SERVER_FILE"; then
    echo "错误: 下载server.py失败!"
    exit 1
fi
sudo chown "$SERVER_USER":"$SERVER_USER" "$INSTALL_DIR/server.py"
sudo chmod +x "$INSTALL_DIR/server.py"
echo "server.py 已下载并强制覆盖（如果文件已存在）"
echo "server.py 下载成功并设置了执行权限"

# 4.1 下载模板文件（强制覆盖）
echo "正在下载模板文件..."
if ! sudo curl -s -f -o "$INSTALL_DIR/templates/dashboard.html" "$DASHBOARD_TEMPLATE"; then
    echo "错误: 下载dashboard.html失败!"
    exit 1
fi

if ! sudo curl -s -f -o "$INSTALL_DIR/templates/login.html" "$LOGIN_TEMPLATE"; then
    echo "错误: 下载login.html失败!"
    exit 1
fi

sudo chown -R "$SERVER_USER":"$SERVER_USER" "$INSTALL_DIR/templates"
echo "模板文件已成功下载并设置了正确的所有权"

# 5. 创建示例配置
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
    sudo chown "$SERVER_USER":"$SERVER_USER" "$INSTALL_DIR/serverconfig.ini"
fi

# 6. 安装依赖
sudo pip3 install flask flask_httpauth

# 7. 创建Systemd服务
sudo tee /etc/systemd/system/${SERVICE_NAME}.service >/dev/null <<EOF
[Unit]
Description=Fail2BanSync API服务器
After=network.target

[Service]
Type=simple
User=$SERVER_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/server.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# 8. 启用并启动Systemd服务
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

echo
echo "==== 完成! ===="
echo "Fail2BanSync服务器现在以Systemd服务运行: $SERVICE_NAME"
echo "使用以下命令检查状态: sudo systemctl status $SERVICE_NAME"
echo
echo "配置文件位于: $INSTALL_DIR/serverconfig.ini"
echo
echo "如果您需要更新server.py，请重新运行安装脚本:"
echo "./install_server.sh && sudo systemctl restart $SERVICE_NAME"
