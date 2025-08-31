#!/bin/bash

# Git Hook - 检测前端变化并自动部署
# 使用方法：将此脚本链接到 .git/hooks/post-merge 或在CI/CD中调用

# 检查是否有前端文件变化
FRONTEND_CHANGED=$(git diff --name-only HEAD@{1} HEAD -- frontend/ | wc -l)

if [[ $FRONTEND_CHANGED -gt 0 ]]; then
    echo "🔍 检测到前端文件变化，开始自动部署..."
    
    # 调用部署脚本
    if [[ -x "/home/ubuntu/Workflow-Is-All-You-Need/deploy-frontend.sh" ]]; then
        /home/ubuntu/Workflow-Is-All-You-Need/deploy-frontend.sh
    else
        echo "❌ 部署脚本不存在或无执行权限"
        exit 1
    fi
else
    echo "📝 未检测到前端文件变化，跳过部署"
fi