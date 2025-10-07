#!/bin/bash
# Playwright MCP 自动启动脚本

echo "🎭 启动Playwright MCP服务器..."
npx @playwright/mcp@latest --port 8087 --headless --isolated &

echo "⏳ 等待服务器启动..."
sleep 3

echo "✅ Playwright MCP服务器已启动"
echo "🌐 服务地址: http://localhost:8087/mcp"
echo "📋 使用方法:"
echo "   1. 在工作流中调用browser工具"
echo "   2. 支持页面导航、点击、输入、截图等操作"
echo ""
echo "🛑 要停止服务器，请运行: pkill -f playwright/mcp"
