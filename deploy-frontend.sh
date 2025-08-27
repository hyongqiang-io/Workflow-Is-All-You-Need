#!/bin/bash

# 前端自动部署脚本
# 功能：构建前端项目并部署到nginx服务器

set -e  # 遇到错误立即退出

# 配置变量
PROJECT_DIR="/home/ubuntu/Workflow-Is-All-You-Need"
FRONTEND_DIR="$PROJECT_DIR/frontend"
BUILD_DIR="$FRONTEND_DIR/build"
DEPLOY_DIR="/var/www/html"
BACKUP_DIR="/var/backups/frontend"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 开始前端自动部署...${NC}"

# 1. 进入项目目录
cd "$FRONTEND_DIR"
echo -e "${YELLOW}📂 当前目录: $(pwd)${NC}"

# 2. 安装依赖（如果需要）
if [[ ! -d "node_modules" ]] || [[ package.json -nt node_modules ]]; then
    echo -e "${YELLOW}📦 安装/更新依赖...${NC}"
    npm ci
fi

# 3. 构建项目
echo -e "${YELLOW}🔨 构建前端项目...${NC}"
npm run build

# 4. 检查构建是否成功
if [[ ! -d "$BUILD_DIR" ]] || [[ ! -f "$BUILD_DIR/index.html" ]]; then
    echo -e "${RED}❌ 构建失败：未找到构建产物${NC}"
    exit 1
fi

# 5. 备份当前部署（如果存在）
if [[ -d "$DEPLOY_DIR" ]] && [[ -f "$DEPLOY_DIR/index.html" ]]; then
    echo -e "${YELLOW}💾 备份当前部署...${NC}"
    sudo mkdir -p "$BACKUP_DIR"
    sudo cp -r "$DEPLOY_DIR" "$BACKUP_DIR/backup-$(date +%Y%m%d-%H%M%S)"
    # 只保留最近5个备份
    sudo find "$BACKUP_DIR" -type d -name "backup-*" | sort -r | tail -n +6 | sudo xargs rm -rf
fi

# 6. 部署新版本
echo -e "${YELLOW}📋 部署新版本...${NC}"
sudo rm -rf "$DEPLOY_DIR"/*
sudo cp -r "$BUILD_DIR"/* "$DEPLOY_DIR/"

# 7. 设置正确的权限
sudo chown -R www-data:www-data "$DEPLOY_DIR"
sudo chmod -R 644 "$DEPLOY_DIR"
sudo find "$DEPLOY_DIR" -type d -exec chmod 755 {} \;

# 8. 测试nginx配置并重启
echo -e "${YELLOW}🔧 测试nginx配置...${NC}"
if sudo nginx -t; then
    echo -e "${YELLOW}🔄 重新加载nginx...${NC}"
    sudo systemctl reload nginx
    echo -e "${GREEN}✅ Nginx配置测试通过并已重新加载${NC}"
else
    echo -e "${RED}❌ Nginx配置测试失败，请检查配置${NC}"
    exit 1
fi

# 9. 验证部署
echo -e "${YELLOW}🔍 验证部署结果...${NC}"
if curl -f -s -o /dev/null http://localhost/; then
    echo -e "${GREEN}✅ 本地访问测试通过${NC}"
else
    echo -e "${RED}⚠️  本地访问测试失败${NC}"
fi

# 10. 显示部署信息
BUILD_TIME=$(stat -c %y "$BUILD_DIR/index.html" 2>/dev/null || echo "未知")
DEPLOY_SIZE=$(du -sh "$DEPLOY_DIR" 2>/dev/null | cut -f1 || echo "未知")

echo -e "${GREEN}🎉 前端部署完成！${NC}"
echo -e "${GREEN}📊 部署信息:${NC}"
echo -e "   构建时间: $BUILD_TIME"
echo -e "   部署大小: $DEPLOY_SIZE" 
echo -e "   部署路径: $DEPLOY_DIR"
echo -e "   访问地址: https://www.autolabflow.online/"

# 11. 缓存清理提示
echo -e "${YELLOW}💡 提示：${NC}"
echo -e "   - 如果页面未更新，请清除浏览器缓存(Ctrl+F5)"
echo -e "   - 静态资源已启用1年缓存，版本号会自动处理缓存更新"
echo -e "   - 备份保存在: $BACKUP_DIR"

# 12. 显示最新的构建文件
echo -e "${YELLOW}📄 最新构建的主要文件:${NC}"
ls -la "$BUILD_DIR"/ | grep -E '\.(js|css|html)$' | head -5