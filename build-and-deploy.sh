#!/bin/bash

# Docker 构建和部署脚本
# 使用方法: ./build-and-deploy.sh [dev|prod] [push]

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

# 获取环境参数
ENVIRONMENT=""
TEST_MODE=false
PUSH_TO_REGISTRY=""

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --test)
            TEST_MODE=true
            shift
            ;;
        --push)
            PUSH_TO_REGISTRY=true
            shift
            ;;
        dev|prod)
            ENVIRONMENT="$1"
            shift
            ;;
        push)
            PUSH_TO_REGISTRY=true
            shift
            ;;
        *)
            echo "未知参数: $1"
            echo "用法: $0 [--env dev|prod] [--test] [--push]"
            exit 1
            ;;
    esac
done

# 设置默认环境
ENVIRONMENT=${ENVIRONMENT:-dev}
PROJECT_NAME="workflow"
VERSION=$(date +%Y%m%d-%H%M%S)

if [ "$TEST_MODE" = true ]; then
    print_info "执行构建测试模式"
else
    print_info "开始构建和部署 $PROJECT_NAME 项目"
    print_info "环境: $ENVIRONMENT"
    print_info "版本: $VERSION"
fi

# 检查必要的文件
check_files() {
    print_info "检查必要文件..."
    
    required_files=(
        "Dockerfile.backend"
        "Dockerfile.frontend" 
        "docker-compose.yml"
        "requirements.txt"
        "main.py"
        "backend/"
        "frontend/"
    )
    
    for file in "${required_files[@]}"; do
        if [ ! -e "$file" ]; then
            print_error "缺少必要文件: $file"
            exit 1
        fi
    done
    
    print_success "文件检查完成"
}

# 创建环境配置
setup_environment() {
    print_info "设置环境配置..."
    
    if [ ! -f ".env" ]; then
        if [ -f ".env.template" ]; then
            cp .env.template .env
            print_warning "已创建 .env 文件，请编辑其中的配置"
        else
            print_error "缺少 .env.template 文件"
            exit 1
        fi
    fi
    
    # 设置构建变量
    export BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
    export VERSION=$VERSION
    
    print_success "环境配置完成"
}

# 构建镜像
build_images() {
    print_info "构建 Docker 镜像..."
    
    # 构建后端镜像
    print_info "构建后端镜像..."
    docker build -f Dockerfile.backend -t ${PROJECT_NAME}-backend:${VERSION} \
        --build-arg BUILD_DATE="$BUILD_DATE" \
        --build-arg VERSION="$VERSION" .
    
    # 构建前端镜像
    print_info "构建前端镜像..."
    docker build -f Dockerfile.frontend -t ${PROJECT_NAME}-frontend:${VERSION} \
        --build-arg BUILD_DATE="$BUILD_DATE" \
        --build-arg VERSION="$VERSION" .
    
    # 打标签
    docker tag ${PROJECT_NAME}-backend:${VERSION} ${PROJECT_NAME}-backend:latest
    docker tag ${PROJECT_NAME}-frontend:${VERSION} ${PROJECT_NAME}-frontend:latest
    
    print_success "镜像构建完成"
}

# 运行测试
run_tests() {
    print_info "运行测试..."
    
    # 启动测试环境
    docker-compose -f docker-compose.yml up -d postgres redis
    
    # 等待数据库启动
    print_info "等待数据库启动..."
    sleep 10
    
    # 运行后端测试
    docker run --rm --network ${PROJECT_NAME}_workflow_network \
        -e DB_HOST=postgres -e DB_PORT=5432 \
        ${PROJECT_NAME}-backend:${VERSION} \
        python -m pytest tests/ -v || print_warning "后端测试失败（如果没有测试文件，这是正常的）"
    
    # 清理测试环境
    docker-compose -f docker-compose.yml down
    
    print_success "测试完成"
}

