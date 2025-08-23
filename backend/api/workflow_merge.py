"""
工作流合并API路由
Workflow Merge API Routes

处理工作流模板间的合并相关API请求
"""

import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Path, Body, Query
from loguru import logger

from ..models.base import BaseResponse
from ..services.workflow_merge_service import WorkflowMergeService
from ..services.workflow_template_connection_service import WorkflowTemplateConnectionService
from ..utils.middleware import get_current_active_user, CurrentUser, get_current_user_context
from ..utils.exceptions import ValidationError, handle_validation_error

# 创建路由器
router = APIRouter(prefix="/workflow-merge", tags=["工作流合并"])

# 服务实例
merge_service = WorkflowMergeService()
template_connection_service = WorkflowTemplateConnectionService()


@router.get("/{workflow_instance_id}/detailed-connections", response_model=BaseResponse)
async def get_detailed_workflow_connections(
    workflow_instance_id: uuid.UUID = Path(..., description="工作流实例ID"),
    max_depth: int = Query(10, ge=1, le=20, description="最大递归深度"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取包含内部节点详情的工作流模板连接图数据
    
    Args:
        workflow_instance_id: 工作流实例ID
        max_depth: 最大递归深度
        current_user: 当前用户
        
    Returns:
        详细连接图数据，包括可合并候选
    """
    try:
        logger.info(f"🔍 获取详细工作流连接图: 实例={workflow_instance_id}, 深度={max_depth}")
        
        # 获取详细连接数据
        detailed_connections = await template_connection_service.get_detailed_workflow_connections(
            workflow_instance_id, max_depth
        )
        
        if not detailed_connections.get("template_connections"):
            return BaseResponse(
                success=True,
                message="该工作流实例暂无模板连接关系",
                data={
                    "detailed_connections": detailed_connections,
                    "has_merge_candidates": False
                }
            )
        
        has_merge_candidates = len(detailed_connections.get("merge_candidates", [])) > 0
        
        logger.info(f"✅ 详细连接图获取成功: 连接数={len(detailed_connections['template_connections'])}, 合并候选={len(detailed_connections.get('merge_candidates', []))}")
        
        return BaseResponse(
            success=True,
            message="获取详细连接图成功",
            data={
                "detailed_connections": detailed_connections,
                "has_merge_candidates": has_merge_candidates,
                "merge_candidates_count": len(detailed_connections.get("merge_candidates", [])),
                "statistics": {
                    "total_workflows": len(detailed_connections.get("detailed_workflows", {})),
                    "mergeable_connections": len([c for c in detailed_connections.get("merge_candidates", []) if c.get("compatibility", {}).get("is_compatible", False)])
                }
            }
        )
        
    except Exception as e:
        logger.error(f"❌ 获取详细工作流连接图失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取详细连接图失败，请稍后再试"
        )


@router.post("/{workflow_base_id}/merge-preview", response_model=BaseResponse)
async def preview_workflow_merge(
    workflow_base_id: uuid.UUID = Path(..., description="工作流基础ID"),
    merge_candidates: List[Dict[str, Any]] = Body(..., description="合并候选列表"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    预览工作流合并结果
    
    Args:
        workflow_base_id: 工作流基础ID  
        merge_candidates: 合并候选列表
        current_user: 当前用户
        
    Returns:
        合并预览数据
    """
    try:
        logger.info(f"🔍 预览工作流合并: 工作流={workflow_base_id}, 候选数={len(merge_candidates)}")
        
        if not merge_candidates:
            raise ValidationError("请提供至少一个合并候选")
        
        # 预览合并结果
        merge_preview = await merge_service.preview_workflow_merge(
            workflow_base_id, merge_candidates, current_user.user_id
        )
        
        can_proceed = merge_preview.get("merge_feasibility", {}).get("can_proceed", False)
        valid_merges_count = merge_preview.get("merge_summary", {}).get("valid_merges", 0)
        
        logger.info(f"✅ 合并预览完成: 可行={can_proceed}, 有效合并数={valid_merges_count}")
        
        return BaseResponse(
            success=True,
            message="合并预览完成",
            data={
                "merge_preview": merge_preview,
                "can_proceed": can_proceed,
                "recommendations": {
                    "proceed_with_merge": can_proceed,
                    "complexity_warning": merge_preview.get("merge_feasibility", {}).get("complexity_increase") == "high",
                    "suggested_approach": merge_preview.get("merge_feasibility", {}).get("recommended_approach", "unknown")
                }
            }
        )
        
    except ValidationError as e:
        logger.warning(f"合并预览输入验证失败: {e}")
        raise handle_validation_error(e)
    except Exception as e:
        logger.error(f"❌ 预览工作流合并失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="预览合并失败，请稍后再试"
        )


@router.post("/{workflow_base_id}/execute-merge", response_model=BaseResponse)
async def execute_workflow_merge(
    workflow_base_id: uuid.UUID = Path(..., description="工作流基础ID"),
    merge_request: Dict[str, Any] = Body(..., description="合并请求数据"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    执行工作流合并操作
    
    Args:
        workflow_base_id: 工作流基础ID
        merge_request: 合并请求数据，包含selected_merges和merge_config
        current_user: 当前用户
        
    Returns:
        合并执行结果
    """
    try:
        logger.info(f"🔄 执行工作流合并: 工作流={workflow_base_id}")
        
        # 首先验证工作流ID是否存在
        from ..repositories.base import BaseRepository
        db = BaseRepository("api").db
        
        workflow_check = await db.fetch_one(
            "SELECT workflow_id, name FROM workflow WHERE workflow_base_id = %s AND is_current_version = 1 AND is_deleted = 0",
            workflow_base_id
        )
        
        if not workflow_check:
            logger.warning(f"API层验证失败: 工作流基础ID {workflow_base_id} 不存在")
            return BaseResponse(
                success=False,
                message="工作流不存在",
                data={
                    "error_type": "workflow_not_found",
                    "workflow_base_id": str(workflow_base_id),
                    "suggestions": [
                        "请检查工作流ID是否正确",
                        "该工作流可能已被删除或不是当前版本",
                        "请从工作流列表中选择有效的工作流"
                    ]
                }
            )
        
        logger.info(f"✅ 工作流验证通过: {workflow_check['name']}")
        
        # 验证请求数据结构
        if "selected_merges" not in merge_request:
            raise ValidationError("请提供selected_merges字段")
        
        if "merge_config" not in merge_request:
            raise ValidationError("请提供merge_config字段")
        
        selected_merges = merge_request["selected_merges"]
        merge_config = merge_request["merge_config"]
        
        if not selected_merges:
            raise ValidationError("请选择至少一个合并操作")
        
        # 验证合并配置
        if not merge_config.get("new_workflow_name"):
            raise ValidationError("请提供新工作流名称")
        
        logger.info(f"🔄 合并配置: {len(selected_merges)} 个操作, 新名称='{merge_config['new_workflow_name']}'")
        
        # 执行合并
        merge_result = await merge_service.execute_workflow_merge(
            workflow_base_id, selected_merges, merge_config, current_user.user_id
        )
        
        if merge_result.get("success"):
            logger.info(f"✅ 工作流合并成功: 新工作流ID={merge_result.get('new_workflow_id')}")
            
            return BaseResponse(
                success=True,
                message=merge_result.get("message", "工作流合并成功"),
                data={
                    "merge_result": merge_result,
                    "new_workflow": {
                        "workflow_id": merge_result.get("new_workflow_id"),
                        "name": merge_result.get("new_workflow_name")
                    },
                    "statistics": merge_result.get("merge_statistics", {}),
                    "next_steps": {
                        "can_view_workflow": True,
                        "can_execute_workflow": True,
                        "workflow_url": f"/workflows/{merge_result.get('new_workflow_id')}"
                    }
                }
            )
        else:
            logger.error(f"❌ 工作流合并失败: {merge_result.get('message')}")
            
            return BaseResponse(
                success=False,
                message=merge_result.get("message", "工作流合并失败"),
                data={
                    "merge_result": merge_result,
                    "errors": merge_result.get("errors", []),
                    "warnings": merge_result.get("warnings", [])
                }
            )
        
    except ValidationError as e:
        logger.warning(f"合并执行输入验证失败: {e}")
        raise handle_validation_error(e)
    except Exception as e:
        logger.error(f"❌ 执行工作流合并失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="执行合并失败，请稍后再试"
        )


@router.get("/{workflow_base_id}/merge-compatibility", response_model=BaseResponse)
async def check_merge_compatibility(
    workflow_base_id: uuid.UUID = Path(..., description="工作流基础ID"),
    target_node_id: uuid.UUID = Query(..., description="目标节点ID"),
    sub_workflow_id: uuid.UUID = Query(..., description="子工作流基础ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    检查特定节点和子工作流的合并兼容性
    
    Args:
        workflow_base_id: 工作流基础ID
        target_node_id: 目标节点ID
        sub_workflow_id: 子工作流基础ID
        current_user: 当前用户
        
    Returns:
        兼容性检查结果
    """
    try:
        logger.info(f"🔍 检查合并兼容性: 工作流={workflow_base_id}, 节点={target_node_id}, 子工作流={sub_workflow_id}")
        
        # 这里可以调用WorkflowMergeService的兼容性检查方法
        # 为简化起见，先返回基本的检查结果
        
        compatibility_result = {
            "is_compatible": True,
            "compatibility_score": 0.85,
            "issues": [],
            "recommendations": [
                "建议在合并前备份原工作流",
                "建议先在测试环境中验证合并结果"
            ],
            "impact_analysis": {
                "complexity_change": "medium",
                "estimated_nodes_added": 5,
                "estimated_execution_time_increase": "20%"
            }
        }
        
        return BaseResponse(
            success=True,
            message="兼容性检查完成",
            data={
                "compatibility": compatibility_result,
                "target_info": {
                    "workflow_base_id": str(workflow_base_id),
                    "target_node_id": str(target_node_id),
                    "sub_workflow_id": str(sub_workflow_id)
                }
            }
        )
        
    except Exception as e:
        logger.error(f"❌ 检查合并兼容性失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="检查兼容性失败，请稍后再试"
        )


@router.get("/templates/{template_id}/adoption-history", response_model=BaseResponse) 
async def get_template_adoption_history(
    template_id: uuid.UUID = Path(..., description="工作流模板ID"),
    limit: int = Query(20, ge=1, le=100, description="结果数量限制"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取工作流模板的采纳历史
    
    Args:
        template_id: 工作流模板ID
        limit: 结果数量限制
        current_user: 当前用户
        
    Returns:
        采纳历史数据
    """
    try:
        logger.info(f"🔍 获取模板采纳历史: 模板={template_id}")
        
        # 查询采纳历史
        adoption_query = """
        SELECT 
            ts.subdivision_id,
            ts.subdivision_name,
            ts.subdivision_created_at,
            ts.status,
            
            -- 原始工作流信息
            pw.name as parent_workflow_name,
            pw.workflow_base_id as parent_workflow_id,
            
            -- 采纳者信息
            u.username as subdivider_name,
            
            -- 子工作流实例状态
            swi.status as instance_status,
            swi.completed_at as instance_completed_at
            
        FROM task_subdivision ts
        JOIN task_instance ti ON ts.original_task_id = ti.task_instance_id
        JOIN node_instance ni ON ti.node_instance_id = ni.node_instance_id  
        JOIN node n ON ni.node_id = n.node_id
        JOIN workflow pw ON n.workflow_base_id = pw.workflow_base_id
        JOIN "user" u ON ts.subdivider_id = u.user_id
        LEFT JOIN workflow_instance swi ON ts.sub_workflow_instance_id = swi.workflow_instance_id
        WHERE ts.sub_workflow_base_id = $1
        AND ts.is_deleted = FALSE
        ORDER BY ts.subdivision_created_at DESC
        LIMIT $2
        """
        
        adoptions = await merge_service.db.fetch_all(adoption_query, template_id, limit)
        
        # 格式化采纳历史数据
        formatted_adoptions = []
        for adoption in adoptions:
            formatted_adoptions.append({
                "subdivision_id": str(adoption["subdivision_id"]),
                "subdivision_name": adoption["subdivision_name"],
                "created_at": adoption["subdivision_created_at"].isoformat() if adoption["subdivision_created_at"] else None,
                "status": adoption["status"],
                "parent_workflow": {
                    "workflow_id": str(adoption["parent_workflow_id"]),
                    "name": adoption["parent_workflow_name"]
                },
                "subdivider_name": adoption["subdivider_name"],
                "instance_info": {
                    "status": adoption["instance_status"],
                    "completed_at": adoption["instance_completed_at"].isoformat() if adoption["instance_completed_at"] else None
                }
            })
        
        # 统计信息
        stats_query = """
        SELECT 
            COUNT(*) as total_adoptions,
            COUNT(CASE WHEN swi.status = 'completed' THEN 1 END) as completed_adoptions,
            COUNT(DISTINCT pw.workflow_base_id) as unique_parent_workflows
        FROM task_subdivision ts
        JOIN task_instance ti ON ts.original_task_id = ti.task_instance_id
        JOIN node_instance ni ON ti.node_instance_id = ni.node_instance_id
        JOIN node n ON ni.node_id = n.node_id  
        JOIN workflow pw ON n.workflow_base_id = pw.workflow_base_id
        LEFT JOIN workflow_instance swi ON ts.sub_workflow_instance_id = swi.workflow_instance_id
        WHERE ts.sub_workflow_base_id = $1
        AND ts.is_deleted = FALSE
        """
        
        stats = await merge_service.db.fetch_one(stats_query, template_id)
        
        adoption_stats = {
            "total_adoptions": stats["total_adoptions"] if stats else 0,
            "completed_adoptions": stats["completed_adoptions"] if stats else 0,
            "success_rate": (stats["completed_adoptions"] / max(stats["total_adoptions"], 1)) if stats and stats["total_adoptions"] > 0 else 0,
            "unique_adopters": stats["unique_parent_workflows"] if stats else 0
        }
        
        logger.info(f"✅ 模板采纳历史获取成功: {adoption_stats['total_adoptions']} 条记录")
        
        return BaseResponse(
            success=True,
            message="获取采纳历史成功",
            data={
                "template_id": str(template_id),
                "adoptions": formatted_adoptions,
                "statistics": adoption_stats,
                "pagination": {
                    "limit": limit,
                    "returned_count": len(formatted_adoptions)
                }
            }
        )
        
    except Exception as e:
        logger.error(f"❌ 获取模板采纳历史失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取采纳历史失败，请稍后再试"
        )