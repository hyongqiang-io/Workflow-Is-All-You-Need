#!/bin/bash

# 服务器文件检查脚本
# 在服务器终端中运行此脚本来查看上传的文件状态

echo "=== AutoLabFlow 服务器文件检查 ==="
echo "检查时间: $(date)"
echo ""

# 1. 检查项目目录是否存在
echo "1. 检查项目目录:"
if [ -d "/opt/workflow" ]; then
    echo "✅ /opt/workflow 目录存在"
    echo "   目录权限: $(ls -ld /opt/workflow)"
    echo "   目录大小: $(du -sh /opt/workflow 2>/dev/null || echo '无法计算')"
else
    echo "❌ /opt/workflow 目录不存在"
    echo "   需要创建: sudo mkdir -p /opt/workflow"
fi
echo ""

# 2. 检查目录内容
echo "2. 检查目录内容:"
if [ -d "/opt/workflow" ]; then
    echo "文件数量: $(find /opt/workflow -type f 2>/dev/null | wc -l)"
    echo "目录数量: $(find /opt/workflow -type d 2>/dev/null | wc -l)"
    echo ""
    
    echo "主要文件检查:"
    check_files=(
        ".env"
        "main.py"
        "requirements.txt"
        "Dockerfile.backend"
        "Dockerfile.frontend"
        "docker-compose.prod.yml"
        "server-deploy.sh"
        "build-and-deploy.sh"
        "backend/"
        "frontend/"
    )
    
    for file in "${check_files[@]}"; do
        if [ -e "/opt/workflow/$file" ]; then
            echo "✅ $file"
        else
            echo "❌ $file (缺失)"
        fi
    done
else
    echo "目录不存在，无法检查内容"
fi
echo ""

# 3. 检查权限问题
echo "3. 检查权限问题:"
echo "当前用户: $(whoami)"
echo "用户组: $(groups)"

if [ -d "/opt/workflow" ]; then
    echo "目录所有者: $(stat -c '%U:%G' /opt/workflow 2>/dev/null || echo '无法获取')"
    echo "目录权限: $(stat -c '%A' /opt/workflow 2>/dev/null || echo '无法获取')"
    
    # 检查是否有写权限
    if [ -w "/opt/workflow" ]; then
        echo "✅ 当前用户对目录有写权限"
    else
        echo "❌ 当前用户对目录无写权限"
        echo "   解决方案: sudo chown -R $(whoami):$(whoami) /opt/workflow"
    fi
else
    echo "目录不存在"
fi
echo ""

# 4. 检查临时文件
echo "4. 检查临时文件:"
temp_files=$(find /opt/workflow -name ".*" -type f 2>/dev/null | wc -l)
if [ "$temp_files" -gt 0 ]; then
    echo "⚠️ 发现 $temp_files 个临时文件(以.开头)"
    echo "临时文件列表:"
    find /opt/workflow -name ".*" -type f 2>/dev/null | head -10
    echo "   清理命令: sudo find /opt/workflow -name '.*' -type f -delete"
else
    echo "✅ 没有发现临时文件"
fi
echo ""

# 5. 推荐的修复命令
echo "=== 推荐的修复命令 ==="
echo "如果需要修复权限问题，请执行:"
echo ""
echo "# 创建目录(如果不存在)"
echo "sudo mkdir -p /opt/workflow"
echo ""
echo "# 设置正确的所有者"
echo "sudo chown -R \$(whoami):\$(whoami) /opt/workflow"
echo ""
echo "# 清理临时文件(如果有)"
echo "sudo find /opt/workflow -name '.*' -type f -delete"
echo ""
echo "# 设置脚本执行权限"
echo "chmod +x /opt/workflow/*.sh"
echo ""

# 6. 显示目录结构
echo "=== 目录结构预览 ==="
if [ -d "/opt/workflow" ]; then
    echo "前20个文件/目录:"
    ls -la /opt/workflow | head -20
else
    echo "目录不存在"
fi
echo ""

echo "=== 检查完成 ==="
echo "如果文件缺失，可能需要重新上传"
echo "如果权限有问题，请执行上面的修复命令"