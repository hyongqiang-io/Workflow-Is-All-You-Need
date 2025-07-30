#!/usr/bin/env python3
"""
简化启动脚本 - 跳过数据库初始化用于测试
"""

import uvicorn
import sys
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 创建简化的FastAPI应用用于测试
app = FastAPI(
    title="工作流管理框架",
    description="人机协作工作流开发框架",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
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
    return {
        "message": "欢迎使用工作流管理框架",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "message": "服务运行正常"
    }

if __name__ == "__main__":
    print("启动简化后端服务（跳过数据库）...")
    print("服务地址: http://localhost:8000")
    print("API文档: http://localhost:8000/docs")
    print("健康检查: http://localhost:8000/health")
    print("按 Ctrl+C 停止服务")
    
    try:
        uvicorn.run(
            "start_simple:app",
            host="127.0.0.1",
            port=8000,
            reload=False,  # 禁用自动重载以防止服务自动关闭
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n服务已停止")
    except Exception as e:
        print(f"启动失败: {e}")