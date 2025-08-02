#!/bin/bash

# 工作流应用启动脚本
# Workflow Application Start Script

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检测部署类型
detect_deployment_type() {
    if [[ -f "deployment/docker/docker-compose.yml" ]] && command -v docker-compose &> /dev/null; then
        echo "docker"
    elif [[ -f "/etc/systemd/system/workflow-backend.service" ]]; then
        echo "native"
    else
        echo "unknown"
    fi
}

# Docker方式启动
start_docker() {
    log_info "使用Docker启动服务..."
    
    cd deployment/docker
    
    # 检查.env文件
    if [[ ! -f ../../.env ]]; then
        log_warn ".env文件不存在，使用默认配置"
        cp ../../.env.example ../../.env
    fi
    
    # 启动服务
    docker-compose up -d
    
    # 等待服务启动
    log_info "等待服务启动..."
    sleep 10
    
    # 检查服务状态
    check_docker_status
}

# 原生方式启动
start_native() {
    log_info "使用原生方式启动服务..."
    
    # 启动后端服务
    if systemctl is-active --quiet workflow-backend; then
        log_info "后端服务已在运行"
    else
        log_info "启动后端服务..."
        systemctl start workflow-backend
    fi
    
    # 启动Nginx
    if systemctl is-active --quiet nginx; then
        log_info "Nginx已在运行"
    else
        log_info "启动Nginx..."
        systemctl start nginx
    fi
    
    # 检查服务状态
    check_native_status
}

# 检查Docker服务状态
check_docker_status() {
    log_info "检查Docker服务状态..."
    
    if docker-compose ps | grep -q "Up"; then
        log_info "服务启动成功!"
        docker-compose ps
        
        # 健康检查
        log_info "进行健康检查..."
        if curl -s http://localhost/health > /dev/null; then
            log_info "前端健康检查通过"
        else
            log_warn "前端健康检查失败"
        fi
        
        if curl -s http://localhost/api/test/health > /dev/null; then
            log_info "后端健康检查通过"
        else
            log_warn "后端健康检查失败"
        fi
        
    else
        log_error "服务启动失败!"
        docker-compose logs --tail=50
        exit 1
    fi
}

# 检查原生服务状态
check_native_status() {
    log_info "检查原生服务状态..."
    
    # 检查后端服务
    if systemctl is-active --quiet workflow-backend; then
        log_info "后端服务运行正常"
    else
        log_error "后端服务启动失败"
        systemctl status workflow-backend --no-pager -l
        exit 1
    fi
    
    # 检查Nginx
    if systemctl is-active --quiet nginx; then
        log_info "Nginx运行正常"
    else
        log_error "Nginx启动失败"
        systemctl status nginx --no-pager -l
        exit 1
    fi
    
    # 健康检查
    log_info "进行健康检查..."
    if curl -s http://localhost/health > /dev/null; then
        log_info "前端健康检查通过"
    else
        log_warn "前端健康检查失败"
    fi
    
    if curl -s http://localhost:8000/api/test/health > /dev/null; then
        log_info "后端健康检查通过"
    else
        log_warn "后端健康检查失败"
    fi
}

# 停止服务
stop_services() {
    local deployment_type=$(detect_deployment_type)
    
    log_info "停止服务..."
    
    case $deployment_type in
        "docker")
            cd deployment/docker
            docker-compose down
            ;;
        "native")
            systemctl stop workflow-backend nginx
            ;;
        *)
            log_error "无法检测部署类型"
            exit 1
            ;;
    esac
    
    log_info "服务已停止"
}

# 重启服务
restart_services() {
    local deployment_type=$(detect_deployment_type)
    
    log_info "重启服务..."
    
    case $deployment_type in
        "docker")
            cd deployment/docker
            docker-compose restart
            check_docker_status
            ;;
        "native")
            systemctl restart workflow-backend nginx
            check_native_status
            ;;
        *)
            log_error "无法检测部署类型"
            exit 1
            ;;
    esac
    
    log_info "服务重启完成"
}

# 查看日志
show_logs() {
    local deployment_type=$(detect_deployment_type)
    
    case $deployment_type in
        "docker")
            cd deployment/docker
            docker-compose logs -f
            ;;
        "native")
            echo "选择要查看的日志:"
            echo "1) 后端日志"
            echo "2) Nginx访问日志"
            echo "3) Nginx错误日志"
            read -p "请选择 (1-3): " -n 1 -r
            echo
            
            case $REPLY in
                1)
                    journalctl -u workflow-backend -f
                    ;;
                2)
                    tail -f /var/log/nginx/access.log
                    ;;
                3)
                    tail -f /var/log/nginx/error.log
                    ;;
                *)
                    log_error "无效选择"
                    exit 1
                    ;;
            esac
            ;;
        *)
            log_error "无法检测部署类型"
            exit 1
            ;;
    esac
}

# 显示状态
show_status() {
    local deployment_type=$(detect_deployment_type)
    
    log_info "系统状态:"
    
    case $deployment_type in
        "docker")
            cd deployment/docker
            docker-compose ps
            echo
            log_info "资源使用情况:"
            docker stats --no-stream
            ;;
        "native")
            echo "后端服务状态:"
            systemctl status workflow-backend --no-pager -l
            echo
            echo "Nginx状态:"
            systemctl status nginx --no-pager -l
            ;;
        *)
            log_error "无法检测部署类型"
            exit 1
            ;;
    esac
}

# 显示帮助信息
show_help() {
    echo "工作流应用管理脚本"
    echo
    echo "用法: $0 [命令]"
    echo
    echo "命令:"
    echo "  start     启动服务 (默认)"
    echo "  stop      停止服务"
    echo "  restart   重启服务"
    echo "  status    显示服务状态"
    echo "  logs      查看日志"
    echo "  help      显示帮助信息"
    echo
    echo "示例:"
    echo "  $0              # 启动服务"
    echo "  $0 start        # 启动服务"
    echo "  $0 stop         # 停止服务"
    echo "  $0 restart      # 重启服务"
    echo "  $0 status       # 查看状态"
    echo "  $0 logs         # 查看日志"
}

# 主函数
main() {
    local command=${1:-start}
    
    case $command in
        start)
            local deployment_type=$(detect_deployment_type)
            log_info "检测到部署类型: $deployment_type"
            
            case $deployment_type in
                "docker")
                    start_docker
                    ;;
                "native")
                    start_native
                    ;;
                *)
                    log_error "无法检测部署类型，请先运行部署脚本"
                    exit 1
                    ;;
            esac
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 运行主函数
main "$@"