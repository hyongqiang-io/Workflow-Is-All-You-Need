#!/bin/bash
# 启动文生PPT MCP服务器

echo "🎯 安装依赖包..."
pip3 install -r requirements_ppt.txt

echo "🚀 启动文生PPT MCP服务器..."
python3 presentation_generator.py