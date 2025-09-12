"""
Agent工具绑定管理API
Agent Tool Binding Management API
"""

import uuid
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from loguru import logger

from ..utils.auth import get_current_active_user, CurrentUser
from ..models.base import BaseResponse
from ..services.agent_tool_service import agent_tool_service

router = APIRouter()

# ===============================
# 请求/响应模型
# ===============================

class ToolBindingRequest(BaseModel):
    """工具绑定请求"""
    tool_id: str = Field(..., description="工具ID")
    is_enabled: bool = Field(True, description="是否启用")
    priority: int = Field(0, ge=0, le=100, description="优先级(0-100)")
    max_calls_per_task: int = Field(5, ge=1, le=50, description="单任务最大调用次数")
    timeout_override: Optional[int] = Field(None, ge=1, le=300, description="超时时间覆盖(秒)")
    custom_config: Dict[str, Any] = Field(default_factory=dict, description="自定义配置")

class BatchToolBindingRequest(BaseModel):
    """批量工具绑定请求"""
    bindings: List[ToolBindingRequest] = Field(..., description="绑定配置列表")

class ToolBindingUpdateRequest(BaseModel):
    """工具绑定更新请求"""
    is_enabled: Optional[bool] = Field(None, description="是否启用")
    priority: Optional[int] = Field(None, ge=0, le=100, description="优先级")
    max_calls_per_task: Optional[int] = Field(None, ge=1, le=50, description="最大调用次数")
    timeout_override: Optional[int] = Field(None, ge=1, le=300, description="超时时间覆盖")
    custom_config: Optional[Dict[str, Any]] = Field(None, description="自定义配置")

class AgentToolResponse(BaseModel):
    """Agent工具响应模型"""
    binding_id: str
    tool_id: str
    tool_name: str
    server_name: str
    server_url: str
    tool_description: Optional[str]
    tool_parameters: Dict[str, Any]
    is_enabled: bool
    priority: int
    max_calls_per_task: int
    timeout_override: Optional[int]
    custom_config: Dict[str, Any]
    # 统计信息
    total_calls: int
    successful_calls: int
    last_called: Optional[str]
    avg_execution_time: float
    # 工具状态
    is_server_active: bool
    is_tool_active: bool
    server_status: str
    success_rate: float

# ===============================
# Agent工具绑定管理接口
# ===============================

