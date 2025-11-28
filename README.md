
# Fail2BanSync – Fail2Ban的中央IP同步系统

Fail2Ban-Sync 允许在多个运行 Fail2Ban 的服务器之间集中收集、同步和管理被封禁和允许的 IP 地址。  
该系统由带有令牌认证的服务器端 REST-API 和任意数量的同步客户端组成。

---

## 功能特性

- 基于 Flask 的中央 REST-API，具有令牌认证
- 自动收集和分发被封禁/允许的 IP 地址
- 用于 IP 管理的 SQLite 数据库
- 可配置的封禁时间、阻止和释放周期逻辑
- 日志记录、错误处理和 systemd 集成
- 全自动安装（服务器和客户端）
- 基于 Bearer-Token 的认证

---

## 组件

### 服务器

- 在端口 5000（默认）上提供 REST-API
- 在 SQLite 数据库中存储被封禁/允许的 IP
- 通过 Bearer-Token 认证客户端
- 作为 systemd 服务运行
- 示例配置和为多个客户端自动生成令牌

### 客户端

- 从本地 Fail2Ban 查询被封禁的 IP
- 将这些 IP 发送到服务器
- 从中央获取封禁/允许列表并与本地 Fail2Ban 同步
- 作为定时任务运行（每分钟一次）

---

## 快速开始

### 前提条件

- Ubuntu Server（推荐 20.04 或更高版本）
- Python 3.x
- 安装所需的 root 权限

---

### 服务器安装

1. 将 `server.py` 和 `install_server.sh` 放入一个目录。
2. 执行安装脚本：
    ```bash
    chmod +x install_server.sh
    ./install_server.sh
    ```
3. 根据需要在 `/opt/fail2bansync/serverconfig.ini` 中输入令牌和配置。

4. 检查状态：
    ```bash
    sudo systemctl status fail2bansync-server
    ```
5. **日志：**  
   `/opt/fail2bansync/server.log`

---

### 客户端安装

1. 将 `client.py` 和 `install_client.sh` 放到目标服务器上。
2. 执行脚本：
    ```bash
    chmod +x install_client.sh
    ./install_client.sh
    ```
3. 在 `/opt/fail2bansync-client/clientconfig.ini` 中输入服务器 IP 和令牌。

4. 检查定时任务和日志：
    ```bash
    crontab -l
    tail -f /opt/fail2bansync-client/client_cron.log
    tail -f /opt/fail2bansync-client/client.log
    ```

---

## 安全性与生产环境

- **建议：**  
  始终在 NGINX/Apache 后面运行服务器 API 并使用 HTTPS。
- 安全保管令牌，并从配置中删除不再需要的令牌。
- 定期备份数据库 (`ip_management.db`)。

---

## 扩展与定制

- 通过新令牌轻松添加更多客户端。

---

## 故障排除

- **服务器日志：** `/opt/fail2bansync/server.log`
- **客户端日志：** `/opt/fail2bansync-client/client.log`
- **服务状态：** `sudo systemctl status fail2bansync-server`
- **令牌错误？** → HTTP 401 错误

---

## 升级

- 新版本升级时，只需替换 `server.py` 文件并重启服务，或者替换 `client.py` 文件（定时任务会继续运行）。
- 新令牌可以随时添加到服务器配置中。

---

## 联系我们

如有疑问，请联系开发者。

---

**更新日期：2025年5月**  
**Fail2BanSync – 现代服务器环境的中央 IP 同步系统**
