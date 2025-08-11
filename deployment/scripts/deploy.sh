#!/bin/bash

# 工作流应用部署脚本
# Workflow Application Deployment Script

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为root用户
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "此脚本需要root权限运行"
        exit 1
    fi
}

# 检查系统要求
check_requirements() {
    log_info "检查系统要求..."
    
    # 检查操作系统
    if [[ ! -f /etc/os-release ]]; then
        log_error "无法检测操作系统"
        exit 1
    fi
    
    # 检查Docker
    if ! command -v docker &> /dev/null; then
        log_warn "Docker未安装，开始安装..."
        install_docker
    fi
    
    # 检查Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_warn "Docker Compose未安装，开始安装..."
        install_docker_compose
    fi
    
    # 检查Nginx (如果选择非Docker部署)
    if [[ "$DEPLOYMENT_TYPE" == "native" ]] && ! command -v nginx &> /dev/null; then
        log_warn "Nginx未安装，开始安装..."
        install_nginx
    fi
}

# 安装Docker
install_docker() {
    log_info "安装Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    systemctl start docker
    systemctl enable docker
    rm get-docker.sh
    log_info "Docker安装完成"
}

# 安装Docker Compose
install_docker_compose() {
    log_info "安装Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    log_info "Docker Compose安装完成"
}

# 安装Nginx
install_nginx() {
    log_info "安装Nginx..."
    if command -v apt-get &> /dev/null; then
        apt-get update
        apt-get install -y nginx
    elif command -v yum &> /dev/null; then
        yum install -y nginx
    else
        log_error "不支持的包管理器"
        exit 1
    fi
    systemctl start nginx
    systemctl enable nginx
    log_info "Nginx安装完成"
}

# 设置环境变量
setup_environment() {
    log_info "设置环境变量..."
    
    
    # 导入环境变量
    if [[ -f .env ]]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi
}

# Docker部署
deploy_docker() {
    log_info "使用Docker部署..."
    
    # 构建和启动服务
    cd deployment/docker
    docker-compose down --remove-orphans
    docker-compose build --no-cache
    docker-compose up -d
    
    # 等待服务启动
    log_info "等待服务启动..."
    sleep 30
    
    # 检查服务状态
    if docker-compose ps | grep -q "Up"; then
        log_info "Docker部署成功!"
        log_info "前端地址: http://localhost"
        log_info "后端API: http://localhost/api"
        log_info "API文档: http://localhost/docs"
    else
        log_error "Docker部署失败，请检查日志"
        docker-compose logs
        exit 1
    fi
}

# 原生部署
deploy_native() {
    log_info "使用原生方式部署..."
    
    # 部署后端
    deploy_backend_native
    
    # 部署前端
    deploy_frontend_native
    
    # 配置Nginx
    configure_nginx
    
    log_info "原生部署完成!"
}

