"""
节点管理API路由
Node Management API Routes
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Path, Body
from loguru import logger

from ..models.base import BaseResponse
from ..models.node import NodeCreate, NodeUpdate, NodeResponse, NodeConnectionCreate
from ..services.node_service import NodeService
from ..utils.middleware import get_current_active_user, CurrentUser, get_current_user_context
from ..utils.exceptions import ValidationError, handle_validation_error

# 创建路由器
router = APIRouter(prefix="/nodes", tags=["节点管理"])

# 节点服务实例
node_service = NodeService()


@router.post("/", response_model=BaseResponse, status_code=status.HTTP_201_CREATED)
async def create_node(
    node_data: NodeCreate,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    创建新节点
    
    Args:
        node_data: 节点创建数据
        current_user: 当前用户
        
    Returns:
        创建的节点信息
    """
    try:
        node_response = await node_service.create_node(node_data, current_user.user_id)
        
        logger.info(f"用户 {current_user.username} 创建了节点: {node_data.name}")
        
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


@router.get("/workflow/{workflow_base_id}", response_model=BaseResponse)
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


@router.get("/{node_base_id}/workflow/{workflow_base_id}", response_model=BaseResponse)
async def get_node(
    node_base_id: uuid.UUID = Path(..., description="节点基础ID"),
    workflow_base_id: uuid.UUID = Path(..., description="工作流基础ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取节点详细信息
    
    Args:
        node_base_id: 节点基础ID
        workflow_base_id: 工作流基础ID
        current_user: 当前用户
        
    Returns:
        节点详细信息
    """
    try:
        node = await node_service.get_node_by_base_id(node_base_id, workflow_base_id)
        
        if not node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="节点不存在"
            )
        
        return BaseResponse(
            success=True,
            message="获取节点信息成功",
            data={"node": node.model_dump()}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取节点详细信息异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取节点信息失败"
        )


@router.put("/{node_base_id}/workflow/{workflow_base_id}", response_model=BaseResponse)
async def update_node(
    node_base_id: uuid.UUID = Path(..., description="节点基础ID"),
    workflow_base_id: uuid.UUID = Path(..., description="工作流基础ID"),
    node_data: NodeUpdate = Body(...),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    更新节点信息
    
    Args:
        node_base_id: 节点基础ID
        workflow_base_id: 工作流基础ID
        node_data: 更新数据
        current_user: 当前用户
        
    Returns:
        更新后的节点信息
    """
    logger.info(f"🚀 开始处理节点更新请求: {node_base_id} / {workflow_base_id}")
    try:
        logger.info(f"🔥 API入口 - 更新节点请求: node_base_id={node_base_id}, workflow_base_id={workflow_base_id}")
        logger.info(f"🔥 API入口 - 更新数据: {node_data.model_dump()}")
        logger.info(f"🔥 API入口 - 当前用户: {current_user.user_id}")
        
        updated_node = await node_service.update_node(
            node_base_id, workflow_base_id, node_data, current_user.user_id
        )
        
        logger.info(f"用户 {current_user.username} 更新了节点: {node_base_id}")
        
        return BaseResponse(
            success=True,
            message="节点更新成功",
            data={"node": updated_node.model_dump()}
        )
        
    except ValidationError as e:
        logger.warning(f"节点更新输入验证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "VALIDATION_ERROR",
                "message": f"数据验证失败: {str(e)}",
                "details": str(e)
            }
        )
    except ValueError as e:
        logger.warning(f"节点更新业务逻辑错误: {e}")
        error_msg = str(e)
        if "不存在" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="节点不存在"
            )
        elif "无权" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权修改此节点"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_code": "BUSINESS_ERROR", 
                    "message": error_msg,
                    "details": error_msg
                }
            )
    except Exception as e:
        logger.error(f"更新节点异常: {e}")
        import traceback
        logger.error(f"异常堆栈: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_ERROR",
                "message": "更新节点失败，请稍后再试",
                "details": str(e)
            }
        )


