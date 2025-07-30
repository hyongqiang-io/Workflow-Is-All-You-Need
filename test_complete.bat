@echo off
echo 工作流项目完整测试脚本
echo ========================

echo.
echo 1. 测试后端API...
curl -s http://localhost:8000/health
echo.

echo 2. 测试前端是否可以启动...
echo 前端目录应为: D:\HuaweiMoveData\Users\Dr.Tom_Great\Desktop\final
echo.

echo 3. 如果要启动前端，请在新的命令窗口运行:
echo cd /d D:\HuaweiMoveData\Users\Dr.Tom_Great\Desktop\final
echo npm start
echo.

echo 4. 访问地址:
echo 后端API: http://localhost:8000/docs
echo 前端: http://localhost:3000
echo.

echo 测试完成!
pause