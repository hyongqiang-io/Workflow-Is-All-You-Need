# 项目启动指南

## 🚀 快速启动

### 1. 安装依赖

```bash
# 安装Python依赖
pip3 install -r requirements.txt

# 安装Node.js依赖
cd frontend
npm install
```

### 2. 启动后端服务

```bash
# 方法1: 使用简化脚本
python3 start_backend.py

# 方法2: 直接启动
python3 main.py

# 方法3: 使用uvicorn
uvicorn main:app --host 127.0.0.1 --port 8080 --reload
```

### 3. 启动前端服务

```bash
cd frontend
npm start
```

## 🔧 配置说明

### 后端配置
- **端口**: 8080
- **地址**: http://localhost:8080
- **API文档**: http://localhost:8080/docs

### 前端配置
- **端口**: 3000
- **地址**: http://localhost:3000
- **API地址**: http://localhost:8080

## 🐛 故障排除

### 1. 依赖安装问题

```bash
# 检查Python版本
python3 --version

# 升级pip
pip3 install --upgrade pip

# 安装依赖
pip3 install -r requirements.txt
```

### 2. 数据库连接问题

确保PostgreSQL数据库运行：
```bash
# macOS (使用Homebrew)
brew services start postgresql

# 或者手动启动
pg_ctl -D /usr/local/var/postgres start
```

### 3. 端口占用问题

```bash
# 检查端口占用
lsof -i :8080
lsof -i :3000

# 杀死占用进程
kill -9 <PID>
```

### 4. 测试连接

```bash
# 测试后端API
curl http://localhost:8080/health

# 测试前端
curl http://localhost:3000
```

## 📝 常见错误

### 错误1: ModuleNotFoundError
**解决**: 安装缺失的依赖
```bash
pip3 install <module_name>
```

### 错误2: 数据库连接失败
**解决**: 检查数据库配置
```bash
# 检查PostgreSQL是否运行
ps aux | grep postgres
```

### 错误3: 端口被占用
**解决**: 更换端口或杀死占用进程
```bash
# 使用不同端口启动
uvicorn main:app --port 8081
```

## 🎯 验证启动成功

1. **后端**: 访问 http://localhost:8080/docs
2. **前端**: 访问 http://localhost:3000
3. **登录**: 访问 http://localhost:3000/login

## 📞 获取帮助

如果遇到问题：
1. 查看控制台错误信息
2. 检查日志文件
3. 运行测试脚本: `python3 test_backend.py` 