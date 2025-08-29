"""
工作流模板连接 API
Workflow Template Connection API

提供工作流模板之间连接关系的 REST API 接口
用于细分预览中的工作流连接图功能
"""

import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from loguru import logger

from ..services.workflow_template_connection_service import WorkflowTemplateConnectionService
from ..utils.auth import get_current_user_context
from ..utils.responses import success_response, error_response

router = APIRouter(prefix="/api/workflow-template-connections", tags=["Workflow Template Connections"])

# 实例化服务
template_connection_service = WorkflowTemplateConnectionService()


@router.get("/workflow-instances/{workflow_instance_id}/template-connections")
async def get_workflow_template_connections(
    workflow_instance_id: uuid.UUID,
    max_depth: int = Query(10, description="最大递归深度，防止无限递归", ge=1, le=20),
    current_user = Depends(get_current_user_context)
):
    """
    获取工作流实例的模板连接图数据
    
    用于在细分预览中显示工作流模板之间的连接关系
    只显示已完成执行的实例的连接关系
    
    Args:
        workflow_instance_id: 工作流实例ID
        current_user: 当前用户
        
    Returns:
        工作流模板连接图数据
    """
    try:
        logger.info(f"🔍 获取工作流模板连接图: {workflow_instance_id} by user {current_user.user_id}")
        
        # TODO: 添加权限验证 - 检查用户是否有权限访问该工作流实例
        
        # 获取模板连接数据（支持递归展开）
        connection_data = await template_connection_service.get_workflow_template_connections(
            workflow_instance_id, max_depth
        )
        
        return success_response(
            data=connection_data,
            message=f"成功获取工作流模板连接图，找到 {connection_data['statistics']['total_subdivisions']} 个连接关系"
        )
        
    except Exception as e:
        logger.error(f"❌ 获取工作流模板连接图失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取工作流模板连接图失败: {str(e)}"
        )


@router.get("/workflow-instances/{workflow_instance_id}/detailed-template-connections")
async def get_detailed_workflow_template_connections(
    workflow_instance_id: uuid.UUID,
    max_depth: int = Query(10, description="最大递归深度，防止无限递归", ge=1, le=20),
    current_user = Depends(get_current_user_context)
):
    """
    获取工作流实例的优化版详细模板连接图数据
    
    利用parent_subdivision_id优化的版本：
    - 使用WITH RECURSIVE一次性获取所有层级
    - 避免递归数据库调用，性能提升显著
    - 批量计算统计信息
    - 提供更丰富的层级信息和合并候选数据
    
    Args:
        workflow_instance_id: 工作流实例ID
        max_depth: 最大递归深度
        current_user: 当前用户
        
    Returns:
        优化后的详细工作流模板连接图数据
    """
    try:
        logger.info(f"🚀 [优化版API] 获取详细模板连接图: {workflow_instance_id} by user {current_user.user_id}")
        
        # TODO: 添加权限验证 - 检查用户是否有权限访问该工作流实例
        
        # 使用优化后的方法获取详细连接数据
        detailed_connection_data = await template_connection_service.get_detailed_workflow_connections(
            workflow_instance_id, max_depth
        )
        
        return success_response(
            data=detailed_connection_data,
            message=f"成功获取优化版详细模板连接图，找到 {detailed_connection_data['statistics']['total_subdivisions']} 个连接关系，最大深度 {detailed_connection_data.get('performance_info', {}).get('max_depth_reached', 0)}"
        )
        
    except Exception as e:
        logger.error(f"❌ 获取优化版详细模板连接图失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取优化版详细模板连接图失败: {str(e)}"
        )


@router.get("/workflow-templates/{workflow_base_id}/connection-summary")
async def get_workflow_template_connection_summary(
    workflow_base_id: uuid.UUID,
    current_user = Depends(get_current_user_context)
):
    """
    获取工作流模板的连接关系摘要
    
    用于显示工作流模板级别的连接统计信息
    
    Args:
        workflow_base_id: 工作流基础ID（模板ID）
        current_user: 当前用户
        
    Returns:
        工作流模板连接摘要数据
    """
    try:
        logger.info(f"📊 获取工作流模板连接摘要: {workflow_base_id} by user {current_user.user_id}")
        
        # TODO: 添加权限验证 - 检查用户是否有权限访问该工作流模板
        
        # 获取连接摘要数据
        summary_data = await template_connection_service.get_workflow_template_connection_summary(workflow_base_id)
        
        return success_response(
            data=summary_data,
            message=f"成功获取工作流模板连接摘要"
        )
        
    except Exception as e:
        logger.error(f"❌ 获取工作流模板连接摘要失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取工作流模板连接摘要失败: {str(e)}"
        )


