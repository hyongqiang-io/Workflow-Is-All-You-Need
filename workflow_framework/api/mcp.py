"""
MCP工具集成API路由
MCP Tool Integration API Routes
"""

import uuid
import json
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from loguru import logger

from ..models.base import BaseResponse
from ..models.mcp import (
    MCPServerConfig, MCPToolConfig, MCPToolCall, 
    MCPToolResponse, MCPServerStatus, MCPToolDefinition,
    create_default_mcp_config, validate_mcp_config, merge_mcp_config
)
from ..services.mcp_service import mcp_service
from ..repositories.agent.agent_repository import AgentRepository
from ..utils.middleware import get_current_active_user, CurrentUser


# 创建路由器
router = APIRouter(prefix="/mcp", tags=["MCP工具"])

# Repository
agent_repo = AgentRepository()


class MCPServerCreateRequest(BaseModel):
    """MCP服务器创建请求"""
    name: str = Field(..., description="服务器名称")
    url: str = Field(..., description="服务器URL")
    capabilities: List[str] = Field(default_factory=list, description="能力列表")
    auth: Dict[str, Any] = Field(default_factory=dict, description="认证配置")
    timeout: int = Field(30, description="超时时间")


class MCPToolCallRequest(BaseModel):
    """MCP工具调用请求"""
    tool_name: str = Field(..., description="工具名称")
    server_name: str = Field(..., description="服务器名称")
    arguments: Dict[str, Any] = Field(..., description="调用参数")


class AgentToolConfigRequest(BaseModel):
    """Agent工具配置请求"""
    agent_id: uuid.UUID = Field(..., description="Agent ID")
    tool_config: Dict[str, Any] = Field(..., description="工具配置")


