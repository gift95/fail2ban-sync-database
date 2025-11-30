#!/bin/bash

# 客户端安装目录
INSTALL_DIR="/opt/fail2bansync-client"
CLIENT_FILE="https://github.com/gift95/fail2ban-sync-database/raw/refs/heads/main/Client/client.py"
CONFIG_FILE="https://github.com/gift95/fail2ban-sync-database/raw/refs/heads/main/Client/clientconfig.ini"

# 从命令行参数获取服务器地址和令牌
SERVER_ADDR="${1:-192.168.0.1:5000}"
TOKEN="${2:-}"

# 分离host和port
HOST=$(echo "$SERVER_ADDR" | cut -d':' -f1)
PORT=$(echo "$SERVER_ADDR" | cut -d':' -f2 || echo "5000")

echo "Fail2BanSync 客户端安装器"
echo "安装目录: $INSTALL_DIR"
echo "服务器地址: $SERVER_ADDR"
if [ -n "$TOKEN" ]; then
    echo "令牌: 已提供"
fi
echo

# 1. 安装Python和pip（如需）
sudo apt update
sudo apt install -y python3 python3-pip

# 安装Curl（如不存在）
sudo apt install -y curl

# 2. 创建安装目录
sudo mkdir -p "$INSTALL_DIR"
sudo chown "$USER":"$USER" "$INSTALL_DIR"

# 3. 从远程URL下载client.py（强制覆盖）
echo "正在从远程服务器下载client.py..."
if ! curl -s -f -o "$INSTALL_DIR/client.py" "$CLIENT_FILE"; then
    echo "错误: 下载client.py失败!"
    exit 1
fi
echo "client.py 已下载并强制覆盖（如果文件已存在）"
chown "$USER":"$USER" "$INSTALL_DIR/client.py"
echo "client.py 下载成功"

# 4. 从远程URL下载配置文件
echo "正在检查配置文件是否存在..."
# 初始化FIRST_RUN变量为false
FIRST_RUN=false

if [ ! -f "$INSTALL_DIR/clientconfig.ini" ]; then
    FIRST_RUN=true  # 配置文件不存在，将首次运行标志设为true
    echo "配置文件不存在，正在从远程服务器下载配置文件..."
    if ! curl -s  -o "$INSTALL_DIR/clientconfig.ini" "$CONFIG_FILE"; then
        echo "警告: 下载配置文件失败，将创建默认配置文件"
        # 创建默认配置文件
        # 根据端口设置协议
        if [ "$PORT" = "443" ]; then
            PROTOCOL="https"
        else
            PROTOCOL="http"
        fi
        cat > "$INSTALL_DIR/clientconfig.ini" <<EOF
[server]
host = $HOST
port = $PORT
protocol = $PROTOCOL

[logging]
log_file = client.log
max_bytes = 1048576
backup_count = 3

[fail2ban]
jail = sshd

[auth]
token = ${TOKEN:-在此添加令牌}
EOF
    else
        echo "配置文件下载成功"
    fi
else
    echo "配置文件已存在，跳过下载操作"
fi

# 如果提供了令牌，更新配置文件中的令牌
if [ -n "$TOKEN" ]; then
    sed -i "s/token = .*/token = $TOKEN/" "$INSTALL_DIR/clientconfig.ini"
    echo "配置文件已使用提供的令牌更新"
fi

# 完全重新设计服务器配置更新逻辑
# 1. 只有在以下情况下才更新服务器配置：
#    - 用户明确提供了非默认的服务器地址作为命令行参数
#    - 配置文件是新创建的（之前不存在）
DEFAULT_SERVER="192.168.0.1:5000"

# 检查是否应该更新服务器配置
should_update_server=false

# 检查是否是首次运行（配置文件刚创建）
if [ "$FIRST_RUN" = true ]; then
    should_update_server=true
fi

# 检查用户是否提供了非默认的服务器地址
# 通过检查是否显式传递了参数来判断
if [ $# -gt 0 ] && [ "$1" != "" ]; then
    # 用户显式提供了服务器地址参数
    should_update_server=true
fi

# 根据条件更新服务器配置
if [ "$should_update_server" = true ]; then
    echo "更新服务器配置..."
    sed -i "s/host = .*/host = $HOST/" "$INSTALL_DIR/clientconfig.ini"
    sed -i "s/port = .*/port = $PORT/" "$INSTALL_DIR/clientconfig.ini"
    # 根据端口更新协议
    if [ "$PORT" = "443" ]; then
        sed -i "s/protocol = .*/protocol = https/" "$INSTALL_DIR/clientconfig.ini"
    else
        sed -i "s/protocol = .*/protocol = http/" "$INSTALL_DIR/clientconfig.ini"
    fi
    echo "服务器配置已更新"
else
    echo "用户未提供服务器地址或使用默认地址，保持现有服务器配置不变"
fi

chown "$USER":"$USER" "$INSTALL_DIR/clientconfig.ini"

# 5. 安装依赖（包括socket模块，但socket是Python标准库，不需要额外安装）
pip3 install --user requests

# 6. 创建systemd服务文件
echo "创建systemd服务文件..."
SERVICE_FILE="/etc/systemd/system/fail2bansync-client.service"

sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=Fail2Ban Sync Client
After=network.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/client.py
Restart=always
RestartSec=60
User=$USER

[Install]
WantedBy=multi-user.target
EOF

# 重新加载systemd配置
sudo systemctl daemon-reload

# 启动并启用服务
sudo systemctl enable fail2bansync-client.service
sudo systemctl start fail2bansync-client.service

echo
echo "完成!"
echo "客户端已安装在: $INSTALL_DIR"
if [ -z "$TOKEN" ]; then
    echo "请在 $INSTALL_DIR/clientconfig.ini 中输入相应的令牌 [auth] token=..."
fi
echo "日志位于 $INSTALL_DIR/client.log"
echo "系统日志可通过: journalctl -u fail2bansync-client.service 查看"
echo
echo "客户端已作为systemd服务安装并启动。"
echo "管理命令:"
echo "  - 启动服务: sudo systemctl start fail2bansync-client.service"
echo "  - 停止服务: sudo systemctl stop fail2bansync-client.service"
echo "  - 重启服务: sudo systemctl restart fail2bansync-client.service"
echo "  - 查看状态: sudo systemctl status fail2bansync-client.service"
echo
echo "客户端将每60秒自动运行一次（通过服务的RestartSec配置）"
echo
SCRIPT_NAME="install_client.sh"
echo "使用方法: $SCRIPT_NAME <server_host>:<port> <token>"
echo "示例: $SCRIPT_NAME 192.168.1.100:5000 abcdef123456"
