
# Fail2BanSync 客户端

Fail2BanSync 客户端自动将被封禁和允许的 IP 与中央 Fail2BanSync 服务器同步。  
它适用于轻松集成到现有系统中。

---

## 功能特性

- 定期同步（通过定时任务每分钟一次）
- 自动将被封禁的 IP 发送到服务器
- 获取并应用中央允许/阻止的 IP 地址
- 通过简单的 INI 文件配置

---


## 安装（Ubuntu，推荐 20.04 或更高版本）

### 前提条件

Fail2ban 必须已经安装并激活。

```bash
apt install fail2ban
service fail2ban start
```


### 1. 复制文件

将文件 `client.py` 和 `install_client.sh` 放到目标系统上。

### 2. 执行安装脚本

```bash
chmod +x install_client.sh
./install_client.sh
```

脚本将执行以下操作：
- 创建 `/opt/fail2bansync-client` 目录
- 复制 `client.py` 并创建示例配置 `clientconfig.ini`
- 安装 Python 依赖 `requests`
- 设置定时任务以每分钟自动执行

### 3. 配置

打开 `/opt/fail2bansync-client/clientconfig.ini`  
并在 `[server]` 部分输入服务器的 IP 地址，在 `[auth]` 部分输入适合您客户端的令牌。

**示例：**
```ini
[server]
host = 192.168.0.1
port = 5000
protocol = http

[logging]
log_file = client.log
max_bytes = 1048576
backup_count = 3

[fail2ban]
jail = sshd

[auth]
token = 服务器提供的令牌
```

---

## 运行与日志

- **自动执行：**  
  客户端作为定时任务每分钟运行一次，并将日志写入：  
  `/opt/fail2bansync-client/client_cron.log`
  您还可以在同一目录的 `client.log` 文件中找到更多日志。

- **检查定时任务：**  
  ```bash
  crontab -l
  ```

- **手动启动客户端（例如测试）：**
  ```bash
  cd /opt/fail2bansync-client
  python3 client.py
  ```

---

## 安全提示

- 妥善保管 `[auth]` 中的令牌！  
- 确保日志文件不包含敏感数据。
- 如果怀疑令牌泄露，请立即更改令牌（管理员也需要调整服务器配置）。

---

## 故障排除

- 出现问题时，请检查日志文件 `/opt/fail2bansync-client/client_cron.log` 和 `/opt/fail2bansync-client/client.log`。
- 检查系统时间是否正确运行（定时任务是按时间控制的）。
- 服务器 IP 是否正确输入？
- 令牌是否正确输入？错误或缺失的令牌会导致 HTTP 401 错误。

---

## 升级

- 有更新时，只需将新的 `client.py` 文件复制到 `/opt/fail2bansync-client/` 即可。
- 无需重启，定时任务会自动处理一切。

---

## 联系我们

如有疑问，请联系开发者。

---

**更新日期：2025年5月**  
**Fail2BanSync – 简单、安全的 Fail2Ban 中央同步**
