"""
MCP用户工具管理API
MCP User Tool Management API
"""

import uuid
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field

from ..utils.auth import get_current_active_user, CurrentUser
from ..models.base import BaseResponse
from ..services.mcp_tool_service import mcp_tool_service
from ..models.mcp import MCPAuthConfig, MCPAuthType

router = APIRouter()

# ===============================
# 请求/响应模型
# ===============================

class MCPServerAddRequest(BaseModel):
    """添加MCP服务器请求"""
    server_name: str = Field(..., min_length=1, max_length=255, description="服务器名称")
    server_url: str = Field(..., description="服务器URL")
    server_description: Optional[str] = Field(None, description="服务器描述")
    auth_config: Optional[Dict[str, Any]] = Field(None, description="认证配置")

class MCPToolUpdateRequest(BaseModel):
    """更新工具配置请求"""
    server_description: Optional[str] = Field(None, description="服务器描述")
    tool_description: Optional[str] = Field(None, description="工具描述")
    auth_config: Optional[Dict[str, Any]] = Field(None, description="认证配置")
    timeout_seconds: Optional[int] = Field(None, ge=1, le=300, description="超时时间")
    is_server_active: Optional[bool] = Field(None, description="服务器是否激活")
    is_tool_active: Optional[bool] = Field(None, description="工具是否激活")

class MCPToolTestRequest(BaseModel):
    """测试工具调用请求"""
    arguments: Dict[str, Any] = Field(default_factory=dict, description="测试参数")

class MCPToolResponse(BaseModel):
    """MCP工具响应模型"""
    tool_id: str
    server_name: str
    server_url: str
    tool_name: str
    tool_description: Optional[str]
    tool_parameters: Dict[str, Any]
    is_server_active: bool
    is_tool_active: bool
    server_status: str
    tool_usage_count: int
    success_rate: float
    bound_agents_count: int
    last_tool_call: Optional[str]
    created_at: str

class MCPServerResponse(BaseModel):
    """MCP服务器响应模型"""
    server_name: str
    server_url: str
    server_description: Optional[str]
    server_status: str
    tools_count: int
    total_usage_count: int
    avg_success_rate: float
    last_health_check: Optional[str]
    tools: List[MCPToolResponse]

# ===============================
# 用户工具管理接口
# ===============================

