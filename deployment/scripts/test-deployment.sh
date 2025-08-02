#!/bin/bash

# 部署测试脚本
# Deployment Testing Script

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# 测试结果计数
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

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

log_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

# 测试结果函数
test_passed() {
    echo -e "${GREEN}✓ PASSED${NC} - $1"
    ((TESTS_PASSED++))
    ((TESTS_TOTAL++))
}

test_failed() {
    echo -e "${RED}✗ FAILED${NC} - $1"
    ((TESTS_FAILED++))
    ((TESTS_TOTAL++))
}

# 检查命令是否存在
check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# 检查端口是否开放
check_port() {
    local host=$1
    local port=$2
    local timeout=${3:-5}
    
    if timeout $timeout bash -c "cat < /dev/null > /dev/tcp/$host/$port" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# HTTP请求测试
test_http_request() {
    local url=$1
    local expected_code=${2:-200}
    local timeout=${3:-10}
    
    local response_code
    if check_command curl; then
        response_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time $timeout "$url" 2>/dev/null || echo "000")
    elif check_command wget; then
        response_code=$(wget -q -O /dev/null -T $timeout --server-response "$url" 2>&1 | grep "HTTP/" | tail -1 | awk '{print $2}' || echo "000")
    else
        log_error "curl 或 wget 命令不可用"
        return 1
    fi
    
    if [[ "$response_code" == "$expected_code" ]]; then
        return 0
    else
        echo "Expected: $expected_code, Got: $response_code"
        return 1
    fi
}

