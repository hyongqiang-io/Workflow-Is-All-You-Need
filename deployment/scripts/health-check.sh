#!/bin/bash

# 应用健康检查脚本
# Application Health Check Script

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
HEALTH_CHECK_URL="http://localhost/api/test/health"
FRONTEND_URL="http://localhost"
MAX_RETRIES=3
RETRY_DELAY=5
TIMEOUT=10

# 通知配置
ENABLE_EMAIL_ALERTS=false
ENABLE_WEBHOOK_ALERTS=false
EMAIL_TO=""
WEBHOOK_URL=""

# 日志文件
LOG_FILE="/var/log/workflow-health.log"
STATUS_FILE="/tmp/workflow-health-status"

# 健康检查计数器
CONSECUTIVE_FAILURES=0
MAX_CONSECUTIVE_FAILURES=3

# 日志函数
log_message() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
    log_message "INFO" "$1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    log_message "WARN" "$1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    log_message "ERROR" "$1"
}

log_debug() {
    if [[ "${DEBUG:-false}" == "true" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
        log_message "DEBUG" "$1"
    fi
}

# 检查命令是否存在
check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# HTTP健康检查
check_http_endpoint() {
    local url=$1
    local expected_code=${2:-200}
    local timeout=${3:-$TIMEOUT}
    local retries=${4:-$MAX_RETRIES}
    
    log_debug "检查HTTP端点: $url (期望状态码: $expected_code)"
    
    for ((i=1; i<=retries; i++)); do
        if check_command curl; then
            local response_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time $timeout "$url" 2>/dev/null || echo "000")
            local response_time=$(curl -s -o /dev/null -w "%{time_total}" --max-time $timeout "$url" 2>/dev/null || echo "999")
            
            log_debug "尝试 $i/$retries: HTTP $response_code, 响应时间: ${response_time}s"
            
            if [[ "$response_code" == "$expected_code" ]]; then
                log_debug "HTTP检查成功: $url"
                echo "$response_time"
                return 0
            fi
        elif check_command wget; then
            if wget -q -O /dev/null -T $timeout "$url" 2>/dev/null; then
                log_debug "HTTP检查成功: $url"
                echo "0"
                return 0
            fi
        else
            log_error "curl 或 wget 命令不可用"
            return 2
        fi
        
        if [[ $i -lt $retries ]]; then
            log_debug "等待 ${RETRY_DELAY}s 后重试..."
            sleep $RETRY_DELAY
        fi
    done
    
    log_debug "HTTP检查失败: $url"
    return 1
}

# 检查端口
check_port() {
    local host=$1
    local port=$2
    local timeout=${3:-5}
    
    log_debug "检查端口: $host:$port"
    
    if timeout $timeout bash -c "cat < /dev/null > /dev/tcp/$host/$port" 2>/dev/null; then
        log_debug "端口检查成功: $host:$port"
        return 0
    else
        log_debug "端口检查失败: $host:$port"
        return 1
    fi
}

# 检测部署类型
detect_deployment_type() {
    if [[ -f "deployment/docker/docker-compose.yml" ]] && check_command docker-compose; then
        if docker-compose -f deployment/docker/docker-compose.yml ps 2>/dev/null | grep -q "Up"; then
            echo "docker"
            return
        fi
    fi
    
    if systemctl is-active --quiet workflow-backend 2>/dev/null; then
        echo "native"
        return
    fi
    
    echo "unknown"
}

# 检查系统资源
check_system_resources() {
    log_debug "检查系统资源..."
    
    # 检查CPU使用率
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//')
    log_debug "CPU使用率: ${cpu_usage}%"
    
    # 检查内存使用率
    local memory_usage=$(free | grep Mem | awk '{printf("%.1f"), $3/$2 * 100.0}')
    log_debug "内存使用率: ${memory_usage}%"
    
    # 检查磁盘使用率
    local disk_usage=$(df -h . | awk 'NR==2{print $5}' | sed 's/%//')
    log_debug "磁盘使用率: ${disk_usage}%"
    
    # 检查负载
    local load_avg=$(uptime | awk '{print $(NF-2)}' | sed 's/,//')
    log_debug "系统负载: $load_avg"
    
    # 资源使用警告
    if (( $(echo "$memory_usage > 90" | bc -l 2>/dev/null || echo 0) )); then
        log_warn "内存使用率过高: ${memory_usage}%"
    fi
    
    if [[ $disk_usage -gt 90 ]]; then
        log_warn "磁盘使用率过高: ${disk_usage}%"
    fi
    
    if (( $(echo "$load_avg > $(nproc)" | bc -l 2>/dev/null || echo 0) )); then
        log_warn "系统负载过高: $load_avg"
    fi
}

# 检查Docker服务
check_docker_services() {
    log_debug "检查Docker服务..."
    
    if ! check_command docker-compose; then
        log_error "Docker Compose未安装"
        return 1
    fi
    
    cd deployment/docker || return 1
    
    # 检查容器状态
    local containers_status=$(docker-compose ps --format "table {{.Name}}\t{{.State}}")
    log_debug "容器状态:\n$containers_status"
    
    # 检查运行中的容器数量
    local running_containers=$(docker-compose ps | grep "Up" | wc -l)
    local total_containers=$(docker-compose ps -a | tail -n +3 | wc -l)
    
    if [[ $running_containers -eq $total_containers ]] && [[ $total_containers -gt 0 ]]; then
        log_debug "所有容器运行正常 ($running_containers/$total_containers)"
        cd ../..
        return 0
    else
        log_error "容器状态异常 ($running_containers/$total_containers 运行中)"
        
        # 显示失败的容器
        docker-compose ps | grep -v "Up" | tail -n +3 | while read line; do
            if [[ -n "$line" ]]; then
                log_error "异常容器: $line"
            fi
        done
        
        cd ../..
        return 1
    fi
}

# 检查原生服务
check_native_services() {
    log_debug "检查原生服务..."
    
    local services=("workflow-backend" "nginx")
    local failed_services=()
    
    for service in "${services[@]}"; do
        if systemctl is-active --quiet "$service"; then
            log_debug "服务运行正常: $service"
        else
            log_error "服务异常: $service"
            failed_services+=("$service")
        fi
    done
    
    if [[ ${#failed_services[@]} -eq 0 ]]; then
        return 0
    else
        log_error "失败的服务: ${failed_services[*]}"
        return 1
    fi
}

# 检查数据库
check_database() {
    log_debug "检查数据库..."
    
    local deployment_type=$(detect_deployment_type)
    
    case $deployment_type in
        "docker")
            # Docker环境中检查数据库
            if docker-compose -f deployment/docker/docker-compose.yml exec -T backend python -c "
import sqlite3
import sys
try:
    conn = sqlite3.connect('/app/data/workflow.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1')
    result = cursor.fetchone()
    conn.close()
    if result:
        print('SUCCESS')
    else:
        print('EMPTY_RESULT')
        sys.exit(1)
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
            " 2>/dev/null | grep -q "SUCCESS"; then
                log_debug "Docker数据库连接正常"
                return 0
            else
                log_error "Docker数据库连接失败"
                return 1
            fi
            ;;
        "native")
            # 原生环境中检查数据库
            if [[ -f "workflow.db" ]]; then
                if sqlite3 workflow.db "SELECT 1;" &>/dev/null; then
                    log_debug "原生数据库连接正常"
                    return 0
                else
                    log_error "原生数据库连接失败"
                    return 1
                fi
            else
                log_error "数据库文件不存在"
                return 1
            fi
            ;;
        *)
            log_warn "无法检测部署类型，跳过数据库检查"
            return 0
            ;;
    esac
}

# 检查日志错误
check_application_logs() {
    log_debug "检查应用日志..."
    
    local deployment_type=$(detect_deployment_type)
    local error_count=0
    
    case $deployment_type in
        "docker")
            # 检查Docker容器日志
            cd deployment/docker || return 1
            local recent_logs=$(docker-compose logs --tail=100 2>/dev/null)
            error_count=$(echo "$recent_logs" | grep -i "error\|exception\|failed\|fatal" | wc -l)
            cd ../..
            ;;
        "native")
            # 检查systemd服务日志
            local recent_logs=$(journalctl -u workflow-backend --since "5 minutes ago" --no-pager 2>/dev/null || echo "")
            error_count=$(echo "$recent_logs" | grep -i "error\|exception\|failed\|fatal" | wc -l)
            ;;
    esac
    
    if [[ $error_count -gt 0 ]]; then
        log_warn "发现 $error_count 个错误日志条目"
        return 1
    else
        log_debug "应用日志正常"
        return 0
    fi
}

