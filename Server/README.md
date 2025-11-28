# Fail2BanSync 服务器

![Fail2BanSync Logo](https://via.placeholder.com/80x80?text=F2BS)

## 📋 项目简介

Fail2BanSync 服务器是一个强大的中央管理系统，用于集中控制和同步多个 Fail2Ban 实例的 IP 封禁策略。它提供了企业级的 API 服务，使管理员能够在分布式环境中统一管理网络安全策略，实现跨服务器的 IP 封禁协同工作。

## ✨ 功能特性

- **中央化 IP 管理**：统一管理所有客户端的封禁和允许 IP 列表
- **RESTful API 接口**：提供标准的 HTTP API，便于集成和扩展
- **安全认证机制**：使用 Bearer-Token 进行客户端认证，确保 API 安全
- **高性能数据存储**：采用 SQLite 数据库，高效存储和查询 IP 信息
- **智能封禁策略**：支持增量封禁、自定义封禁时间和封禁因子
- **详细日志记录**：完整记录系统操作和 API 请求，支持日志轮转
- **可靠的服务管理**：通过 systemd 提供自动启动、重启和状态监控
- **客户端标识支持**：记录并显示每个连接客户端的名称和 IP 地址

## 🚀 安装指南

### 前提条件

- **操作系统**：Ubuntu 20.04 LTS 或更高版本
- **Python 3**：需要 Python 3.6 或更高版本
- **root 权限**：安装过程需要 sudo 权限
- **网络配置**：确保服务器端口（默认 5000）可被客户端访问

### 快速安装

使用提供的安装脚本进行快速部署：

```bash
# 1. 克隆项目（或下载相关文件）
cd /tmp
git clone https://gitea.yxliu.cc/gift95/fail2ban-sync.git
cd fail2ban-sync/Server

# 2. 赋予脚本执行权限
chmod +x install_server.sh

# 3. 运行安装脚本
./install_server.sh
```

### 安装过程详解

安装脚本会自动执行以下操作：

1. **环境准备**：
   - 检查并安装必要的系统依赖
   - 安装 Python 3 和 pip 包管理器
   - 创建专用的系统用户和组

2. **目录结构**：
   - 创建安装目录：`/opt/fail2bansync/`
   - 设置适当的文件权限

3. **文件部署**：
   - 复制 `server.py` 到安装目录
   - 创建默认配置文件 `serverconfig.ini`
   - 初始化 SQLite 数据库

4. **依赖安装**：
   - 安装 Flask Web 框架
   - 安装 Flask HTTPAuth 认证库
   - 安装其他必要的 Python 依赖

5. **令牌生成**：
   - 自动生成 9 个唯一的客户端认证令牌
   - 在配置文件中注册这些令牌

6. **服务配置**：
   - 创建 systemd 服务文件
   - 设置服务自动启动和重启策略
   - 启动 fail2bansync-server 服务

### 验证安装

安装完成后，验证服务是否正常运行：

```bash
# 检查服务状态
sudo systemctl status fail2bansync-server

# 查看服务日志
sudo journalctl -u fail2bansync-server -n 50
```

## ⚙️ 配置说明

服务器通过 `serverconfig.ini` 文件进行配置，该文件位于 `/opt/fail2bansync/` 目录。

### 完整配置示例

```ini
[DEFAULT]
bantime = 10m            # 默认封禁时间（分钟）
bantime.increment = true # 是否启用增量封禁
bantime.factor = 3       # 增量封禁因子
bantime.maxtime = 5w     # 最大封禁时间（周）
known_duration = 48h     # IP 保留在已知列表中的时间（小时）
allowed_duration = 2m    # IP 保留在允许列表中的时间（分钟）

[api_tokens]
# 为每个客户端分配一个唯一的令牌
client1 = a1b2c3d4e5f6...
client2 = f6e5d4c3b2a1...
client3 = 1a2b3c4d5e6f...
# 可以根据需要添加更多客户端令牌
```

### 配置选项详解

#### [DEFAULT] 部分

| 配置项 | 描述 | 默认值 | 示例值 |
|--------|------|--------|--------|
| `bantime` | 默认的 IP 封禁时间 | 10m | 1h, 30m, 1d |
| `bantime.increment` | 是否启用增量封禁机制 | true | true, false |
| `bantime.factor` | 增量封禁的乘法因子 | 3 | 2, 5, 10 |
| `bantime.maxtime` | 最大的封禁时间限制 | 5w | 1w, 2w, 4w |
| `known_duration` | IP 在已知列表中的保留时间 | 48h | 24h, 72h, 168h |
| `allowed_duration` | IP 在允许列表中的保留时间 | 2m | 1m, 5m, 10m |

#### [api_tokens] 部分

为每个客户端配置一个唯一的认证令牌：

```ini
[api_tokens]
# 格式：客户端名称 = 认证令牌
client1 = 32字符的十六进制令牌
web_server = 另一个32字符的十六进制令牌
```

## 📊 服务管理

### Systemd 服务控制

| 命令 | 用途 |
|------|------|
| `sudo systemctl start fail2bansync-server` | 启动服务器服务 |
| `sudo systemctl stop fail2bansync-server` | 停止服务器服务 |
| `sudo systemctl restart fail2bansync-server` | 重启服务器服务 |
| `sudo systemctl status fail2bansync-server` | 查看服务器状态 |
| `sudo systemctl enable fail2bansync-server` | 设置开机自启 |
| `sudo systemctl disable fail2bansync-server` | 禁用开机自启 |

每次修改 `server.py` 或 `serverconfig.ini` 后，需要重启服务以应用更改：

```bash
sudo systemctl restart fail2bansync-server
```

### 查看日志

#### 系统服务日志

```bash
# 查看最近的服务日志
sudo journalctl -u fail2bansync-server -n 100

# 实时监控服务日志
sudo journalctl -u fail2bansync-server -f

# 查看特定时间范围的日志
sudo journalctl -u fail2bansync-server --since "1 hour ago"
```

#### 应用程序日志

服务器应用日志位于：`/opt/fail2bansync/server.log`

```bash
# 查看应用日志
cat /opt/fail2bansync/server.log

# 实时监控应用日志
tail -f /opt/fail2bansync/server.log

# 搜索日志中的错误信息
grep -i error /opt/fail2bansync/server.log
```

## 🔌 API 端点文档

### API 基础信息

- **基本 URL**：`http://服务器IP:5000/`
- **认证方式**：Bearer Token（在请求头中添加 `Authorization: Bearer <token>`）
- **响应格式**：JSON
- **客户端标识**：支持在认证头中包含客户端名称（格式：`{"token": "<token>", "name": "<client_name>"}`）

### API 端点列表

#### 1. 上传本地封禁 IP

**POST /add_ips**

用于客户端向服务器上传本地封禁的 IP 地址。

**请求头**：
```
Authorization: Bearer {"token": "客户端令牌", "name": "客户端名称"}
Content-Type: application/json
```

**请求体**：
```json
{
  "ips": [
    {"ip": "192.168.1.100", "reason": "sshd", "time": "2023-11-10T12:00:00"},
    {"ip": "192.168.1.101", "reason": "sshd", "time": "2023-11-10T12:05:00"}
  ]
}
```

**响应**：
```json
{"status": "success", "message": "IPs added successfully"}
```

#### 2. 获取全局封禁 IP 列表

**GET /get_ips**

获取服务器上所有需要全局封禁的 IP 地址列表。

**请求头**：
```
Authorization: Bearer {"token": "客户端令牌", "name": "客户端名称"}
```

**响应**：
```json
{
  "ips": [
    {"ip": "192.168.1.100", "reason": "sshd", "time": "2023-11-10T12:00:00", "ban_until": "2023-11-10T12:10:00"},
    {"ip": "192.168.1.101", "reason": "sshd", "time": "2023-11-10T12:05:00", "ban_until": "2023-11-10T12:15:00"}
  ]
}
```

#### 3. 获取允许的 IP 列表

**GET /get_allowed_ips**

获取需要从本地封禁列表中移除的 IP 地址列表。

**请求头**：
```
Authorization: Bearer {"token": "客户端令牌", "name": "客户端名称"}
```

**响应**：
```json
{
  "allowed_ips": ["192.168.1.200", "192.168.1.201"]
}
```

#### 4. 获取所有已知 IP 信息

**GET /get_known_ips**

获取服务器已知的所有 IP 地址及其详细信息。

**请求头**：
```
Authorization: Bearer {"token": "客户端令牌", "name": "客户端名称"}
```

**响应**：
```json
{
  "known_ips": [
    {"ip": "192.168.1.100", "reason": "sshd", "time": "2023-11-10T12:00:00", "ban_until": "2023-11-10T12:10:00", "reported_by": "client1"},
    {"ip": "192.168.1.101", "reason": "sshd", "time": "2023-11-10T12:05:00", "ban_until": "2023-11-10T12:15:00", "reported_by": "client2"}
  ]
}
```

## 🔒 安全最佳实践

### 认证与授权

1. **令牌管理**：
   - 为每个客户端分配唯一的认证令牌
   - 定期轮换令牌以增强安全性
   - 立即撤销泄露的令牌

2. **访问控制**：
   - 限制对配置文件的访问权限：`sudo chmod 600 /opt/fail2bansync/serverconfig.ini`
   - 确保数据库文件安全：`sudo chmod 600 /opt/fail2bansync/ip_management.db`

3. **网络安全**：
   - 考虑在防火墙中限制对服务器端口的访问
   - 仅允许受信任网络的客户端连接
   - 对于生产环境，建议使用 HTTPS 协议

### 日志安全

- 定期审查日志文件，查找异常活动
- 确保日志文件不被未授权访问
- 考虑配置日志集中管理系统

## 📊 数据库管理

### 数据库结构

Fail2BanSync 使用 SQLite 数据库，主要包含以下表结构：

- **banned_ips**：存储当前被封禁的 IP 信息
- **allowed_ips**：存储需要允许的 IP 信息
- **known_ips**：存储服务器已知的所有 IP 历史信息

### 数据库文件

- **位置**：`/opt/fail2bansync/ip_management.db`
- **备份**：建议定期备份此文件

### 数据库备份与恢复

**备份数据库**：

```bash
# 创建数据库备份
sudo cp /opt/fail2bansync/ip_management.db /opt/fail2bansync/ip_management.db.backup

# 创建定时备份（可添加到 crontab）
sudo crontab -e
# 添加以下行（每天凌晨 2 点备份）
0 2 * * * cp /opt/fail2bansync/ip_management.db /opt/fail2bansync/ip_management.db.$(date +\%Y\%m\%d)
```

**恢复数据库**：

```bash
# 停止服务
sudo systemctl stop fail2bansync-server

# 恢复备份
sudo cp /opt/fail2bansync/ip_management.db.backup /opt/fail2bansync/ip_management.db

# 启动服务
sudo systemctl start fail2bansync-server
```

## 🔧 客户端管理

### 添加新客户端

1. **生成新令牌**：

```bash
# 使用 openssl 生成安全令牌
openssl rand -hex 32
```

2. **添加到配置文件**：

```bash
# 编辑配置文件
sudo nano /opt/fail2bansync/serverconfig.ini

# 在 [api_tokens] 部分添加新客户端
[api_tokens]
client1 = existing_token1
client2 = existing_token2
new_client = newly_generated_token
```

3. **重启服务**：

```bash
sudo systemctl restart fail2bansync-server
```

4. **配置客户端**：

为新客户端提供令牌，用于其 `clientconfig.ini` 文件：

```ini
[auth]
token = newly_generated_token
```

### 移除客户端

1. **从配置文件中删除令牌**：

```bash
sudo nano /opt/fail2bansync/serverconfig.ini
# 删除对应的客户端令牌行
```

2. **重启服务**：

```bash
sudo systemctl restart fail2bansync-server
```

## 🛠️ 故障排除

### 常见问题及解决方案

#### 1. 服务无法启动

**症状**：
- `systemctl status` 显示服务启动失败
- 日志中出现错误信息

**解决方案**：

```bash
# 检查服务状态和错误信息
sudo systemctl status fail2bansync-server
sudo journalctl -u fail2bansync-server -n 100 --no-pager

# 检查端口是否被占用
netstat -tulpn | grep 5000

# 检查配置文件格式
sudo python3 -m configparser /opt/fail2bansync/serverconfig.ini

# 手动运行服务器进行调试
cd /opt/fail2bansync
sudo python3 server.py
```

#### 2. 客户端无法连接

**症状**：
- 客户端日志显示连接错误
- 服务器日志显示认证失败

**解决方案**：

```bash
# 检查服务器是否运行
sudo systemctl status fail2bansync-server

# 验证客户端令牌是否正确
grep -A 10 "[api_tokens]" /opt/fail2bansync/serverconfig.ini

# 检查防火墙设置
sudo ufw status

# 测试 API 连接
gcurl -X GET http://localhost:5000/get_ips -H "Authorization: Bearer client1_token"
```

#### 3. 数据库错误

**症状**：
- 日志中显示数据库相关错误
- API 返回数据库错误

**解决方案**：

```bash
# 检查数据库文件权限
sudo ls -la /opt/fail2bansync/ip_management.db

# 验证数据库完整性
sudo sqlite3 /opt/fail2bansync/ip_management.db "PRAGMA integrity_check;"

# 如果数据库损坏，从备份恢复
```

#### 4. 性能问题

**症状**：
- API 响应缓慢
- 服务器资源使用率高

**解决方案**：

```bash
# 检查系统资源使用情况
top -u fail2bansync

# 检查日志文件大小
du -h /opt/fail2bansync/server.log*

# 考虑优化数据库索引（如果需要）
sudo sqlite3 /opt/fail2bansync/ip_management.db "CREATE INDEX IF NOT EXISTS idx_banned_ips_ip ON banned_ips(ip);"
```

### 诊断命令

```bash
# 检查 Python 版本
python3 --version

# 检查安装的 Python 包
pip3 list | grep -E 'flask|sqlite3'

# 测试网络连接
ping 客户端IP
telnet 客户端IP 5000

# 检查服务器监听端口
netstat -tulpn | grep 5000

# 查看系统负载
uptime

# 检查磁盘空间
df -h
```

## 🔄 升级指南

### 服务器升级

```bash
# 1. 停止当前服务
sudo systemctl stop fail2bansync-server

# 2. 备份当前配置和数据库
cp /opt/fail2bansync/serverconfig.ini /tmp/
cp /opt/fail2bansync/ip_management.db /tmp/

# 3. 下载新版本的 server.py
cd /opt/fail2bansync
sudo curl -s -o server.py https://gitea.yxliu.cc/gift95/fail2ban-sync/raw/branch/main/Server/server.py

# 4. 恢复配置文件（如果新版本有配置变更，可能需要手动合并）
cp /tmp/serverconfig.ini /opt/fail2bansync/

# 5. 重启服务
sudo systemctl start fail2bansync-server

# 6. 验证服务状态
sudo systemctl status fail2bansync-server
```

### 配置升级

当升级到新版本时，可能需要更新配置文件以支持新功能。请参考最新的配置示例进行必要的调整。

## 📈 性能与扩展

### 性能优化建议

- **日志轮转**：确保日志文件不会变得过大
- **数据库维护**：定期备份和优化数据库
- **资源监控**：监控服务器资源使用情况，及时调整配置
- **网络优化**：确保网络连接稳定，考虑使用 HTTPS 加速

### 扩展考虑

- **多服务器部署**：对于大规模部署，考虑使用主从架构
- **负载均衡**：如果需要支持大量客户端，可以配置负载均衡
- **外部数据库**：对于非常大的部署，可以考虑迁移到 PostgreSQL 或 MySQL

## 📝 常见部署场景

### 场景 1：小型环境（1-10 台服务器）

- 单服务器部署 Fail2BanSync 服务
- 所有客户端连接到同一中央服务器
- 使用默认配置即可满足需求

### 场景 2：中型环境（11-50 台服务器）

- 单服务器部署，可能需要增加系统资源
- 考虑使用 HTTPS 协议增强安全性
- 配置日志集中管理
- 定期备份数据库

### 场景 3：大型环境（50+ 台服务器）

- 考虑高可用部署方案
- 可能需要迁移到更强大的数据库系统
- 实施严格的访问控制和监控
- 考虑使用 API 网关进行请求管理

## 🤝 贡献指南

我们欢迎社区贡献！如果您想参与项目开发：

1. Fork 本项目
2. 创建功能分支（`git checkout -b feature/AmazingFeature`）
3. 提交更改（`git commit -m 'Add some AmazingFeature'`）
4. 推送到分支（`git push origin feature/AmazingFeature`）
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](https://gitea.yxliu.cc/gift95/fail2ban-sync/src/branch/main/LICENSE) 文件了解详情。

## 🆘 支持

如果您在使用过程中遇到问题：

1. 检查 [故障排除](#故障排除) 部分
2. 查看 [服务器日志](#查看日志) 获取详细错误信息
3. 查看项目的 [Gitea Issues](https://gitea.yxliu.cc/gift95/fail2ban-sync/issues) 页面
4. 联系项目维护者获取支持

## 📞 联系我们

- **项目主页**：[https://gitea.yxliu.cc/gift95/fail2ban-sync](https://gitea.yxliu.cc/gift95/fail2ban-sync)
- **文档**：[README.md](README.md)
- **问题反馈**：[Gitea Issues](https://gitea.yxliu.cc/gift95/fail2ban-sync/issues)

---

**更新日期：** 2025年11月  
**版本：** v2.0.0  
**Fail2BanSync - 企业级 IP 封禁管理解决方案**
