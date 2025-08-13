#!/bin/bash
# MySQL密码重置为mysql123的完整脚本

echo "🔧 开始重置MySQL root密码为 mysql123"
echo "请按照提示执行命令..."
echo ""

echo "步骤 1: 停止MySQL服务"
echo "执行: sudo pkill mysqld"
sudo pkill mysqld
sleep 3

echo ""
echo "步骤 2: 创建密码重置SQL文件"
cat > /tmp/mysql_reset.sql << EOF
ALTER USER 'root'@'localhost' IDENTIFIED BY 'mysql123';
FLUSH PRIVILEGES;
EOF
echo "✅ 重置SQL文件已创建: /tmp/mysql_reset.sql"

echo ""
echo "步骤 3: 以安全模式启动MySQL并执行密码重置"
echo "执行: sudo /usr/local/mysql/bin/mysqld_safe --init-file=/tmp/mysql_reset.sql --daemonize"
sudo /usr/local/mysql/bin/mysqld_safe --init-file=/tmp/mysql_reset.sql --daemonize

echo ""
echo "步骤 4: 等待MySQL初始化完成..."
sleep 10

echo ""
echo "步骤 5: 测试新密码"
if /usr/local/mysql/bin/mysql -u root -pmysql123 -e "SELECT 'Password reset successful!' AS result;" 2>/dev/null; then
    echo "✅ 密码重置成功！"
    echo "✅ MySQL root密码已设置为: mysql123"
    echo ""
    echo "现在可以运行应用程序了！"
else
    echo "❌ 密码重置可能失败，尝试重新启动MySQL服务"
    echo "执行: sudo /usr/local/mysql/support-files/mysql.server restart"
    sudo /usr/local/mysql/support-files/mysql.server restart
    sleep 5
    
    echo "再次测试密码..."
    if /usr/local/mysql/bin/mysql -u root -pmysql123 -e "SELECT 'Password reset successful!' AS result;" 2>/dev/null; then
        echo "✅ 密码重置成功！"
        echo "✅ MySQL root密码已设置为: mysql123"
    else
        echo "❌ 密码重置失败，请检查MySQL状态"
        echo "可能需要手动重置密码"
    fi
fi

echo ""
echo "步骤 6: 清理临时文件"
rm -f /tmp/mysql_reset.sql
echo "✅ 清理完成"

echo ""
echo "🎉 MySQL密码重置过程完成！"