# 检测部署类型
detect_deployment_type() {
    if [[ -f "deployment/docker/docker-compose.yml" ]] && check_command docker-compose; then
        if docker-compose -f deployment/docker/docker-compose.yml ps | grep -q "Up"; then
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

# 测试系统要求
test_system_requirements() {
    log_test "检查系统要求..."
    
    # 检查操作系统
    if [[ -f /etc/os-release ]]; then
        test_passed "操作系统信息可用"
        log_info "OS: $(grep PRETTY_NAME /etc/os-release | cut -d'"' -f2)"
    else
        test_failed "无法获取操作系统信息"
    fi
    
    # 检查内存
    local memory_gb=$(free -g | awk '/^Mem:/{print $2}')
    if [[ $memory_gb -ge 2 ]]; then
        test_passed "内存充足 (${memory_gb}GB >= 2GB)"
    else
        test_failed "内存不足 (${memory_gb}GB < 2GB)"
    fi
    
    # 检查磁盘空间
    local disk_space=$(df -BG . | awk 'NR==2{print $4}' | sed 's/G//')
    if [[ $disk_space -ge 10 ]]; then
        test_passed "磁盘空间充足 (${disk_space}GB >= 10GB)"
    else
        test_failed "磁盘空间不足 (${disk_space}GB < 10GB)"
    fi
}

# 测试Docker环境
test_docker_environment() {
    log_test "检查Docker环境..."
    
    if check_command docker; then
        test_passed "Docker已安装"
        log_info "Docker版本: $(docker --version)"
    else
        test_failed "Docker未安装"
        return
    fi
    
    if check_command docker-compose; then
        test_passed "Docker Compose已安装"
        log_info "Docker Compose版本: $(docker-compose --version)"
    else
        test_failed "Docker Compose未安装"
    fi
    
    # 检查Docker服务状态
    if systemctl is-active --quiet docker; then
        test_passed "Docker服务运行中"
    else
        test_failed "Docker服务未运行"
    fi
    
    # 检查Docker权限
    if docker ps &>/dev/null; then
        test_passed "Docker权限正常"
    else
        test_failed "Docker权限不足，可能需要sudo或将用户加入docker组"
    fi
}

# 测试原生环境
test_native_environment() {
    log_test "检查原生环境..."
    
    # 检查Python
    if check_command python3; then
        test_passed "Python3已安装"
        log_info "Python版本: $(python3 --version)"
    else
        test_failed "Python3未安装"
    fi
    
    # 检查Node.js
    if check_command node; then
        test_passed "Node.js已安装"
        log_info "Node.js版本: $(node --version)"
    else
        test_failed "Node.js未安装"
    fi
    
    # 检查Nginx
    if check_command nginx; then
        test_passed "Nginx已安装"
        log_info "Nginx版本: $(nginx -v 2>&1)"
    else
        test_failed "Nginx未安装"
    fi
    
    # 检查SQLite
    if check_command sqlite3; then
        test_passed "SQLite3已安装"
        log_info "SQLite版本: $(sqlite3 --version)"
    else
        test_failed "SQLite3未安装"
    fi
}

# 测试网络连接
test_network_connectivity() {
    log_test "检查网络连接..."
    
    # 测试常用端口
    local ports=("80" "443" "8000")
    for port in "${ports[@]}"; do
        if check_port "localhost" "$port" 2; then
            test_passed "端口 $port 可访问"
        else
            test_failed "端口 $port 不可访问"
        fi
    done
    
    # 测试外网连接
    if ping -c 1 8.8.8.8 &>/dev/null; then
        test_passed "外网连接正常"
    else
        test_failed "外网连接失败"
    fi
    
    # 测试DNS解析
    if nslookup google.com &>/dev/null; then
        test_passed "DNS解析正常"
    else
        test_failed "DNS解析失败"
    fi
}

# 测试配置文件
test_configuration_files() {
    log_test "检查配置文件..."
    
    # 检查.env文件
    if [[ -f .env ]]; then
        test_passed ".env文件存在"
        
        # 检查必要的环境变量
        local required_vars=("SECRET_KEY" "DATABASE_URL")
        for var in "${required_vars[@]}"; do
            if grep -q "^$var=" .env; then
                test_passed "环境变量 $var 已配置"
            else
                test_failed "环境变量 $var 未配置"
            fi
        done
    else
        test_failed ".env文件不存在"
        log_warn "请从.env.example复制并配置.env文件"
    fi
    
    # 检查部署配置文件
    local config_files=(
        "deployment/docker/docker-compose.yml"
        "deployment/nginx/workflow.conf"
        "deployment/scripts/deploy.sh"
        "deployment/scripts/start.sh"
    )
    
    for file in "${config_files[@]}"; do
        if [[ -f "$file" ]]; then
            test_passed "配置文件存在: $file"
        else
            test_failed "配置文件缺失: $file"
        fi
    done
}

# 测试Docker部署
test_docker_deployment() {
    log_test "测试Docker部署..."
    
    cd deployment/docker || return 1
    
    # 检查Docker Compose配置
    if docker-compose config &>/dev/null; then
        test_passed "Docker Compose配置有效"
    else
        test_failed "Docker Compose配置无效"
        cd ../..
        return 1
    fi
    
    # 检查容器状态
    local containers=$(docker-compose ps -q)
    if [[ -n "$containers" ]]; then
        local running_containers=$(docker-compose ps | grep "Up" | wc -l)
        if [[ $running_containers -gt 0 ]]; then
            test_passed "Docker容器运行中 ($running_containers 个)"
        else
            test_failed "Docker容器未运行"
        fi
    else
        test_failed "未找到Docker容器"
    fi
    
    cd ../..
}

# 测试原生部署
test_native_deployment() {
    log_test "测试原生部署..."
    
    # 检查后端服务
    if systemctl is-active --quiet workflow-backend; then
        test_passed "后端服务运行中"
        log_info "后端服务状态: $(systemctl is-active workflow-backend)"
    else
        test_failed "后端服务未运行"
    fi
    
    # 检查Nginx服务
    if systemctl is-active --quiet nginx; then
        test_passed "Nginx服务运行中"
        log_info "Nginx服务状态: $(systemctl is-active nginx)"
    else
        test_failed "Nginx服务未运行"
    fi
    
    # 检查数据库文件
    if [[ -f "workflow.db" ]]; then
        test_passed "数据库文件存在"
        
        # 检查数据库完整性
        if sqlite3 workflow.db "PRAGMA integrity_check;" | grep -q "ok"; then
            test_passed "数据库完整性检查通过"
        else
            test_failed "数据库完整性检查失败"
        fi
    else
        test_failed "数据库文件不存在"
    fi
}

# 测试应用服务
test_application_services() {
    log_test "测试应用服务..."
    
    local base_url="http://localhost"
    
    # 测试前端页面
    if test_http_request "$base_url" 200 10; then
        test_passed "前端页面可访问"
    else
        test_failed "前端页面不可访问"
    fi
    
    # 测试API健康检查
    if test_http_request "$base_url/api/test/health" 200 10; then
        test_passed "后端API健康检查通过"
    else
        test_failed "后端API健康检查失败"
    fi
    
    # 测试API文档
    if test_http_request "$base_url/docs" 200 10; then
        test_passed "API文档可访问"
    else
        test_failed "API文档不可访问"
    fi
    
    # 测试静态资源
    if test_http_request "$base_url/favicon.ico" 200 5; then
        test_passed "静态资源可访问"
    else
        test_failed "静态资源不可访问"
    fi
}

# 测试API端点
test_api_endpoints() {
    log_test "测试API端点..."
    
    local api_base="http://localhost/api"
    
    # 测试基础API端点
    local endpoints=("test/health" "auth/register" "users/me")
    
    for endpoint in "${endpoints[@]}"; do
        local url="$api_base/$endpoint"
        local response_code
        
        if check_command curl; then
            response_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo "000")
        else
            response_code="000"
        fi
        
        # 不同端点期望不同的响应码
        case $endpoint in
            "test/health")
                if [[ "$response_code" == "200" ]]; then
                    test_passed "API端点可访问: $endpoint"
                else
                    test_failed "API端点不可访问: $endpoint (HTTP $response_code)"
                fi
                ;;
            "auth/register"|"users/me")
                if [[ "$response_code" =~ ^(200|401|422)$ ]]; then
                    test_passed "API端点响应正常: $endpoint"
                else
                    test_failed "API端点响应异常: $endpoint (HTTP $response_code)"
                fi
                ;;
        esac
    done
}

