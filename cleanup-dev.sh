#!/bin/bash
# ==============================================
# 开发环境清理脚本
# 用于彻底清理开发环境的进程和缓存
# ==============================================

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_DIR="/home/ubuntu/Workflow-Is-All-You-Need"
FRONTEND_DIR="$PROJECT_DIR/frontend"

echo -e "${BLUE}🧹 开始彻底清理开发环境...${NC}"

# 停止所有相关进程
echo -e "${YELLOW}1. 停止所有相关进程...${NC}"
pkill -9 -f "python.*main.py" 2>/dev/null || true
pkill -9 -f "uvicorn" 2>/dev/null || true
pkill -9 -f "fastapi" 2>/dev/null || true
pkill -9 -f "npm.*start" 2>/dev/null || true
pkill -9 -f "node.*react-scripts" 2>/dev/null || true
pkill -9 -f "webpack" 2>/dev/null || true

# 清理端口
echo -e "${YELLOW}2. 检查端口状态...${NC}"
if netstat -tlnp 2>/dev/null | grep -q ":8000 "; then
    echo -e "${RED}   端口8000仍被占用${NC}"
else
    echo -e "${GREEN}   端口8000已释放${NC}"
fi

if netstat -tlnp 2>/dev/null | grep -q ":3000 "; then
    echo -e "${RED}   端口3000仍被占用${NC}"
else
    echo -e "${GREEN}   端口3000已释放${NC}"
fi

# 清理Python缓存
echo -e "${YELLOW}3. 清理Python缓存...${NC}"
cd "$PROJECT_DIR"
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
echo -e "${GREEN}   ✅ Python缓存已清理${NC}"

# 清理前端缓存
echo -e "${YELLOW}4. 清理前端缓存...${NC}"
if [ -d "$FRONTEND_DIR/node_modules/.cache" ]; then
    rm -rf "$FRONTEND_DIR/node_modules/.cache/"
    echo -e "${GREEN}   ✅ 前端node_modules缓存已清理${NC}"
fi

if [ -d "$FRONTEND_DIR/build" ]; then
    rm -rf "$FRONTEND_DIR/build/"
    echo -e "${GREEN}   ✅ 前端build目录已清理${NC}"
fi

# 清理日志文件（可选）
read -p "是否清理日志文件? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -d "$PROJECT_DIR/logs" ]; then
        rm -rf "$PROJECT_DIR/logs/"
        echo -e "${GREEN}   ✅ 日志文件已清理${NC}"
    fi
fi

echo -e "${GREEN}🎉 开发环境清理完成！${NC}"
echo -e "${BLUE}💡 现在可以运行 ./start-dev.sh 启动干净的开发环境${NC}"