@router.delete("/{node_base_id}/workflow/{workflow_base_id}", response_model=BaseResponse)
async def delete_node(
    node_base_id: uuid.UUID = Path(..., description="节点基础ID"),
    workflow_base_id: uuid.UUID = Path(..., description="工作流基础ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    删除节点
    
    Args:
        node_base_id: 节点基础ID
        workflow_base_id: 工作流基础ID
        current_user: 当前用户
        
    Returns:
        删除结果
    """
    try:
        success = await node_service.delete_node(
            node_base_id, workflow_base_id, current_user.user_id
        )
        
        if success:
            logger.info(f"用户 {current_user.username} 删除了节点: {node_base_id}")
            return BaseResponse(
                success=True,
                message="节点删除成功",
                data={"message": "节点及其相关连接已删除"}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除节点失败"
            )
        
    except Exception as e:
        logger.error(f"删除节点异常: {e}")
        if "不存在" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="节点不存在"
            )
        elif "无权" in str(e):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此节点"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除节点失败，请稍后再试"
            )


@router.post("/connections", response_model=BaseResponse, status_code=status.HTTP_201_CREATED)
async def create_node_connection(
    connection_data: NodeConnectionCreate,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    创建节点连接
    
    Args:
        connection_data: 连接创建数据
        current_user: 当前用户
        
    Returns:
        创建的连接信息
    """
    try:
        connection = await node_service.create_node_connection(
            connection_data, current_user.user_id
        )
        
        logger.info(f"用户 {current_user.username} 创建了节点连接")
        
        return BaseResponse(
            success=True,
            message="节点连接创建成功",
            data={
                "connection": connection,
                "message": "节点连接已创建"
            }
        )
        
    except Exception as e:
        logger.error(f"创建节点连接异常: {e}")
        if "无权" in str(e):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权在此工作流中创建连接"
            )
        elif "不存在" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="源节点或目标节点不存在"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="创建节点连接失败，请稍后再试"
            )


@router.get("/connections/workflow/{workflow_base_id}", response_model=BaseResponse)
async def get_workflow_connections(
    workflow_base_id: uuid.UUID = Path(..., description="工作流基础ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取工作流的所有节点连接
    
    Args:
        workflow_base_id: 工作流基础ID
        current_user: 当前用户
        
    Returns:
        连接列表
    """
    try:
        connections = await node_service.get_workflow_connections(
            workflow_base_id, current_user.user_id
        )
        
        return BaseResponse(
            success=True,
            message="获取连接列表成功",
            data={
                "connections": connections,
                "count": len(connections),
                "workflow_id": str(workflow_base_id)
            }
        )
        
    except Exception as e:
        logger.error(f"获取工作流连接列表异常: {e}")
        if "无权访问" in str(e):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此工作流的连接"
            )
        elif "不存在" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流不存在"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取连接列表失败"
            )


@router.delete("/connections", response_model=BaseResponse)
async def delete_node_connection(
    from_node_base_id: uuid.UUID = Body(..., description="源节点基础ID"),
    to_node_base_id: uuid.UUID = Body(..., description="目标节点基础ID"),
    workflow_base_id: uuid.UUID = Body(..., description="工作流基础ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    删除节点连接
    
    Args:
        from_node_base_id: 源节点基础ID
        to_node_base_id: 目标节点基础ID
        workflow_base_id: 工作流基础ID
        current_user: 当前用户
        
    Returns:
        删除结果
    """
    try:
        logger.info(f"删除连接请求: from={from_node_base_id}, to={to_node_base_id}, workflow={workflow_base_id}")
        
        success = await node_service.delete_node_connection(
            from_node_base_id, to_node_base_id, workflow_base_id, current_user.user_id
        )
        
        if success:
            logger.info(f"用户 {current_user.username} 删除了节点连接")
            return BaseResponse(
                success=True,
                message="节点连接删除成功",
                data={"message": "连接已删除"}
            )
        else:
            logger.warning(f"连接删除失败，可能连接不存在")
            return BaseResponse(
                success=True,
                message="连接删除成功（连接可能已不存在）",
                data={"message": "连接已删除"}
            )
        
    except ValueError as e:
        logger.warning(f"删除节点连接业务逻辑错误: {e}")
        error_msg = str(e)
        if "无权" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此工作流的连接"
            )
        elif "不存在" in error_msg:
            # 连接不存在也算删除成功
            return BaseResponse(
                success=True,
                message="连接删除成功（连接已不存在）",
                data={"message": "连接已删除"}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_code": "BUSINESS_ERROR",
                    "message": error_msg,
                    "details": error_msg
                }
            )
    except Exception as e:
        logger.error(f"删除节点连接异常: {e}")
        import traceback
        logger.error(f"异常堆栈: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_ERROR",
                "message": "删除连接失败，请稍后再试",
                "details": str(e)
            }
        )


