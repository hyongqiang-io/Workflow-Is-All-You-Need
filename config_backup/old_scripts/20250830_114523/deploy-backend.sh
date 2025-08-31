#!/bin/bash

# 后端服务部署和管理脚本
# 功能：部署、启动、停止、重启后端服务

set -e

# 配置变量
PROJECT_DIR="/home/ubuntu/Workflow-Is-All-You-Need"
SERVICE_NAME="workflow-backend"
SERVICE_FILE="workflow-backend.service"
LOG_DIR="/var/log/workflow"
BACKUP_DIR="/var/backups/backend"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 显示使用说明
show_usage() {
    echo -e "${BLUE}用法: $0 {install|start|stop|restart|status|logs|update|backup|restore}${NC}"
    echo ""
    echo "命令说明:"
    echo "  install  - 安装服务到系统"
    echo "  start    - 启动服务"
    echo "  stop     - 停止服务"
    echo "  restart  - 重启服务"
    echo "  status   - 查看服务状态"
    echo "  logs     - 查看服务日志"
    echo "  update   - 更新代码并重启服务"
    echo "  backup   - 备份当前代码"
    echo "  restore  - 恢复备份"
}

# 检查依赖
check_dependencies() {
    echo -e "${YELLOW}📋 检查依赖...${NC}"
    
    # 检查Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python3 未安装${NC}"
        return 1
    fi
    
    # 检查pip
    if ! command -v pip3 &> /dev/null; then
        echo -e "${RED}❌ pip3 未安装${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ 依赖检查通过${NC}"
}

# 安装Python依赖
install_python_deps() {
    echo -e "${YELLOW}📦 安装Python依赖...${NC}"
    cd "$PROJECT_DIR"
    
    if [[ -f "requirements.txt" ]]; then
        pip3 install --user -r requirements.txt
        echo -e "${GREEN}✅ Python依赖安装完成${NC}"
    else
        echo -e "${YELLOW}⚠️  requirements.txt 不存在${NC}"
    fi
}

# 创建日志目录
setup_logs() {
    echo -e "${YELLOW}📁 设置日志目录...${NC}"
    
    sudo mkdir -p "$LOG_DIR"
    sudo chown -R ubuntu:ubuntu "$LOG_DIR"
    sudo chmod -R 755 "$LOG_DIR"
    
    echo -e "${GREEN}✅ 日志目录设置完成${NC}"
}

# 安装服务
install_service() {
    echo -e "${YELLOW}🚀 安装后端服务...${NC}"
    
    check_dependencies
    setup_logs
    install_python_deps
    
    # 停止现有进程
    echo -e "${YELLOW}🛑 停止现有后端进程...${NC}"
    pkill -f "python3 main.py" || true
    sleep 2
    
    # 复制服务文件
    if [[ -f "$PROJECT_DIR/$SERVICE_FILE" ]]; then
        sudo cp "$PROJECT_DIR/$SERVICE_FILE" "/etc/systemd/system/"
        echo -e "${GREEN}✅ 服务文件已复制${NC}"
    else
        echo -e "${RED}❌ 服务文件不存在: $PROJECT_DIR/$SERVICE_FILE${NC}"
        return 1
    fi
    
    # 重新加载systemd
    sudo systemctl daemon-reload
    
    # 启用服务
    sudo systemctl enable "$SERVICE_NAME"
    
    echo -e "${GREEN}🎉 服务安装完成${NC}"
    echo -e "${BLUE}💡 使用以下命令管理服务:${NC}"
    echo "  启动: sudo systemctl start $SERVICE_NAME"
    echo "  停止: sudo systemctl stop $SERVICE_NAME"
    echo "  重启: sudo systemctl restart $SERVICE_NAME"
    echo "  状态: sudo systemctl status $SERVICE_NAME"
}

# 启动服务
start_service() {
    echo -e "${YELLOW}▶️  启动服务...${NC}"
    
    if sudo systemctl start "$SERVICE_NAME"; then
        echo -e "${GREEN}✅ 服务启动成功${NC}"
        sleep 2
        show_status
    else
        echo -e "${RED}❌ 服务启动失败${NC}"
        echo -e "${YELLOW}📋 查看错误日志:${NC}"
        sudo systemctl status "$SERVICE_NAME" --no-pager -l
        return 1
    fi
}

# 停止服务
stop_service() {
    echo -e "${YELLOW}⏹️  停止服务...${NC}"
    
    if sudo systemctl stop "$SERVICE_NAME"; then
        echo -e "${GREEN}✅ 服务停止成功${NC}"
    else
        echo -e "${RED}❌ 服务停止失败${NC}"
        return 1
    fi
}