# 测试数据库连接
test_database_connection() {
    log_test "测试数据库连接..."
    
    local deployment_type=$(detect_deployment_type)
    
    case $deployment_type in
        "docker")
            # Docker环境中测试数据库
            if docker-compose -f deployment/docker/docker-compose.yml exec -T backend python -c "
from workflow_framework.utils.database import get_database_connection
import asyncio
async def test_db():
    try:
        conn = await get_database_connection()
        await conn.close()
        print('SUCCESS')
    except Exception as e:
        print(f'ERROR: {e}')
asyncio.run(test_db())
            " 2>/dev/null | grep -q "SUCCESS"; then
                test_passed "Docker数据库连接正常"
            else
                test_failed "Docker数据库连接失败"
            fi
            ;;
        "native")
            # 原生环境中测试数据库
            if [[ -f "workflow.db" ]]; then
                if sqlite3 workflow.db "SELECT 1;" &>/dev/null; then
                    test_passed "原生数据库连接正常"
                else
                    test_failed "原生数据库连接失败"
                fi
            else
                test_failed "数据库文件不存在"
            fi
            ;;
        *)
            test_failed "无法检测部署类型，跳过数据库测试"
            ;;
    esac
}

# 性能测试
test_performance() {
    log_test "执行性能测试..."
    
    local base_url="http://localhost"
    
    if check_command curl; then
        # 测试响应时间
        local response_time=$(curl -s -o /dev/null -w "%{time_total}" --max-time 10 "$base_url" 2>/dev/null || echo "999")
        local response_time_ms=$(echo "$response_time * 1000" | bc 2>/dev/null || echo "999")
        
        if (( $(echo "$response_time < 2.0" | bc -l 2>/dev/null || echo 0) )); then
            test_passed "响应时间良好 (${response_time_ms%.*}ms)"
        else
            test_failed "响应时间过长 (${response_time_ms%.*}ms)"
        fi
        
        # 简单的并发测试
        log_info "执行简单并发测试 (5个并发请求)..."
        local success_count=0
        for i in {1..5}; do
            if curl -s --max-time 5 "$base_url" >/dev/null 2>&1; then
                ((success_count++))
            fi &
        done
        wait
        
        if [[ $success_count -ge 4 ]]; then
            test_passed "并发测试通过 ($success_count/5 成功)"
        else
            test_failed "并发测试失败 ($success_count/5 成功)"
        fi
    else
        test_failed "curl命令不可用，跳过性能测试"
    fi
}

