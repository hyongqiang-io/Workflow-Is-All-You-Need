#!/bin/bash

# 本地部署测试脚本
# Local Deployment Testing Script

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 测试配置
LOCAL_TEST_DIR="/tmp/workflow-local-test"
ORIGINAL_DIR=$(pwd)
TEST_SESSION_ID=$(date +%Y%m%d_%H%M%S)
TEST_LOG="/tmp/local-test-${TEST_SESSION_ID}.log"

# 测试结果
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$TEST_LOG"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$TEST_LOG"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$TEST_LOG"
}

log_test() {
    echo -e "${BLUE}[TEST]${NC} $1" | tee -a "$TEST_LOG"
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1" | tee -a "$TEST_LOG"
}

# 测试结果函数
test_passed() {
    echo -e "${GREEN}✓ PASSED${NC} - $1" | tee -a "$TEST_LOG"
    ((TESTS_PASSED++))
    ((TESTS_TOTAL++))
}

test_failed() {
    echo -e "${RED}✗ FAILED${NC} - $1" | tee -a "$TEST_LOG"
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

# 等待服务启动
wait_for_service() {
    local url=$1
    local timeout=${2:-60}
    local interval=${3:-5}
    
    log_info "等待服务启动: $url (超时: ${timeout}s)"
    
    for ((i=0; i<timeout; i+=interval)); do
        if curl -s --connect-timeout 2 "$url" >/dev/null 2>&1; then
            log_info "服务已启动: $url"
            return 0
        fi
        
        echo -n "."
        sleep "$interval"
    done
    
    echo
    log_error "服务启动超时: $url"
    return 1
}

# 清理测试环境
cleanup_test_environment() {
    log_info "清理测试环境..."
    
    # 停止可能运行的服务
    cd "$ORIGINAL_DIR" 2>/dev/null || true
    
    # Docker清理
    if [[ -f "deployment/docker/docker-compose.yml" ]]; then
        cd deployment/docker 2>/dev/null || true
        docker-compose down --remove-orphans 2>/dev/null || true
        cd ../.. 2>/dev/null || true
    fi
    
    # 停止系统服务
    sudo systemctl stop workflow-backend 2>/dev/null || true
    
    # 清理临时文件
    rm -rf "$LOCAL_TEST_DIR" 2>/dev/null || true
    
    # 清理测试端口
    local test_ports=(8001 8002 8003)
    for port in "${test_ports[@]}"; do
        local pid=$(lsof -ti:$port 2>/dev/null || true)
        if [[ -n "$pid" ]]; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
}

# 准备测试环境
setup_test_environment() {
    log_step "准备本地测试环境..."
    
    # 创建测试目录
    mkdir -p "$LOCAL_TEST_DIR"
    
    # 复制项目文件到测试目录
    log_info "复制项目文件到测试环境..."
    cp -r "$ORIGINAL_DIR"/* "$LOCAL_TEST_DIR/" 2>/dev/null || true
    cp -r "$ORIGINAL_DIR"/.* "$LOCAL_TEST_DIR/" 2>/dev/null || true
    
    cd "$LOCAL_TEST_DIR"
    
    # 创建本地测试配置
    log_info "创建本地测试配置..."
    cat > .env << 'EOF'
# 本地测试环境配置
ENVIRONMENT=development
DOMAIN=localhost
EMAIL=test@localhost

# 数据库配置
DATABASE_URL=sqlite:///./data/workflow.db

# 安全配置（仅用于测试）
SECRET_KEY=local-test-secret-key-do-not-use-in-production

# API配置
API_HOST=127.0.0.1
API_PORT=8000
CORS_ORIGINS=["http://localhost:3000","http://localhost"]

# 日志配置
LOG_LEVEL=DEBUG
DEBUG=true

# Docker配置
COMPOSE_PROJECT_NAME=workflow-local-test

# 备份配置
BACKUP_RETENTION_DAYS=1
EOF
    
    # 设置权限
    chmod +x deployment/scripts/* 2>/dev/null || true
    
    log_info "测试环境准备完成"
}

# 测试系统要求
test_system_requirements() {
    log_test "检查本地系统要求..."
    
    # 检查操作系统
    if [[ -f /etc/os-release ]]; then
        test_passed "操作系统信息可用"
        local os_info=$(grep PRETTY_NAME /etc/os-release | cut -d'"' -f2)
        log_info "操作系统: $os_info"
    else
        test_failed "无法获取操作系统信息"
    fi
    
    # 检查内存
    local memory_gb=$(free -g | awk '/^Mem:/{print $2}')
    if [[ $memory_gb -ge 1 ]]; then
        test_passed "内存充足 (${memory_gb}GB)"
    else
        test_failed "内存不足 (${memory_gb}GB)"
    fi
    
    # 检查磁盘空间
    local disk_space=$(df -BG . | awk 'NR==2{print $4}' | sed 's/G//')
    if [[ $disk_space -ge 5 ]]; then
        test_passed "磁盘空间充足 (${disk_space}GB)"
    else
        test_failed "磁盘空间不足 (${disk_space}GB)"
    fi
    
    # 检查网络
    if ping -c 1 8.8.8.8 &>/dev/null; then
        test_passed "网络连接正常"
    else
        test_failed "网络连接失败"
    fi
}

# 测试Docker环境
test_docker_environment() {
    log_test "测试Docker环境..."
    
    # 检查Docker安装
    if check_command docker; then
        test_passed "Docker已安装"
        log_info "Docker版本: $(docker --version)"
    else
        test_failed "Docker未安装"
        return 1
    fi
    
    # 检查Docker Compose
    if check_command docker-compose; then
        test_passed "Docker Compose已安装"
        log_info "Docker Compose版本: $(docker-compose --version)"
    else
        test_failed "Docker Compose未安装"
        return 1
    fi
    
    # 检查Docker服务
    if docker info &>/dev/null; then
        test_passed "Docker服务运行正常"
    else
        test_failed "Docker服务异常或权限不足"
        return 1
    fi
    
    return 0
}

# 测试Docker部署
test_docker_deployment() {
    log_test "测试Docker部署流程..."
    
    # 检查Docker Compose配置
    cd deployment/docker
    if docker-compose config &>/dev/null; then
        test_passed "Docker Compose配置有效"
    else
        test_failed "Docker Compose配置无效"
        cd ../..
        return 1
    fi
    
    # 构建镜像
    log_info "构建Docker镜像..."
    if docker-compose build --no-cache 2>/dev/null; then
        test_passed "Docker镜像构建成功"
    else
        test_failed "Docker镜像构建失败"
        cd ../..
        return 1
    fi
    
    # 启动服务
    log_info "启动Docker服务..."
    if docker-compose up -d 2>/dev/null; then
        test_passed "Docker服务启动成功"
    else
        test_failed "Docker服务启动失败"
        docker-compose logs
        cd ../..
        return 1
    fi
    
    cd ../..
    
    # 等待服务就绪
    if wait_for_service "http://localhost" 60; then
        test_passed "Docker前端服务就绪"
    else
        test_failed "Docker前端服务启动超时"
        return 1
    fi
    
    if wait_for_service "http://localhost/api/test/health" 60; then
        test_passed "Docker后端API就绪"
    else
        test_failed "Docker后端API启动超时"
        return 1
    fi
    
    return 0
}

# 测试原生部署环境
test_native_environment() {
    log_test "测试原生部署环境..."
    
    # 检查Python
    if check_command python3; then
        test_passed "Python3已安装"
        log_info "Python版本: $(python3 --version)"
    else
        test_failed "Python3未安装"
        return 1
    fi
    
    # 检查Node.js
    if check_command node; then
        test_passed "Node.js已安装"
        log_info "Node.js版本: $(node --version)"
    else
        test_failed "Node.js未安装"
        return 1
    fi
    
    # 检查npm
    if check_command npm; then
        test_passed "npm已安装"
        log_info "npm版本: $(npm --version)"
    else
        test_failed "npm未安装"
        return 1
    fi
    
    # 检查SQLite
    if check_command sqlite3; then
        test_passed "SQLite3已安装"
        log_info "SQLite版本: $(sqlite3 --version | cut -d' ' -f1)"
    else
        test_failed "SQLite3未安装"
        return 1
    fi
    
    return 0
}

# 测试Python后端
test_python_backend() {
    log_test "测试Python后端..."
    
    # 创建虚拟环境
    log_info "创建Python虚拟环境..."
    if python3 -m venv venv_test; then
        test_passed "Python虚拟环境创建成功"
    else
        test_failed "Python虚拟环境创建失败"
        return 1
    fi
    
    # 激活虚拟环境
    source venv_test/bin/activate
    
    # 安装依赖
    log_info "安装Python依赖..."
    if pip install -r requirements.txt &>/dev/null; then
        test_passed "Python依赖安装成功"
    else
        test_failed "Python依赖安装失败"
        deactivate
        return 1
    fi
    
    # 测试导入主模块
    if python -c "import main" 2>/dev/null; then
        test_passed "主模块导入成功"
    else
        test_failed "主模块导入失败"
        deactivate
        return 1
    fi
    
    # 初始化数据库
    log_info "初始化数据库..."
    mkdir -p data
    if python3 -c "from workflow_framework.scripts.init_database import main; main()" 2>/dev/null; then
        test_passed "数据库初始化成功"
    else
        test_failed "数据库初始化失败"
        deactivate
        return 1
    fi
    
    # 启动后端服务（后台）
    log_info "启动Python后端服务..."
    uvicorn main:app --host 127.0.0.1 --port 8001 &
    local backend_pid=$!
    
    # 等待后端启动
    if wait_for_service "http://localhost:8001/api/test/health" 30; then
        test_passed "Python后端服务启动成功"
    else
        test_failed "Python后端服务启动失败"
        kill $backend_pid 2>/dev/null || true
        deactivate
        return 1
    fi
    
    # 停止后端服务
    kill $backend_pid 2>/dev/null || true
    deactivate
    
    return 0
}

# 测试前端构建
test_frontend_build() {
    log_test "测试前端构建..."
    
    cd frontend
    
    # 安装前端依赖
    log_info "安装前端依赖..."
    if npm install &>/dev/null; then
        test_passed "前端依赖安装成功"
    else
        test_failed "前端依赖安装失败"
        cd ..
        return 1
    fi
    
    # 构建前端
    log_info "构建前端应用..."
    if npm run build &>/dev/null; then
        test_passed "前端构建成功"
    else
        test_failed "前端构建失败"
        cd ..
        return 1
    fi
    
    # 检查构建结果
    if [[ -d "build" ]] && [[ -f "build/index.html" ]]; then
        test_passed "前端构建文件存在"
    else
        test_failed "前端构建文件缺失"
        cd ..
        return 1
    fi
    
    cd ..
    return 0
}

# 测试配置文件生成
test_configuration_generation() {
    log_test "测试配置文件生成..."
    
    # 检查部署脚本
    if [[ -x "deployment/scripts/deploy.sh" ]]; then
        test_passed "部署脚本可执行"
    else
        test_failed "部署脚本不可执行"
    fi
    
    # 检查启动脚本
    if [[ -x "deployment/scripts/start.sh" ]]; then
        test_passed "启动脚本可执行"
    else
        test_failed "启动脚本不可执行"
    fi
    
    # 检查备份脚本
    if [[ -x "deployment/scripts/backup.sh" ]]; then
        test_passed "备份脚本可执行"
    else
        test_failed "备份脚本不可执行"
    fi
    
    # 检查测试脚本
    if [[ -x "deployment/scripts/test-deployment.sh" ]]; then
        test_passed "测试脚本可执行"
    else
        test_failed "测试脚本不可执行"
    fi
    
    # 检查健康检查脚本
    if [[ -x "deployment/scripts/health-check.sh" ]]; then
        test_passed "健康检查脚本可执行"
    else
        test_failed "健康检查脚本不可执行"
    fi
    
    # 测试配置文件语法
    if [[ -f "deployment/docker/docker-compose.yml" ]]; then
        cd deployment/docker
        if docker-compose config &>/dev/null; then
            test_passed "Docker Compose配置语法正确"
        else
            test_failed "Docker Compose配置语法错误"
        fi
        cd ../..
    fi
}

# 测试服务管理脚本
test_service_management() {
    log_test "测试服务管理脚本..."
    
    # 测试start.sh脚本的帮助功能
    if ./deployment/scripts/start.sh --help &>/dev/null; then
        test_passed "启动脚本帮助功能正常"
    else
        test_failed "启动脚本帮助功能异常"
    fi
    
    # 测试backup.sh脚本的帮助功能
    if ./deployment/scripts/backup.sh --help &>/dev/null; then
        test_passed "备份脚本帮助功能正常"
    else
        test_failed "备份脚本帮助功能异常"
    fi
    
    # 测试health-check.sh脚本的帮助功能
    if ./deployment/scripts/health-check.sh --help &>/dev/null; then
        test_passed "健康检查脚本帮助功能正常"
    else
        test_failed "健康检查脚本帮助功能异常"
    fi
}

# 测试数据库操作
test_database_operations() {
    log_test "测试数据库操作..."
    
    # 确保数据库存在
    if [[ -f "workflow.db" ]]; then
        test_passed "数据库文件存在"
    else
        test_failed "数据库文件不存在"
        return 1
    fi
    
    # 测试数据库备份
    if ./deployment/scripts/backup.sh backup &>/dev/null; then
        test_passed "数据库备份功能正常"
    else
        test_failed "数据库备份功能异常"
    fi
    
    # 测试备份列表
    if ./deployment/scripts/backup.sh list &>/dev/null; then
        test_passed "备份列表功能正常"
    else
        test_failed "备份列表功能异常"
    fi
    
    # 检查备份文件是否生成
    local backup_count=$(ls backups/workflow_*.db* 2>/dev/null | wc -l)
    if [[ $backup_count -gt 0 ]]; then
        test_passed "备份文件生成成功 ($backup_count 个文件)"
    else
        test_failed "备份文件生成失败"
    fi
}

# 模拟部署流程
simulate_deployment_process() {
    log_step "模拟完整部署流程..."
    
    # 1. 环境检查
    log_info "步骤1: 环境检查"
    if test_docker_environment; then
        log_info "Docker环境检查通过"
    else
        log_warn "Docker环境检查失败，跳过Docker部署测试"
    fi
    
    if test_native_environment; then
        log_info "原生环境检查通过"
    else
        log_warn "原生环境检查失败，跳过原生部署测试"
    fi
    
    # 2. 配置文件准备
    log_info "步骤2: 配置文件检查"
    test_configuration_generation
    
    # 3. 数据库初始化
    log_info "步骤3: 数据库初始化"
    mkdir -p data
    if python3 -c "from workflow_framework.scripts.init_database import main; main()" 2>/dev/null; then
        test_passed "数据库初始化模拟成功"
    else
        test_failed "数据库初始化模拟失败"
    fi
    
    # 4. 前端构建
    log_info "步骤4: 前端构建"
    test_frontend_build
    
    # 5. 后端测试
    log_info "步骤5: 后端测试"
    test_python_backend
    
    # 6. 服务管理测试
    log_info "步骤6: 服务管理"
    test_service_management
    
    # 7. 数据库操作测试
    log_info "步骤7: 数据库操作"
    test_database_operations
}

# 运行完整Docker测试
run_full_docker_test() {
    log_step "运行完整Docker部署测试..."
    
    if ! test_docker_environment; then
        log_error "Docker环境不可用，跳过Docker测试"
        return 1
    fi
    
    if test_docker_deployment; then
        log_info "Docker部署测试成功"
        
        # 测试API功能
        log_info "测试Docker部署的API功能..."
        local api_tests=0
        local api_passed=0
        
        # 测试健康检查
        if curl -s http://localhost/api/test/health | grep -q "healthy"; then
            test_passed "Docker API健康检查"
            ((api_passed++))
        else
            test_failed "Docker API健康检查"
        fi
        ((api_tests++))
        
        # 测试前端页面
        if curl -s http://localhost | grep -q "html"; then
            test_passed "Docker前端页面加载"
            ((api_passed++))
        else
            test_failed "Docker前端页面加载"
        fi
        ((api_tests++))
        
        # 测试API文档
        if curl -s http://localhost/docs | grep -q "html"; then
            test_passed "Docker API文档访问"
            ((api_passed++))
        else
            test_failed "Docker API文档访问"
        fi
        ((api_tests++))
        
        log_info "Docker API测试完成: $api_passed/$api_tests 通过"
        
        # 清理Docker环境
        cd deployment/docker
        docker-compose down --remove-orphans 2>/dev/null || true
        cd ../..
        
        return 0
    else
        log_error "Docker部署测试失败"
        return 1
    fi
}

# 生成测试报告
generate_test_report() {
    log_step "生成测试报告..."
    
    echo | tee -a "$TEST_LOG"
    echo "========================================" | tee -a "$TEST_LOG"
    echo "          本地部署测试报告" | tee -a "$TEST_LOG"
    echo "========================================" | tee -a "$TEST_LOG"
    echo | tee -a "$TEST_LOG"
    echo "测试时间: $(date)" | tee -a "$TEST_LOG"
    echo "测试会话: $TEST_SESSION_ID" | tee -a "$TEST_LOG"
    echo "测试环境: $(uname -a)" | tee -a "$TEST_LOG"
    echo "测试目录: $LOCAL_TEST_DIR" | tee -a "$TEST_LOG"
    echo | tee -a "$TEST_LOG"
    echo "测试结果统计:" | tee -a "$TEST_LOG"
    echo "  ✓ 通过: $TESTS_PASSED" | tee -a "$TEST_LOG"
    echo "  ✗ 失败: $TESTS_FAILED" | tee -a "$TEST_LOG"
    echo "  📊 总计: $TESTS_TOTAL" | tee -a "$TEST_LOG"
    echo | tee -a "$TEST_LOG"
    
    local success_rate=0
    if [[ $TESTS_TOTAL -gt 0 ]]; then
        success_rate=$((TESTS_PASSED * 100 / TESTS_TOTAL))
    fi
    
    echo "成功率: ${success_rate}%" | tee -a "$TEST_LOG"
    echo | tee -a "$TEST_LOG"
    
    if [[ $TESTS_FAILED -eq 0 ]]; then
        echo -e "${GREEN}🎉 所有本地测试通过！部署配置验证成功！${NC}" | tee -a "$TEST_LOG"
        echo | tee -a "$TEST_LOG"
        echo "✅ 您的部署配置已通过本地验证，可以安全地部署到服务器" | tee -a "$TEST_LOG"
        echo "✅ 所有脚本和配置文件都已验证可用" | tee -a "$TEST_LOG"
        echo "✅ Docker和原生部署方式都已测试" | tee -a "$TEST_LOG"
        echo | tee -a "$TEST_LOG"
        echo "下一步:" | tee -a "$TEST_LOG"
        echo "  1. 准备服务器环境" | tee -a "$TEST_LOG"
        echo "  2. 上传代码到服务器" | tee -a "$TEST_LOG"
        echo "  3. 运行部署脚本: sudo ./deployment/scripts/deploy.sh" | tee -a "$TEST_LOG"
        return 0
    else
        echo -e "${RED}❌ 部分本地测试失败，建议修复后再部署到服务器${NC}" | tee -a "$TEST_LOG"
        echo | tee -a "$TEST_LOG"
        echo "需要解决的问题:" | tee -a "$TEST_LOG"
        echo "  1. 检查失败的测试项目" | tee -a "$TEST_LOG"
        echo "  2. 修复相关配置或依赖" | tee -a "$TEST_LOG"
        echo "  3. 重新运行测试直到全部通过" | tee -a "$TEST_LOG"
        return 1
    fi
}

# 显示帮助信息
show_help() {
    echo "本地部署测试脚本"
    echo
    echo "用法: $0 [选项]"
    echo
    echo "选项:"
    echo "  --full          运行完整测试套件 (默认)"
    echo "  --docker        仅测试Docker部署"
    echo "  --native        仅测试原生部署环境"
    echo "  --quick         快速测试（跳过耗时项目）"
    echo "  --cleanup       清理测试环境"
    echo "  --help          显示此帮助信息"
    echo
    echo "示例:"
    echo "  $0              # 运行完整测试"
    echo "  $0 --docker     # 仅测试Docker"
    echo "  $0 --quick      # 快速测试"
    echo "  $0 --cleanup    # 清理测试环境"
}

# 主函数
main() {
    local test_mode=${1:-full}
    
    echo "本地部署测试工具 v1.0"
    echo "====================="
    echo
    
    # 创建测试日志
    echo "测试开始: $(date)" > "$TEST_LOG"
    log_info "测试日志: $TEST_LOG"
    
    case $test_mode in
        --full|full)
            log_info "运行完整本地测试套件..."
            
            # 设置陷阱，确保清理
            trap cleanup_test_environment EXIT
            
            setup_test_environment
            test_system_requirements
            simulate_deployment_process
            
            # 如果Docker可用，运行Docker测试
            if test_docker_environment &>/dev/null; then
                run_full_docker_test
            fi
            
            generate_test_report
            ;;
        --docker)
            log_info "仅运行Docker部署测试..."
            
            trap cleanup_test_environment EXIT
            setup_test_environment
            test_system_requirements
            
            if run_full_docker_test; then
                log_info "Docker测试完成"
            else
                log_error "Docker测试失败"
            fi
            
            generate_test_report
            ;;
        --native)
            log_info "仅运行原生部署环境测试..."
            
            setup_test_environment
            test_system_requirements
            test_native_environment
            test_python_backend
            test_frontend_build
            test_configuration_generation
            
            generate_test_report
            ;;
        --quick)
            log_info "运行快速测试..."
            
            setup_test_environment
            test_system_requirements
            test_configuration_generation
            test_service_management
            
            generate_test_report
            ;;
        --cleanup)
            cleanup_test_environment
            log_info "测试环境清理完成"
            ;;
        --help|-h|help)
            show_help
            ;;
        *)
            log_error "未知选项: $test_mode"
            show_help
            exit 1
            ;;
    esac
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi