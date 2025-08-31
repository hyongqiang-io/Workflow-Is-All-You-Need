#!/bin/bash
# 简化版开发环境启动脚本

set -e

PROJECT_DIR="/home/ubuntu/Workflow-Is-All-You-Need"
FRONTEND_DIR="$PROJECT_DIR/frontend"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🛠️  启动开发环境...${NC}"

cd "$PROJECT_DIR"

# 简单的进程清理
echo -e "${YELLOW}🧹 清理现有进程...${NC}"
pkill -f "python.*main.py" 2>/dev/null || true
pkill -f "npm.*start" 2>/dev/null || true
sleep 2

# 清理缓存
echo -e "${YELLOW}🧹 清理缓存...${NC}"
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

if [ -d "$FRONTEND_DIR/node_modules/.cache" ]; then
    rm -rf "$FRONTEND_DIR/node_modules/.cache/"
fi

# 加载环境变量
echo -e "${YELLOW}🔧 加载环境配置...${NC}"
set -a
source .env.development
set +a

# 创建日志目录
mkdir -p logs

# 启动后端
echo -e "${YELLOW}📡 启动后端服务...${NC}"
nohup python3 main.py > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo -e "${BLUE}   后端PID: $BACKEND_PID${NC}"

# 等待后端启动
echo -e "${YELLOW}   等待后端启动...${NC}"
for i in {1..30}; do
    if curl -f -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 后端启动成功 (耗时${i}秒)${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

# 启动前端
echo -e "${YELLOW}🌐 启动前端服务...${NC}"
cd "$FRONTEND_DIR"
nohup npm start > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo -e "${BLUE}   前端PID: $FRONTEND_PID${NC}"

cd "$PROJECT_DIR"

# 清理函数
cleanup() {
    echo -e "\n${YELLOW}🛑 停止开发服务...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    pkill -f "python.*main.py" 2>/dev/null || true
    pkill -f "npm.*start" 2>/dev/null || true
    exit 0
}

trap cleanup INT TERM

echo -e "${GREEN}🎯 开发环境运行中${NC}"
echo -e "${GREEN}前端: http://localhost:3000${NC}"
echo -e "${GREEN}后端: http://localhost:8000/docs${NC}"
echo -e "${BLUE}日志查看:${NC}"
echo -e "${BLUE}  后端日志: tail -f logs/backend.log${NC}"
echo -e "${BLUE}  前端日志: tail -f logs/frontend.log${NC}"
echo ""
echo "按 Ctrl+C 停止所有服务"

wait