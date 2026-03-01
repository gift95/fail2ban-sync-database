#!/bin/bash
set -e  # 遇到错误立即退出

# 可调整的变量（与安装脚本保持一致）
INSTALL_DIR="/opt/fail2bansync"
SERVER_USER="fail2bansync"
SERVICE_NAME="fail2bansync-server"
LOG_FILE="/var/log/fail2bansync-server.log"

echo "==== Fail2BanSync 服务器卸载器 ===="
echo "这将完全移除 Fail2BanSync 服务器及其所有组件"
echo "安装目录: $INSTALL_DIR"
echo "系统用户: $SERVER_USER"
echo "服务名称: $SERVICE_NAME"
echo

# 确认卸载
read -p "是否继续卸载? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "卸载已取消"
    exit 0
fi

echo -e "\n=== 1/5 停止并禁用服务 ==="
if systemctl is-active --quiet "$SERVICE_NAME"; then
    sudo systemctl stop "$SERVICE_NAME"
    echo "服务已停止"
else
    echo "服务未运行，跳过停止"
fi

if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    sudo systemctl disable "$SERVICE_NAME"
    echo "服务已禁用"
else
    echo "服务未启用，跳过禁用"
fi

echo -e "\n=== 2/5 删除Systemd服务文件 ==="
if [ -f "/etc/systemd/system/${SERVICE_NAME}.service" ]; then
    sudo rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
    sudo systemctl daemon-reload
    echo "服务文件已删除，systemd已重载"
else
    echo "服务文件不存在，跳过删除"
fi

echo -e "\n=== 3/5 删除日志文件 ==="
if [ -f "$LOG_FILE" ]; then
    sudo rm -f "$LOG_FILE"
    echo "日志文件已删除: $LOG_FILE"
else
    echo "日志文件不存在，跳过删除"
fi

echo -e "\n=== 4/5 删除安装目录 ==="
if [ -d "$INSTALL_DIR" ]; then
    sudo rm -rf "$INSTALL_DIR"
    echo "安装目录已删除: $INSTALL_DIR"
else
    echo "安装目录不存在，跳过删除"
fi

echo -e "\n=== 5/5 删除系统用户 ==="
if id "$SERVER_USER" &>/dev/null; then
    # 检查是否有其他进程在使用该用户
    if pgrep -u "$SERVER_USER" >/dev/null; then
        echo "警告: 用户 $SERVER_USER 仍有进程在运行，跳过删除用户"
        echo "您可以手动检查并删除该用户: sudo userdel $SERVER_USER"
    else
        sudo userdel "$SERVER_USER"
        echo "系统用户已删除: $SERVER_USER"
    fi
else
    echo "用户 $SERVER_USER 不存在，跳过删除"
fi

echo -e "\n==== 卸载完成! ===="
echo "✅ Fail2BanSync 服务器已从系统中移除"
echo "📝 注意: 系统依赖包 (python3, python3-venv, curl, openssl) 未被卸载，如有需要请手动移除"
echo "📝 如果还有其他相关文件需要清理，请手动检查"