@router.post("/{node_base_id}/processors", response_model=BaseResponse, status_code=status.HTTP_201_CREATED)
async def assign_processor_to_node(
    node_base_id: uuid.UUID = Path(..., description="节点基础ID"),
    workflow_base_id: uuid.UUID = Body(..., description="工作流基础ID"),
    processor_id: uuid.UUID = Body(..., description="处理器ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    为节点分配处理器
    
    Args:
        node_base_id: 节点基础ID
        workflow_base_id: 工作流基础ID
        processor_id: 处理器ID
        current_user: 当前用户
        
    Returns:
        分配结果
    """
    try:
        result = await node_service.assign_processor_to_node(
            node_base_id, workflow_base_id, processor_id, current_user.user_id
        )
        
        logger.info(f"用户 {current_user.username} 为节点分配了处理器")
        
        return BaseResponse(
            success=True,
            message="处理器分配成功",
            data={
                "assignment": result,
                "message": "处理器已分配给节点"
            }
        )
        
    except Exception as e:
        logger.error(f"分配处理器异常: {e}")
        if "无权" in str(e):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权为此工作流的节点分配处理器"
            )
        elif "不存在" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="节点或处理器不存在"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="分配处理器失败，请稍后再试"
            )


@router.get("/{node_base_id}/processors", response_model=BaseResponse)
async def get_node_processors(
    node_base_id: uuid.UUID = Path(..., description="节点基础ID"),
    workflow_base_id: uuid.UUID = Path(..., description="工作流基础ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取节点的处理器列表
    
    Args:
        node_base_id: 节点基础ID
        workflow_base_id: 工作流基础ID
        current_user: 当前用户
        
    Returns:
        处理器列表
    """
    try:
        processors = await node_service.get_node_processors(
            node_base_id, workflow_base_id, current_user.user_id
        )
        
        return BaseResponse(
            success=True,
            message="获取节点处理器列表成功",
            data={
                "processors": processors,
                "count": len(processors),
                "node_id": str(node_base_id)
            }
        )
        
    except Exception as e:
        logger.error(f"获取节点处理器列表异常: {e}")
        if "无权访问" in str(e):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此工作流的节点处理器"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取处理器列表失败"
            )


@router.delete("/{node_base_id}/processors/{processor_id}", response_model=BaseResponse)
async def remove_processor_from_node(
    node_base_id: uuid.UUID = Path(..., description="节点基础ID"),
    processor_id: uuid.UUID = Path(..., description="处理器ID"),
    workflow_base_id: uuid.UUID = Body(..., description="工作流基础ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    从节点移除处理器
    
    Args:
        node_base_id: 节点基础ID
        processor_id: 处理器ID
        workflow_base_id: 工作流基础ID
        current_user: 当前用户
        
    Returns:
        移除结果
    """
    try:
        success = await node_service.remove_processor_from_node(
            node_base_id, workflow_base_id, processor_id, current_user.user_id
        )
        
        if success:
            logger.info(f"用户 {current_user.username} 从节点移除了处理器")
            return BaseResponse(
                success=True,
                message="处理器移除成功",
                data={"message": "处理器已从节点移除"}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="移除处理器失败"
            )
        
    except Exception as e:
        logger.error(f"移除处理器异常: {e}")
        if "无权" in str(e):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权移除此工作流节点的处理器"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="移除处理器失败，请稍后再试"
            )