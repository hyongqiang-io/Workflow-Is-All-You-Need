# 工作流框架部署指南

## 概述

本目录包含了工作流框架应用的完整部署配置和脚本，支持Docker容器化部署和原生服务器部署两种方式。

## 目录结构

```
deployment/
├── docker/                 # Docker相关配置
│   ├── Dockerfile.backend   # 后端Docker镜像
│   ├── Dockerfile.frontend  # 前端Docker镜像
│   └── docker-compose.yml   # Docker Compose配置
├── nginx/                   # Nginx配置文件
│   ├── default.conf         # Docker容器内Nginx配置
│   └── workflow.conf        # 服务器直接部署Nginx配置
├── scripts/                 # 部署和管理脚本
│   ├── deploy.sh           # 自动化部署脚本
│   ├── start.sh            # 应用启动脚本
│   └── backup.sh           # 数据库备份脚本
├── systemd/                # Systemd服务配置
│   └── workflow-backend.service
└── README.md               # 本文件
```

## 快速开始

### 方式一：Docker部署（推荐）

1. **准备环境**
   ```bash
   # 安装Docker和Docker Compose
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER
   
   # 安装Docker Compose
   sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

2. **配置环境变量**
   ```bash
   cp .env.example .env
   # 编辑.env文件，修改必要的配置
   nano .env
   ```

3. **一键部署**
   ```bash
   sudo ./deployment/scripts/deploy.sh
   ```

4. **访问应用**
   - 前端: http://your-server-ip
   - API文档: http://your-server-ip/docs

### 方式二：原生部署

1. **运行部署脚本**
   ```bash
   sudo ./deployment/scripts/deploy.sh
   # 选择原生部署方式
   ```

2. **手动配置SSL（可选）**
   ```bash
   # 安装Certbot
   sudo apt install certbot python3-certbot-nginx
   
   # 获取SSL证书
   sudo certbot --nginx -d your-domain.com
   ```

## 详细配置

### 环境变量配置

主要配置项说明：

- `DOMAIN`: 你的域名
- `SECRET_KEY`: JWT密钥，请生成强密钥
- `OPENAI_API_KEY`: OpenAI API密钥
- `DATABASE_URL`: 数据库连接URL

生成强密钥：
```bash
openssl rand -hex 32
```

### 数据库配置

默认使用SQLite数据库，生产环境建议使用PostgreSQL：

```env
# PostgreSQL配置
DATABASE_URL=postgresql://username:password@localhost:5432/workflow_db
```

### 反向代理配置

#### Docker部署
使用内置的Nginx配置，自动处理前后端路由。

#### 原生部署
需要配置系统Nginx：

```bash
# 复制配置文件
sudo cp deployment/nginx/workflow.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/workflow.conf /etc/nginx/sites-enabled/

# 重启Nginx
sudo systemctl reload nginx
```

## 管理命令

### 应用管理

```bash
# 启动应用
./deployment/scripts/start.sh start

# 停止应用
./deployment/scripts/start.sh stop

# 重启应用
./deployment/scripts/start.sh restart

# 查看状态
./deployment/scripts/start.sh status

# 查看日志
./deployment/scripts/start.sh logs
```

### 数据库备份

```bash
# 执行备份
./deployment/scripts/backup.sh backup

# 列出备份
./deployment/scripts/backup.sh list

# 恢复备份
./deployment/scripts/backup.sh restore workflow_20240101_120000.db

# 验证备份
./deployment/scripts/backup.sh verify workflow_20240101_120000.db

# 清理过期备份
./deployment/scripts/backup.sh cleanup
```

## 监控和日志

### Docker部署
```bash
# 查看容器状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 查看资源使用
docker stats
```

### 原生部署
```bash
# 查看后端服务状态
sudo systemctl status workflow-backend

# 查看后端日志
sudo journalctl -u workflow-backend -f

# 查看Nginx日志
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## 性能优化

### 数据库优化
- 定期执行VACUUM清理
- 创建适当的索引
- 监控查询性能

### 缓存优化
- 启用Nginx缓存
- 配置Redis缓存（可选）
- 优化静态资源缓存

### 系统优化
```bash
# 调整文件描述符限制
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# 优化内核参数
echo "net.core.somaxconn = 65536" >> /etc/sysctl.conf
sysctl -p
```

## 安全配置

### 防火墙设置
```bash
# 启用UFW防火墙
sudo ufw enable

# 允许必要端口
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
```

### SSL/TLS配置
- 使用Let's Encrypt免费证书
- 配置HSTS头
- 启用HTTP/2
- 定期更新证书

### 访问控制
- 配置IP白名单（如需要）
- 设置API速率限制
- 启用内容安全策略(CSP)

## 故障排除

### 常见问题

1. **服务无法启动**
   - 检查端口是否被占用
   - 查看服务日志
   - 验证配置文件语法

2. **数据库连接失败**
   - 检查数据库路径
   - 验证权限设置
   - 确认数据库文件存在

3. **前端无法访问后端API**
   - 检查CORS配置
   - 验证Nginx代理设置
   - 确认防火墙规则

### 日志位置

- Docker: `docker-compose logs`
- 后端: `/var/log/workflow-backend/`
- Nginx: `/var/log/nginx/`
- 系统: `journalctl -u workflow-backend`

## 升级和维护

### 应用升级
```bash
# 停止服务
./deployment/scripts/start.sh stop

# 备份数据
./deployment/scripts/backup.sh backup

# 更新代码
git pull origin main

# 重新部署
./deployment/scripts/deploy.sh

# 启动服务
./deployment/scripts/start.sh start
```

### 定期维护
- 定期备份数据库
- 清理日志文件
- 更新系统包
- 监控磁盘空间
- 检查SSL证书有效期

## 扩展配置

### 负载均衡
如需要处理高并发，可以配置多实例负载均衡：

```yaml
# docker-compose.yml 示例
services:
  backend1:
    build: ...
    ports:
      - "8001:8000"
  
  backend2:
    build: ...
    ports:
      - "8002:8000"
  
  nginx:
    # 配置upstream负载均衡
```

### 集群部署
- 使用Docker Swarm或Kubernetes
- 配置共享存储
- 设置服务发现
- 实现高可用架构

## 技术支持

如遇到问题，请检查：
1. 系统要求是否满足
2. 配置文件是否正确
3. 日志文件中的错误信息
4. 网络连接是否正常

更多详细信息请参考项目文档或联系技术支持。