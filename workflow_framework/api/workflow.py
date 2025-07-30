"""
工作流管理API路由
Workflow Management API Routes
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from loguru import logger

from ..models.base import BaseResponse
from ..models.workflow import WorkflowCreate, WorkflowUpdate, WorkflowResponse
from ..services.workflow_service import WorkflowService
from ..utils.middleware import get_current_active_user, CurrentUser, get_current_user_context
from ..utils.exceptions import (
    ValidationError, ConflictError, handle_validation_error, handle_conflict_error
)

# 创建路由器
router = APIRouter(prefix="/workflows", tags=["工作流管理"])

# 工作流服务实例
workflow_service = WorkflowService()


@router.post("", response_model=BaseResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    workflow_data: dict = None,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    创建新工作流
    
    Args:
        workflow_data: 工作流创建数据
        current_user: 当前用户
        
    Returns:
        创建的工作流信息
    """
    try:
        if not workflow_data:
            raise ValidationError("请提供工作流数据")
        
        # 设置创建者ID
        workflow_data["creator_id"] = current_user.user_id
        
        # 创建WorkflowCreate对象
        workflow_create = WorkflowCreate(**workflow_data)
        
        # 创建工作流
        workflow_response = await workflow_service.create_workflow(workflow_create)
        
        logger.info(f"用户 {current_user.username} 创建了工作流: {workflow_data.get('name', '')}")
        
        return BaseResponse(
            success=True,
            message="工作流创建成功",
            data={
                "workflow": workflow_response.model_dump(),
                "message": "工作流已创建，可以开始添加节点"
            }
        )
        
    except ValidationError as e:
        logger.warning(f"工作流创建输入验证失败: {e}")
        raise handle_validation_error(e)
    except ConflictError as e:
        logger.warning(f"工作流创建冲突: {e}")
        raise handle_conflict_error(e)
    except Exception as e:
        logger.error(f"创建工作流异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建工作流失败，请稍后再试"
        )


@router.get("", response_model=BaseResponse)
async def get_user_workflows(
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取当前用户的工作流列表
    
    Args:
        current_user: 当前用户
        
    Returns:
        用户的工作流列表
    """
    try:
        workflows = await workflow_service.get_user_workflows(current_user.user_id)
        
        return BaseResponse(
            success=True,
            message="获取工作流列表成功",
            data={
                "workflows": [workflow.model_dump() for workflow in workflows],
                "count": len(workflows)
            }
        )
        
    except Exception as e:
        logger.error(f"获取用户工作流列表异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取工作流列表失败"
        )


@router.get("/{workflow_base_id}", response_model=BaseResponse)
async def get_workflow(
    workflow_base_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取工作流详细信息
    
    Args:
        workflow_base_id: 工作流基础ID
        current_user: 当前用户
        
    Returns:
        工作流详细信息
    """
    try:
        workflow = await workflow_service.get_workflow_by_base_id(workflow_base_id)
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流不存在"
            )
        
        # 检查访问权限（暂时只允许创建者访问）
        if workflow.creator_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此工作流"
            )
        
        return BaseResponse(
            success=True,
            message="获取工作流信息成功",
            data={"workflow": workflow.model_dump()}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工作流详细信息异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取工作流信息失败"
        )


@router.put("/{workflow_base_id}", response_model=BaseResponse)
async def update_workflow(
    workflow_base_id: uuid.UUID,
    workflow_data: WorkflowUpdate,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    更新工作流信息
    
    Args:
        workflow_base_id: 工作流基础ID
        workflow_data: 更新数据
        current_user: 当前用户
        
    Returns:
        更新后的工作流信息
    """
    try:
        # 检查工作流是否存在和权限
        existing_workflow = await workflow_service.get_workflow_by_base_id(workflow_base_id)
        if not existing_workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流不存在"
            )
        
        if existing_workflow.creator_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权修改此工作流"
            )
        
        # 更新工作流
        updated_workflow = await workflow_service.update_workflow(
            workflow_base_id, workflow_data, current_user.user_id
        )
        
        logger.info(f"用户 {current_user.username} 更新了工作流: {workflow_base_id}")
        
        return BaseResponse(
            success=True,
            message="工作流更新成功",
            data={"workflow": updated_workflow.model_dump()}
        )
        
    except HTTPException:
        raise
    except ValidationError as e:
        logger.warning(f"工作流更新输入验证失败: {e}")
        raise handle_validation_error(e)
    except ConflictError as e:
        logger.warning(f"工作流更新冲突: {e}")
        raise handle_conflict_error(e)
    except Exception as e:
        logger.error(f"更新工作流异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新工作流失败，请稍后再试"
        )


@router.delete("/{workflow_base_id}", response_model=BaseResponse)
async def delete_workflow(
    workflow_base_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    删除工作流
    
    Args:
        workflow_base_id: 工作流基础ID
        current_user: 当前用户
        
    Returns:
        删除结果
    """
    try:
        # 检查工作流是否存在和权限
        existing_workflow = await workflow_service.get_workflow_by_base_id(workflow_base_id)
        if not existing_workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流不存在"
            )
        
        if existing_workflow.creator_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此工作流"
            )
        
        # 删除工作流
        success = await workflow_service.delete_workflow(workflow_base_id, current_user.user_id)
        
        if success:
            logger.info(f"用户 {current_user.username} 删除了工作流: {workflow_base_id}")
            return BaseResponse(
                success=True,
                message="工作流删除成功",
                data={"message": "工作流及其所有相关数据已删除"}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除工作流失败"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除工作流异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除工作流失败，请稍后再试"
        )