@router.post("/servers", response_model=BaseResponse)
async def add_mcp_server(
    server_data: MCPServerCreateRequest,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """添加MCP服务器"""
    try:
        # 创建服务器配置
        from ..services.mcp_service import MCPServerConfig
        server_config = MCPServerConfig(
            name=server_data.name,
            url=server_data.url,
            capabilities=server_data.capabilities,
            auth=server_data.auth,
            timeout=server_data.timeout
        )
        
        # 添加服务器
        success = await mcp_service.add_server(server_config)
        
        if success:
            return BaseResponse(
                success=True,
                message="MCP服务器添加成功",
                data={"server_name": server_data.name}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法连接到MCP服务器"
            )
            
    except Exception as e:
        logger.error(f"添加MCP服务器失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加MCP服务器失败: {str(e)}"
        )


@router.get("/servers", response_model=BaseResponse)
async def get_mcp_servers(
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """获取所有MCP服务器状态"""
    try:
        servers_status = await mcp_service.get_all_servers_status()
        
        return BaseResponse(
            success=True,
            message="获取MCP服务器状态成功",
            data={"servers": servers_status}
        )
        
    except Exception as e:
        logger.error(f"获取MCP服务器状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取MCP服务器状态失败: {str(e)}"
        )


@router.get("/servers/{server_name}/status", response_model=BaseResponse)
async def get_server_status(
    server_name: str,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """获取特定服务器状态"""
    try:
        status_info = await mcp_service.get_server_status(server_name)
        
        return BaseResponse(
            success=True,
            message="获取服务器状态成功",
            data=status_info
        )
        
    except Exception as e:
        logger.error(f"获取服务器状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取服务器状态失败: {str(e)}"
        )


@router.get("/servers/{server_name}/tools", response_model=BaseResponse)
async def discover_server_tools(
    server_name: str,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """发现服务器工具"""
    try:
        tools = await mcp_service.discover_tools(server_name)
        tools_data = [tool.to_dict() for tool in tools]
        
        return BaseResponse(
            success=True,
            message="工具发现成功",
            data={"tools": tools_data}
        )
        
    except Exception as e:
        logger.error(f"工具发现失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"工具发现失败: {str(e)}"
        )


@router.post("/tools/call", response_model=BaseResponse)
async def call_mcp_tool(
    call_request: MCPToolCallRequest,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """调用MCP工具"""
    try:
        result = await mcp_service.call_tool(
            call_request.tool_name,
            call_request.server_name,
            call_request.arguments
        )
        
        return BaseResponse(
            success=result['success'],
            message="工具调用完成" if result['success'] else "工具调用失败",
            data=result
        )
        
    except Exception as e:
        logger.error(f"工具调用失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"工具调用失败: {str(e)}"
        )


@router.get("/agents/{agent_id}/tools", response_model=BaseResponse)
async def get_agent_tools(
    agent_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """获取Agent的可用工具"""
    try:
        tools = await mcp_service.get_agent_tools(agent_id)
        tools_data = [tool.to_dict() for tool in tools]
        
        return BaseResponse(
            success=True,
            message="获取Agent工具成功",
            data={"tools": tools_data}
        )
        
    except Exception as e:
        logger.error(f"获取Agent工具失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取Agent工具失败: {str(e)}"
        )


@router.get("/agents/{agent_id}/config", response_model=BaseResponse)
async def get_agent_tool_config(
    agent_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """获取Agent的工具配置"""
    try:
        # 获取Agent信息
        agent = await agent_repo.get_agent_by_id(agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent不存在"
            )
        
        # 获取工具配置
        tool_config = agent.get('tool_config', {})
        
        # 如果没有配置，使用默认配置
        if not tool_config:
            tool_config = create_default_mcp_config()
        
        # 验证配置格式
        try:
            validated_config = validate_mcp_config(tool_config)
            tool_config = validated_config.dict()
        except Exception as e:
            logger.warning(f"工具配置验证失败，使用默认配置: {e}")
            tool_config = create_default_mcp_config()
        
        return BaseResponse(
            success=True,
            message="获取Agent工具配置成功",
            data=tool_config
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取Agent工具配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取Agent工具配置失败: {str(e)}"
        )


@router.put("/agents/{agent_id}/config", response_model=BaseResponse)
async def update_agent_tool_config(
    agent_id: uuid.UUID,
    config_request: Dict[str, Any],
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """更新Agent的工具配置"""
    try:
        # 获取Agent信息
        agent = await agent_repo.get_agent_by_id(agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent不存在"
            )
        
        # 验证新配置
        try:
            validated_config = validate_mcp_config(config_request)
            new_config = validated_config.dict()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"工具配置格式错误: {str(e)}"
            )
        
        # 合并现有配置
        current_config = agent.get('tool_config', {})
        merged_config = merge_mcp_config(current_config, new_config)
        
        # 更新Agent配置
        from ..models.agent import AgentUpdate
        update_data = AgentUpdate(tool_config=merged_config)
        updated_agent = await agent_repo.update_agent(agent_id, update_data)
        
        if not updated_agent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新Agent配置失败"
            )
        
        # 清除相关工具缓存
        for server in merged_config.get('mcp_servers', []):
            mcp_service.clear_tools_cache(server.get('name'))
        
        return BaseResponse(
            success=True,
            message="Agent工具配置更新成功",
            data=merged_config
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新Agent工具配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新Agent工具配置失败: {str(e)}"
        )


@router.delete("/servers/{server_name}", response_model=BaseResponse)
async def remove_mcp_server(
    server_name: str,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """移除MCP服务器"""
    try:
        success = await mcp_service.remove_server(server_name)
        
        if success:
            return BaseResponse(
                success=True,
                message="MCP服务器移除成功",
                data={"server_name": server_name}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="MCP服务器不存在"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"移除MCP服务器失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"移除MCP服务器失败: {str(e)}"
        )


@router.post("/servers/{server_name}/refresh-tools", response_model=BaseResponse)
async def refresh_server_tools(
    server_name: str,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """刷新服务器工具缓存"""
    try:
        # 清除缓存
        mcp_service.clear_tools_cache(server_name)
        
        # 重新发现工具
        tools = await mcp_service.discover_tools(server_name)
        tools_data = [tool.to_dict() for tool in tools]
        
        return BaseResponse(
            success=True,
            message="工具缓存刷新成功",
            data={"tools": tools_data}
        )
        
    except Exception as e:
        logger.error(f"刷新工具缓存失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"刷新工具缓存失败: {str(e)}"
        )


@router.get("/health", response_model=BaseResponse)
async def mcp_service_health():
    """MCP服务健康检查"""
    try:
        # 检查MCP服务状态
        is_initialized = mcp_service.is_initialized
        server_count = len(mcp_service.servers)
        
        return BaseResponse(
            success=True,
            message="MCP服务运行正常",
            data={
                "initialized": is_initialized,
                "server_count": server_count,
                "service_status": "healthy"
            }
        )
        
    except Exception as e:
        logger.error(f"MCP服务健康检查失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MCP服务异常: {str(e)}"
        )