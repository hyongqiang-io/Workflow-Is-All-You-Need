"""
工作流合并API端点
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Dict, Any, Optional
import uuid
from loguru import logger

from ..services.workflow_merge_service import WorkflowMergeService
from ..utils.auth import get_current_user

router = APIRouter(
    prefix="/workflow-merge",
    tags=["workflow_merge"],
    responses={404: {"description": "Not found"}},
)

merge_service = WorkflowMergeService()


@router.get("/{workflow_instance_id}/candidates")
async def get_merge_candidates(
    workflow_instance_id: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    获取工作流的合并候选项
    """
    try:
        logger.info(f"🔍 获取合并候选项: {workflow_instance_id}")
        
        # 验证工作流实例ID格式
        try:
            workflow_uuid = uuid.UUID(workflow_instance_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的工作流实例ID格式"
            )
        
        # 获取合并候选项
        candidates = await merge_service.get_merge_candidates(workflow_uuid)
        
        # 转换为前端需要的格式
        candidate_data = [
            {
                "subdivision_id": candidate.subdivision_id,
                "parent_subdivision_id": candidate.parent_subdivision_id,
                "workflow_instance_id": candidate.workflow_instance_id,
                "workflow_base_id": candidate.workflow_base_id,
                "node_name": candidate.node_name,
                "depth": candidate.depth,
                "can_merge": candidate.can_merge,
                "merge_reason": candidate.merge_reason
            }
            for candidate in candidates
        ]
        
        return {
            "success": True,
            "message": "获取合并候选项成功",
            "data": {
                "candidates": candidate_data,
                "total_candidates": len(candidates),
                "mergeable_candidates": len([c for c in candidates if c.can_merge])
            }
        }
        
    except Exception as e:
        logger.error(f"❌ 获取合并候选项失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取合并候选项失败: {str(e)}"
        )


@router.post("/{workflow_instance_id}/execute")
async def execute_workflow_merge(
    workflow_instance_id: str,
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    执行工作流合并
    """
    try:
        logger.info(f"🚀 执行工作流合并: {workflow_instance_id}")
        logger.info(f"合并请求: {request}")
        
        # 验证工作流实例ID格式
        try:
            workflow_uuid = uuid.UUID(workflow_instance_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的工作流实例ID格式"
            )
        
        # 获取请求参数
        selected_subdivisions = request.get("selected_subdivisions", [])
        merge_config = request.get("merge_config", {})
        
        if not selected_subdivisions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="未选择要合并的subdivision"
            )
        
        # 验证subdivision ID格式
        for subdivision_id in selected_subdivisions:
            try:
                uuid.UUID(subdivision_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"无效的subdivision ID格式: {subdivision_id}"
                )
        
        # 执行合并
        merge_result = await merge_service.execute_merge(
            workflow_uuid, 
            selected_subdivisions,
            current_user.user_id
        )
        
        if merge_result["success"]:
            return {
                "success": True,
                "message": "工作流合并成功",
                "data": merge_result
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=merge_result.get("message", "工作流合并失败")
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 工作流合并失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"工作流合并失败: {str(e)}"
        )