#!/bin/bash

echo "=== 跨机器访问测试脚本 ==="
echo "测试域名: autolabflow.online"
echo "服务器IP: 106.54.12.39"
echo "测试时间: $(date)"
echo ""

# 测试主要功能点
echo "1. 测试主页访问..."
curl -s -o /dev/null -w "HTTP状态码: %{http_code}, 响应时间: %{time_total}s\n" http://autolabflow.online

echo ""
echo "2. 测试API健康检查..."
curl -s -w "HTTP状态码: %{http_code}, 响应时间: %{time_total}s\n" http://autolabflow.online/api/health

echo ""
echo "3. 测试API文档访问..."
curl -s -o /dev/null -w "HTTP状态码: %{http_code}, 响应时间: %{time_total}s\n" http://autolabflow.online/docs

echo ""
echo "4. 测试静态资源..."
curl -s -o /dev/null -w "HTTP状态码: %{http_code}, 响应时间: %{time_total}s\n" http://autolabflow.online/favicon.ico

echo ""
echo "5. 检查DNS解析..."
nslookup autolabflow.online

echo ""
echo "6. 测试端口连通性..."
timeout 5 telnet autolabflow.online 80 2>/dev/null && echo "端口80可达" || echo "端口80不可达"

echo ""
echo "=== 测试完成 ==="
echo ""
echo "如果从其他机器运行此脚本："
echo "curl -O http://autolabflow.online/test_access.sh && chmod +x test_access.sh && ./test_access.sh"