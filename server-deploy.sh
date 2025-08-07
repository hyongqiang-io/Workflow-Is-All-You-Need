#!/bin/bash

# 服务器部署脚本 - 在服务器上运行此脚本
# 使用方法: ./server-deploy.sh [域名] [邮箱]

set -e

# 颜色输出函数
print_info() {
    echo -e "\033[1;34m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[1;32m[SUCCESS]\033[0m $1"
}

print_error() {
    echo -e "\033[1;31m[ERROR]\033[0m $1"
}

print_warning() {
    echo -e "\033[1;33m[WARNING]\033[0m $1"
}

# 配置变量
DOMAIN=${1:-"autolabflow.online"}
EMAIL=${2:-"admin@autolabflow.online"}
PROJECT_NAME="workflow"
PROJECT_DIR="/opt/${PROJECT_NAME}"
DOCKER_REGISTRY=${DOCKER_REGISTRY:-"your-registry.com"}

print_info "开始服务器部署"
print_info "域名: $DOMAIN"
print_info "邮箱: $EMAIL"
print_info "项目目录: $PROJECT_DIR"

# 检查是否为root用户
check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "请使用 root 用户或 sudo 运行此脚本"
        exit 1
    fi
}

# 安装系统依赖
install_dependencies() {
    print_info "安装系统依赖..."
    
    # 更新系统
    apt-get update -y
    apt-get upgrade -y
    
    # 安装基础工具
    apt-get install -y \
        curl \
        wget \
        git \
        unzip \
        software-properties-common \
        apt-transport-https \
        ca-certificates \
        gnupg \
        lsb-release \
        nginx \
        certbot \
        python3-certbot-nginx
    
    print_success "系统依赖安装完成"
}

# 安装 Docker
install_docker() {
    print_info "安装 Docker..."
    
    # 检查是否已安装
    if command -v docker &> /dev/null; then
        print_warning "Docker 已安装，跳过安装步骤"
        return
    fi
    
    # 添加 Docker 官方 GPG key
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    
    # 添加 Docker 仓库
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # 安装 Docker
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    
    # 启动 Docker
    systemctl start docker
    systemctl enable docker
    
    # 添加当前用户到 docker 组
    usermod -aG docker $SUDO_USER 2>/dev/null || true
    
    print_success "Docker 安装完成"
}

# 安装 Docker Compose
install_docker_compose() {
    print_info "安装 Docker Compose..."
    
    # 检查是否已安装
    if command -v docker-compose &> /dev/null; then
        print_warning "Docker Compose 已安装，跳过安装步骤"
        return
    fi
    
    # 下载最新版本的 Docker Compose
    DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
    curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    
    # 添加执行权限
    chmod +x /usr/local/bin/docker-compose
    
    # 创建软链接
    ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
    
    print_success "Docker Compose 安装完成"
}

# 配置防火墙
configure_firewall() {
    print_info "配置防火墙..."
    
    # 安装 ufw（如果没有）
    apt-get install -y ufw
    
    # 重置防火墙规则
    ufw --force reset
    
    # 默认策略
    ufw default deny incoming
    ufw default allow outgoing
    
    # 允许必要的端口
    ufw allow ssh
    ufw allow 80/tcp    # HTTP
    ufw allow 443/tcp   # HTTPS
    
    # 启用防火墙
    ufw --force enable
    
    print_success "防火墙配置完成"
}

# 创建项目目录
setup_project_directory() {
    print_info "创建项目目录..."
    
    # 创建项目目录
    mkdir -p $PROJECT_DIR
    mkdir -p $PROJECT_DIR/logs
    mkdir -p $PROJECT_DIR/ssl
    mkdir -p $PROJECT_DIR/backups
    
    # 设置权限
    chown -R $SUDO_USER:$SUDO_USER $PROJECT_DIR 2>/dev/null || true
    
    print_success "项目目录创建完成"
}

# 配置 SSL 证书
setup_ssl() {
    print_info "配置 SSL 证书..."
    
    # 停止 nginx（如果正在运行）
    systemctl stop nginx 2>/dev/null || true
    
    # 获取 SSL 证书
    certbot certonly --standalone \
        --non-interactive \
        --agree-tos \
        --email $EMAIL \
        -d $DOMAIN \
        -d www.$DOMAIN
    
    # 创建证书软链接
    ln -sf /etc/letsencrypt/live/$DOMAIN/fullchain.pem $PROJECT_DIR/ssl/cert.pem
    ln -sf /etc/letsencrypt/live/$DOMAIN/privkey.pem $PROJECT_DIR/ssl/private.key
    
    # 设置证书自动续期
    echo "0 12 * * * /usr/bin/certbot renew --quiet && systemctl reload nginx" | crontab -
    
    print_success "SSL 证书配置完成"
}