@router.get("/workflow-instances/{workflow_instance_id}/subdivision-graph")  
async def get_subdivision_connection_graph(
    workflow_instance_id: uuid.UUID,
    current_user = Depends(get_current_user_context),
    include_pending: bool = Query(False, description="是否包含未完成的子工作流"),
    layout_algorithm: str = Query("hierarchical", description="图形布局算法"),
    max_depth: int = Query(10, description="最大递归深度", ge=1, le=20)
):
    """
    获取细分连接图数据（专门用于图形可视化）
    
    优化的API接口，专门为前端图形组件提供数据
    
    Args:
        workflow_instance_id: 工作流实例ID
        current_user: 当前用户
        include_pending: 是否包含未完成的子工作流
        layout_algorithm: 图形布局算法
        
    Returns:
        优化的图形数据结构
    """
    try:
        logger.info(f"🎨 获取细分连接图数据: {workflow_instance_id}")
        
        # 获取完整的连接数据（支持递归）
        connection_data = await template_connection_service.get_workflow_template_connections(
            workflow_instance_id, max_depth
        )
        
        # 根据参数过滤数据
        template_connections = connection_data["template_connections"]
        if not include_pending:
            # 只包含已完成的子工作流
            template_connections = [
                conn for conn in template_connections 
                if conn["sub_workflow"]["status"] == "completed"
            ]
        
        # 重新构建连接图（应用过滤和布局参数）
        if layout_algorithm == "tree":
            # 使用新的树状布局算法
            filtered_graph = template_connection_service._build_recursive_connection_graph(template_connections)
            filtered_graph["layout"]["algorithm"] = "tree"
            filtered_graph["layout"]["node_spacing"] = 250  # 树状布局需要更大的节点间距
            filtered_graph["layout"]["level_spacing"] = 150
        elif layout_algorithm == "file_system":
            # 使用递归连接图构建方法，支持文件系统式布局
            filtered_graph = template_connection_service._build_recursive_connection_graph(template_connections)
            filtered_graph["layout"]["algorithm"] = "file_system"
        else:
            filtered_graph = template_connection_service._build_connection_graph(template_connections)
        
        # 根据布局算法调整图形参数
        if layout_algorithm == "force":
            filtered_graph["layout"]["algorithm"] = "force"
            filtered_graph["layout"]["repulsion"] = 300
            filtered_graph["layout"]["attraction"] = 0.1
        elif layout_algorithm == "circular":
            filtered_graph["layout"]["algorithm"] = "circular"
            filtered_graph["layout"]["radius"] = 200
        
        # 构建响应数据
        response_data = {
            "workflow_instance_id": str(workflow_instance_id),
            "graph": filtered_graph,
            "metadata": {
                "total_connections": len(template_connections),
                "include_pending": include_pending,
                "layout_algorithm": layout_algorithm,
                "generated_at": connection_data.get("statistics", {})
            }
        }
        
        return success_response(
            data=response_data,
            message=f"成功获取细分连接图，包含 {len(filtered_graph['nodes'])} 个节点和 {len(filtered_graph['edges'])} 条连接"
        )
        
    except Exception as e:
        logger.error(f"❌ 获取细分连接图数据失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取细分连接图数据失败: {str(e)}"
        )


@router.get("/subdivisions/{subdivision_id}/connection-detail")
async def get_subdivision_connection_detail(
    subdivision_id: uuid.UUID,
    current_user = Depends(get_current_user_context)
):
    """
    获取单个细分连接的详细信息
    
    用于在用户点击连接边时显示详细信息
    
    Args:
        subdivision_id: 细分ID
        current_user: 当前用户
        
    Returns:
        细分连接的详细信息
    """
    try:
        logger.info(f"🔍 获取细分连接详情: {subdivision_id}")
        
        # 从task_subdivision_service获取详细信息
        from ..services.task_subdivision_service import TaskSubdivisionService
        subdivision_service = TaskSubdivisionService()
        
        # 获取细分的基本信息
        subdivision_detail = await subdivision_service.subdivision_repo.get_subdivision_by_id(subdivision_id)
        
        if not subdivision_detail:
            raise HTTPException(
                status_code=404,
                detail=f"未找到细分连接: {subdivision_id}"
            )
        
        # 构建详细信息响应
        detail_data = {
            "subdivision_id": str(subdivision_id),
            "subdivision_name": subdivision_detail.get("subdivision_name"),
            "subdivision_description": subdivision_detail.get("subdivision_description"),
            "created_at": subdivision_detail.get("subdivision_created_at").isoformat() if subdivision_detail.get("subdivision_created_at") else None,
            "subdivider_name": subdivision_detail.get("subdivider_name"),
            "original_task": {
                "task_id": str(subdivision_detail.get("original_task_id")),
                "task_title": subdivision_detail.get("original_task_title")
            },
            "sub_workflow": {
                "workflow_base_id": str(subdivision_detail.get("sub_workflow_base_id")),
                "workflow_name": subdivision_detail.get("sub_workflow_name"),
                "instance_id": str(subdivision_detail.get("sub_workflow_instance_id")) if subdivision_detail.get("sub_workflow_instance_id") else None,
                "total_nodes": subdivision_detail.get("total_sub_nodes", 0),
                "completed_nodes": subdivision_detail.get("completed_sub_nodes", 0)
            },
            "status": subdivision_detail.get("status")
        }
        
        return success_response(
            data=detail_data,
            message="成功获取细分连接详情"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取细分连接详情失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取细分连接详情失败: {str(e)}"
        )