# 性能检查
check_performance() {
    log_debug "检查应用性能..."
    
    # 检查前端响应时间
    local frontend_response_time
    if frontend_response_time=$(check_http_endpoint "$FRONTEND_URL" 200); then
        local response_ms=$(echo "$frontend_response_time * 1000" | bc 2>/dev/null || echo "999")
        
        if (( $(echo "$frontend_response_time < 2.0" | bc -l 2>/dev/null || echo 0) )); then
            log_debug "前端响应时间正常: ${response_ms%.*}ms"
        else
            log_warn "前端响应时间过长: ${response_ms%.*}ms"
        fi
    else
        log_error "前端性能检查失败"
        return 1
    fi
    
    # 检查API响应时间
    local api_response_time
    if api_response_time=$(check_http_endpoint "$HEALTH_CHECK_URL" 200); then
        local api_response_ms=$(echo "$api_response_time * 1000" | bc 2>/dev/null || echo "999")
        
        if (( $(echo "$api_response_time < 1.0" | bc -l 2>/dev/null || echo 0) )); then
            log_debug "API响应时间正常: ${api_response_ms%.*}ms"
        else
            log_warn "API响应时间过长: ${api_response_ms%.*}ms"
        fi
    else
        log_error "API性能检查失败"
        return 1
    fi
    
    return 0
}