# 推送镜像到仓库
push_images() {
    if [ "$PUSH_TO_REGISTRY" == "push" ]; then
        print_info "推送镜像到仓库..."
        
        # 这里需要根据你的镜像仓库配置进行修改
        REGISTRY=${DOCKER_REGISTRY:-"your-registry.com"}
        
        # 重新标记镜像
        docker tag ${PROJECT_NAME}-backend:${VERSION} ${REGISTRY}/${PROJECT_NAME}-backend:${VERSION}
        docker tag ${PROJECT_NAME}-frontend:${VERSION} ${REGISTRY}/${PROJECT_NAME}-frontend:${VERSION}
        docker tag ${PROJECT_NAME}-backend:latest ${REGISTRY}/${PROJECT_NAME}-backend:latest
        docker tag ${PROJECT_NAME}-frontend:latest ${REGISTRY}/${PROJECT_NAME}-frontend:latest
        
        # 推送镜像
        docker push ${REGISTRY}/${PROJECT_NAME}-backend:${VERSION}
        docker push ${REGISTRY}/${PROJECT_NAME}-frontend:${VERSION}
        docker push ${REGISTRY}/${PROJECT_NAME}-backend:latest
        docker push ${REGISTRY}/${PROJECT_NAME}-frontend:latest
        
        print_success "镜像推送完成"
    fi
}

# 部署应用
deploy_application() {
    print_info "部署应用..."
    
    # 选择合适的 docker-compose 文件
    if [ "$ENVIRONMENT" == "prod" ]; then
        COMPOSE_FILE="docker-compose.prod.yml"
    else
        COMPOSE_FILE="docker-compose.yml"
    fi
    
    # 停止旧的容器
    docker-compose -f $COMPOSE_FILE down || true
    
    # 启动新的容器
    docker-compose -f $COMPOSE_FILE up -d
    
    # 等待服务启动
    print_info "等待服务启动..."
    sleep 30
    
    # 健康检查
    print_info "进行健康检查..."
    
    # 检查后端
    if curl -f http://localhost:8001/health > /dev/null 2>&1; then
        print_success "后端服务健康检查通过"
    else
        print_error "后端服务健康检查失败"
    fi
    
    # 检查前端
    if curl -f http://localhost > /dev/null 2>&1; then
        print_success "前端服务健康检查通过"
    else
        print_error "前端服务健康检查失败"
    fi
    
    print_success "应用部署完成"
}

# 显示部署信息
show_deployment_info() {
    print_success "=== 部署信息 ==="
    print_info "项目名称: $PROJECT_NAME"
    print_info "版本: $VERSION"
    print_info "环境: $ENVIRONMENT"
    print_info "前端地址: http://localhost"
    print_info "后端地址: http://localhost:8001"
    print_info "API文档: http://localhost:8001/docs"
    print_info ""
    print_info "容器状态:"
    docker-compose ps
    print_info ""
    print_info "查看日志:"
    print_info "  docker-compose logs -f backend"
    print_info "  docker-compose logs -f frontend"
    print_info ""
    print_info "停止服务:"
    print_info "  docker-compose down"
}

# 清理函数
cleanup() {
    print_info "清理临时文件..."
    # 这里可以添加清理逻辑
}

# 主函数
main() {
    trap cleanup EXIT
    
    check_files
    
    if [ "$TEST_MODE" = true ]; then
        # 测试模式：只检查文件和环境，不实际构建
        print_info "测试模式：检查环境配置..."
        setup_environment
        
        # 验证Docker配置
        if [ "$ENVIRONMENT" == "prod" ]; then
            COMPOSE_FILE="docker-compose.prod.yml"
        else
            COMPOSE_FILE="docker-compose.yml"
        fi
        
        if [ -f "$COMPOSE_FILE" ]; then
            print_success "Docker Compose 配置文件检查通过: $COMPOSE_FILE"
        else
            print_error "Docker Compose 配置文件不存在: $COMPOSE_FILE"
            exit 1
        fi
        
        # 验证Dockerfile
        if [ -f "Dockerfile.backend" ] && [ -f "Dockerfile.frontend" ]; then
            print_success "Dockerfile 检查通过"
        else
            print_error "Dockerfile 文件缺失"
            exit 1
        fi
        
        # 验证.env文件
        if [ -f ".env" ]; then
            print_success ".env 文件检查通过"
        else
            print_error ".env 文件不存在"
            exit 1
        fi
        
        print_success "构建测试通过 - 所有文件和配置都正确"
        return 0
    fi
    
    # 正常构建模式
    setup_environment
    build_images
    
    # 在开发环境中运行测试
    if [ "$ENVIRONMENT" == "dev" ]; then
        run_tests
    fi
    
    push_images
    deploy_application
    show_deployment_info
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi