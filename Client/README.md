# Fail2BanSync 客户端


## � 目录

- [�📋 项目简介](#项目简介)
- [✨ 功能特性](#功能特性)
- [🚀 安装指南](#安装指南)
  - [前提条件](#前提条件)
  - [快速安装](#快速安装)
  - [安装脚本参数](#安装脚本参数)
  - [安装过程](#安装过程)
- [⚙️ 配置说明](#配置说明)
  - [完整配置示例](#完整配置示例)
  - [配置选项详解](#配置选项详解)
- [📊 运行与管理](#运行与管理)
  - [Systemd 服务管理](#systemd-服务管理)
  - [查看日志](#查看日志)
  - [手动运行（测试模式）](#手动运行测试模式)
- [🔍 工作原理](#工作原理)
  - [数据流向](#数据流向)
  - [API 交互](#api-交互)
- [🔒 安全最佳实践](#安全最佳实践)
- [🛠️ 故障排除](#故障排除)
  - [常见问题](#常见问题)
  - [诊断命令](#诊断命令)
- [📈 性能与监控](#性能与监控)
- [🔄 升级指南](#升级指南)
- [📝 常见场景](#常见场景)
- [🤝 贡献指南](#贡献指南)
- [📄 许可证](#许可证)
- [🆘 支持](#支持)

## 📋 项目简介

Fail2BanSync 客户端是一个专业的安全工具，用于在分布式环境中同步和集中管理 IP 封禁策略。它能够自动将本地 Fail2Ban 实例与中央服务器同步封禁和允许的 IP 地址，提供企业级的安全防护解决方案，帮助管理员高效管理多服务器环境下的安全策略。

## ✨ 功能特性

- **自动化同步机制**：通过 systemd 服务实现持续运行，确保 IP 列表实时更新
- **双向数据交换**：
  - 将本地被封禁的 IP 实时同步至中央服务器
  - 从中央服务器获取全局封禁 IP 列表
  - 接收并应用中央允许的 IP 地址策略
- **智能协议检测**：根据服务器端口自动选择 HTTP 或 HTTPS 协议
- **灵活配置选项**：通过简洁的 INI 文件实现全面配置
- **完善的日志系统**：支持日志轮转，便于故障排查和审计
- **安全认证机制**：使用专用令牌确保数据传输安全
- **无缝集成**：与现有 Fail2Ban 安装完美集成，无需修改核心配置

## 🚀 安装指南

### 前提条件

- **操作系统**：Ubuntu 20.04 LTS 或更高版本的 Linux 系统
- **Fail2Ban**：必须已安装并正常运行
- **Python 3**：需要 Python 3.6 或更高版本
- **网络连接**：能够访问 Fail2BanSync 服务器

```bash
# 安装 Fail2Ban（如果尚未安装）
sudo apt update
sudo apt install -y fail2ban
sudo systemctl start fail2ban
sudo systemctl enable fail2ban
```

### 快速安装

使用提供的安装脚本进行快速部署：

```bash
# 1. 克隆项目（或下载相关文件）
cd /tmp
git clone https://gitea.yxliu.cc/gift95/fail2ban-sync.git
cd fail2ban-sync/Client

# 2. 赋予脚本执行权限
chmod +x install_client.sh

# 3. 运行安装脚本（指定服务器地址和令牌）
./install_client.sh server_ip:5000 your_auth_token
```

### 安装脚本参数

```bash
./install_client.sh [server_address:port] [auth_token]
```

- `server_address:port`：Fail2BanSync 服务器地址和端口（默认：192.168.0.1:5000）
- `auth_token`：用于认证的令牌（可选，可后续配置）

### 安装过程

安装脚本会自动执行以下操作：

1. **安装依赖**：Python 3、pip 和 curl
2. **创建安装目录**：`/opt/fail2bansync-client`
3. **部署必要文件**：client.py、get_ips.py 和配置文件
4. **安装 Python 依赖**：requests 库
5. **配置自动运行**：创建并启用 systemd 服务
6. **启动服务**：立即启动客户端服务

## ⚙️ 配置说明

客户端通过 `clientconfig.ini` 文件进行配置，该文件位于 `/opt/fail2bansync-client/` 目录。

### 完整配置示例

```ini
[server]
host = 192.168.0.1     # 服务器IP地址
port = 5000            # 服务器端口（443端口自动使用HTTPS）
protocol = http        # 协议（http或https，可自动检测）

[logging]
log_file = client.log  # 日志文件名
max_bytes = 1048576    # 日志文件最大大小（字节）
backup_count = 3       # 保留的日志文件数量

[fail2ban]
jail = sshd            # Fail2Ban jail名称

[auth]
token = your_token_here # 认证令牌
```

### 配置选项详解

#### [server] 部分
- `host`：Fail2BanSync 服务器的 IP 地址或主机名
- `port`：服务器监听端口（443端口自动使用HTTPS）
- `protocol`：通信协议（http或https，可自动检测）

#### [logging] 部分
- `log_file`：日志文件名（默认：client.log）
- `max_bytes`：单个日志文件的最大大小（默认：1MB）
- `backup_count`：日志轮转时保留的备份文件数量（默认：3）

#### [fail2ban] 部分
- `jail`：要监控和管理的 Fail2Ban jail 名称（默认：sshd）

#### [auth] 部分
- `token`：用于服务器认证的唯一令牌
  - 必须与服务器配置中的令牌匹配
  - 保护此令牌，避免未授权访问

## 📊 运行与管理

### Systemd 服务管理

客户端作为 systemd 服务运行，提供可靠的后台执行和自动重启功能：

```bash
# 启动服务
sudo systemctl start fail2bansync-client.service

# 停止服务
sudo systemctl stop fail2bansync-client.service

# 重启服务
sudo systemctl restart fail2bansync-client.service

# 查看服务状态
sudo systemctl status fail2bansync-client.service

# 设置开机自启
sudo systemctl enable fail2bansync-client.service

# 禁用开机自启
sudo systemctl disable fail2bansync-client.service
```

### 查看日志

#### 系统日志

```bash
# 实时查看服务日志
sudo journalctl -u fail2bansync-client.service -f

# 查看最近100行服务日志
sudo journalctl -u fail2bansync-client.service -n 100
```

#### 应用日志

```bash
# 查看客户端详细日志
cat /opt/fail2bansync-client/client.log

# 实时监控日志
tail -f /opt/fail2bansync-client/client.log
```

### 手动运行（测试模式）

```bash
# 进入安装目录
cd /opt/fail2bansync-client

# 停止服务（避免冲突）
sudo systemctl stop fail2bansync-client.service

# 手动运行客户端进行测试
python3 client.py

# 测试完成后重新启动服务
sudo systemctl start fail2bansync-client.service
```

## 🔍 工作原理

### 数据流向

1. **本地数据采集**：
   - 从 Fail2Ban 获取当前被封禁的 IP 地址列表

2. **数据同步上传**：
   - 将本地被封禁的 IP 发送到中央服务器
   - 包含封禁原因和来源信息

3. **全局数据下载**：
   - 从中央服务器获取全局封禁的 IP 列表
   - 获取需要从本地封禁列表中移除的 IP 列表（允许列表）

4. **本地策略应用**：
   - 将新的全局封禁 IP 添加到本地 Fail2Ban
   - 将允许的 IP 从本地封禁列表中移除
   - 更新本地 IP 数据库状态

### API 交互

客户端与服务器通过以下 API 端点进行通信：

- **POST /add_ips**：上传本地被封禁的 IP 数据
- **GET /get_ips**：获取全局封禁的 IP 列表
- **GET /get_allowed_ips**：获取需要允许的 IP 列表
- **GET /get_known_ips**：获取服务器已知的所有 IP 信息

## 🔒 安全最佳实践

1. **令牌管理**：
   - 为每个客户端使用唯一的认证令牌
   - 定期轮换令牌以增强安全性
   - 发现令牌泄露时立即在服务器和所有客户端更新

2. **网络安全**：
   - 优先使用 HTTPS 协议（端口 443）
   - 配置防火墙规则，限制对服务器端口的访问
   - 仅允许受信任网络的客户端连接

3. **访问控制**：
   - 严格限制对配置文件的访问权限
   - 定期审计日志中的异常活动
   - 持续监控客户端服务状态，确保正常运行

## 🛠️ 故障排除

### 常见问题

#### 1. 服务无法启动

```bash
# 检查服务状态
sudo systemctl status fail2bansync-client.service

# 查看详细错误日志
sudo journalctl -u fail2bansync-client.service -n 200 --no-pager
```

**可能的解决方案：**
- 验证配置文件中的服务器地址和端口设置
- 确认认证令牌有效且与服务器配置匹配
- 确保 Fail2Ban 服务正常运行
- 检查网络连接是否正常

#### 2. IP 同步失败

**症状**：本地封禁的 IP 未同步到服务器，或全局封禁的 IP 未应用到本地。

```bash
# 检查应用日志中的错误信息
cat /opt/fail2bansync-client/client.log | grep -i error
```

**可能的解决方案：**
- 验证网络连接和防火墙设置
- 确认服务器可正常访问
- 检查认证令牌是否正确且未过期
- 确认 Fail2Ban jail 名称配置正确

#### 3. 权限错误

**症状**：客户端无法读取 Fail2Ban 数据或写入配置文件。

**可能的解决方案：**
- 检查文件和目录权限设置
- 确认服务运行用户具有必要权限
- 验证对 Fail2Ban 命令的执行权限

#### 4. 日志中出现 401 错误

**症状**：日志中显示 `HTTP 401 Unauthorized` 错误。

**解决方案：**
- 检查认证令牌是否正确配置
- 确认令牌在服务器上已正确注册
- 验证令牌格式，确保不包含多余的空格或特殊字符

### 诊断命令

```bash
# 检查 Python 版本
python3 --version

# 验证 Fail2Ban 状态
fail2ban-client status
fail2ban-client status sshd

# 测试网络连接到服务器
ping server_ip
telnet server_ip 5000

# 检查 Python 依赖
pip3 list | grep requests

# 手动测试 API 连接
curl -X GET http://server_ip:5000/get_ips -H "Authorization: Bearer your_token"
```

## 📈 性能与监控

### 资源使用情况

- **CPU 使用率**：通常低于 1%，仅在同步周期短暂增加
- **内存使用**：约 30-50MB
- **磁盘空间**：日志文件默认限制为 4MB（1MB + 3 个备份）
- **网络流量**：根据 IP 数量，通常维持在 KB 级别

### 监控建议

1. **服务状态监控**：
   - 使用 systemd 监控服务健康状态
   - 利用已配置的自动重启策略确保服务可用性

2. **日志监控**：
   - 定期检查应用日志中的错误和警告信息
   - 考虑集成日志分析工具进行集中监控和告警

3. **性能监控**：
   - 监控服务启动时间和资源消耗
   - 记录并分析同步操作的执行时间

## 🔄 升级指南

### 客户端升级

```bash
# 1. 停止当前服务
sudo systemctl stop fail2bansync-client.service


# 2. 下载新版本的 client.py
sudo curl -s -o /opt/fail2bansync-client/client.py https://gitea.yxliu.cc/gift95/fail2ban-sync/raw/branch/main/Client/client.py

# 3. 重启服务
sudo systemctl start fail2bansync-client.service

# 4. 验证服务状态
sudo systemctl status fail2bansync-client.service
```

### 配置升级

升级到新版本时，可能需要更新配置文件以支持新增功能。请参考最新的配置示例进行必要的调整，确保所有配置项与新版本兼容。

## 📝 常见场景

### 场景 1：多服务器环境

在企业级多服务器环境中：

1. 在所有服务器节点上安装 Fail2BanSync 客户端
2. 为每个客户端分配唯一的认证令牌
3. 配置指向同一中央服务器的连接参数
4. 通过服务器管理界面监控全局封禁统计和趋势

### 场景 2：特定服务保护

针对特定服务进行针对性保护：

```ini
[fail2ban]
jail = apache-badbots  # 保护 Apache 服务器免受恶意爬虫攻击
```

可根据需要配置不同的 jail 名称，以保护各类网络服务。

### 场景 3：高安全性环境

在对安全性要求较高的生产环境中：

1. 强制使用 HTTPS 协议（配置端口为 443）
2. 部署严格的防火墙规则，限制服务器访问来源
3. 建立令牌定期轮换机制
4. 启用详细日志记录，配置集中式日志审计系统

## 🤝 贡献指南

我们欢迎社区贡献和改进！如果您有意参与项目开发：

1. Fork 本项目仓库
2. 创建功能分支（`git checkout -b feature/your-feature-name`）
3. 提交代码更改（`git commit -m 'Add some amazing feature'`）
4. 推送到分支（`git push origin feature/your-feature-name`）
5. 提交 Pull Request 进行审核

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](https://gitea.yxliu.cc/gift95/fail2ban-sync/raw/branch/main/LICENSE) 文件。

## 🆘 支持

如在使用过程中遇到问题，请按以下顺序寻求支持：

1. 查阅本文档中的 [故障排除](#故障排除) 部分
2. 检查 [应用日志](#查看日志) 获取详细错误信息
3. 确认服务器端日志中是否有相关记录
4. 访问项目的 [Gitea Issues](https://gitea.yxliu.cc/gift95/fail2ban-sync/issues) 页面提交问题
5. 联系项目维护者获取直接支持

---

**更新日期：** 2025年11月  
**版本：** v2.0.0  
**Fail2BanSync - 企业级 IP 封禁管理解决方案**
