#!/usr/bin/env python3
"""
简单的MCP服务器模拟器
Simple MCP Server Simulator for Testing
"""

import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import uvicorn

app = FastAPI(
    title="MCP Server Simulator",
    description="用于测试的MCP服务器模拟器",
    version="1.0.0"
)

# ===============================
# 请求/响应模型
# ===============================

class MCPRequest(BaseModel):
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[str] = None

class MCPResponse(BaseModel):
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[str] = None

# ===============================
# 模拟工具定义
# ===============================

MOCK_TOOLS = [
    {
        "name": "read_file",
        "description": "读取文件内容",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file", 
        "description": "写入文件内容",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径"
                },
                "content": {
                    "type": "string",
                    "description": "文件内容"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "list_directory",
        "description": "列出目录内容",
        "parameters": {
            "type": "object", 
            "properties": {
                "path": {
                    "type": "string",
                    "description": "目录路径"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "search_files",
        "description": "搜索文件",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "directory": {
                    "type": "string", 
                    "description": "搜索目录",
                    "default": "."
                }
            },
            "required": ["query"]
        }
    }
]

# ===============================
# MCP协议端点
# ===============================

@app.get("/")
async def root():
    """根端点"""
    return {"message": "MCP Server Simulator", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/mcp")
async def mcp_handler(request: MCPRequest):
    """MCP协议主处理端点"""
    
    method = request.method
    params = request.params or {}
    request_id = request.id or str(uuid.uuid4())
    
    try:
        if method == "initialize":
            return handle_initialize(request_id)
        elif method == "tools/list":
            return handle_tools_list(request_id)
        elif method == "tools/call":
            return handle_tool_call(params, request_id)
        else:
            return MCPResponse(
                error={
                    "code": -32601,
                    "message": f"Method not found: {method}"
                },
                id=request_id
            )
    
    except Exception as e:
        return MCPResponse(
            error={
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            },
            id=request_id
        )

def handle_initialize(request_id: str) -> MCPResponse:
    """处理初始化请求"""
    return MCPResponse(
        result={
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {
                    "listChanged": True
                }
            },
            "serverInfo": {
                "name": "mcp-server-simulator",
                "version": "1.0.0"
            }
        },
        id=request_id
    )

def handle_tools_list(request_id: str) -> MCPResponse:
    """处理工具列表请求"""
    return MCPResponse(
        result={
            "tools": MOCK_TOOLS
        },
        id=request_id
    )

def handle_tool_call(params: Dict[str, Any], request_id: str) -> MCPResponse:
    """处理工具调用请求"""
    tool_name = params.get("name")
    arguments = params.get("arguments", {})
    
    if not tool_name:
        return MCPResponse(
            error={
                "code": -32602,
                "message": "Missing tool name"
            },
            id=request_id
        )
    
    # 查找工具定义
    tool_def = None
    for tool in MOCK_TOOLS:
        if tool["name"] == tool_name:
            tool_def = tool
            break
    
    if not tool_def:
        return MCPResponse(
            error={
                "code": -32602,
                "message": f"Unknown tool: {tool_name}"
            },
            id=request_id
        )
    
    # 模拟工具执行
    try:
        result = simulate_tool_execution(tool_name, arguments)
        return MCPResponse(
            result={
                "content": [
                    {
                        "type": "text",
                        "text": result
                    }
                ],
                "isError": False
            },
            id=request_id
        )
    
    except Exception as e:
        return MCPResponse(
            result={
                "content": [
                    {
                        "type": "text", 
                        "text": f"Tool execution error: {str(e)}"
                    }
                ],
                "isError": True
            },
            id=request_id
        )

def simulate_tool_execution(tool_name: str, arguments: Dict[str, Any]) -> str:
    """模拟工具执行"""
    
    if tool_name == "read_file":
        path = arguments.get("path", "")
        return f"模拟读取文件: {path}\n内容: Hello, this is a mock file content!"
    
    elif tool_name == "write_file":
        path = arguments.get("path", "")
        content = arguments.get("content", "")
        return f"模拟写入文件: {path}\n内容长度: {len(content)} 字符\n写入成功!"
    
    elif tool_name == "list_directory":
        path = arguments.get("path", "")
        mock_files = [
            "file1.txt",
            "file2.py", 
            "subdirectory/",
            "image.png",
            "document.pdf"
        ]
        return f"目录 {path} 内容:\n" + "\n".join([f"  - {f}" for f in mock_files])
    
    elif tool_name == "search_files":
        query = arguments.get("query", "")
        directory = arguments.get("directory", ".")
        mock_results = [
            f"找到匹配文件: /path/to/{query}_file1.txt",
            f"找到匹配文件: /path/to/docs/{query}_readme.md",
            f"找到匹配文件: /path/to/src/{query}_module.py"
        ]
        return f"在 {directory} 中搜索 '{query}':\n" + "\n".join(mock_results)
    
    else:
        return f"模拟执行工具 {tool_name}，参数: {json.dumps(arguments, ensure_ascii=False)}"

# ===============================
# 兼容性端点
# ===============================

@app.get("/mcp/tools")
async def get_tools():
    """获取工具列表（REST风格）"""
    return {"tools": MOCK_TOOLS}

@app.post("/mcp/tools/call")
async def call_tool(request: Dict[str, Any]):
    """调用工具（REST风格）"""
    tool_name = request.get("name")
    arguments = request.get("arguments", {})
    
    try:
        result = simulate_tool_execution(tool_name, arguments)
        return {
            "success": True,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    print("🚀 启动MCP服务器模拟器")
    print("📡 服务地址: http://localhost:8001")
    print("🔧 可用工具:", [tool["name"] for tool in MOCK_TOOLS])
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )