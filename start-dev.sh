#!/bin/bash
# ==============================================
# 开发环境快速启动脚本
# ==============================================

set -e

PROJECT_DIR="/home/ubuntu/Workflow-Is-All-You-Need"
FRONTEND_DIR="$PROJECT_DIR/frontend"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🛠️  启动开发环境...${NC}"

cd "$PROJECT_DIR"

# 检查端口
if netstat -tlnp | grep -q ":8000 "; then
    echo -e "${YELLOW}⚠️  端口8000已占用，尝试停止现有进程...${NC}"
    pkill -f "python main.py" || true
    sleep 2
fi

if netstat -tlnp | grep -q ":3000 "; then
    echo -e "${YELLOW}⚠️  端口3000已占用，尝试停止现有进程...${NC}"
    pkill -f "npm start" || true
    sleep 2
fi

# 加载开发环境变量 (过滤掉包含特殊字符的变量)
set -a
source .env.development
set +a

echo -e "${YELLOW}📡 启动后端 (localhost:8000)...${NC}"
python3 main.py &
BACKEND_PID=$!

# 等待后端启动
sleep 3

# 检查后端
if curl -f -s http://localhost:8000/health > /dev/null; then
    echo -e "${GREEN}✅ 后端启动成功${NC}"
else
    echo -e "${RED}❌ 后端启动失败${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

echo -e "${YELLOW}🌐 启动前端 (localhost:3000)...${NC}"
cd "$FRONTEND_DIR"
npm start &
FRONTEND_PID=$!

# 清理函数
cleanup() {
    echo -e "\n${YELLOW}🛑 停止开发服务...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    exit 0
}

trap cleanup INT

echo -e "${GREEN}🎯 开发环境运行中${NC}"
echo -e "${GREEN}前端: http://localhost:3000${NC}"
echo -e "${GREEN}后端: http://localhost:8000/docs${NC}"
echo ""
echo "按 Ctrl+C 停止服务"

wait