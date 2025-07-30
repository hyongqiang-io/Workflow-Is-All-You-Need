@echo off
echo 修复并启动前端服务
echo ==================

echo.
echo 1. 切换到正确目录...
cd /d D:\HuaweiMoveData\Users\Dr.Tom_Great\Desktop\final

echo.
echo 2. 检查当前目录文件...
dir | findstr /i "package.json"

echo.
echo 3. 检查react-scripts安装状态...
npm list react-scripts

echo.
echo 4. 重新安装react-scripts...
npm install react-scripts --save

echo.
echo 5. 启动前端服务...
npm start

pause