@router.get("/agents/{agent_id}/tools", response_model=BaseResponse)
async def get_agent_tools(
    agent_id: str,
    is_enabled: Optional[bool] = None,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """获取Agent绑定的工具列表"""
    try:
        agent_uuid = uuid.UUID(agent_id)
        
        tools = await agent_tool_service.get_agent_tools(
            agent_id=agent_uuid,
            user_id=current_user.user_id,
            is_enabled=is_enabled
        )
        
        # 格式化响应
        formatted_tools = []
        for tool in tools:
            formatted_tool = {
                "binding_id": str(tool['binding_id']),
                "tool_id": str(tool['tool_id']),
                "tool_name": tool['tool_name'],
                "server_name": tool['server_name'],
                "server_url": tool['server_url'],
                "tool_description": tool.get('tool_description'),
                "tool_parameters": tool.get('tool_parameters', {}),
                "is_enabled": tool['is_enabled'],
                "priority": tool['priority'],
                "max_calls_per_task": tool['max_calls_per_task'],
                "timeout_override": tool.get('timeout_override'),
                "custom_config": tool.get('custom_config', {}),
                "total_calls": tool.get('total_calls', 0),
                "successful_calls": tool.get('successful_calls', 0),
                "last_called": str(tool['last_called']) if tool.get('last_called') else None,
                "avg_execution_time": float(tool.get('avg_execution_time', 0)),
                "is_server_active": tool.get('is_server_active', False),
                "is_tool_active": tool.get('is_tool_active', False),
                "server_status": tool.get('server_status', 'unknown'),
                "success_rate": float(tool.get('success_rate', 0))
            }
            formatted_tools.append(formatted_tool)
        
        # 统计信息
        enabled_count = len([t for t in tools if t['is_enabled']])
        active_count = len([t for t in tools if t['is_enabled'] and t.get('is_server_active') and t.get('is_tool_active')])
        
        return BaseResponse(
            success=True,
            message=f"获取Agent工具成功，共 {len(tools)} 个工具",
            data={
                "agent_id": agent_id,
                "total_tools": len(tools),
                "enabled_tools": enabled_count,
                "active_tools": active_count,
                "tools": formatted_tools
            }
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的Agent ID"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取Agent工具失败: {str(e)}"
        )

@router.post("/agents/{agent_id}/tools", response_model=BaseResponse)
async def bind_tool_to_agent(
    agent_id: str,
    request: ToolBindingRequest,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """为Agent绑定工具"""
    try:
        agent_uuid = uuid.UUID(agent_id)
        tool_uuid = uuid.UUID(request.tool_id)
        
        config = {
            "is_enabled": request.is_enabled,
            "priority": request.priority,
            "max_calls_per_task": request.max_calls_per_task,
            "timeout_override": request.timeout_override,
            "custom_config": request.custom_config
        }
        
        result = await agent_tool_service.bind_tool_to_agent(
            agent_id=agent_uuid,
            tool_id=tool_uuid,
            user_id=current_user.user_id,
            config=config
        )
        
        return BaseResponse(
            success=True,
            message="工具绑定成功",
            data=result
        )
        
    except ValueError as ve:
        if "无效" in str(ve):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(ve)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(ve)
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"绑定工具失败: {str(e)}"
        )

@router.post("/agents/{agent_id}/tools/batch", response_model=BaseResponse)
async def batch_bind_tools_to_agent(
    agent_id: str,
    request: BatchToolBindingRequest,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """批量为Agent绑定工具"""
    try:
        agent_uuid = uuid.UUID(agent_id)
        
        # 转换绑定配置
        tool_bindings = []
        for binding in request.bindings:
            tool_binding = {
                "tool_id": binding.tool_id,
                "config": {
                    "is_enabled": binding.is_enabled,
                    "priority": binding.priority,
                    "max_calls_per_task": binding.max_calls_per_task,
                    "timeout_override": binding.timeout_override,
                    "custom_config": binding.custom_config
                }
            }
            tool_bindings.append(tool_binding)
        
        result = await agent_tool_service.batch_bind_tools(
            agent_id=agent_uuid,
            user_id=current_user.user_id,
            tool_bindings=tool_bindings
        )
        
        return BaseResponse(
            success=True,
            message=f"批量绑定完成: 成功 {result['successful_bindings']}, 失败 {result['failed_bindings']}",
            data=result
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的Agent ID"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量绑定工具失败: {str(e)}"
        )

@router.put("/agents/{agent_id}/tools/{tool_id}", response_model=BaseResponse)
async def update_tool_binding(
    agent_id: str,
    tool_id: str,
    request: ToolBindingUpdateRequest,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """更新工具绑定配置"""
    try:
        # 首先获取绑定ID
        agent_uuid = uuid.UUID(agent_id)
        tool_uuid = uuid.UUID(tool_id)
        
        # 查找绑定记录
        tools = await agent_tool_service.get_agent_tools(
            agent_id=agent_uuid,
            user_id=current_user.user_id
        )
        
        binding_record = None
        for tool in tools:
            if str(tool['tool_id']) == tool_id:
                binding_record = tool
                break
        
        if not binding_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工具绑定不存在"
            )
        
        binding_uuid = binding_record['binding_id']
        
        # 构建更新数据
        updates = {}
        if request.is_enabled is not None:
            updates['is_enabled'] = request.is_enabled
        if request.priority is not None:
            updates['priority'] = request.priority
        if request.max_calls_per_task is not None:
            updates['max_calls_per_task'] = request.max_calls_per_task
        if request.timeout_override is not None:
            updates['timeout_override'] = request.timeout_override
        if request.custom_config is not None:
            updates['custom_config'] = request.custom_config
        
        result = await agent_tool_service.update_tool_binding(
            binding_id=binding_uuid,
            user_id=current_user.user_id,
            updates=updates
        )
        
        return BaseResponse(
            success=True,
            message="工具绑定配置更新成功",
            data={
                "binding_id": str(binding_uuid),
                "agent_id": agent_id,
                "tool_id": tool_id,
                "updated_fields": list(updates.keys())
            }
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的ID格式"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新工具绑定失败: {str(e)}"
        )

@router.delete("/agents/{agent_id}/tools/{tool_id}", response_model=BaseResponse)
async def unbind_tool_from_agent(
    agent_id: str,
    tool_id: str,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """解除Agent工具绑定"""
    try:
        # 获取绑定ID
        agent_uuid = uuid.UUID(agent_id)
        
        tools = await agent_tool_service.get_agent_tools(
            agent_id=agent_uuid,
            user_id=current_user.user_id
        )
        
        binding_record = None
        for tool in tools:
            if str(tool['tool_id']) == tool_id:
                binding_record = tool
                break
        
        if not binding_record:
            # 修复：如果找不到绑定记录，可能是工具已失效，尝试自动清理
            logger.warning(f"工具绑定记录不存在，尝试自动清理失效绑定: agent_id={agent_id}, tool_id={tool_id}")
            
            cleanup_result = await agent_tool_service.cleanup_unhealthy_tool_bindings(
                user_id=current_user.user_id
            )
            
            if cleanup_result['cleaned_bindings'] > 0:
                return BaseResponse(
                    success=True,
                    message=f"工具已失效，已自动清理 {cleanup_result['cleaned_bindings']} 个失效绑定",
                    data={
                        "agent_id": agent_id,
                        "tool_id": tool_id,
                        "cleanup_result": cleanup_result
                    }
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="工具绑定不存在"
                )
        
        binding_uuid = binding_record['binding_id']
        
        success = await agent_tool_service.unbind_tool_from_agent(
            binding_id=binding_uuid,
            user_id=current_user.user_id
        )
        
        if success:
            return BaseResponse(
                success=True,
                message="工具绑定解除成功",
                data={
                    "agent_id": agent_id,
                    "tool_id": tool_id,
                    "tool_name": binding_record['tool_name']
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工具绑定不存在或已解除"
            )
        
    except ValueError as ve:
        # 处理权限相关的ValueError
        if "无权删除" in str(ve):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(ve)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(ve)
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"解除工具绑定失败: {str(e)}"
        )

@router.post("/agents/cleanup-unhealthy-bindings", response_model=BaseResponse)
async def cleanup_unhealthy_tool_bindings(
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """自动清理失效工具的绑定"""
    try:
        result = await agent_tool_service.cleanup_unhealthy_tool_bindings(
            user_id=current_user.user_id
        )
        
        return BaseResponse(
            success=True,
            message=f"失效工具绑定清理完成，已清理 {result['cleaned_bindings']} 个绑定",
            data=result
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理失效工具绑定失败: {str(e)}"
        )

@router.post("/agents/cleanup-orphaned-bindings", response_model=BaseResponse)
async def cleanup_orphaned_tool_bindings(
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """清理孤儿工具绑定（工具已不存在的绑定）"""
    try:
        result = await agent_tool_service.cleanup_orphaned_bindings(
            user_id=current_user.user_id
        )
        
        return BaseResponse(
            success=True,
            message=f"孤儿工具绑定清理完成，已清理 {result['cleaned_orphans']} 个绑定",
            data=result
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理孤儿工具绑定失败: {str(e)}"
        )

@router.post("/agents/cleanup-all-bindings", response_model=BaseResponse)
async def cleanup_all_tool_bindings(
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """全面清理所有失效的工具绑定（失效工具 + 孤儿绑定）"""
    try:
        # 先清理失效工具绑定
        unhealthy_result = await agent_tool_service.cleanup_unhealthy_tool_bindings(
            user_id=current_user.user_id
        )
        
        # 再清理孤儿绑定
        orphaned_result = await agent_tool_service.cleanup_orphaned_bindings(
            user_id=current_user.user_id
        )
        
        total_cleaned = unhealthy_result['cleaned_bindings'] + orphaned_result['cleaned_orphans']
        
        return BaseResponse(
            success=True,
            message=f"全面清理完成，共清理 {total_cleaned} 个失效绑定",
            data={
                "total_cleaned": total_cleaned,
                "unhealthy_cleaned": unhealthy_result['cleaned_bindings'],
                "orphaned_cleaned": orphaned_result['cleaned_orphans'],
                "unhealthy_details": unhealthy_result['details'],
                "orphaned_details": orphaned_result['details']
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"全面清理工具绑定失败: {str(e)}"
        )

# ===============================
# Agent工具配置相关接口
# ===============================

@router.get("/agents/{agent_id}/tool-config", response_model=BaseResponse)
async def get_agent_tool_config(
    agent_id: str,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """获取Agent的工具配置 (替代原有的tool_config字段)"""
    try:
        agent_uuid = uuid.UUID(agent_id)
        
        config = await agent_tool_service.get_agent_tool_config(agent_uuid)
        
        return BaseResponse(
            success=True,
            message="获取Agent工具配置成功",
            data={
                "agent_id": agent_id,
                "tool_config": config
            }
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的Agent ID"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取Agent工具配置失败: {str(e)}"
        )

@router.get("/agents/{agent_id}/execution-tools", response_model=BaseResponse)
async def get_agent_execution_tools(
    agent_id: str,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """获取Agent可用于执行的工具列表"""
    try:
        agent_uuid = uuid.UUID(agent_id)
        
        tools = await agent_tool_service.get_agent_tools_for_execution(agent_uuid)
        
        return BaseResponse(
            success=True,
            message=f"获取Agent执行工具成功，共 {len(tools)} 个可用工具",
            data={
                "agent_id": agent_id,
                "available_tools_count": len(tools),
                "tools": tools
            }
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的Agent ID"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取Agent执行工具失败: {str(e)}"
        )

@router.get("/agents/{agent_id}/tool-stats", response_model=BaseResponse)
async def get_agent_tool_usage_stats(
    agent_id: str,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """获取Agent工具使用统计"""
    try:
        agent_uuid = uuid.UUID(agent_id)
        
        stats = await agent_tool_service.get_agent_tool_usage_stats(agent_uuid)
        
        return BaseResponse(
            success=True,
            message="获取Agent工具统计成功",
            data={
                "agent_id": agent_id,
                "stats": stats
            }
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的Agent ID"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取Agent工具统计失败: {str(e)}"
        )

# ===============================
# 工具推荐和发现接口
# ===============================

@router.get("/tools/popular", response_model=BaseResponse)
async def get_popular_tools(
    limit: int = 10,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """获取用户的热门工具列表"""
    try:
        if limit < 1 or limit > 50:
            limit = 10
        
        popular_tools = await agent_tool_service.get_popular_tools(
            user_id=current_user.user_id,
            limit=limit
        )
        
        return BaseResponse(
            success=True,
            message=f"获取热门工具成功，共 {len(popular_tools)} 个",
            data={
                "tools": popular_tools
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取热门工具失败: {str(e)}"
        )