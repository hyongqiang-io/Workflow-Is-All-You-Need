#!/bin/bash
# MySQL密码重置脚本

echo "🔧 MySQL密码重置脚本"
echo "注意：此脚本需要管理员权限"

# 检查是否以管理员身份运行
if [[ $EUID -eq 0 ]]; then
   echo "请不要以root身份运行此脚本"
   exit 1
fi

echo ""
echo "步骤 1: 停止MySQL服务"
echo "请执行以下命令（需要输入管理员密码）:"
echo "sudo /usr/local/mysql/support-files/mysql.server stop"
echo ""
read -p "按回车键继续，当你已经停止了MySQL服务..."

echo ""
echo "步骤 2: 以安全模式启动MySQL（跳过权限验证）"
echo "请在新的终端窗口中执行以下命令："
echo "sudo /usr/local/mysql/bin/mysqld_safe --skip-grant-tables --skip-networking &"
echo ""
read -p "按回车键继续，当你已经启动了安全模式MySQL..."

echo ""
echo "步骤 3: 连接到MySQL并重置密码"
echo "请执行以下命令："
echo "/usr/local/mysql/bin/mysql -u root"
echo ""
echo "然后在MySQL提示符下执行："
echo "FLUSH PRIVILEGES;"
echo "ALTER USER 'root'@'localhost' IDENTIFIED BY 'workflow123';"
echo "EXIT;"
echo ""
read -p "按回车键继续，当你已经重置了密码..."

echo ""
echo "步骤 4: 重新启动MySQL服务"
echo "首先停止安全模式的MySQL："
echo "sudo killall mysqld"
echo ""
echo "然后正常启动MySQL："
echo "sudo /usr/local/mysql/support-files/mysql.server start"
echo ""
read -p "按回车键继续，当你已经重新启动了MySQL..."

echo ""
echo "步骤 5: 测试新密码"
echo "测试连接："
echo "/usr/local/mysql/bin/mysql -u root -pworkflow123 -e 'SELECT VERSION();'"

echo ""
echo "🎉 如果上述步骤成功，MySQL root密码已设置为: workflow123"
echo "现在可以更新应用配置文件使用新密码。"