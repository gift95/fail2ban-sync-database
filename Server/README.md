
# Fail2BanSync 服务器

Fail2BanSync 是一个中央 API，用于管理多个 Fail2Ban 实例的被封禁和允许的 IP。  
具有令牌认证、systemd 集成和简单配置。

---

## 功能特性

- 用于被封禁和允许的 IP 地址的中央 REST-API
- Bearer-Token 认证
- SQLite 数据库
- 日志记录和轮转支持
- 通过 systemd 自动启动/重启

---

## 安装（Ubuntu）

### 1. 准备文件

将 `server.py` 和 `install_server.sh` 复制到服务器上的任意目录。

### 2. 执行安装脚本

```bash
chmod +x install_server.sh
./install_server.sh
```

脚本将执行以下操作：
- 创建系统用户和目录 (`/opt/fail2bansync`)
- 将 `server.py` 复制到该目录
- 生成 9 个令牌并在 `serverconfig.ini` 中注册
- 安装依赖项 (`flask`, `flask_httpauth`)
- 激活并启动 `fail2bansync-server` 服务

### 3. 检查状态

```bash
sudo systemctl status fail2bansync-server
```

---

## 配置

- 主配置：`/opt/fail2bansync/serverconfig.ini`
- 示例：
    ```ini
    [DEFAULT]
    bantime = 10m
    bantime.increment = true
    bantime.factor = 3
    bantime.maxtime = 5w
    known_duration = 48h
    allowed_duration = 2m

    [api_tokens]
    client1 = <TOKEN1>
    client2 = <TOKEN2>
    ...
    ```
- 每个客户端需要一个独立的令牌。

---

## Systemd 服务控制

| 命令                                      | 用途             |
|------------------------------------------|------------------|
| `sudo systemctl start fail2bansync-server`   | 启动服务器    |
| `sudo systemctl stop fail2bansync-server`    | 停止服务器    |
| `sudo systemctl restart fail2bansync-server` | 重启服务器 |
| `sudo systemctl status fail2bansync-server`  | 显示状态   |

每次修改 `server.py` 或 `serverconfig.ini` 后，请重启服务。

---

## 日志文件

- 服务器日志位于：  
  `/opt/fail2bansync/server.log`

---

## 客户端连接

安装结束时，脚本会输出 9 个用于 `clientconfig.ini` 的 `[auth]` 块 - 每个客户端一个（1-9）。

**每个客户端：**
```ini
[auth]
token = <从SERVERCONFIG.INI获取的独立令牌>
```

---

## 安全性与运行

- **API 仅可通过有效的 Bearer-Token 访问**
- 在 `[api_tokens]` 中删除已泄露的令牌，然后重启服务
- 建议定期备份数据库 (`ip_management.db`)

---

## 故障排除

- 检查日志：`/opt/fail2bansync/server.log`
- 显示状态：`sudo systemctl status fail2bansync-server`

---

## 常见问题

- **添加更多客户端？**  
  → 生成令牌（例如使用 `openssl rand -hex 32`），添加到 `[api_tokens]`，重启服务。
- **日志太大？**  
  → 通过 `logrotate` 或手动设置日志轮转。

---

## 联系我们

如有疑问，请联系开发者。

---

**更新日期：2025年5月**  
**Fail2BanSync – Fail2Ban 的中央、安全的 IP 同步**
