"""
上下文健康监控API
Context Health Monitoring API
"""

import uuid
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends
from loguru import logger

from ..utils.middleware import CurrentUser
from ..utils.auth import get_current_user
from ..services.workflow_execution_context import get_context_manager

router = APIRouter(prefix="/api/context", tags=["context-health"])


@router.get("/health/{workflow_instance_id}")
async def check_workflow_context_health(
    workflow_instance_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """检查特定工作流的上下文健康状态"""
    try:
        logger.info(f"🔍 检查工作流上下文健康状态: {workflow_instance_id}")
        
        context_manager = get_context_manager()
        health_status = await context_manager.check_context_health(workflow_instance_id)
        
        return {
            "success": True,
            "workflow_instance_id": str(workflow_instance_id),
            "health_status": health_status,
            "timestamp": "2025-01-01T00:00:00"  # 实际使用时应该用 datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"检查上下文健康状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"检查上下文健康状态失败: {str(e)}")


@router.post("/recovery/{workflow_instance_id}")
async def trigger_context_recovery(
    workflow_instance_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """手动触发工作流上下文恢复"""
    try:
        logger.info(f"🔧 手动触发上下文恢复: {workflow_instance_id}")
        
        context_manager = get_context_manager()
        
        # 检查当前健康状态
        health_before = await context_manager.check_context_health(workflow_instance_id)
        
        # 尝试恢复上下文
        recovered_context = await context_manager._restore_context_from_database(workflow_instance_id)
        
        if recovered_context:
            # 检查恢复后的健康状态
            health_after = await context_manager.check_context_health(workflow_instance_id)
            
            return {
                "success": True,
                "workflow_instance_id": str(workflow_instance_id),
                "recovery_performed": True,
                "health_before": health_before,
                "health_after": health_after,
                "message": "上下文恢复成功"
            }
        else:
            return {
                "success": False,
                "workflow_instance_id": str(workflow_instance_id),
                "recovery_performed": False,
                "health_before": health_before,
                "message": "上下文恢复失败，工作流可能不存在"
            }
            
    except Exception as e:
        logger.error(f"触发上下文恢复失败: {e}")
        raise HTTPException(status_code=500, detail=f"触发上下文恢复失败: {str(e)}")


@router.get("/overview")
async def get_context_overview(
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """获取所有工作流上下文概览"""
    try:
        context_manager = get_context_manager()
        
        overview = {
            "total_contexts": len(context_manager.contexts),
            "workflow_contexts": [],
            "system_config": {
                "persistence_enabled": context_manager._persistence_enabled,
                "auto_recovery_enabled": context_manager._auto_recovery_enabled
            }
        }
        
        # 获取每个工作流的基本信息
        for workflow_id, context in context_manager.contexts.items():
            workflow_info = {
                "workflow_instance_id": str(workflow_id),
                "completed_nodes": len(context.execution_context.get('completed_nodes', set())),
                "executing_nodes": len(context.execution_context.get('current_executing_nodes', set())),
                "failed_nodes": len(context.execution_context.get('failed_nodes', set())),
                "dependency_count": len(context.node_dependencies),
                "last_activity": context.execution_context.get('last_snapshot_time')
            }
            overview["workflow_contexts"].append(workflow_info)
        
        return {
            "success": True,
            "overview": overview
        }
        
    except Exception as e:
        logger.error(f"获取上下文概览失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取上下文概览失败: {str(e)}")


@router.post("/batch-health-check")
async def batch_health_check(
    workflow_ids: List[str],
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """批量检查多个工作流的上下文健康状态"""
    try:
        logger.info(f"🔍 批量检查 {len(workflow_ids)} 个工作流的上下文健康状态")
        
        context_manager = get_context_manager()
        results = {}
        
        for workflow_id_str in workflow_ids:
            try:
                workflow_id = uuid.UUID(workflow_id_str)
                health_status = await context_manager.check_context_health(workflow_id)
                results[workflow_id_str] = health_status
            except Exception as e:
                logger.error(f"检查工作流 {workflow_id_str} 健康状态失败: {e}")
                results[workflow_id_str] = {
                    "healthy": False,
                    "status": "check_failed",
                    "error": str(e)
                }
        
        # 统计
        healthy_count = sum(1 for status in results.values() if status.get("healthy", False))
        unhealthy_count = len(results) - healthy_count
        
        return {
            "success": True,
            "summary": {
                "total_checked": len(workflow_ids),
                "healthy_count": healthy_count,
                "unhealthy_count": unhealthy_count
            },
            "results": results
        }
        
    except Exception as e:
        logger.error(f"批量健康检查失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量健康检查失败: {str(e)}")


@router.post("/toggle-auto-recovery")
async def toggle_auto_recovery(
    enabled: bool,
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """切换自动恢复功能开关"""
    try:
        context_manager = get_context_manager()
        old_status = context_manager._auto_recovery_enabled
        context_manager._auto_recovery_enabled = enabled
        
        logger.info(f"🔧 自动恢复功能: {old_status} -> {enabled}")
        
        return {
            "success": True,
            "auto_recovery_enabled": enabled,
            "previous_status": old_status,
            "message": f"自动恢复功能已{'启用' if enabled else '禁用'}"
        }
        
    except Exception as e:
        logger.error(f"切换自动恢复功能失败: {e}")
        raise HTTPException(status_code=500, detail=f"切换自动恢复功能失败: {str(e)}")