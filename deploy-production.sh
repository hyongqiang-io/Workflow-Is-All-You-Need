#!/bin/bash
# 生产环境部署脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 开始生产环境部署...${NC}"

# 1. 停止现有服务
echo -e "${YELLOW}📦 停止现有服务...${NC}"
sudo systemctl stop workflow-backend.service || true
sudo systemctl stop nginx || true

# 2. 构建前端
echo -e "${YELLOW}🔨 构建前端...${NC}"
cd /home/ubuntu/Workflow-Is-All-You-Need/frontend
NODE_ENV=production npm run build

# 3. 部署前端
echo -e "${YELLOW}🌐 部署前端文件...${NC}"
sudo rm -rf /var/www/html/*
sudo cp -r /home/ubuntu/Workflow-Is-All-You-Need/frontend/build/* /var/www/html/
sudo chown -R www-data:www-data /var/www/html
sudo chmod -R 755 /var/www/html

# 4. 更新后端依赖
echo -e "${YELLOW}📚 更新后端依赖...${NC}"
cd /home/ubuntu/Workflow-Is-All-You-Need
pip install --user -r requirements.txt

# 5. 数据库迁移（如果需要）
echo -e "${YELLOW}🗄️  检查数据库状态...${NC}"
python -c "from backend.utils.database_mysql import engine; from backend.models.base import Base; print('数据库连接正常')" || {
    echo -e "${RED}❌ 数据库连接失败${NC}"
    exit 1
}

# 6. 启动服务
echo -e "${YELLOW}🔄 启动服务...${NC}"
sudo systemctl start workflow-backend.service
sudo systemctl start nginx

# 7. 检查服务状态
echo -e "${YELLOW}🔍 检查服务状态...${NC}"
sleep 5

if sudo systemctl is-active --quiet workflow-backend.service; then
    echo -e "${GREEN}✅ 后端服务启动成功${NC}"
else
    echo -e "${RED}❌ 后端服务启动失败${NC}"
    exit 1
fi

if sudo systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✅ Nginx服务启动成功${NC}"
else
    echo -e "${RED}❌ Nginx服务启动失败${NC}"
    exit 1
fi

# 8. 健康检查
echo -e "${YELLOW}🏥 进行健康检查...${NC}"
sleep 10

if curl -f -s http://localhost:8001/health > /dev/null; then
    echo -e "${GREEN}✅ 后端健康检查通过${NC}"
else
    echo -e "${RED}❌ 后端健康检查失败${NC}"
fi

if curl -f -s http://localhost/health > /dev/null; then
    echo -e "${GREEN}✅ 前端健康检查通过${NC}"
else
    echo -e "${RED}❌ 前端健康检查失败${NC}"
fi

# 9. 显示部署信息
echo -e "${GREEN}🎉 部署完成！${NC}"
echo -e "${GREEN}📊 服务状态:${NC}"
echo "前端URL: https://autolabflow.online"
echo "后端API: https://autolabflow.online/api"
echo "API文档: https://autolabflow.online/docs"
echo ""
echo -e "${GREEN}📝 日志文件位置:${NC}"
echo "后端日志: /var/log/workflow/backend.log"
echo "后端错误日志: /var/log/workflow/backend-error.log"
echo "Nginx日志: /var/log/nginx/access.log"
echo ""
echo -e "${GREEN}🔧 管理命令:${NC}"
echo "重启后端: sudo systemctl restart workflow-backend.service"
echo "查看后端状态: sudo systemctl status workflow-backend.service"
echo "查看后端日志: sudo journalctl -u workflow-backend.service -f"
echo "重启Nginx: sudo systemctl restart nginx"