#!/bin/bash
# ==============================================
# 工作流系统统一部署脚本
# 支持开发和生产环境的启动、部署和管理
# ==============================================

set -e

# 配置变量
PROJECT_DIR="/home/ubuntu/Workflow-Is-All-You-Need"
FRONTEND_DIR="$PROJECT_DIR/frontend"
DEPLOY_DIR="/var/www/html"
LOG_DIR="/var/log/workflow"
BACKUP_DIR="/var/backups/workflow"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 显示使用说明
show_usage() {
    echo -e "${BLUE}=== 工作流系统管理脚本 ===${NC}"
    echo -e "${BLUE}用法: $0 {command} [environment]${NC}"
    echo ""
    echo -e "${YELLOW}启动命令:${NC}"
    echo "  start-dev        - 启动开发环境 (后端8000 + 前端3000)"
    echo "  start-prod       - 启动生产环境 (systemd服务)"
    echo ""
    echo -e "${YELLOW}部署命令:${NC}"
    echo "  deploy           - 开发环境 -> 生产环境完整部署"
    echo "  deploy-frontend  - 仅部署前端"
    echo "  deploy-backend   - 仅部署后端"
    echo ""
    echo -e "${YELLOW}管理命令:${NC}"
    echo "  status           - 查看服务状态"
    echo "  logs             - 查看日志"
    echo "  stop             - 停止所有服务"
    echo "  restart          - 重启生产服务"
    echo "  health           - 健康检查"
}

# 检查环境
check_environment() {
    echo -e "${YELLOW}🔍 检查环境...${NC}"
    
    if [[ ! -d "$PROJECT_DIR" ]]; then
        echo -e "${RED}❌ 项目目录不存在: $PROJECT_DIR${NC}"
        exit 1
    fi
    
    cd "$PROJECT_DIR"
    
    if [[ ! -f ".env.production" ]] || [[ ! -f ".env.development" ]]; then
        echo -e "${RED}❌ 环境配置文件缺失${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ 环境检查通过${NC}"
}

# 启动开发环境
start_development() {
    echo -e "${BLUE}🛠️  启动开发环境...${NC}"
    
    cd "$PROJECT_DIR"
    
    # 检查端口占用
    if netstat -tlnp | grep -q ":8000 "; then
        echo -e "${RED}❌ 端口8000已被占用${NC}"
        echo "请停止占用该端口的进程或使用其他端口"
        exit 1
    fi
    
    # 加载开发环境变量
    export $(cat .env.development | grep -v '^#' | xargs)
    
    echo -e "${YELLOW}📡 启动后端服务 (端口8000)...${NC}"
    echo "使用 Ctrl+C 停止服务"
    echo "后端日志将显示在此终端"
    echo -e "${GREEN}访问 API 文档: http://localhost:8000/docs${NC}"
    echo ""
    
    # 启动后端
    python3 main.py &
    BACKEND_PID=$!
    
    # 等待后端启动
    sleep 3
    
    # 检查后端是否启动成功
    if curl -f -s http://localhost:8000/health > /dev/null; then
        echo -e "${GREEN}✅ 后端启动成功${NC}"
    else
        echo -e "${RED}❌ 后端启动失败${NC}"
        kill $BACKEND_PID 2>/dev/null || true
        exit 1
    fi
    
    echo -e "${YELLOW}🌐 启动前端开发服务器...${NC}"
    echo -e "${GREEN}前端地址: http://localhost:3000${NC}"
    echo "使用 Ctrl+C 停止所有服务"
    
    # 启动前端
    cd "$FRONTEND_DIR"
    npm start &
    FRONTEND_PID=$!
    
    # 等待用户中断
    trap "echo -e '\n${YELLOW}🛑 停止开发服务...${NC}'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true; exit 0" INT
    
    echo -e "${GREEN}🎯 开发环境运行中...${NC}"
    echo "按 Ctrl+C 停止服务"
    
    wait
}

# 启动生产环境
start_production() {
    echo -e "${BLUE}🏭 启动生产环境...${NC}"
    
    # 启动后端服务
    if ! sudo systemctl is-active --quiet workflow-backend; then
        echo -e "${YELLOW}📡 启动后端服务...${NC}"
        sudo systemctl start workflow-backend
    fi
    
    # 启动Nginx
    if ! sudo systemctl is-active --quiet nginx; then
        echo -e "${YELLOW}🌐 启动Nginx服务...${NC}"
        sudo systemctl start nginx
    fi
    
    # 显示状态
    show_status
}