@router.get("/user-tools", response_model=BaseResponse)
async def get_user_tools(
    server_name: Optional[str] = None,
    tool_name: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """获取用户的MCP工具列表"""
    try:
        tools = await mcp_tool_service.get_user_tools(
            user_id=current_user.user_id,
            server_name=server_name,
            tool_name=tool_name,
            is_active=is_active
        )
        
        # 按服务器分组
        servers_map = {}
        for tool in tools:
            server_name = tool['server_name']
            if server_name not in servers_map:
                servers_map[server_name] = {
                    'server_name': server_name,
                    'server_url': tool['server_url'],
                    'server_description': tool.get('server_description'),
                    'server_status': tool['server_status'],
                    'tools_count': 0,
                    'total_usage_count': 0,
                    'tools': []
                }
            
            server_data = servers_map[server_name]
            server_data['tools_count'] += 1
            server_data['total_usage_count'] += tool.get('tool_usage_count', 0)
            server_data['tools'].append({
                'tool_id': str(tool['tool_id']),
                'tool_name': tool['tool_name'],
                'tool_description': tool.get('tool_description'),
                'tool_parameters': tool.get('tool_parameters', {}),
                'is_tool_active': tool['is_tool_active'],
                'tool_usage_count': tool.get('tool_usage_count', 0),
                'success_rate': tool.get('success_rate', 0.0),
                'bound_agents_count': tool.get('bound_agents_count', 0),
                'last_tool_call': tool.get('last_tool_call'),
                'created_at': str(tool['created_at']) if tool.get('created_at') else None
            })
        
        return BaseResponse(
            success=True,
            message=f"获取用户工具成功，共 {len(tools)} 个工具",
            data={
                "total_tools": len(tools),
                "total_servers": len(servers_map),
                "servers": list(servers_map.values())
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取用户工具失败: {str(e)}"
        )

@router.post("/user-tools", response_model=BaseResponse)
async def add_mcp_server(
    request: MCPServerAddRequest,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """添加MCP服务器并发现工具"""
    try:
        result = await mcp_tool_service.add_mcp_server(
            user_id=current_user.user_id,
            server_name=request.server_name,
            server_url=request.server_url,
            auth_config=request.auth_config,
            server_description=request.server_description
        )
        
        return BaseResponse(
            success=True,
            message=f"MCP服务器添加成功，发现 {result['tools_discovered']} 个工具",
            data=result
        )
        
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加MCP服务器失败: {str(e)}"
        )

@router.put("/user-tools/{tool_id}", response_model=BaseResponse)
async def update_mcp_tool(
    tool_id: str,
    request: MCPToolUpdateRequest,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """更新MCP工具配置"""
    try:
        tool_uuid = uuid.UUID(tool_id)
        
        # 构建更新数据
        updates = {}
        if request.server_description is not None:
            updates['server_description'] = request.server_description
        if request.tool_description is not None:
            updates['tool_description'] = request.tool_description
        if request.auth_config is not None:
            updates['auth_config'] = request.auth_config
        if request.timeout_seconds is not None:
            updates['timeout_seconds'] = request.timeout_seconds
        if request.is_server_active is not None:
            updates['is_server_active'] = request.is_server_active
        if request.is_tool_active is not None:
            updates['is_tool_active'] = request.is_tool_active
        
        updated_tool = await mcp_tool_service.update_tool(
            user_id=current_user.user_id,
            tool_id=tool_uuid,
            updates=updates
        )
        
        return BaseResponse(
            success=True,
            message="工具配置更新成功",
            data={
                "tool_id": tool_id,
                "updated_fields": list(updates.keys()),
                "tool_info": {
                    "tool_name": updated_tool.get('tool_name'),
                    "server_name": updated_tool.get('server_name')
                }
            }
        )
        
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新工具配置失败: {str(e)}"
        )

@router.delete("/user-tools/{tool_id}", response_model=BaseResponse)
async def delete_mcp_tool(
    tool_id: str,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """删除MCP工具"""
    try:
        tool_uuid = uuid.UUID(tool_id)
        
        success = await mcp_tool_service.delete_tool(
            user_id=current_user.user_id,
            tool_id=tool_uuid
        )
        
        if success:
            return BaseResponse(
                success=True,
                message="工具删除成功",
                data={"tool_id": tool_id}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工具不存在或已删除"
            )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的工具ID"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除工具失败: {str(e)}"
        )

@router.delete("/user-tools/server/{server_name}", response_model=BaseResponse)
async def delete_mcp_server_tools(
    server_name: str,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """删除服务器的所有工具"""
    try:
        deleted_count = await mcp_tool_service.delete_server_tools(
            user_id=current_user.user_id,
            server_name=server_name
        )
        
        return BaseResponse(
            success=True,
            message=f"服务器删除成功，共删除 {deleted_count} 个工具",
            data={
                "server_name": server_name,
                "deleted_tools_count": deleted_count
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除服务器工具失败: {str(e)}"
        )

@router.post("/user-tools/server/{server_name}/rediscover", response_model=BaseResponse)
async def rediscover_server_tools(
    server_name: str,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """重新发现服务器工具"""
    try:
        result = await mcp_tool_service.rediscover_server_tools(
            user_id=current_user.user_id,
            server_name=server_name
        )
        
        return BaseResponse(
            success=True,
            message=f"重新发现完成，新增 {result['new_tools']} 个工具，更新 {result['updated_tools']} 个工具",
            data=result
        )
        
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重新发现服务器工具失败: {str(e)}"
        )

@router.post("/user-tools/{tool_id}/test", response_model=BaseResponse)
async def test_mcp_tool(
    tool_id: str,
    request: MCPToolTestRequest,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """测试MCP工具调用"""
    try:
        tool_uuid = uuid.UUID(tool_id)
        
        result = await mcp_tool_service.test_tool_call(
            user_id=current_user.user_id,
            tool_id=tool_uuid,
            test_arguments=request.arguments
        )
        
        return BaseResponse(
            success=result['success'],
            message=f"工具测试{'成功' if result['success'] else '失败'}",
            data=result
        )
        
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"测试工具调用失败: {str(e)}"
        )

# ===============================
# 工具发现和管理辅助接口
# ===============================

@router.get("/auth-types", response_model=BaseResponse)
async def get_auth_types():
    """获取支持的认证类型"""
    auth_types = [
        {
            "type": "none",
            "name": "无认证",
            "description": "不需要认证",
            "fields": []
        },
        {
            "type": "bearer",
            "name": "Bearer Token",
            "description": "使用Bearer token认证",
            "fields": [{"name": "token", "type": "string", "required": True, "description": "访问令牌"}]
        },
        {
            "type": "api_key",
            "name": "API Key",
            "description": "使用API Key认证",
            "fields": [{"name": "key", "type": "string", "required": True, "description": "API密钥"}]
        },
        {
            "type": "basic",
            "name": "Basic Auth",
            "description": "使用用户名密码认证",
            "fields": [
                {"name": "username", "type": "string", "required": True, "description": "用户名"},
                {"name": "password", "type": "password", "required": True, "description": "密码"}
            ]
        }
    ]
    
    return BaseResponse(
        success=True,
        message="获取认证类型成功",
        data={"auth_types": auth_types}
    )

@router.get("/user-tools/stats", response_model=BaseResponse)
async def get_user_tools_stats(
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """获取用户工具统计信息"""
    try:
        tools = await mcp_tool_service.get_user_tools(user_id=current_user.user_id)
        
        # 计算统计信息
        stats = {
            "total_tools": len(tools),
            "active_tools": len([t for t in tools if t.get('is_tool_active') and t.get('is_server_active')]),
            "total_servers": len(set(t['server_name'] for t in tools)),
            "total_usage_count": sum(t.get('tool_usage_count', 0) for t in tools),
            "avg_success_rate": sum(t.get('success_rate', 0) for t in tools) / len(tools) if tools else 0,
            "bound_agents": sum(t.get('bound_agents_count', 0) for t in tools)
        }
        
        # 服务器统计
        server_stats = {}
        for tool in tools:
            server_name = tool['server_name']
            if server_name not in server_stats:
                server_stats[server_name] = {
                    "server_name": server_name,
                    "tools_count": 0,
                    "active_tools_count": 0,
                    "total_usage": 0,
                    "server_status": tool['server_status']
                }
            
            server_stats[server_name]["tools_count"] += 1
            if tool.get('is_tool_active') and tool.get('is_server_active'):
                server_stats[server_name]["active_tools_count"] += 1
            server_stats[server_name]["total_usage"] += tool.get('tool_usage_count', 0)
        
        return BaseResponse(
            success=True,
            message="获取用户工具统计成功",
            data={
                "overview": stats,
                "servers": list(server_stats.values())
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取工具统计失败: {str(e)}"
        )