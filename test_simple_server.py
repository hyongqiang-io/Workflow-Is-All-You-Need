#!/usr/bin/env python3
"""
简单的测试服务器，用于验证前端连接
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# 创建FastAPI应用
app = FastAPI(title="测试API服务器")

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
    return {"message": "测试服务器运行正常", "status": "success"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "服务运行正常"}

@app.get("/api/auth/me")
async def get_current_user():
    return {
        "success": True,
        "data": {
            "user": {
                "user_id": "test-user-id",
                "username": "testuser",
                "email": "test@example.com",
                "role": "user"
            }
        }
    }

@app.get("/api/workflows")
async def get_workflows():
    return {
        "success": True,
        "data": {
            "workflows": [
                {
                    "workflow_id": "test-workflow-1",
                    "workflow_base_id": "test-base-1",
                    "name": "测试工作流",
                    "description": "这是一个测试工作流",
                    "status": "draft",
                    "version": 1,
                    "is_current_version": True,
                    "creator_name": "测试用户",
                    "creator_id": "test-user-id",
                    "created_at": "2025-07-26T08:00:00Z",
                    "updated_at": "2025-07-26T08:00:00Z",
                    "node_count": 0,
                    "execution_count": 0
                }
            ],
            "count": 1
        }
    }

@app.post("/api/workflows")
async def create_workflow(data: dict):
    return {
        "success": True,
        "message": "工作流创建成功",
        "data": {
            "workflow": {
                "workflow_id": "new-workflow-id",
                "workflow_base_id": "new-base-id",
                "name": data.get("name", "新工作流"),
                "description": data.get("description", ""),
                "creator_id": data.get("creator_id"),
                "version": 1,
                "is_current_version": True
            }
        }
    }

if __name__ == "__main__":
    print("启动测试服务器...")
    print("访问地址: http://localhost:8001")
    print("API文档: http://localhost:8001/docs")
    uvicorn.run(app, host="0.0.0.0", port=8001)