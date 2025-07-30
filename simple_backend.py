#!/usr/bin/env python3
"""
简化的后端启动脚本 - 跳过数据库连接
"""

import uvicorn
import sys
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 创建简化的FastAPI应用
app = FastAPI(
    title="工作流管理框架",
    description="人机协作工作流开发框架",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "欢迎使用工作流管理框架",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "message": "服务运行正常"
    }

@app.get("/api/test")
async def test_api():
    """测试API"""
    return {
        "success": True,
        "message": "API连接正常",
        "data": {
            "timestamp": "2024-01-01T00:00:00Z"
        }
    }

if __name__ == "__main__":
    print("启动简化后端服务...")
    print("服务地址: http://localhost:8080")
    print("健康检查: http://localhost:8080/health")
    print("API测试: http://localhost:8080/api/test")
    print("按 Ctrl+C 停止服务")
    
    try:
        uvicorn.run(
            "simple_backend:app",
            host="127.0.0.1",
            port=8080,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n服务已停止")
    except Exception as e:
        print(f"启动失败: {e}") 