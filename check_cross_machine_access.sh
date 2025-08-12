#!/bin/bash

echo "🔍 工作流系统跨机器访问配置检查"
echo "=================================="

# 获取服务器IP地址
INTERNAL_IP=$(hostname -I | awk '{print $1}')
echo "📍 服务器内网IP: $INTERNAL_IP"

# 检查服务状态
echo ""
echo "🔍 检查服务状态:"
echo "前端服务 (端口3000): $(netstat -tln | grep :3000 > /dev/null && echo '✅ 运行中' || echo '❌ 未运行')"
echo "API服务 (端口8002): $(netstat -tln | grep :8002 > /dev/null && echo '✅ 运行中' || echo '❌ 未运行')"

# 测试API访问
echo ""
echo "🔍 测试API访问:"
if curl -s http://$INTERNAL_IP:8002/health > /dev/null; then
    echo "✅ API健康检查通过"
else
    echo "❌ API健康检查失败"
fi

# 显示访问地址
echo ""
echo "🌐 外部访问地址:"
echo "前端地址: http://$INTERNAL_IP:3000"
echo "API地址:  http://$INTERNAL_IP:8002"

# 检查环境变量配置
echo ""
echo "🔍 前端API配置:"
cat /home/ubuntu/Workflow-Is-All-You-Need/frontend/.env | grep REACT_APP_API_BASE_URL

echo ""
echo "💡 解决方案:"
echo "1. 从外部机器访问: http://$INTERNAL_IP:3000"
echo "2. 如果还是loading，请清除浏览器缓存"
echo "3. 打开浏览器开发者工具查看Network标签"