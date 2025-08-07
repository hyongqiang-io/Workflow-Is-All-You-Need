#!/bin/bash

# 简化的部署配置验证脚本
# Simple Deployment Configuration Verification Script

set -e

echo "==================================="
echo "部署配置验证脚本 v1.0"
echo "==================================="

# 检查配置文件
echo "1. 检查配置文件..."

# 检查 .env.example
if [[ -f ".env.example" ]]; then
    echo "   ✓ .env.example 存在"
    if grep -q "DB_HOST" .env.example; then
        echo "   ✓ 数据库配置正确"
    fi
else
    echo "   ✗ .env.example 缺失"
fi

# 检查 Docker Compose 配置
if [[ -f "deployment/docker/docker-compose.yml" ]]; then
    echo "   ✓ docker-compose.yml 存在"
    if grep -q "postgres:" deployment/docker/docker-compose.yml; then
        echo "   ✓ PostgreSQL 服务已配置"
    fi
else
    echo "   ✗ docker-compose.yml 缺失"
fi

# 检查 Dockerfile
if [[ -f "deployment/docker/Dockerfile.backend" ]]; then
    echo "   ✓ Backend Dockerfile 存在"
fi

if [[ -f "deployment/docker/Dockerfile.frontend" ]]; then
    echo "   ✓ Frontend Dockerfile 存在"
fi

# 检查 Nginx 配置
if [[ -f "deployment/nginx/default.conf" ]]; then
    echo "   ✓ Nginx 配置存在"
fi

if [[ -f "deployment/nginx/production.conf" ]]; then
    echo "   ✓ 生产环境 Nginx 配置存在"
fi

# 2. 检查脚本文件
echo
echo "2. 检查部署脚本..."

scripts=(
    "deployment/scripts/deploy.sh"
    "deployment/scripts/backup.sh"
    "deployment/scripts/start.sh"
    "deployment/scripts/health-check.sh"
    "deployment/scripts/monitor.sh"
    "deployment/scripts/upgrade.sh"
)

for script in "${scripts[@]}"; do
    if [[ -f "$script" ]]; then
        if [[ -x "$script" ]]; then
            echo "   ✓ $script 存在且可执行"
        else
            echo "   ⚠ $script 存在但不可执行"
        fi
    else
        echo "   ✗ $script 缺失"
    fi
done

# 3. 检查项目结构
echo
echo "3. 检查项目结构..."

required_dirs=(
    "backend"
    "frontend"
    "deployment"
    "deployment/docker"
    "deployment/nginx"
    "deployment/scripts"
)

for dir in "${required_dirs[@]}"; do
    if [[ -d "$dir" ]]; then
        echo "   ✓ $dir/ 目录存在"
    else
        echo "   ✗ $dir/ 目录缺失"
    fi
done

# 4. 检查主要文件
echo
echo "4. 检查关键文件..."

key_files=(
    "main.py"
    "requirements.txt"
    "frontend/package.json"
)

for file in "${key_files[@]}"; do
    if [[ -f "$file" ]]; then
        echo "   ✓ $file 存在"
    else
        echo "   ✗ $file 缺失"
    fi
done

# 5. 测试 Docker Compose 配置语法
echo
echo "5. 验证 Docker Compose 配置..."

if command -v docker-compose &> /dev/null; then
    cd deployment/docker
    if docker-compose config > /dev/null 2>&1; then
        echo "   ✓ Docker Compose 配置语法正确"
    else
        echo "   ✗ Docker Compose 配置语法错误"
    fi
    cd ../..
else
    echo "   ⚠ Docker Compose 未安装，跳过语法检查"
fi

# 6. 检查备份目录
echo
echo "6. 检查配置备份..."

if [[ -d "config_backup" ]]; then
    backup_count=$(ls config_backup/ | wc -l)
    echo "   ✓ 配置备份目录存在，包含 $backup_count 个备份文件"
else
    echo "   ⚠ 配置备份目录不存在"
fi

echo
echo "==================================="
echo "配置验证完成"
echo "==================================="

# 提供下一步建议
echo
echo "🚀 下一步操作建议："
echo
echo "本地测试部署："
echo "  1. 复制环境配置: cp .env.example .env"
echo "  2. 编辑数据库配置: nano .env"
echo "  3. Docker 部署测试:"
echo "     cd deployment/docker"
echo "     docker-compose up -d"
echo "  4. 检查服务状态:"
echo "     docker-compose ps"
echo "     curl http://localhost/api/test/health"
echo
echo "生产环境部署："
echo "  1. 上传代码到服务器"
echo "  2. 运行部署脚本: sudo ./deployment/scripts/deploy.sh"
echo "  3. 选择 Docker 部署（推荐）"
echo "  4. 配置环境变量和域名"
echo
echo "监控和维护："
echo "  - 健康检查: ./deployment/scripts/monitor.sh --check"
echo "  - 查看日志: docker-compose logs -f"
echo "  - 备份数据: ./deployment/scripts/backup.sh"
echo "  - 升级系统: ./deployment/scripts/upgrade.sh"