# 发送邮件通知
send_email_alert() {
    local subject=$1
    local message=$2
    
    if [[ "$ENABLE_EMAIL_ALERTS" != "true" ]] || [[ -z "$EMAIL_TO" ]]; then
        return 0
    fi
    
    if check_command mail; then
        echo "$message" | mail -s "$subject" "$EMAIL_TO"
        log_info "邮件通知已发送到: $EMAIL_TO"
    else
        log_warn "mail命令不可用，无法发送邮件通知"
    fi
}

# 发送Webhook通知
send_webhook_alert() {
    local message=$1
    
    if [[ "$ENABLE_WEBHOOK_ALERTS" != "true" ]] || [[ -z "$WEBHOOK_URL" ]]; then
        return 0
    fi
    
    if check_command curl; then
        curl -X POST -H "Content-Type: application/json" \
             -d "{\"text\":\"$message\"}" \
             "$WEBHOOK_URL" &>/dev/null
        
        if [[ $? -eq 0 ]]; then
            log_info "Webhook通知已发送"
        else
            log_warn "Webhook通知发送失败"
        fi
    else
        log_warn "curl命令不可用，无法发送Webhook通知"
    fi
}

# 处理健康检查失败
handle_health_check_failure() {
    local check_name=$1
    
    ((CONSECUTIVE_FAILURES++))
    
    log_error "健康检查失败: $check_name (连续失败 $CONSECUTIVE_FAILURES 次)"
    
    # 记录失败状态
    echo "UNHEALTHY:$check_name:$(date)" > "$STATUS_FILE"
    
    # 如果连续失败次数达到阈值，发送告警
    if [[ $CONSECUTIVE_FAILURES -ge $MAX_CONSECUTIVE_FAILURES ]]; then
        local alert_message="工作流应用健康检查失败！
检查项: $check_name
连续失败次数: $CONSECUTIVE_FAILURES
时间: $(date)
服务器: $(hostname)
请立即检查应用状态！"
        
        send_email_alert "工作流应用健康检查失败" "$alert_message"
        send_webhook_alert "$alert_message"
        
        # 尝试自动重启服务
        if [[ "${AUTO_RESTART:-false}" == "true" ]]; then
            log_info "尝试自动重启服务..."
            restart_services
        fi
    fi
}

# 处理健康检查成功
handle_health_check_success() {
    # 如果之前有失败，记录恢复
    if [[ $CONSECUTIVE_FAILURES -gt 0 ]]; then
        log_info "应用健康检查恢复正常 (之前连续失败 $CONSECUTIVE_FAILURES 次)"
        
        local recovery_message="工作流应用已恢复正常！
恢复时间: $(date)
服务器: $(hostname)
之前连续失败: $CONSECUTIVE_FAILURES 次"
        
        send_email_alert "工作流应用已恢复" "$recovery_message"
        send_webhook_alert "$recovery_message"
    fi
    
    CONSECUTIVE_FAILURES=0
    echo "HEALTHY:$(date)" > "$STATUS_FILE"
}

# 重启服务
restart_services() {
    log_info "重启应用服务..."
    
    local deployment_type=$(detect_deployment_type)
    
    case $deployment_type in
        "docker")
            cd deployment/docker
            docker-compose restart
            cd ../..
            ;;
        "native")
            systemctl restart workflow-backend nginx
            ;;
        *)
            log_error "无法检测部署类型，无法重启服务"
            return 1
            ;;
    esac
}

