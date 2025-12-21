#!/bin/bash
set -e  # 遇到错误立即退出

# 客户端安装目录
INSTALL_DIR="/opt/fail2bansync-client"
VENV_DIR="${INSTALL_DIR}/venv"  # 虚拟环境目录
CLIENT_FILE="https://gitea.yxliu.cc/gift95/fail2ban-sync/raw/branch/main/Client/client.py"
CONFIG_FILE="https://gitea.yxliu.cc/gift95/fail2ban-sync/raw/branch/main/Client/clientconfig.ini"
PYTHON_BIN="${VENV_DIR}/bin/python3"  # 虚拟环境Python路径
PIP_BIN="${VENV_DIR}/bin/pip3"        # 虚拟环境pip路径

# 从命令行参数获取服务器地址和令牌
SERVER_ADDR="${1:-192.168.0.1:5000}"
TOKEN="${2:-}"

# 分离host和port（兼容仅传host的情况）
HOST=$(echo "$SERVER_ADDR" | cut -d':' -f1)
PORT=$(echo "$SERVER_ADDR" | cut -d':' -f2 || echo "5000")
# 修复port为空的情况（仅传host时）
if [ -z "$PORT" ] || [ "$PORT" = "$HOST" ]; then
    PORT="5000"
fi

# 定义服务名
SERVICE_NAME="fail2bansync-client"

echo "==== Fail2BanSync 客户端安装器（带Python虚拟环境） ===="
echo "安装目录: $INSTALL_DIR"
echo "虚拟环境: $VENV_DIR"
echo "服务器地址: $SERVER_ADDR (host: $HOST, port: $PORT)"
if [ -n "$TOKEN" ]; then
    echo "令牌: 已提供"
else
    echo "令牌: 未提供（需后续手动配置）"
fi
echo

# 1. 安装系统依赖（包含python3-venv）
echo "=== 1/7 安装系统基础依赖 ==="
sudo apt update
sudo apt install -y python3 python3-venv curl openssl
echo "系统依赖安装完成"

# 2. 创建安装目录
echo -e "\n=== 2/7 创建安装目录 ==="
sudo mkdir -p "$INSTALL_DIR"
sudo chown -R "$USER:$USER" "$INSTALL_DIR"
echo "安装目录已创建: $INSTALL_DIR"

# 3. 下载client.py（强制覆盖）
echo -e "\n=== 3/7 下载客户端核心文件 ==="
if ! curl -s -f -o "$INSTALL_DIR/client.py" "$CLIENT_FILE"; then
    echo "错误: 下载client.py失败!"
    exit 1
fi
chmod +x "$INSTALL_DIR/client.py"
chown "$USER:$USER" "$INSTALL_DIR/client.py"
echo "client.py 下载完成并设置执行权限"

# 4. 配置文件处理
echo -e "\n=== 4/7 配置文件处理 ==="
# 初始化FIRST_RUN变量为false
FIRST_RUN=false

if [ ! -f "$INSTALL_DIR/clientconfig.ini" ]; then
    FIRST_RUN=true  # 配置文件不存在，将首次运行标志设为true
    echo "配置文件不存在，尝试从远程下载..."
    if ! curl -s -f -o "$INSTALL_DIR/clientconfig.ini" "$CONFIG_FILE"; then
        echo "警告: 下载配置文件失败，创建默认配置文件"
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
if [ $# -gt 0 ] && [ "$1" != "" ] && [ "$1" != "$DEFAULT_SERVER" ]; then
    # 用户显式提供了非默认服务器地址参数
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
    echo "用户未提供非默认服务器地址，保持现有服务器配置不变"
fi

chown "$USER:$USER" "$INSTALL_DIR/clientconfig.ini"

# 5. 创建Python虚拟环境并安装依赖
echo -e "\n=== 5/7 创建Python虚拟环境并安装依赖 ==="
# 创建虚拟环境
python3 -m venv "$VENV_DIR"
echo "虚拟环境已创建: $VENV_DIR"

# 升级pip并安装依赖（使用虚拟环境的pip）
"$PIP_BIN" install --upgrade pip
"$PIP_BIN" install requests
echo "依赖包安装完成: requests"

# 6. 创建systemd服务文件（使用虚拟环境Python）
echo -e "\n=== 6/7 创建Systemd服务 ==="
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=Fail2Ban Sync Client
After=network.target
StartLimitInterval=60
StartLimitBurst=5

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=$PYTHON_BIN $INSTALL_DIR/client.py
Restart=always
RestartSec=60
User=$USER
Group=$USER
# 日志配置
StandardOutput=append:/var/log/${SERVICE_NAME}.log
StandardError=append:/var/log/${SERVICE_NAME}.log
# 资源限制
LimitNOFILE=1024
LimitNPROC=512

[Install]
WantedBy=multi-user.target
EOF

# 创建日志文件并设置权限
sudo touch "/var/log/${SERVICE_NAME}.log"
sudo chown "$USER:$USER" "/var/log/${SERVICE_NAME}.log"

# 7. 启动并启用服务
echo -e "\n=== 7/7 启动Systemd服务 ==="
# 重新加载systemd配置
sudo systemctl daemon-reload

# 启动并启用服务
sudo systemctl enable --now "${SERVICE_NAME}.service"
sudo systemctl restart "${SERVICE_NAME}.service"

echo -e "\n==== 安装完成! ===="
echo "✅ 客户端已安装在: $INSTALL_DIR"
echo "🌐 虚拟环境路径: $VENV_DIR"
if [ -z "$TOKEN" ]; then
    echo "⚠️  请在 $INSTALL_DIR/clientconfig.ini 中配置令牌：[auth] token=你的令牌"
fi
echo "📜 应用日志: $INSTALL_DIR/client.log"
echo "📋 系统日志: /var/log/${SERVICE_NAME}.log"
echo -e "\n📌 服务管理命令:"
echo "  - 启动服务: sudo systemctl start ${SERVICE_NAME}.service"
echo "  - 停止服务: sudo systemctl stop ${SERVICE_NAME}.service"
echo "  - 重启服务: sudo systemctl restart ${SERVICE_NAME}.service"
echo "  - 查看状态: sudo systemctl status ${SERVICE_NAME}.service"
echo "  - 查看日志: journalctl -u ${SERVICE_NAME}.service -f"
echo -e "\n💡 使用方法（重新安装/更新）:"
SCRIPT_NAME=$(basename "$0")
echo "  $SCRIPT_NAME <server_host>:<port> <token>"
echo "  示例: $SCRIPT_NAME 192.168.1.100:5000 abcdef123456"
echo -e "\n客户端将每60秒自动运行一次（通过RestartSec配置）"