# Fail2BanSync – Fail2Ban的IP同步系统


## 📑 目录

- [项目简介](#项目简介)
- [功能特性](#功能特性)
- [系统架构](#系统架构)
  - [服务器组件](#服务器组件)
  - [客户端组件](#客户端组件)
- [快速开始](#快速开始)
  - [前提条件](#前提条件)
  - [服务器安装](#服务器安装)
  - [客户端安装](#客户端安装)
- [AI 协助构建指南](#ai-协助构建指南)
  - [使用 AI 进行项目初始化](#使用-ai-进行项目初始化)
  - [利用 AI 生成配置文件](#利用-ai-生成配置文件)
  - [AI 辅助故障排除](#ai-辅助故障排除)
  - [使用 AI 扩展功能](#使用-ai-扩展功能)
- [安全性与生产环境](#安全性与生产环境)
- [扩展与定制](#扩展与定制)
- [故障排除](#故障排除)
- [升级指南](#升级指南)
- [许可证](#许可证)
- [联系我们](#联系我们)

## 📋 项目简介

Fail2BanSync 是一个强大的中央 IP 同步系统，专门为运行 Fail2Ban 的服务器集群设计。该系统允许在多个服务器之间集中收集、同步和管理被封禁和允许的 IP 地址，从而提高整体安全性和防御能力。

系统架构采用服务器-客户端模式，由带有令牌认证的中央 REST-API 服务器和任意数量的同步客户端组成，确保在分布式环境中的高效协同工作。 灵感来自 [davidus05] (https://github.com/davidus05/fail2ban-sync)

## ✨ 功能特性

- **中央化管理**：基于 Flask 的 REST-API 服务器，提供令牌认证机制
- **智能 IP 同步**：自动收集和分发被封禁/允许的 IP 地址
- **高效数据存储**：使用 SQLite 数据库进行 IP 信息管理
- **灵活配置**：可定制的封禁时间、阻止和释放周期逻辑
- **完善的监控**：详细的日志记录、错误处理和 systemd 集成
- **简单部署**：提供全自动安装脚本（服务器和客户端）
- **安全认证**：基于 Bearer-Token 的客户端身份验证

## 🏗️ 系统架构

### 服务器组件

- **API 服务**：在端口 5000（默认）上提供 REST-API 接口
- **数据存储**：在 SQLite 数据库中存储被封禁/允许的 IP 信息
- **认证机制**：通过 Bearer-Token 验证客户端身份
- **服务管理**：作为 systemd 服务持续运行
- **配置管理**：提供示例配置和自动生成多客户端令牌

### 客户端组件

- **IP 收集**：从本地 Fail2Ban 查询被封禁的 IP 地址
- **数据同步**：将本地封禁 IP 发送到中央服务器
- **策略执行**：从中央获取封禁/允许列表并与本地 Fail2Ban 同步
- **定时任务**：作为 systemd 服务每分钟运行一次

## 🚀 快速开始

### 前提条件

- **操作系统**：Ubuntu Server 20.04 LTS 或更高版本
- **Python 3**：需要 Python 3.6 或更高版本
- **权限**：安装过程需要 root 权限
- **Fail2Ban**：客户端服务器需已安装并配置 Fail2Ban

### 服务器安装

1. **准备安装文件**：
   ```bash
   # 克隆项目
   git clone https://gitea.yxliu.cc/gift95/fail2ban-sync.git
   cd fail2ban-sync/Server
   ```

2. **执行安装脚本**：
   ```bash
   chmod +x install_server.sh
   ./install_server.sh
   ```

3. **配置服务器**：
   根据需要编辑 `/opt/fail2bansync/serverconfig.ini` 文件，调整令牌和其他配置项。

4. **验证安装**：
   ```bash
   sudo systemctl status fail2bansync-server
   ```

5. **查看日志**：
   服务器日志位于：`/opt/fail2bansync/server.log`

### 客户端安装

1. **准备安装文件**：
   ```bash
   # 在客户端服务器上克隆项目
   git clone https://gitea.yxliu.cc/gift95/fail2ban-sync.git
   cd fail2ban-sync/Client
   ```

2. **执行安装脚本**：
   ```bash
   chmod +x install_client.sh
   ./install_client.sh
   ```

3. **配置客户端**：
   编辑 `/opt/fail2bansync-client/clientconfig.ini` 文件，输入服务器 IP 地址和认证令牌。

4. **验证安装**：
   ```bash
   # 检查服务状态
   sudo systemctl status fail2bansync-client
   # 查看日志
   tail -f /opt/fail2bansync-client/client.log
   ```

## 🤖 AI 协助构建指南

Fail2BanSync 项目支持通过 AI 工具进行辅助构建和配置，大大简化了项目部署和维护过程。

### 使用 AI 进行项目初始化

利用 AI 工具可以快速启动和配置 Fail2BanSync 项目：

1. **项目结构生成**：
   - 向 AI 工具提供服务器和客户端的基本需求
   - 生成初始项目目录结构和基础文件
   - 根据具体环境自动调整安装脚本

2. **自动化配置**：
   ```bash
   # AI 生成的快速部署命令示例
   curl -s https://example.com/ai-scripts/init-fail2bansync.sh | bash
   ```

### 利用 AI 生成配置文件

AI 可以帮助创建和优化配置文件：

1. **服务器配置生成**：
   - 生成适合不同规模部署的 `serverconfig.ini`
   - 根据安全需求调整封禁策略参数
   - 自动生成和管理客户端认证令牌

2. **客户端配置优化**：
   - 创建符合服务器规范的客户端配置
   - 根据网络环境调整连接参数
   - 配置最佳的日志级别和监控选项

### AI 辅助故障排除

AI 工具可以帮助快速诊断和解决问题：

1. **错误分析**：
   - 向 AI 提供错误日志，获取诊断建议
   - 自动检测常见配置错误和网络问题
   - 生成修复步骤和最佳实践

2. **命令生成器**：
   ```bash
   # AI 生成的诊断命令示例
   AI生成的诊断命令集合，用于检查服务状态、日志分析和网络连接
   ```

### 使用 AI 扩展功能

利用 AI 工具可以轻松扩展 Fail2BanSync 功能：

1. **新特性开发**：
   - 生成代码模板用于添加新的 API 端点
   - 实现自定义的封禁策略和规则引擎
   - 创建管理界面的前端组件

2. **性能优化**：
   - 分析并优化数据库查询性能
   - 改进同步算法减少网络流量
   - 生成资源使用分析和优化建议

## 🔒 安全性与生产环境

### 最佳安全实践

- **反向代理**：始终在 NGINX/Apache 后面运行服务器 API，并配置 HTTPS 加密
- **令牌管理**：安全保管认证令牌，定期轮换并删除不再使用的令牌
- **数据保护**：定期备份数据库文件 (`/opt/fail2bansync/ip_management.db`)
- **访问控制**：限制服务器端口只接受来自受信任 IP 的连接
- **日志监控**：设置日志监控系统，检测异常访问模式

### 生产环境建议

```bash
# 推荐的防火墙配置
sudo ufw allow from 192.168.1.0/24 to any port 5000 proto tcp

# 为 API 设置 HTTPS (使用 NGINX)
sudo apt install nginx
# 配置 SSL 证书和反向代理
```

## 🛠️ 扩展与定制

### 功能扩展

- **客户端管理**：通过服务器配置轻松添加或移除客户端
  ```bash
  # 添加新客户端令牌到服务器配置
  sudo nano /opt/fail2bansync/serverconfig.ini
  # 在 [api_tokens] 部分添加新条目
  ```

- **自定义封禁策略**：调整服务器配置中的封禁参数
  ```ini
  [DEFAULT]
  bantime = 15m          # 调整默认封禁时间
  bantime.increment = true
  bantime.factor = 2    # 调整增量因子
  ```

### 监控集成

- 可以与 Prometheus、Grafana 等监控工具集成
- 通过 API 端点获取系统状态和统计信息

## 🚧 故障排除

### 常见问题与解决方案

1. **服务无法启动**
   - 检查日志：`/opt/fail2bansync/server.log`
   - 验证端口可用性：`netstat -tulpn | grep 5000`
   - 检查依赖安装：`pip3 list | grep flask`

2. **客户端连接失败**
   - 检查服务器状态：`sudo systemctl status fail2bansync-server`
   - 验证网络连接：`ping 服务器IP`
   - 确认令牌正确：检查客户端配置中的令牌

3. **认证错误**
   - 检查 HTTP 401 错误，验证令牌匹配
   - 确认服务器配置中的令牌列表包含客户端令牌

4. **IP 同步问题**
   - 检查客户端日志：`/opt/fail2bansync-client/client.log`
   - 验证 Fail2Ban 服务运行正常：`sudo systemctl status fail2ban`

### 诊断命令

```bash
# 检查服务器状态
sudo systemctl status fail2bansync-server

# 检查客户端状态
sudo systemctl status fail2bansync-client

# 查看服务器日志
tail -n 50 /opt/fail2bansync/server.log

# 查看客户端日志
tail -n 50 /opt/fail2bansync-client/client.log

# 测试 API 连接
curl -X GET http://服务器IP:5000/get_ips -H "Authorization: Bearer 客户端令牌"

# 检查数据库完整性
sudo sqlite3 /opt/fail2bansync/ip_management.db "PRAGMA integrity_check;"
```

## 🔄 升级指南

### 服务器升级

```bash
# 1. 停止当前服务
sudo systemctl stop fail2bansync-server

# 2. 备份数据库
cp /opt/fail2bansync/ip_management.db /opt/fail2bansync/ip_management.db.backup

# 3. 替换服务器文件
cp server.py /opt/fail2bansync/

# 4. 重启服务
sudo systemctl start fail2bansync-server

# 5. 验证升级
sudo systemctl status fail2bansync-server
```

### 客户端升级

```bash
# 1. 停止当前服务
sudo systemctl stop fail2bansync-client

# 2. 替换客户端文件
cp client.py /opt/fail2bansync-client/

# 3. 重启服务
sudo systemctl start fail2bansync-client

# 4. 验证升级
sudo systemctl status fail2bansync-client
```

### 配置升级

- 新客户端令牌可以随时添加到服务器配置中，无需重启服务
- 配置文件更新后需要重启相应服务以应用更改

## 📄 许可证

本项目采用 MIT 许可证。详情请参阅 [LICENSE](https://gitea.yxliu.cc/gift95/fail2ban-sync/src/branch/main/LICENSE) 文件。

## 📞 联系我们

如有疑问、建议或需要帮助，请联系项目维护者。

- **项目主页**：[https://gitea.yxliu.cc/gift95/fail2ban-sync](https://gitea.yxliu.cc/gift95/fail2ban-sync)
- **问题反馈**：[https://gitea.yxliu.cc/gift95/fail2ban-sync/issues](https://gitea.yxliu.cc/gift95/fail2ban-sync/issues)

---

**更新日期**：2025年11月  
**版本**：v2.0.0  

**Fail2BanSync – 现代化多服务器 IP 封禁协同解决方案**