@router.get("/{workflow_base_id}/versions", response_model=BaseResponse)
async def get_workflow_versions(
    workflow_base_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取工作流版本历史
    
    Args:
        workflow_base_id: 工作流基础ID
        current_user: 当前用户
        
    Returns:
        版本历史列表
    """
    try:
        # 检查工作流是否存在和权限
        existing_workflow = await workflow_service.get_workflow_by_base_id(workflow_base_id)
        if not existing_workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流不存在"
            )
        
        if existing_workflow.creator_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此工作流"
            )
        
        # 获取版本历史
        versions = await workflow_service.get_workflow_versions(workflow_base_id)
        
        return BaseResponse(
            success=True,
            message="获取版本历史成功",
            data={
                "versions": versions,
                "count": len(versions)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工作流版本历史异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取版本历史失败"
        )


@router.get("/search/", response_model=BaseResponse)
async def search_workflows(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(50, ge=1, le=100, description="结果数量限制"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    搜索工作流
    
    Args:
        keyword: 搜索关键词
        limit: 结果数量限制
        current_user: 当前用户
        
    Returns:
        搜索结果
    """
    try:
        workflows = await workflow_service.search_workflows(keyword, limit)
        
        return BaseResponse(
            success=True,
            message="搜索完成",
            data={
                "workflows": [workflow.model_dump() for workflow in workflows],
                "count": len(workflows),
                "keyword": keyword
            }
        )
        
    except Exception as e:
        logger.error(f"搜索工作流异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="搜索失败，请稍后再试"
        )


@router.get("/stats/summary", response_model=BaseResponse)
async def get_workflow_stats(
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取工作流统计信息
    
    Args:
        current_user: 当前用户
        
    Returns:
        统计信息
    """
    try:
        stats = await workflow_service.get_workflow_stats()
        
        return BaseResponse(
            success=True,
            message="获取统计信息成功",
            data={"stats": stats}
        )
        
    except Exception as e:
        logger.error(f"获取工作流统计信息异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取统计信息失败"
        )


# 工作流节点相关端点
@router.get("/{workflow_base_id}/nodes", response_model=BaseResponse)
async def get_workflow_nodes(
    workflow_base_id: uuid.UUID = Path(..., description="工作流基础ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取工作流的所有节点
    
    Args:
        workflow_base_id: 工作流基础ID
        current_user: 当前用户
        
    Returns:
        节点列表
    """
    try:
        from ..services.node_service import NodeService
        node_service = NodeService()
        nodes = await node_service.get_workflow_nodes(workflow_base_id, current_user.user_id)
        
        return BaseResponse(
            success=True,
            message="获取节点列表成功",
            data={
                "nodes": [node.model_dump() for node in nodes],
                "count": len(nodes),
                "workflow_id": str(workflow_base_id)
            }
        )
        
    except Exception as e:
        logger.error(f"获取工作流节点列表异常: {e}")
        if "无权访问" in str(e):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此工作流的节点"
            )
        elif "不存在" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流不存在"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取节点列表失败"
            )


@router.post("/{workflow_base_id}/nodes", response_model=BaseResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow_node(
    workflow_base_id: uuid.UUID = Path(..., description="工作流基础ID"),
    node_data: dict = None,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    为工作流创建新节点
    
    Args:
        workflow_base_id: 工作流基础ID
        node_data: 节点创建数据
        current_user: 当前用户
        
    Returns:
        创建的节点信息
    """
    try:
        from ..services.node_service import NodeService
        from ..models.node import NodeCreate
        
        if not node_data:
            raise ValidationError("请提供节点数据")
        
        # 设置工作流ID
        node_data["workflow_base_id"] = workflow_base_id
        node_data["creator_id"] = current_user.user_id
        
        # 创建NodeCreate对象
        node_create = NodeCreate(**node_data)
        
        node_service = NodeService()
        node_response = await node_service.create_node(node_create, current_user.user_id)
        
        logger.info(f"用户 {current_user.username} 为工作流 {workflow_base_id} 创建了节点: {node_data.get('name', '')}")
        
        return BaseResponse(
            success=True,
            message="节点创建成功",
            data={
                "node": node_response.model_dump(),
                "message": "节点已创建，可以继续添加处理器和连接"
            }
        )
        
    except ValidationError as e:
        logger.warning(f"节点创建输入验证失败: {e}")
        raise handle_validation_error(e)
    except Exception as e:
        logger.error(f"创建节点异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建节点失败，请稍后再试"
        )