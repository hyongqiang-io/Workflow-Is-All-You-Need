#!/bin/bash

# 工作流应用健康监控脚本
# Workflow Application Health Monitor

set -e

# 配置
BACKEND_URL="http://localhost:8000/api/test/health"
FRONTEND_URL="http://localhost"
CHECK_INTERVAL=60
LOG_FILE="/var/log/workflow-monitor.log"
ALERT_EMAIL=""

# 日志函数
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 检查服务健康状态
check_service_health() {
    local url=$1
    local service_name=$2
    
    if curl -s --connect-timeout 5 --max-time 10 "$url" >/dev/null 2>&1; then
        log_message "✅ $service_name 服务正常"
        return 0
    else
        log_message "❌ $service_name 服务异常"
        return 1
    fi
}

# 检查Docker服务状态
check_docker_services() {
    if command -v docker-compose &> /dev/null; then
        if [[ -f "deployment/docker/docker-compose.yml" ]]; then
            cd deployment/docker
            local unhealthy=$(docker-compose ps | grep -E "(Exit|unhealthy)" | wc -l)
            cd ../..
            
            if [[ $unhealthy -gt 0 ]]; then
                log_message "❌ 发现 $unhealthy 个异常的Docker服务"
                return 1
            else
                log_message "✅ 所有Docker服务正常运行"
                return 0
            fi
        fi
    fi
    return 0
}

# 检查磁盘空间
check_disk_space() {
    local usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    
    if [[ $usage -gt 85 ]]; then
        log_message "⚠️ 磁盘空间不足: ${usage}%"
        return 1
    else
        log_message "✅ 磁盘空间充足: ${usage}%"
        return 0
    fi
}

# 检查内存使用
check_memory_usage() {
    local memory_usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    
    if [[ $memory_usage -gt 90 ]]; then
        log_message "⚠️ 内存使用率过高: ${memory_usage}%"
        return 1
    else
        log_message "✅ 内存使用正常: ${memory_usage}%"
        return 0
    fi
}

# 发送告警
send_alert() {
    local message=$1
    
    log_message "🚨 告警: $message"
    
    if [[ -n "$ALERT_EMAIL" ]]; then
        echo "$message" | mail -s "工作流应用告警" "$ALERT_EMAIL" 2>/dev/null || true
    fi
}

# 修复尝试
attempt_fix() {
    log_message "🔧 尝试自动修复..."
    
    # 重启Docker服务
    if [[ -f "deployment/docker/docker-compose.yml" ]]; then
        cd deployment/docker
        docker-compose restart 2>/dev/null || true
        cd ../..
        sleep 30
    fi
    
    # 重启系统服务
    systemctl restart workflow-backend 2>/dev/null || true
    systemctl restart nginx 2>/dev/null || true
}

# 主监控循环
monitor_loop() {
    log_message "🎯 开始健康监控 (检查间隔: ${CHECK_INTERVAL}s)"
    
    while true; do
        local failed_checks=0
        
        # 检查各项指标
        check_service_health "$BACKEND_URL" "后端API" || ((failed_checks++))
        check_service_health "$FRONTEND_URL" "前端" || ((failed_checks++))
        check_docker_services || ((failed_checks++))
        check_disk_space || ((failed_checks++))
        check_memory_usage || ((failed_checks++))
        
        # 如果有失败的检查，尝试修复
        if [[ $failed_checks -gt 0 ]]; then
            send_alert "发现 $failed_checks 个健康检查失败"
            attempt_fix
        fi
        
        sleep "$CHECK_INTERVAL"
    done
}

# 单次检查
check_once() {
    log_message "📊 执行单次健康检查..."
    
    local results=()
    check_service_health "$BACKEND_URL" "后端API" && results+=("后端✅") || results+=("后端❌")
    check_service_health "$FRONTEND_URL" "前端" && results+=("前端✅") || results+=("前端❌")
    check_docker_services && results+=("Docker✅") || results+=("Docker❌")
    check_disk_space && results+=("磁盘✅") || results+=("磁盘❌")
    check_memory_usage && results+=("内存✅") || results+=("内存❌")
    
    log_message "📋 检查结果: ${results[*]}"
}

# 显示帮助
show_help() {
    echo "工作流应用健康监控脚本"
    echo
    echo "用法: $0 [选项]"
    echo
    echo "选项:"
    echo "  --daemon       后台运行持续监控"
    echo "  --check        执行单次健康检查"
    echo "  --status       显示当前服务状态" 
    echo "  --help         显示此帮助"
    echo
    echo "配置:"
    echo "  BACKEND_URL    后端健康检查地址 (默认: $BACKEND_URL)"
    echo "  FRONTEND_URL   前端地址 (默认: $FRONTEND_URL)"
    echo "  CHECK_INTERVAL 检查间隔秒数 (默认: $CHECK_INTERVAL)"
    echo "  ALERT_EMAIL    告警邮箱地址"
}

# 主函数
case "${1:-check}" in
    --daemon)
        monitor_loop
        ;;
    --check)
        check_once
        ;;
    --status)
        check_once
        ;;
    --help)
        show_help
        ;;
    *)
        echo "未知选项: $1"
        show_help
        exit 1
        ;;
esac
