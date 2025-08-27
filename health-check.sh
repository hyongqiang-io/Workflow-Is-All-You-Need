#!/bin/bash

# 后端服务健康检查脚本
# 可以配置为cron任务定期执行

LOG_FILE="/var/log/workflow/health-check.log"
SERVICE_NAME="workflow-backend"
API_ENDPOINT="http://localhost:8001/health"
ALERT_EMAIL="admin@autolabflow.online"  # 可选：设置告警邮箱

# 记录日志函数
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# 检查服务状态
check_service() {
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        return 0
    else
        return 1
    fi
}

# 检查API健康
check_api() {
    if curl -f -s -o /dev/null --connect-timeout 5 "$API_ENDPOINT"; then
        return 0
    else
        return 1
    fi
}

# 主检查逻辑
main() {
    local issues=0
    
    # 检查服务运行状态
    if check_service; then
        log_message "✅ Service $SERVICE_NAME is running"
    else
        log_message "❌ Service $SERVICE_NAME is not running"
        issues=$((issues + 1))
        
        # 尝试重启服务
        log_message "🔄 Attempting to restart service..."
        if systemctl restart "$SERVICE_NAME"; then
            log_message "✅ Service restarted successfully"
            sleep 10  # 等待服务启动
        else
            log_message "❌ Failed to restart service"
            issues=$((issues + 1))
        fi
    fi
    
    # 检查API响应
    if check_api; then
        log_message "✅ API endpoint is responding"
    else
        log_message "❌ API endpoint is not responding"
        issues=$((issues + 1))
    fi
    
    # 检查端口监听
    if netstat -tlnp | grep -q ":8001"; then
        log_message "✅ Port 8001 is listening"
    else
        log_message "❌ Port 8001 is not listening"
        issues=$((issues + 1))
    fi
    
    # 检查磁盘空间
    disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ $disk_usage -lt 85 ]]; then
        log_message "✅ Disk usage: ${disk_usage}%"
    else
        log_message "⚠️  High disk usage: ${disk_usage}%"
        issues=$((issues + 1))
    fi
    
    # 检查内存使用
    mem_usage=$(free | awk '/Mem/ {printf("%.0f", $3/$2*100)}')
    if [[ $mem_usage -lt 85 ]]; then
        log_message "✅ Memory usage: ${mem_usage}%"
    else
        log_message "⚠️  High memory usage: ${mem_usage}%"
    fi
    
    # 总结
    if [[ $issues -eq 0 ]]; then
        log_message "🎉 All health checks passed"
        exit 0
    else
        log_message "⚠️  $issues issues detected"
        exit 1
    fi
}

# 创建日志目录
mkdir -p "$(dirname "$LOG_FILE")"

# 执行检查
main "$@"