# 安全测试
test_security() {
    log_test "执行安全检查..."
    
    local base_url="http://localhost"
    
    # 检查安全头
    if check_command curl; then
        local headers=$(curl -s -I "$base_url" 2>/dev/null)
        
        if echo "$headers" | grep -qi "x-frame-options"; then
            test_passed "X-Frame-Options安全头存在"
        else
            test_failed "X-Frame-Options安全头缺失"
        fi
        
        if echo "$headers" | grep -qi "x-content-type-options"; then
            test_passed "X-Content-Type-Options安全头存在"
        else
            test_failed "X-Content-Type-Options安全头缺失"
        fi
    fi
    
    # 检查默认密钥
    if [[ -f .env ]] && grep -q "your-super-secret-jwt-key-change-this-in-production" .env; then
        test_failed "使用默认JWT密钥，存在安全风险"
    else
        test_passed "JWT密钥已自定义"
    fi
}

# 生成测试报告
generate_test_report() {
    echo
    echo "=================================="
    echo "        测试报告 / Test Report"
    echo "=================================="
    echo
    echo "测试时间: $(date)"
    echo "部署类型: $(detect_deployment_type)"
    echo
    echo "测试结果统计:"
    echo "  ✓ 通过: $TESTS_PASSED"
    echo "  ✗ 失败: $TESTS_FAILED"
    echo "  📊 总计: $TESTS_TOTAL"
    echo
    
    if [[ $TESTS_FAILED -eq 0 ]]; then
        echo -e "${GREEN}🎉 所有测试通过！部署成功！${NC}"
        echo
        echo "您可以通过以下方式访问应用:"
        echo "  前端: http://localhost"
        echo "  API文档: http://localhost/docs"
        echo "  健康检查: http://localhost/api/test/health"
        return 0
    else
        echo -e "${RED}❌ 部分测试失败，请检查上述错误信息${NC}"
        echo
        echo "故障排除建议:"
        echo "  1. 检查服务状态: ./deployment/scripts/start.sh status"
        echo "  2. 查看日志: ./deployment/scripts/start.sh logs"
        echo "  3. 重启服务: ./deployment/scripts/start.sh restart"
        return 1
    fi
}

# 主测试函数
main() {
    echo "开始部署测试..."
    echo "=================="
    echo
    
    # 检测部署类型
    local deployment_type=$(detect_deployment_type)
    log_info "检测到部署类型: $deployment_type"
    echo
    
    # 执行测试
    test_system_requirements
    echo
    
    test_network_connectivity
    echo
    
    test_configuration_files
    echo
    
    case $deployment_type in
        "docker")
            test_docker_environment
            echo
            test_docker_deployment
            ;;
        "native")
            test_native_environment
            echo
            test_native_deployment
            ;;
        "unknown")
            log_warn "无法检测部署类型，执行通用测试"
            test_docker_environment
            test_native_environment
            ;;
    esac
    echo
    
    test_application_services
    echo
    
    test_api_endpoints
    echo
    
    test_database_connection
    echo
    
    test_performance
    echo
    
    test_security
    echo
    
    # 生成报告
    generate_test_report
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi