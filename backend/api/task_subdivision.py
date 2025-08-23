"""
任务细分API路由
Task Subdivision API Routes
"""

import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, Path, Query
from loguru import logger

from ..models.base import BaseResponse
from ..models.task_subdivision import (
    TaskSubdivisionRequest, TaskSubdivisionResponse,
    AdoptSubdivisionRequest, WorkflowAdoptionResponse,
    WorkflowSubdivisionsResponse
)
from ..services.task_subdivision_service import TaskSubdivisionService
from ..utils.middleware import get_current_user_context, CurrentUser
from ..utils.exceptions import ValidationError, handle_validation_error

# 创建路由器
router = APIRouter(prefix="/task-subdivision", tags=["任务细分"])

# 服务实例
subdivision_service = TaskSubdivisionService()


@router.post("/tasks/{task_id}/subdivide", response_model=BaseResponse, status_code=status.HTTP_201_CREATED)
async def create_task_subdivision(
    task_id: uuid.UUID = Path(..., description="任务ID"),
    request: TaskSubdivisionRequest = None,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    创建任务细分
    
    Args:
        task_id: 任务ID
        request: 细分请求数据
        current_user: 当前用户
        
    Returns:
        创建的任务细分信息
    """
    try:
        logger.info(f"🔄 用户 {current_user.username} 请求细分任务: {task_id}")
        logger.info(f"   细分名称: {request.subdivision_name}")
        logger.info(f"   是否立即执行: {request.execute_immediately}")
        
        # 构造细分数据
        from ..models.task_subdivision import TaskSubdivisionCreate
        subdivision_data = TaskSubdivisionCreate(
            original_task_id=task_id,
            subdivider_id=current_user.user_id,
            subdivision_name=request.subdivision_name,
            subdivision_description=request.subdivision_description,
            sub_workflow_base_id=request.sub_workflow_base_id,
            sub_workflow_data=request.sub_workflow_data,
            context_to_pass=request.task_context.get('task_context_data', '') if request.task_context else ""
        )
        
        # 创建细分
        subdivision = await subdivision_service.create_task_subdivision(
            subdivision_data, request.execute_immediately
        )
        
        logger.info(f"✅ 任务细分创建成功: {subdivision.subdivision_id}")
        
        return BaseResponse(
            success=True,
            message="任务细分创建成功",
            data={
                "subdivision": subdivision.model_dump(),
                "execute_immediately": request.execute_immediately
            }
        )
        
    except ValidationError as e:
        logger.warning(f"任务细分创建验证失败: {e}")
        raise handle_validation_error(e)
    except Exception as e:
        logger.error(f"创建任务细分异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建任务细分失败，请稍后再试"
        )


@router.get("/tasks/{task_id}/subdivisions", response_model=BaseResponse)
async def get_task_subdivisions(
    task_id: uuid.UUID = Path(..., description="任务ID"),
    with_instances_only: bool = Query(False, description="是否只返回有工作流实例的细分"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取任务的所有细分
    
    Args:
        task_id: 任务ID
        with_instances_only: 是否只返回有工作流实例的细分
        current_user: 当前用户
        
    Returns:
        任务的细分列表
    """
    try:
        subdivisions = await subdivision_service.get_task_subdivisions(task_id)
        
        # 如果只需要有工作流实例的细分，过滤并增强数据
        if with_instances_only:
            subdivisions_with_instances = []
            for subdivision in subdivisions:
                # 检查是否有工作流实例ID
                if subdivision.sub_workflow_instance_id:
                    try:
                        # 获取工作流实例详情
                        workflow_instance = await subdivision_service.get_subdivision_workflow_instance(
                            subdivision.subdivision_id
                        )
                        
                        if workflow_instance:
                            # 创建增强的细分数据
                            enhanced_subdivision = subdivision.model_dump()
                            enhanced_subdivision.update({
                                "workflow_instance": {
                                    "workflow_instance_id": workflow_instance.get('workflow_instance_id'),
                                    "workflow_instance_name": workflow_instance.get('workflow_instance_name'),
                                    "status": workflow_instance.get('status'),
                                    "created_at": workflow_instance.get('created_at'),
                                    "started_at": workflow_instance.get('started_at'),
                                    "completed_at": workflow_instance.get('completed_at'),
                                    "result_summary": workflow_instance.get('result_summary'),
                                    "output_data": workflow_instance.get('output_data')
                                }
                            })
                            subdivisions_with_instances.append(enhanced_subdivision)
                    except Exception as e:
                        logger.warning(f"获取细分 {subdivision.subdivision_id} 的工作流实例失败: {e}")
                        continue
            
            return BaseResponse(
                success=True,
                message=f"获取任务细分列表成功（仅包含有实例的细分）",
                data={
                    "subdivisions": subdivisions_with_instances,
                    "count": len(subdivisions_with_instances),
                    "total_subdivisions": len(subdivisions),
                    "with_instances_only": True
                }
            )
        else:
            return BaseResponse(
                success=True,
                message="获取任务细分列表成功",
                data={
                    "subdivisions": [s.model_dump() for s in subdivisions],
                    "count": len(subdivisions)
                }
            )
        
    except Exception as e:
        logger.error(f"获取任务细分列表异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取任务细分列表失败"
        )


@router.get("/workflows/{workflow_base_id}/subdivisions", response_model=BaseResponse)
async def get_workflow_subdivisions(
    workflow_base_id: uuid.UUID = Path(..., description="工作流基础ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取工作流相关的所有细分（用于预览）
    
    Args:
        workflow_base_id: 工作流基础ID
        current_user: 当前用户
        
    Returns:
        工作流的细分预览信息
    """
    try:
        logger.info(f"📊 用户 {current_user.username} 请求查看工作流细分: {workflow_base_id}")
        
        subdivisions_overview = await subdivision_service.get_workflow_subdivisions(workflow_base_id)
        
        logger.info(f"✅ 找到 {subdivisions_overview.total_count} 个相关细分")
        
        return BaseResponse(
            success=True,
            message="获取工作流细分预览成功",
            data=subdivisions_overview.model_dump()
        )
        
    except ValidationError as e:
        logger.warning(f"获取工作流细分预览验证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"获取工作流细分预览异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取工作流细分预览失败"
        )


@router.post("/workflows/{workflow_base_id}/adopt", response_model=BaseResponse)
async def adopt_subdivision(
    workflow_base_id: uuid.UUID = Path(..., description="工作流基础ID"),
    request: AdoptSubdivisionRequest = None,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    采纳子工作流到原始工作流
    
    Args:
        workflow_base_id: 工作流基础ID
        request: 采纳请求数据
        current_user: 当前用户
        
    Returns:
        采纳结果
    """
    try:
        logger.info(f"🔄 用户 {current_user.username} 请求采纳子工作流")
        logger.info(f"   工作流ID: {workflow_base_id}")
        logger.info(f"   细分ID: {request.subdivision_id}")
        logger.info(f"   目标节点ID: {request.target_node_id}")
        logger.info(f"   采纳名称: {request.adoption_name}")
        
        # 构造采纳数据
        from ..models.task_subdivision import WorkflowAdoptionCreate
        adoption_data = WorkflowAdoptionCreate(
            subdivision_id=request.subdivision_id,
            original_workflow_base_id=workflow_base_id,
            adopter_id=current_user.user_id,
            adoption_name=request.adoption_name,
            target_node_id=request.target_node_id
        )
        
        # 执行采纳
        adoption_result = await subdivision_service.adopt_subdivision(adoption_data)
        
        logger.info(f"✅ 子工作流采纳成功，新增 {adoption_result.new_nodes_count} 个节点")
        
        return BaseResponse(
            success=True,
            message="子工作流采纳成功",
            data={
                "adoption": adoption_result.model_dump(),
                "message": f"成功将子工作流采纳到原始工作流，新增 {adoption_result.new_nodes_count} 个节点"
            }
        )
        
    except ValidationError as e:
        logger.warning(f"采纳子工作流验证失败: {e}")
        raise handle_validation_error(e)
    except Exception as e:
        logger.error(f"采纳子工作流异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="采纳子工作流失败，请稍后再试"
        )


@router.get("/tasks/{task_id}/sub-workflow-info", response_model=BaseResponse)
async def get_task_sub_workflow_info(
    task_id: uuid.UUID = Path(..., description="任务ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取任务的子工作流信息
    
    Args:
        task_id: 任务ID
        current_user: 当前用户
        
    Returns:
        任务的子工作流实例信息
    """
    try:
        logger.info(f"📊 用户 {current_user.username} 请求任务子工作流信息: {task_id}")
        
        # 查找该任务相关的细分
        subdivisions = await subdivision_service.get_task_subdivisions(task_id)
        
        if not subdivisions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="该任务没有相关的子工作流"
            )
        
        # 获取最新的细分（如果有多个）
        latest_subdivision = subdivisions[0]  # 假设按创建时间倒序排列
        
        # 获取子工作流实例信息
        sub_workflow_info = await subdivision_service.get_subdivision_workflow_instance(
            latest_subdivision.subdivision_id
        )
        
        if not sub_workflow_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="找不到子工作流实例信息"
            )
        
        logger.info(f"✅ 找到子工作流实例: {sub_workflow_info.get('workflow_instance_id')}")
        
        return BaseResponse(
            success=True,
            message="获取任务子工作流信息成功",
            data={
                "sub_workflow_instance_id": sub_workflow_info.get('workflow_instance_id'),
                "workflow_instance_id": sub_workflow_info.get('workflow_instance_id'),
                "sub_workflow_name": sub_workflow_info.get('workflow_instance_name'),
                "sub_workflow_status": sub_workflow_info.get('status'),
                "subdivision_id": latest_subdivision.subdivision_id,
                "subdivision_name": latest_subdivision.subdivision_name,
                "created_at": sub_workflow_info.get('created_at'),
                "started_at": sub_workflow_info.get('started_at'),
                "completed_at": sub_workflow_info.get('completed_at')
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务子工作流信息异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取任务子工作流信息失败"
        )


@router.get("/subdivisions/{subdivision_id}", response_model=BaseResponse)
async def get_subdivision_details(
    subdivision_id: uuid.UUID = Path(..., description="细分ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取细分详情
    
    Args:
        subdivision_id: 细分ID
        current_user: 当前用户
        
    Returns:
        细分详细信息
    """
    try:
        # 这里可以添加具体的细分详情获取逻辑
        # 包括子工作流的执行状态、节点信息等
        
        subdivision = await subdivision_service.subdivision_repo.get_subdivision_by_id(subdivision_id)
        if not subdivision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="细分不存在"
            )
        
        # 格式化响应
        subdivision_response = await subdivision_service._format_subdivision_response(subdivision)
        
        return BaseResponse(
            success=True,
            message="获取细分详情成功",
            data={"subdivision": subdivision_response.model_dump()}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取细分详情异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取细分详情失败"
        )


@router.get("/subdivisions/{subdivision_id}/workflow-results", response_model=BaseResponse)
async def get_subdivision_workflow_results(
    subdivision_id: uuid.UUID = Path(..., description="细分ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取子工作流的完整执行结果
    
    Args:
        subdivision_id: 细分ID
        current_user: 当前用户
        
    Returns:
        子工作流的完整执行结果
    """
    try:
        logger.info(f"🔍 获取细分工作流结果: {subdivision_id}")
        
        # 获取细分信息
        subdivision = await subdivision_service.subdivision_repo.get_subdivision_by_id(subdivision_id)
        if not subdivision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="细分不存在"
            )
        
        # 获取子工作流实例ID
        sub_workflow_instance_id = subdivision.get('sub_workflow_instance_id')
        if not sub_workflow_instance_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="子工作流实例不存在"
            )
        
        # 使用 monitoring_service 获取完整的工作流执行结果
        from ..services.monitoring_service import MonitoringService
        monitoring_service = MonitoringService()
        
        workflow_results = await monitoring_service._collect_workflow_results(sub_workflow_instance_id)
        
        # 格式化结果为可读文本
        formatted_result = subdivision_service._format_subdivision_output(workflow_results)
        
        response_data = {
            "subdivision_id": str(subdivision_id),
            "sub_workflow_instance_id": str(sub_workflow_instance_id),
            "subdivision_name": subdivision.get('subdivision_name'),
            "workflow_status": workflow_results.get('status'),
            "execution_results": workflow_results,
            "formatted_result": formatted_result,
            "has_end_node_output": workflow_results.get('has_end_node_output', False),
            "final_output": workflow_results.get('final_output', ''),
            "total_tasks": workflow_results.get('total_tasks', 0),
            "completed_tasks": workflow_results.get('completed_tasks', 0),
            "failed_tasks": workflow_results.get('failed_tasks', 0)
        }
        
        return BaseResponse(
            success=True,
            message="获取子工作流执行结果成功",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取子工作流执行结果异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取子工作流执行结果失败"
        )


@router.delete("/subdivisions/{subdivision_id}", response_model=BaseResponse)
async def delete_subdivision(
    subdivision_id: uuid.UUID = Path(..., description="细分ID"),
    soft_delete: bool = Query(True, description="是否软删除"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    删除任务细分
    
    Args:
        subdivision_id: 细分ID
        soft_delete: 是否软删除
        current_user: 当前用户
        
    Returns:
        删除结果
    """
    try:
        logger.info(f"🗑️ 用户 {current_user.username} 请求删除细分: {subdivision_id}")
        
        # 验证细分存在且属于当前用户
        subdivision = await subdivision_service.subdivision_repo.get_subdivision_by_id(subdivision_id)
        if not subdivision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="细分不存在"
            )
        
        if subdivision['subdivider_id'] != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只能删除自己创建的细分"
            )
        
        # 执行删除
        success = await subdivision_service.subdivision_repo.delete_subdivision(
            subdivision_id, soft_delete
        )
        
        if success:
            logger.info(f"✅ 细分删除成功: {subdivision_id}")
            return BaseResponse(
                success=True,
                message="细分删除成功",
                data={"subdivision_id": str(subdivision_id)}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除细分失败"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除细分异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除细分失败，请稍后再试"
        )


@router.get("/my-subdivisions", response_model=BaseResponse)
async def get_my_subdivisions(
    limit: int = Query(50, ge=1, le=100, description="结果数量限制"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取当前用户创建的所有细分
    
    Args:
        limit: 结果数量限制
        current_user: 当前用户
        
    Returns:
        用户的细分列表
    """
    try:
        subdivisions = await subdivision_service.subdivision_repo.get_subdivisions_by_subdivider(
            current_user.user_id
        )
        
        # 限制返回数量
        subdivisions = subdivisions[:limit]
        
        # 格式化响应
        subdivision_responses = []
        for subdivision in subdivisions:
            response = await subdivision_service._format_subdivision_response(subdivision)
            subdivision_responses.append(response.model_dump())
        
        return BaseResponse(
            success=True,
            message="获取我的细分列表成功",
            data={
                "subdivisions": subdivision_responses,
                "count": len(subdivision_responses)
            }
        )
        
    except Exception as e:
        logger.error(f"获取用户细分列表异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取细分列表失败"
        )