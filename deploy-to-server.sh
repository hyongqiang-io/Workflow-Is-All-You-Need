#!/bin/bash

# AutoLabFlow 一键部署脚本
# 适用于服务器 106.54.12.39, 域名 autolabflow.online

set -e

# 颜色输出
print_info() { echo -e "\033[1;34m[INFO]\033[0m $1"; }
print_success() { echo -e "\033[1;32m[SUCCESS]\033[0m $1"; }
print_error() { echo -e "\033[1;31m[ERROR]\033[0m $1"; }

# 服务器配置
SERVER_IP="106.54.12.39"
DOMAIN="autolabflow.online"
EMAIL="admin@autolabflow.online"
PROJECT_DIR="/opt/workflow"

print_info "AutoLabFlow 一键部署开始"
print_info "服务器IP: $SERVER_IP"
print_info "域名: $DOMAIN"

# 1. 检查.env文件是否存在
if [ ! -f ".env" ]; then
    print_error ".env 文件不存在，请先配置环境变量"
    exit 1
fi

print_success ".env 文件检查通过"

# 2. 本地构建测试
print_info "执行本地构建测试..."
if ! ./build-and-deploy.sh --test; then
    print_error "本地构建测试失败"
    exit 1
fi

print_success "本地构建测试通过"

# 3. 上传文件到服务器
print_info "上传文件到服务器..."
rsync -avz --progress \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='logs/*' \
    --exclude='backups/*' \
    ./ ubuntu@${SERVER_IP}:${PROJECT_DIR}/

print_success "文件上传完成"

# 4. 在服务器上执行部署
print_info "在服务器上执行部署..."
ssh ubuntu@${SERVER_IP} << 'ENDSSH'
    cd /opt/workflow
    
    # 赋予执行权限
    chmod +x server-deploy.sh
    chmod +x build-and-deploy.sh
    
    # 执行服务器部署
    ./server-deploy.sh autolabflow.online admin@autolabflow.online
    
    # 构建并启动应用
    ./build-and-deploy.sh --env prod
    
    # 启动系统服务
    systemctl enable workflow
    systemctl start workflow
    
    # 检查服务状态
    systemctl status workflow --no-pager -l
    
    echo "=== 部署完成检查 ==="
    docker-compose -f docker-compose.prod.yml ps
    
    echo "=== 等待服务启动 ==="
    sleep 30
    
    echo "=== 健康检查 ==="
    curl -f http://localhost:8001/health || echo "后端健康检查失败"
    curl -f http://localhost/health || echo "前端健康检查失败"
ENDSSH

# 5. 验证部署
print_info "验证部署结果..."
sleep 10

print_info "检查网站可访问性..."
if curl -f -s -o /dev/null https://${DOMAIN}/health; then
    print_success "网站健康检查通过"
else
    print_error "网站健康检查失败"
fi

if curl -f -s -o /dev/null https://${DOMAIN}/api/docs; then
    print_success "API文档可访问"
else
    print_error "API文档不可访问"
fi

# 6. 显示部署结果
print_success "=== AutoLabFlow 部署完成 ==="
echo ""
print_info "网站地址："
echo "  主站: https://${DOMAIN}"
echo "  API文档: https://${DOMAIN}/api/docs"
echo "  健康检查: https://${DOMAIN}/health"
echo ""
print_info "服务器管理命令："
echo "  查看状态: ssh ubuntu@${SERVER_IP} 'systemctl status workflow'"
echo "  查看日志: ssh ubuntu@${SERVER_IP} 'docker-compose -f ${PROJECT_DIR}/docker-compose.prod.yml logs -f'"
echo "  重启服务: ssh ubuntu@${SERVER_IP} 'systemctl restart workflow'"
echo ""
print_info "自动化任务已配置："
echo "  每日凌晨2点自动备份"
echo "  每5分钟服务监控"
echo "  SSL证书自动续期"
echo ""
print_success "部署成功！请访问 https://${DOMAIN} 查看您的应用"