# 部署后端 (原生)
deploy_backend_native() {
    log_info "部署后端..."
    
    # 创建应用目录
    mkdir -p /opt/workflow-app
    cp -r ../../* /opt/workflow-app/
    cd /opt/workflow-app
    
    # 创建Python虚拟环境
    python3 -m venv venv
    source venv/bin/activate
    
    # 安装依赖
    pip install -r requirements.txt
    
    # 初始化数据库
    python -c "from backend.scripts.init_database import main; main()"
    
    # 创建systemd服务
    cp deployment/systemd/workflow-backend.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable workflow-backend
    systemctl start workflow-backend
}

# 部署前端 (原生)
deploy_frontend_native() {
    log_info "部署前端..."
    
    # 检查Node.js
    if ! command -v node &> /dev/null; then
        log_info "安装Node.js..."
        curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
        apt-get install -y nodejs
    fi
    
    # 构建前端
    cd /opt/workflow-app/frontend
    npm install
    npm run build
    
    # 部署到nginx目录
    mkdir -p /var/www/workflow-frontend
    cp -r build/* /var/www/workflow-frontend/
    chown -R www-data:www-data /var/www/workflow-frontend
}

# 配置Nginx
configure_nginx() {
    log_info "配置Nginx..."
    
    # 复制配置文件
    cp /opt/workflow-app/deployment/nginx/workflow.conf /etc/nginx/sites-available/
    
    # 启用站点
    ln -sf /etc/nginx/sites-available/workflow.conf /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    # 测试配置
    nginx -t
    
    # 重启Nginx
    systemctl reload nginx
}

# 设置SSL证书
setup_ssl() {
    log_info "设置SSL证书..."
    
    if [[ -z "$DOMAIN" ]]; then
        log_warn "未设置域名，跳过SSL配置"
        return
    fi
    
    # 安装Certbot
    if ! command -v certbot &> /dev/null; then
        if command -v apt-get &> /dev/null; then
            apt-get update
            apt-get install -y certbot python3-certbot-nginx
        elif command -v yum &> /dev/null; then
            yum install -y certbot python3-certbot-nginx
        fi
    fi
    
    # 获取SSL证书
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "${EMAIL:-admin@${DOMAIN}}"
    
    # 设置自动续期
    echo "0 12 * * * /usr/bin/certbot renew --quiet" | crontab -
}

# 创建备份任务
setup_backup() {
    log_info "设置备份任务..."
    
    mkdir -p /opt/backups
    cp deployment/scripts/backup.sh /opt/backups/
    chmod +x /opt/backups/backup.sh
    
    # 添加到crontab
    echo "0 2 * * * /opt/backups/backup.sh" | crontab -
}

# 显示状态
show_status() {
    log_info "系统状态:"
    
    if [[ "$DEPLOYMENT_TYPE" == "docker" ]]; then
        docker-compose -f deployment/docker/docker-compose.yml ps
    else
        systemctl status workflow-backend --no-pager -l
        systemctl status nginx --no-pager -l
    fi
}

# 主函数
main() {
    log_info "开始部署工作流应用..."
    
    # 获取部署类型
    echo "请选择部署方式:"
    echo "1) Docker (推荐)"
    echo "2) 原生部署"
    read -p "请选择 (1-2): " -n 1 -r
    echo
    
    case $REPLY in
        1)
            DEPLOYMENT_TYPE="docker"
            ;;
        2)
            DEPLOYMENT_TYPE="native"
            ;;
        *)
            log_error "无效选择"
            exit 1
            ;;
    esac
    
    # 检查系统要求
    check_requirements
    
    # 设置环境变量
    setup_environment
    
    # 执行部署
    if [[ "$DEPLOYMENT_TYPE" == "docker" ]]; then
        deploy_docker
    else
        deploy_native
        setup_ssl
    fi
    
    # 设置备份
    setup_backup
    
    # 显示状态
    show_status
    
    log_info "部署完成!"
    log_info "请访问您的应用："
    if [[ -n "$DOMAIN" ]]; then
        log_info "https://$DOMAIN"
    else
        log_info "http://localhost"
    fi
}

# 检查参数
if [[ $# -eq 0 ]]; then
    check_root
    main
else
    case $1 in
        --help|-h)
            echo "工作流应用部署脚本"
            echo "用法: $0 [选项]"
            echo "选项:"
            echo "  --help, -h     显示帮助信息"
            echo "  --status       显示服务状态"
            echo "  --restart      重启服务"
            echo "  --logs         查看日志"
            ;;
        --status)
            show_status
            ;;
        --restart)
            log_info "重启服务..."
            if [[ -f deployment/docker/docker-compose.yml ]]; then
                cd deployment/docker
                docker-compose restart
            else
                systemctl restart workflow-backend nginx
            fi
            ;;
        --logs)
            if [[ -f deployment/docker/docker-compose.yml ]]; then
                cd deployment/docker
                docker-compose logs -f
            else
                journalctl -u workflow-backend -f
            fi
            ;;
        *)
            log_error "未知参数: $1"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
fi