#!/bin/bash

# 系统监控脚本
# System Monitoring Script

echo "🔍 工作流平台系统监控报告"
echo "=============================="
echo "时间: $(date)"
echo ""

# 检查Docker服务状态
echo "📦 Docker服务状态:"
if systemctl is-active --quiet docker; then
    echo "✅ Docker服务正在运行"
else
    echo "❌ Docker服务未运行"
fi
echo ""

# 检查容器状态
echo "🐳 容器运行状态:"
docker-compose ps
echo ""

# 检查系统资源
echo "💻 系统资源使用情况:"
echo "CPU使用率:"
top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1
echo ""

echo "内存使用情况:"
free -h
echo ""

echo "磁盘使用情况:"
df -h /
echo ""

# 检查端口监听
echo "🌐 端口监听状态:"
echo "端口 80 (前端):"
if netstat -tln | grep -q :80; then
    echo "✅ 正在监听"
else
    echo "❌ 未监听"
fi

echo "端口 8001 (后端):"
if netstat -tln | grep -q :8001; then
    echo "✅ 正在监听"
else
    echo "❌ 未监听"  
fi

echo "端口 5432 (数据库):"
if netstat -tln | grep -q :5432; then
    echo "✅ 正在监听"
else
    echo "❌ 未监听"
fi
echo ""

# 检查健康状态
echo "🏥 服务健康检查:"
echo "前端健康检查:"
if curl -f -s http://localhost > /dev/null; then
    echo "✅ 前端服务正常"
else
    echo "❌ 前端服务异常"
fi

echo "后端健康检查:"
if curl -f -s http://localhost:8001/health > /dev/null; then
    echo "✅ 后端服务正常"
else
    echo "❌ 后端服务异常"
fi
echo ""

# 检查日志错误
echo "📋 最近错误日志:"
echo "后端错误:"
docker-compose logs --tail=10 backend 2>&1 | grep -i error | tail -5

echo ""
echo "前端错误:"
docker-compose logs --tail=10 frontend 2>&1 | grep -i error | tail -5

echo ""
echo "数据库错误:"
docker-compose logs --tail=10 postgres 2>&1 | grep -i error | tail -5

echo ""
echo "=============================="
echo "监控报告完成"