# 创建 nginx 配置
create_nginx_config() {
    print_info "创建 Nginx 配置..."
    
    cat > /etc/nginx/sites-available/$PROJECT_NAME << EOF
# 重定向 www 到主域名
server {
    listen 80;
    listen 443 ssl http2;
    server_name www.$DOMAIN;
    
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    
    return 301 https://$DOMAIN\$request_uri;
}

# HTTP 重定向到 HTTPS
server {
    listen 80;
    server_name $DOMAIN;
    
    return 301 https://\$server_name\$request_uri;
}

# 主服务器配置
server {
    listen 443 ssl http2;
    server_name $DOMAIN;
    
    # SSL 配置
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_session_timeout 1d;
    ssl_session_cache shared:MozTLS:10m;
    ssl_session_tickets off;
    
    # SSL 安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;
    
    # 安全头
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    
    # 前端静态文件
    location / {
        proxy_pass http://127.0.0.1:80;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # API 路由
    location /api/ {
        proxy_pass http://127.0.0.1:8001/api/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # 超时配置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # 健康检查
    location /health {
        proxy_pass http://127.0.0.1:8001/health;
        access_log off;
    }
    
    # 日志配置
    access_log /var/log/nginx/${PROJECT_NAME}_access.log;
    error_log /var/log/nginx/${PROJECT_NAME}_error.log;
}
EOF
    
    # 启用站点
    ln -sf /etc/nginx/sites-available/$PROJECT_NAME /etc/nginx/sites-enabled/
    
    # 移除默认站点
    rm -f /etc/nginx/sites-enabled/default
    
    # 测试配置
    nginx -t
    
    # 启动 nginx
    systemctl enable nginx
    systemctl start nginx
    
    print_success "Nginx 配置完成"
}

# 创建系统服务
create_systemd_service() {
    print_info "创建系统服务..."
    
    cat > /etc/systemd/system/${PROJECT_NAME}.service << EOF
[Unit]
Description=Workflow Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/local/bin/docker-compose -f docker-compose.prod.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.prod.yml down
User=root
Group=root

[Install]
WantedBy=multi-user.target
EOF
    
    # 重新加载 systemd
    systemctl daemon-reload
    systemctl enable ${PROJECT_NAME}.service
    
    print_success "系统服务创建完成"
}

# 创建备份脚本
create_backup_script() {
    print_info "创建备份脚本..."
    
    cat > $PROJECT_DIR/backup.sh << 'EOF'
#!/bin/bash

# 工作流应用备份脚本
PROJECT_DIR="/opt/workflow"
BACKUP_DIR="$PROJECT_DIR/backups"
DATE=$(date +%Y%m%d-%H%M%S)

# 创建备份目录
mkdir -p $BACKUP_DIR

# 备份数据库
docker-compose -f $PROJECT_DIR/docker-compose.prod.yml exec -T postgres \
    pg_dump -U postgres workflow_db | gzip > $BACKUP_DIR/database_$DATE.sql.gz

# 备份应用数据
tar -czf $BACKUP_DIR/app_data_$DATE.tar.gz -C $PROJECT_DIR logs ssl

# 清理旧备份（保留7天）
find $BACKUP_DIR -name "*.gz" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "备份完成: $DATE"
EOF
    
    chmod +x $PROJECT_DIR/backup.sh
    
    # 添加到 crontab（每天凌晨2点备份）
    echo "0 2 * * * $PROJECT_DIR/backup.sh >> $PROJECT_DIR/logs/backup.log 2>&1" | crontab -
    
    print_success "备份脚本创建完成"
}

# 创建监控脚本
create_monitoring_script() {
    print_info "创建监控脚本..."
    
    cat > $PROJECT_DIR/monitor.sh << 'EOF'
#!/bin/bash

# 服务监控脚本
PROJECT_DIR="/opt/workflow"
LOG_FILE="$PROJECT_DIR/logs/monitor.log"

# 日志函数
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> $LOG_FILE
}

# 检查服务状态
check_service() {
    if ! docker-compose -f $PROJECT_DIR/docker-compose.prod.yml ps | grep -q "Up"; then
        log_message "服务异常，尝试重启..."
        docker-compose -f $PROJECT_DIR/docker-compose.prod.yml restart
        sleep 30
        
        if docker-compose -f $PROJECT_DIR/docker-compose.prod.yml ps | grep -q "Up"; then
            log_message "服务重启成功"
        else
            log_message "服务重启失败，需要人工干预"
        fi
    fi
}

# 检查磁盘空间
check_disk_space() {
    USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ $USAGE -gt 80 ]; then
        log_message "警告：磁盘使用率已达 ${USAGE}%"
    fi
}

# 清理日志
cleanup_logs() {
    find $PROJECT_DIR/logs -name "*.log" -mtime +30 -delete
    docker system prune -f --volumes
}

# 执行检查
check_service
check_disk_space

# 每周一执行清理
if [ $(date +%u) -eq 1 ]; then
    cleanup_logs
    log_message "执行了日志清理"
fi
EOF
    
    chmod +x $PROJECT_DIR/monitor.sh
    
    # 添加到 crontab（每5分钟检查一次）
    echo "*/5 * * * * $PROJECT_DIR/monitor.sh" | crontab -l | { cat; echo "*/5 * * * * $PROJECT_DIR/monitor.sh"; } | crontab -
    
    print_success "监控脚本创建完成"
}

# 显示部署信息
show_deployment_info() {
    print_success "=== 服务器部署完成 ==="
    print_info "域名: https://$DOMAIN"
    print_info "项目目录: $PROJECT_DIR"
    print_info ""
    print_info "管理命令："
    print_info "  启动服务: systemctl start $PROJECT_NAME"
    print_info "  停止服务: systemctl stop $PROJECT_NAME"
    print_info "  查看状态: systemctl status $PROJECT_NAME"
    print_info "  查看日志: docker-compose -f $PROJECT_DIR/docker-compose.prod.yml logs -f"
    print_info ""
    print_info "文件位置："
    print_info "  应用日志: $PROJECT_DIR/logs/"
    print_info "  备份文件: $PROJECT_DIR/backups/"
    print_info "  SSL证书: $PROJECT_DIR/ssl/"
    print_info ""
    print_info "自动化任务："
    print_info "  每天2点自动备份"
    print_info "  每5分钟服务监控"
    print_info "  SSL证书自动续期"
}

# 主函数
main() {
    check_root
    install_dependencies
    install_docker
    install_docker_compose
    configure_firewall
    setup_project_directory
    setup_ssl
    create_nginx_config
    create_systemd_service
    create_backup_script
    create_monitoring_script
    show_deployment_info
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi