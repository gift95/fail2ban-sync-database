#!/bin/bash
set -e  # 遇到错误立即退出

# 客户端安装目录
INSTALL_DIR="/opt/fail2bansync-client"
SERVICE_NAME="fail2bansync-client"
LOG_FILE="/var/log/${SERVICE_NAME}.log"

echo "==== Fail2BanSync 客户端卸载程序 ===="
echo "这将完全卸载 Fail2BanSync 客户端，包括："
echo "  - 停止并删除 systemd 服务"
echo "  - 删除安装目录: $INSTALL_DIR"
echo "  - 删除日志文件: $LOG_FILE"
echo

# 确认卸载
read -p "确定要继续卸载吗？(y/N): " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "卸载已取消"
    exit 0
fi

# 1. 停止并禁用服务
echo -e "\n=== 1/4 停止并禁用服务 ==="
if systemctl is-active --quiet "$SERVICE_NAME.service" 2>/dev/null; then
    echo "停止服务: $SERVICE_NAME"
    sudo systemctl stop "$SERVICE_NAME.service"
else
    echo "服务未运行"
fi

if systemctl is-enabled --quiet "$SERVICE_NAME.service" 2>/dev/null; then
    echo "禁用服务: $SERVICE_NAME"
    sudo systemctl disable "$SERVICE_NAME.service"
else
    echo "服务未启用"
fi

# 2. 删除服务文件
echo -e "\n=== 2/4 删除服务文件 ==="
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
if [ -f "$SERVICE_FILE" ]; then
    sudo rm -f "$SERVICE_FILE"
    echo "已删除服务文件: $SERVICE_FILE"
    sudo systemctl daemon-reload
    echo "已重新加载 systemd 配置"
else
    echo "服务文件不存在"
fi

# 3. 删除安装目录
echo -e "\n=== 3/4 删除安装目录 ==="
if [ -d "$INSTALL_DIR" ]; then
    sudo rm -rf "$INSTALL_DIR"
    echo "已删除安装目录: $INSTALL_DIR"
else
    echo "安装目录不存在"
fi

# 4. 删除日志文件
echo -e "\n=== 4/4 删除日志文件 ==="
# 删除系统日志
if [ -f "$LOG_FILE" ]; then
    sudo rm -f "$LOG_FILE"
    echo "已删除系统日志: $LOG_FILE"
else
    echo "系统日志不存在"
fi

# 删除客户端日志（在安装目录内，但安装目录已删除，这里只做检查）
CLIENT_LOG="/var/log/${SERVICE_NAME}.log"
if [ -f "$CLIENT_LOG" ]; then
    sudo rm -f "$CLIENT_LOG"
    echo "已删除客户端日志: $CLIENT_LOG"
fi

echo -e "\n==== 卸载完成! ===="
echo "✅ Fail2BanSync 客户端已从系统中完全移除"

# 可选：检查是否有残留的进程
if pgrep -f "python.*client.py" >/dev/null 2>&1; then
    echo -e "\n⚠️  警告: 检测到仍有客户端进程在运行"
    echo "   请手动检查并终止: pkill -f 'python.*client.py'"
fi

# 显示卸载结果
echo -e "\n📌 卸载结果摘要:"
echo "  - 服务: 已停止并禁用"
echo "  - 服务文件: 已删除"
echo "  - 安装目录: 已删除"
echo "  - 日志文件: 已删除"