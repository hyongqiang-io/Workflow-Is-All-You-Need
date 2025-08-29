#!/bin/bash
# 综合系统健康监控脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🏥 工作流系统健康检查${NC}"
echo "======================================"

# 1. 检查系统服务状态
echo -e "${YELLOW}📊 检查系统服务...${NC}"
services=("workflow-backend.service" "nginx")

for service in "${services[@]}"; do
    if systemctl is-active --quiet "$service"; then
        echo -e "✅ $service: ${GREEN}运行中${NC}"
    else
        echo -e "❌ $service: ${RED}已停止${NC}"
    fi
done

# 2. 检查端口占用
echo -e "\n${YELLOW}🔌 检查端口状态...${NC}"
ports=(80 443 8001 3306)

for port in "${ports[@]}"; do
    if netstat -tlnp | grep -q ":$port "; then
        echo -e "✅ 端口 $port: ${GREEN}已占用${NC}"
    else
        echo -e "❌ 端口 $port: ${RED}未占用${NC}"
    fi
done

# 3. 健康检查端点测试
echo -e "\n${YELLOW}🌐 测试服务端点...${NC}"

# 后端API健康检查
if curl -f -s http://localhost:8001/health > /dev/null; then
    echo -e "✅ 后端API: ${GREEN}健康${NC}"
else
    echo -e "❌ 后端API: ${RED}不健康${NC}"
fi

# 前端健康检查
if curl -f -s https://autolabflow.online/health > /dev/null; then
    echo -e "✅ 前端服务: ${GREEN}健康${NC}"
else
    echo -e "❌ 前端服务: ${RED}不健康${NC}"
fi

# API代理检查
if curl -f -s https://autolabflow.online/api/health > /dev/null; then
    echo -e "✅ API代理: ${GREEN}健康${NC}"
else
    echo -e "❌ API代理: ${RED}不健康${NC}"
fi

# 4. 检查资源使用情况
echo -e "\n${YELLOW}📈 系统资源使用情况...${NC}"

# 内存使用率
mem_usage=$(free | grep Mem | awk '{printf("%.2f"), ($3/$2)*100}')
echo -e "内存使用率: ${mem_usage}%"

# 磁盘使用率
disk_usage=$(df -h / | awk 'NR==2 {print $5}')
echo -e "磁盘使用率: ${disk_usage}"

# 5. 检查SSL证书状态
echo -e "\n${YELLOW}🔒 SSL证书检查...${NC}"
cert_file="/etc/nginx/autolabflow.online_bundle.crt"
if [[ -f "$cert_file" ]]; then
    expiry_date=$(openssl x509 -in "$cert_file" -noout -dates | grep "notAfter" | cut -d= -f2)
    echo -e "📅 SSL证书过期时间: ${expiry_date}"
else
    echo -e "❌ SSL证书: ${RED}文件不存在${NC}"
fi

echo -e "\n${GREEN}🏥 健康检查完成！${NC}"