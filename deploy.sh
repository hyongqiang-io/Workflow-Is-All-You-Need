#!/bin/bash

# 工作流平台部署脚本
# Workflow Platform Deployment Script

set -e

echo "🚀 开始部署工作流平台..."

# 检查Docker和Docker Compose
if ! command -v docker &> /dev/null; then
    echo "❌ Docker未安装，请先安装Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose未安装，请先安装Docker Compose"
    exit 1
fi

# 环境设置
ENVIRONMENT=${1:-production}
echo "📝 部署环境: $ENVIRONMENT"

# 检查环境配置文件
if [ ! -f ".env.$ENVIRONMENT" ]; then
    echo "❌ 环境配置文件 .env.$ENVIRONMENT 不存在"
    echo "请从 .env.production 模板创建配置文件"
    exit 1
fi

# 复制环境配置
cp .env.$ENVIRONMENT .env
echo "✅ 环境配置已加载"

# 创建必要的目录
mkdir -p logs uploads ssl

# 生成强密钥（如果不存在）
if ! grep -q "your_very_strong_secret_key" .env; then
    SECRET_KEY=$(openssl rand -hex 32)
    sed -i "s/your_very_strong_secret_key_at_least_32_characters_long/$SECRET_KEY/g" .env
    echo "✅ 已生成随机密钥"
fi

# 构建和启动服务
echo "🔨 构建Docker镜像..."
docker-compose build --no-cache

echo "🚀 启动服务..."
docker-compose up -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 30

# 健康检查
echo "🔍 检查服务状态..."
docker-compose ps

# 检查后端健康状态
if curl -f http://localhost:8001/health > /dev/null 2>&1; then
    echo "✅ 后端服务运行正常"
else
    echo "❌ 后端服务启动失败"
    docker-compose logs backend
    exit 1
fi

# 检查前端健康状态
if curl -f http://localhost > /dev/null 2>&1; then
    echo "✅ 前端服务运行正常"
else
    echo "❌ 前端服务启动失败"
    docker-compose logs frontend
    exit 1
fi

# 显示访问信息
echo ""
echo "🎉 部署完成！"
echo "📱 前端访问地址: http://localhost"
echo "🔧 后端API地址: http://localhost:8001"
echo "📚 API文档地址: http://localhost:8001/docs"
echo ""
echo "📋 服务管理命令:"
echo "  查看日志: docker-compose logs -f [service]"
echo "  重启服务: docker-compose restart [service]"
echo "  停止服务: docker-compose down"
echo "  更新部署: ./deploy.sh $ENVIRONMENT"
echo ""

# 显示初始管理员信息
echo "👤 默认管理员账户:"
echo "  用户名: admin"
echo "  邮箱: admin@example.com"
echo "  密码: 请查看数据库或通过注册创建"