# 重启服务
restart_service() {
    echo -e "${YELLOW}🔄 重启服务...${NC}"
    
    if sudo systemctl restart "$SERVICE_NAME"; then
        echo -e "${GREEN}✅ 服务重启成功${NC}"
        sleep 2
        show_status
    else
        echo -e "${RED}❌ 服务重启失败${NC}"
        show_status
        return 1
    fi
}

# 显示服务状态
show_status() {
    echo -e "${YELLOW}📊 服务状态:${NC}"
    sudo systemctl status "$SERVICE_NAME" --no-pager -l || true
    
    echo -e "\n${YELLOW}🌐 端口监听状态:${NC}"
    sudo netstat -tlnp | grep :8001 || echo "端口8001未监听"
    
    echo -e "\n${YELLOW}💾 内存使用:${NC}"
    ps aux | grep "python3 main.py" | grep -v grep || echo "进程未运行"
}

# 查看日志
show_logs() {
    echo -e "${YELLOW}📋 查看服务日志:${NC}"
    echo "最近50行日志:"
    sudo journalctl -u "$SERVICE_NAME" -n 50 --no-pager -l
    
    echo -e "\n${YELLOW}📄 应用日志文件:${NC}"
    if [[ -f "$LOG_DIR/backend.log" ]]; then
        echo "最近20行应用日志:"
        tail -20 "$LOG_DIR/backend.log"
    else
        echo "应用日志文件不存在"
    fi
}

# 更新代码并重启
update_service() {
    echo -e "${YELLOW}🔄 更新后端服务...${NC}"
    
    cd "$PROJECT_DIR"
    
    # 备份当前代码
    backup_code
    
    # 拉取最新代码（如果是git仓库）
    if [[ -d ".git" ]]; then
        echo -e "${YELLOW}📥 拉取最新代码...${NC}"
        git pull origin main || git pull origin master || echo "Git pull failed, continuing..."
    fi
    
    # 更新依赖
    install_python_deps
    
    # 重启服务
    restart_service
    
    echo -e "${GREEN}🎉 更新完成${NC}"
}

# 备份代码
backup_code() {
    echo -e "${YELLOW}💾 备份当前代码...${NC}"
    
    sudo mkdir -p "$BACKUP_DIR"
    backup_name="backend-backup-$(date +%Y%m%d-%H%M%S)"
    
    sudo cp -r "$PROJECT_DIR" "$BACKUP_DIR/$backup_name"
    sudo chown -R ubuntu:ubuntu "$BACKUP_DIR/$backup_name"
    
    echo -e "${GREEN}✅ 备份完成: $BACKUP_DIR/$backup_name${NC}"
    
    # 只保留最近10个备份
    cd "$BACKUP_DIR"
    sudo find . -type d -name "backend-backup-*" | sort -r | tail -n +11 | sudo xargs rm -rf
}

# 恢复备份
restore_backup() {
    echo -e "${YELLOW}🔄 恢复备份...${NC}"
    
    if [[ ! -d "$BACKUP_DIR" ]]; then
        echo -e "${RED}❌ 备份目录不存在${NC}"
        return 1
    fi
    
    echo "可用的备份："
    ls -la "$BACKUP_DIR/" | grep "backend-backup-"
    
    read -p "请输入要恢复的备份名称: " backup_name
    
    if [[ -d "$BACKUP_DIR/$backup_name" ]]; then
        stop_service
        sudo cp -r "$BACKUP_DIR/$backup_name/"* "$PROJECT_DIR/"
        sudo chown -R ubuntu:ubuntu "$PROJECT_DIR"
        start_service
        echo -e "${GREEN}✅ 备份恢复完成${NC}"
    else
        echo -e "${RED}❌ 备份不存在${NC}"
        return 1
    fi
}

# 主函数
main() {
    case "${1:-}" in
        install)
            install_service
            ;;
        start)
            start_service
            ;;
        stop)
            stop_service
            ;;
        restart)
            restart_service
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        update)
            update_service
            ;;
        backup)
            backup_code
            ;;
        restore)
            restore_backup
            ;;
        *)
            show_usage
            exit 1
            ;;
    esac
}

# 检查是否以root身份运行某些命令
if [[ "$1" == "install" || "$1" == "start" || "$1" == "stop" || "$1" == "restart" ]]; then
    if [[ $EUID -eq 0 ]]; then
        echo -e "${RED}❌ 请不要以root身份运行此脚本${NC}"
        echo -e "${YELLOW}💡 正确用法: ./deploy-backend.sh $1${NC}"
        exit 1
    fi
fi

# 执行主函数
main "$@"