# 完整部署 (开发 -> 生产)
deploy_full() {
    echo -e "${BLUE}🚀 开始完整部署 (开发环境 -> 生产环境)${NC}"
    
    cd "$PROJECT_DIR"
    
    # 1. 备份当前生产环境
    echo -e "${YELLOW}💾 备份当前生产环境...${NC}"
    create_backup
    
    # 2. 停止生产服务
    echo -e "${YELLOW}⏹️  停止生产服务...${NC}"
    sudo systemctl stop workflow-backend || true
    
    # 3. 更新后端依赖
    echo -e "${YELLOW}📦 更新后端依赖...${NC}"
    pip install --user -r requirements.txt
    
    # 4. 构建并部署前端
    echo -e "${YELLOW}🔨 构建前端...${NC}"
    cd "$FRONTEND_DIR"
    
    # 使用生产环境变量构建
    NODE_ENV=production npm run build
    
    # 部署前端
    echo -e "${YELLOW}📋 部署前端...${NC}"
    sudo rm -rf "$DEPLOY_DIR"/*
    sudo cp -r build/* "$DEPLOY_DIR/"
    sudo chown -R www-data:www-data "$DEPLOY_DIR"
    sudo chmod -R 644 "$DEPLOY_DIR"
    sudo find "$DEPLOY_DIR" -type d -exec chmod 755 {} \;
    
    # 5. 启动服务
    echo -e "${YELLOW}🔄 启动生产服务...${NC}"
    cd "$PROJECT_DIR"
    sudo systemctl start workflow-backend
    sudo nginx -s reload
    
    # 6. 健康检查
    echo -e "${YELLOW}🏥 等待服务启动...${NC}"
    sleep 10
    
    health_check
    
    echo -e "${GREEN}🎉 部署完成！${NC}"
    echo -e "${GREEN}🌐 访问地址: https://autolabflow.online${NC}"
}

# 仅部署前端
deploy_frontend() {
    echo -e "${BLUE}🌐 部署前端...${NC}"
    
    cd "$FRONTEND_DIR"
    
    # 构建
    NODE_ENV=production npm run build
    
    # 备份当前前端
    if [[ -f "$DEPLOY_DIR/index.html" ]]; then
        sudo mkdir -p "$BACKUP_DIR/frontend"
        sudo cp -r "$DEPLOY_DIR" "$BACKUP_DIR/frontend/backup-$(date +%Y%m%d_%H%M%S)"
    fi
    
    # 部署
    sudo rm -rf "$DEPLOY_DIR"/*
    sudo cp -r build/* "$DEPLOY_DIR/"
    sudo chown -R www-data:www-data "$DEPLOY_DIR"
    sudo chmod -R 644 "$DEPLOY_DIR"
    sudo find "$DEPLOY_DIR" -type d -exec chmod 755 {} \;
    
    # 重新加载Nginx
    sudo nginx -s reload
    
    echo -e "${GREEN}✅ 前端部署完成${NC}"
}

# 仅部署后端
deploy_backend() {
    echo -e "${BLUE}📡 部署后端...${NC}"
    
    cd "$PROJECT_DIR"
    
    # 更新依赖
    pip install --user -r requirements.txt
    
    # 重启服务
    sudo systemctl restart workflow-backend
    
    # 等待启动
    sleep 5
    
    if curl -f -s http://localhost:8001/health > /dev/null; then
        echo -e "${GREEN}✅ 后端部署完成${NC}"
    else
        echo -e "${RED}❌ 后端部署失败${NC}"
        sudo systemctl status workflow-backend --no-pager
        exit 1
    fi
}

# 显示服务状态
show_status() {
    echo -e "${YELLOW}📊 服务状态:${NC}"
    
    # 检查后端服务
    if sudo systemctl is-active --quiet workflow-backend; then
        echo -e "  后端服务: ${GREEN}✅ 运行中${NC}"
    else
        echo -e "  后端服务: ${RED}❌ 未运行${NC}"
    fi
    
    # 检查Nginx
    if sudo systemctl is-active --quiet nginx; then
        echo -e "  Nginx: ${GREEN}✅ 运行中${NC}"
    else
        echo -e "  Nginx: ${RED}❌ 未运行${NC}"
    fi
    
    # 检查MySQL
    if sudo systemctl is-active --quiet mysql; then
        echo -e "  MySQL: ${GREEN}✅ 运行中${NC}"
    else
        echo -e "  MySQL: ${RED}❌ 未运行${NC}"
    fi
    
    # 显示端口占用
    echo -e "\n${YELLOW}🔌 端口占用:${NC}"
    netstat -tlnp | grep -E "(8001|80|443|3306)" | while read line; do
        port=$(echo "$line" | awk '{print $4}' | cut -d: -f2)
        echo "  端口 $port: 已占用"
    done
}

# 健康检查
health_check() {
    echo -e "${YELLOW}🏥 健康检查...${NC}"
    
    # 后端健康检查
    if curl -f -s http://localhost:8001/health > /dev/null; then
        echo -e "  后端API: ${GREEN}✅ 健康${NC}"
    else
        echo -e "  后端API: ${RED}❌ 异常${NC}"
    fi
    
    # 前端健康检查
    if curl -f -s http://localhost/ > /dev/null; then
        echo -e "  前端服务: ${GREEN}✅ 健康${NC}"
    else
        echo -e "  前端服务: ${RED}❌ 异常${NC}"
    fi
    
    # 数据库连接检查
    if python3 -c "import mysql.connector; mysql.connector.connect(host='localhost', user='root', password='mysql123', database='workflow_db')" 2>/dev/null; then
        echo -e "  数据库: ${GREEN}✅ 连接正常${NC}"
    else
        echo -e "  数据库: ${RED}❌ 连接异常${NC}"
    fi
}

# 查看日志
show_logs() {
    echo -e "${YELLOW}📋 选择查看的日志:${NC}"
    echo "1) 后端服务日志 (systemd)"
    echo "2) 后端应用日志"
    echo "3) Nginx访问日志"
    echo "4) Nginx错误日志"
    echo "5) 全部日志摘要"
    
    read -p "请选择 (1-5): " choice
    
    case $choice in
        1)
            sudo journalctl -u workflow-backend -f
            ;;
        2)
            tail -f "$LOG_DIR/backend.log" 2>/dev/null || echo "应用日志文件不存在"
            ;;
        3)
            sudo tail -f /var/log/nginx/access.log
            ;;
        4)
            sudo tail -f /var/log/nginx/error.log
            ;;
        5)
            echo -e "${YELLOW}最近10条后端服务日志:${NC}"
            sudo journalctl -u workflow-backend -n 10 --no-pager
            echo -e "\n${YELLOW}最近5条Nginx错误日志:${NC}"
            sudo tail -5 /var/log/nginx/error.log 2>/dev/null || echo "无错误日志"
            ;;
        *)
            echo -e "${RED}无效选择${NC}"
            ;;
    esac
}

# 创建备份
create_backup() {
    echo -e "${YELLOW}💾 创建系统备份...${NC}"
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_PATH="$BACKUP_DIR/$TIMESTAMP"
    
    sudo mkdir -p "$BACKUP_PATH"
    
    # 备份前端
    if [[ -d "$DEPLOY_DIR" ]]; then
        sudo cp -r "$DEPLOY_DIR" "$BACKUP_PATH/frontend"
    fi
    
    # 备份配置
    sudo cp .env.production "$BACKUP_PATH/"
    sudo cp frontend/.env.production "$BACKUP_PATH/"
    
    echo -e "${GREEN}✅ 备份创建完成: $BACKUP_PATH${NC}"
}

# 停止所有服务
stop_all() {
    echo -e "${YELLOW}🛑 停止所有服务...${NC}"
    
    # 停止systemd服务
    sudo systemctl stop workflow-backend || true
    sudo systemctl stop nginx || true
    
    # 停止开发进程
    pkill -f "python main.py" || true
    pkill -f "npm start" || true
    
    echo -e "${GREEN}✅ 所有服务已停止${NC}"
}

# 重启生产服务
restart_production() {
    echo -e "${YELLOW}🔄 重启生产服务...${NC}"
    
    sudo systemctl restart workflow-backend
    sudo systemctl restart nginx
    
    sleep 5
    health_check
    
    echo -e "${GREEN}✅ 生产服务重启完成${NC}"
}

# 主函数
main() {
    case "${1:-}" in
        start-dev)
            check_environment
            start_development
            ;;
        start-prod)
            check_environment
            start_production
            ;;
        deploy)
            check_environment
            deploy_full
            ;;
        deploy-frontend)
            check_environment
            deploy_frontend
            ;;
        deploy-backend)
            check_environment
            deploy_backend
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        stop)
            stop_all
            ;;
        restart)
            restart_production
            ;;
        health)
            health_check
            ;;
        *)
            show_usage
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"