#!/bin/bash

# 可调整的变量:
INSTALL_DIR="/opt/fail2bansync"
SERVER_USER="fail2bansync"
SERVER_FILE="server.py"
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

# 3. 创建安装目录
sudo mkdir -p "$INSTALL_DIR"
sudo chown "$SERVER_USER":"$SERVER_USER" "$INSTALL_DIR"

# 4. 从当前目录复制server.py
if [ ! -f "$SERVER_FILE" ]; then
    echo "错误: 在当前目录未找到 $SERVER_FILE!"
    exit 1
fi
sudo cp "$SERVER_FILE" "$INSTALL_DIR/$SERVER_FILE"
sudo chown "$SERVER_USER":"$SERVER_USER" "$INSTALL_DIR/$SERVER_FILE"

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
ExecStart=/usr/bin/python3 $INSTALL_DIR/$SERVER_FILE
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
echo "如果您修改了server.py，请将其重新复制到目标目录并重启服务:"
echo "sudo cp server.py $INSTALL_DIR/server.py && sudo systemctl restart $SERVICE_NAME"
