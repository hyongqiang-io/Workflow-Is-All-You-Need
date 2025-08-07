#!/bin/bash

# 工作流应用升级脚本
# Workflow Application Upgrade Script

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 日志函数
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 配置
BACKUP_DIR="/opt/backups/workflow-$(date +%Y%m%d_%H%M%S)"
DEPLOYMENT_TYPE=""

# 检测部署类型
detect_deployment_type() {
    if [[ -f "deployment/docker/docker-compose.yml" ]] && docker-compose ps &>/dev/null; then
        DEPLOYMENT_TYPE="docker"
        log_info "检测到Docker部署"
    elif systemctl is-active workflow-backend &>/dev/null; then
        DEPLOYMENT_TYPE="native"
        log_info "检测到原生部署"
    else
        log_error "无法检测部署类型"
        exit 1
    fi
}

# 创建备份
create_backup() {
    log_info "创建升级前备份..."
    
    mkdir -p "$BACKUP_DIR"
    
    # 备份数据库
    ./deployment/scripts/backup.sh backup
    cp backups/workflow_*.db* "$BACKUP_DIR/" 2>/dev/null || true
    
    # 备份配置文件
    cp .env "$BACKUP_DIR/" 2>/dev/null || true
    
    # 备份Docker数据卷（如果是Docker部署）
    if [[ "$DEPLOYMENT_TYPE" == "docker" ]]; then
        cd deployment/docker
        docker-compose exec backend tar czf /tmp/app_backup.tar.gz /app/data /app/logs 2>/dev/null || true
        docker cp $(docker-compose ps -q backend):/tmp/app_backup.tar.gz "$BACKUP_DIR/" 2>/dev/null || true
        cd ../..
    fi
    
    log_info "备份已保存到: $BACKUP_DIR"
}

# 停止服务
stop_services() {
    log_info "停止当前服务..."
    
    if [[ "$DEPLOYMENT_TYPE" == "docker" ]]; then
        cd deployment/docker
        docker-compose down
        cd ../..
    else
        systemctl stop workflow-backend
        systemctl stop nginx
    fi
}

# 更新代码
update_code() {
    log_info "更新应用代码..."
    
    # 这里假设使用git进行代码更新
    if [[ -d ".git" ]]; then
        git fetch origin
        git pull origin main
        log_info "代码更新完成"
    else
        log_warn "未检测到git仓库，跳过代码更新"
    fi
}

# 更新依赖
update_dependencies() {
    log_info "更新依赖项..."
    
    if [[ "$DEPLOYMENT_TYPE" == "docker" ]]; then
        cd deployment/docker
        docker-compose build --no-cache
        cd ../..
    else
        # 更新Python依赖
        source venv/bin/activate
        pip install -r requirements.txt --upgrade
        deactivate
        
        # 更新前端依赖
        cd frontend
        npm install
        npm run build
        cd ..
    fi
}

# 数据库迁移
run_database_migration() {
    log_info "运行数据库迁移..."
    
    if [[ "$DEPLOYMENT_TYPE" == "docker" ]]; then
        cd deployment/docker
        docker-compose run --rm backend python -c "from backend.scripts.init_database import main; main()"
        cd ../..
    else
        source venv/bin/activate
        python -c "from backend.scripts.init_database import main; main()"
        deactivate
    fi
}

# 启动服务
start_services() {
    log_info "启动更新后的服务..."
    
    if [[ "$DEPLOYMENT_TYPE" == "docker" ]]; then
        cd deployment/docker
        docker-compose up -d
        cd ../..
    else
        systemctl start workflow-backend
        systemctl start nginx
    fi
}

# 验证升级
verify_upgrade() {
    log_info "验证升级结果..."
    
    local max_wait=60
    local wait_time=0
    
    while [[ $wait_time -lt $max_wait ]]; do
        if curl -s http://localhost/api/test/health | grep -q "healthy"; then
            log_info "✅ 服务验证成功"
            return 0
        fi
        
        sleep 5
        ((wait_time+=5))
    done
    
    log_error "❌ 服务验证失败"
    return 1
}

# 回滚
rollback() {
    log_warn "开始回滚到升级前状态..."
    
    # 停止服务
    stop_services
    
    # 恢复配置文件
    cp "$BACKUP_DIR/.env" ./ 2>/dev/null || true
    
    # 恢复数据库
    if [[ -f "$BACKUP_DIR/workflow_"*.db ]]; then
        cp "$BACKUP_DIR/workflow_"*.db ./data/ 2>/dev/null || true
    fi
    
    # 恢复Docker数据（如果需要）
    if [[ "$DEPLOYMENT_TYPE" == "docker" ]] && [[ -f "$BACKUP_DIR/app_backup.tar.gz" ]]; then
        cd deployment/docker
        docker-compose run --rm backend tar xzf /tmp/app_backup.tar.gz -C / 2>/dev/null || true
        cd ../..
    fi
    
    # 重启服务
    start_services
    
    log_info "回滚完成"
}

# 清理
cleanup() {
    log_info "清理临时文件..."
    
    # 清理Docker镜像
    if [[ "$DEPLOYMENT_TYPE" == "docker" ]]; then
        docker system prune -f 2>/dev/null || true
    fi
    
    # 清理旧备份（保留最近5个）
    if [[ -d "/opt/backups" ]]; then
        cd /opt/backups
        ls -t workflow-* 2>/dev/null | tail -n +6 | xargs rm -rf 2>/dev/null || true
        cd -
    fi
}

# 主升级流程
main() {
    log_info "开始工作流应用升级..."
    
    # 检测部署类型
    detect_deployment_type
    
    # 创建备份
    create_backup
    
    # 停止服务
    stop_services
    
    # 更新代码
    update_code
    
    # 更新依赖
    update_dependencies
    
    # 数据库迁移
    run_database_migration
    
    # 启动服务
    start_services
    
    # 验证升级
    if verify_upgrade; then
        log_info "🎉 升级成功完成！"
        cleanup
    else
        log_error "🚨 升级失败，开始回滚..."
        rollback
        exit 1
    fi
}

# 显示帮助
show_help() {
    echo "工作流应用升级脚本"
    echo
    echo "用法: $0 [选项]"
    echo
    echo "选项:"
    echo "  --help     显示帮助信息"
    echo "  --rollback 回滚到最近的备份"
    echo "  --dry-run  模拟升级过程（不执行实际操作）"
}

# 参数处理
case "${1:-upgrade}" in
    upgrade)
        main
        ;;
    --rollback)
        log_info "手动回滚功能尚未实现"
        log_info "请手动从备份目录恢复: $BACKUP_DIR"
        ;;
    --dry-run)
        log_info "模拟升级过程..."
        detect_deployment_type
        log_info "✅ 升级模拟完成"
        ;;
    --help)
        show_help
        ;;
    *)
        log_error "未知选项: $1"
        show_help
        exit 1
        ;;
esac
