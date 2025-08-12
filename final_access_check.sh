#!/bin/bash

echo "🎉 工作流系统跨机器访问解决方案"
echo "=================================="

PUBLIC_IP="106.54.12.39"

echo "📍 服务器信息:"
echo "公网IP: $PUBLIC_IP"
echo "内网IP: $(hostname -I | awk '{print $1}')"

echo ""
echo "🔍 服务状态检查:"

# 检查nginx
if systemctl is-active --quiet nginx; then
    echo "✅ Nginx反向代理: 运行中"
else
    echo "❌ Nginx反向代理: 未运行"
fi

# 检查前端
if netstat -tln | grep :3000 > /dev/null; then
    echo "✅ 前端服务 (3000): 运行中"
else
    echo "❌ 前端服务 (3000): 未运行"
fi

# 检查API
if netstat -tln | grep :8002 > /dev/null; then
    echo "✅ API服务 (8002): 运行中"
else
    echo "❌ API服务 (8002): 未运行"
fi

echo ""
echo "🧪 连接测试:"

# 测试健康检查
if curl -s http://$PUBLIC_IP/health > /dev/null; then
    echo "✅ 公网健康检查: 通过"
else
    echo "❌ 公网健康检查: 失败"
fi

# 测试API
if curl -s http://$PUBLIC_IP/api/auth/me > /dev/null; then
    echo "✅ 公网API访问: 通过"
else
    echo "❌ 公网API访问: 失败"
fi

echo ""
echo "🌐 外部访问地址:"
echo "主应用: http://$PUBLIC_IP"
echo "API测试: http://$PUBLIC_IP/health"

echo ""
echo "📋 配置信息:"
echo "前端API配置: $(grep REACT_APP_API_BASE_URL /home/ubuntu/Workflow-Is-All-You-Need/frontend/.env)"
echo "Nginx配置: /etc/nginx/sites-enabled/workflow-proxy"

echo ""
echo "💡 如果仍无法访问，请检查:"
echo "1. 云服务器安全组是否开放80端口"
echo "2. 企业防火墙是否阻止访问"
echo "3. 浏览器是否需要清除缓存"