# 综合健康检查
perform_health_check() {
    log_info "开始应用健康检查..."
    
    local overall_status="HEALTHY"
    local failed_checks=()
    
    # 1. 检查系统资源
    if ! check_system_resources; then
        failed_checks+=("系统资源")
    fi
    
    # 2. 检查服务状态
    local deployment_type=$(detect_deployment_type)
    case $deployment_type in
        "docker")
            if ! check_docker_services; then
                failed_checks+=("Docker服务")
                overall_status="UNHEALTHY"
            fi
            ;;
        "native")
            if ! check_native_services; then
                failed_checks+=("系统服务")
                overall_status="UNHEALTHY"
            fi
            ;;
        *)
            log_warn "无法检测部署类型"
            failed_checks+=("部署类型检测")
            overall_status="UNKNOWN"
            ;;
    esac
    
    # 3. 检查HTTP端点
    if ! check_http_endpoint "$FRONTEND_URL" 200 >/dev/null; then
        failed_checks+=("前端页面")
        overall_status="UNHEALTHY"
    fi
    
    if ! check_http_endpoint "$HEALTH_CHECK_URL" 200 >/dev/null; then
        failed_checks+=("后端API")
        overall_status="UNHEALTHY"
    fi
    
    # 4. 检查数据库
    if ! check_database; then
        failed_checks+=("数据库")
        overall_status="UNHEALTHY"
    fi
    
    # 5. 检查应用日志
    if ! check_application_logs; then
        failed_checks+=("应用日志")
        # 日志错误不会导致整体状态为UNHEALTHY，只是警告
    fi
    
    # 6. 性能检查
    if ! check_performance; then
        failed_checks+=("性能指标")
        # 性能问题不会导致整体状态为UNHEALTHY，只是警告
    fi
    
    # 处理结果
    if [[ "$overall_status" == "HEALTHY" ]]; then
        log_info "应用健康检查通过 ✓"
        handle_health_check_success
        return 0
    else
        log_error "应用健康检查失败: ${failed_checks[*]}"
        handle_health_check_failure "${failed_checks[*]}"
        return 1
    fi
}

# 显示帮助信息
show_help() {
    echo "工作流应用健康检查脚本"
    echo
    echo "用法: $0 [选项]"
    echo
    echo "选项:"
    echo "  --check          执行健康检查 (默认)"
    echo "  --status         显示当前状态"
    echo "  --restart        重启服务"
    echo "  --monitor        持续监控模式"
    echo "  --debug          启用调试输出"
    echo "  --help           显示此帮助信息"
    echo
    echo "环境变量:"
    echo "  HEALTH_CHECK_URL      健康检查API地址"
    echo "  FRONTEND_URL          前端地址"
    echo "  MAX_RETRIES          最大重试次数"
    echo "  TIMEOUT              请求超时时间"
    echo "  ENABLE_EMAIL_ALERTS   启用邮件通知"
    echo "  EMAIL_TO             通知邮箱地址"
    echo "  ENABLE_WEBHOOK_ALERTS 启用Webhook通知"
    echo "  WEBHOOK_URL          Webhook地址"
    echo "  AUTO_RESTART         自动重启服务"
    echo
    echo "示例:"
    echo "  $0                    # 执行健康检查"
    echo "  $0 --monitor          # 持续监控"
    echo "  $0 --debug --check    # 调试模式健康检查"
}

# 显示当前状态
show_status() {
    if [[ -f "$STATUS_FILE" ]]; then
        local status_info=$(cat "$STATUS_FILE")
        log_info "当前状态: $status_info"
    else
        log_info "没有状态信息，请先运行健康检查"
    fi
    
    # 显示服务状态
    local deployment_type=$(detect_deployment_type)
    case $deployment_type in
        "docker")
            log_info "Docker容器状态:"
            cd deployment/docker
            docker-compose ps
            cd ../..
            ;;
        "native")
            log_info "系统服务状态:"
            systemctl status workflow-backend --no-pager -l
            systemctl status nginx --no-pager -l
            ;;
    esac
}

# 监控模式
monitor_mode() {
    log_info "启动监控模式..."
    
    local interval=${MONITOR_INTERVAL:-60}
    
    while true; do
        perform_health_check
        log_info "等待 ${interval}s 后进行下次检查..."
        sleep $interval
    done
}

# 主函数
main() {
    # 创建日志目录
    sudo mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    
    # 读取上次失败次数
    if [[ -f "$STATUS_FILE" ]] && grep -q "UNHEALTHY" "$STATUS_FILE"; then
        # 可以从状态文件中读取失败计数，这里简化处理
        CONSECUTIVE_FAILURES=1
    fi
    
    case "${1:-check}" in
        --check|check)
            perform_health_check
            ;;
        --status|status)
            show_status
            ;;
        --restart|restart)
            restart_services
            ;;
        --monitor|monitor)
            monitor_mode
            ;;
        --debug)
            export DEBUG=true
            main "${2:-check}"
            ;;
        --help|help|-h)
            show_help
            ;;
        *)
            log_error "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi