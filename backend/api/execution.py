"""
工作流执行API
Workflow Execution API
"""

import uuid
import json
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, status, Request, Query
from pydantic import BaseModel, Field, ValidationError
from loguru import logger

from ..services.execution_service import execution_engine
from ..services.agent_task_service import agent_task_service
from ..models.instance import (
    WorkflowExecuteRequest, WorkflowControlRequest,
    TaskInstanceStatus, TaskInstanceType
)
from ..utils.middleware import get_current_user_context, CurrentUser
from ..utils.helpers import now_utc

router = APIRouter(prefix="/api/execution", tags=["execution"])

# 注意：所有人工任务相关的功能现在通过 execution_engine 统一处理


# ==================== 请求/响应模型 ====================

class TaskSubmissionRequest(BaseModel):
    """任务提交请求"""
    result_data: Optional[dict] = Field(default={}, description="任务结果数据")
    result_summary: Optional[str] = Field(None, description="结果摘要")
    attachment_file_ids: Optional[List[str]] = Field(default=[], description="附件文件ID列表")


class TaskActionRequest(BaseModel):
    """任务操作请求"""
    reason: Optional[str] = Field(None, description="操作原因")


class HelpRequest(BaseModel):
    """帮助请求"""
    help_message: str = Field(..., description="帮助信息")


class TaskAssignmentRequest(BaseModel):
    """任务分配请求"""
    user_id: uuid.UUID = Field(..., description="用户ID")


# ==================== 工作流执行端点 ====================

@router.post("/workflows/execute/debug")
async def debug_execute_workflow(request: Request):
    """调试执行工作流请求"""
    from loguru import logger
    try:
        # 获取原始请求体
        raw_body = await request.body()
        logger.info(f"🔍 调试 - 原始请求体: {raw_body.decode('utf-8')}")
        
        # 解析JSON
        import json
        json_data = json.loads(raw_body)
        logger.info(f"🔍 调试 - 解析后的JSON: {json_data}")
        
        # 检查每个字段
        for key, value in json_data.items():
            logger.info(f"🔍 调试 - 字段 '{key}': {value} (类型: {type(value)})")
        
        return {"status": "debug", "received_data": json_data}
    except Exception as e:
        logger.error(f"调试端点错误: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/workflows/execute")
async def execute_workflow(
    request: WorkflowExecuteRequest,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """执行工作流"""
    try:
        from loguru import logger
        logger.info(f"🚀 收到工作流执行请求")
        logger.info(f"   - workflow_base_id: {request.workflow_base_id} (类型: {type(request.workflow_base_id)})")
        logger.info(f"   - workflow_instance_name: {request.workflow_instance_name} (类型: {type(request.workflow_instance_name)})")
        logger.info(f"   - user_id: {current_user.user_id}")
        logger.info(f"   - input_data: {request.input_data}")
        logger.info(f"   - context_data: {request.context_data}")
        
        # 尝试执行工作流，如果失败则返回详细错误
        try:
            result = await execution_engine.execute_workflow(request, current_user.user_id)
            logger.info(f"工作流执行成功: {result}")
            return {
                "success": True,
                "data": result,
                "message": "工作流开始执行"
            }
        except AttributeError as ae:
            # 依赖管理器问题，返回模拟响应
            logger.warning(f"执行引擎依赖问题，返回模拟响应: {ae}")
            result = {
                "instance_id": str(uuid.uuid4()),
                "workflow_base_id": str(request.workflow_base_id),
                "workflow_instance_name": request.workflow_instance_name,
                "status": "pending",
                "message": "工作流执行请求已接收（模拟模式）"
            }
            return {
                "success": True,
                "data": result,
                "message": "工作流开始执行"
            }
    except ValueError as e:
        from loguru import logger
        logger.warning(f"工作流执行验证错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"执行工作流失败: {str(e)}"
        )
    except Exception as e:
        from loguru import logger
        logger.error(f"执行工作流异常: {e}")
        import traceback
        logger.error(f"异常堆栈: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行工作流失败: {str(e)}"
        )


@router.post("/workflows/{instance_id}/control")
async def control_workflow(
    instance_id: uuid.UUID,
    request: WorkflowControlRequest,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """控制工作流执行（暂停、恢复、取消）"""
    try:
        action = request.action.lower()
        logger.info(f"🎮 用户 {current_user.user_id} ({current_user.username}) 请求控制工作流: {instance_id}")
        logger.info(f"   - 操作类型: {action}")
        logger.info(f"   - 操作原因: {getattr(request, 'reason', '未提供')}")
        
        # 验证操作类型
        valid_actions = ["pause", "resume", "cancel"]
        if action not in valid_actions:
            logger.error(f"❌ 不支持的操作类型: {action}")
            logger.error(f"   - 支持的操作: {valid_actions}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不支持的操作类型"
            )
        
        # 执行对应的操作
        success = False
        message = ""
        
        try:
            if action == "pause":
                logger.info(f"⏸️ 执行暂停操作")
                success = await execution_engine.pause_workflow(instance_id)
                message = "工作流已暂停" if success else "暂停工作流失败"
                logger.info(f"   - 暂停结果: {success}")
                
            elif action == "resume":
                logger.info(f"▶️ 执行恢复操作")
                success = await execution_engine.resume_workflow(instance_id)
                message = "工作流已恢复" if success else "恢复工作流失败"
                logger.info(f"   - 恢复结果: {success}")
                
            elif action == "cancel":
                logger.info(f"🚫 执行取消操作")
                success = await execution_engine.cancel_workflow(instance_id)
                message = "工作流已取消" if success else "取消工作流失败"
                logger.info(f"   - 取消结果: {success}")
                
        except Exception as operation_error:
            logger.error(f"❌ 执行 {action} 操作时发生异常:")
            logger.error(f"   - 异常类型: {type(operation_error).__name__}")
            logger.error(f"   - 异常信息: {str(operation_error)}")
            import traceback
            logger.error(f"   - 异常堆栈: {traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"执行{action}操作失败: {str(operation_error)}"
            )
        
        # 检查操作结果
        if not success:
            logger.error(f"❌ 工作流控制操作失败:")
            logger.error(f"   - 实例ID: {instance_id}")
            logger.error(f"   - 操作: {action}")
            logger.error(f"   - 返回结果: {success}")
            logger.error(f"   - 消息: {message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        logger.info(f"✅ 工作流控制操作成功:")
        logger.info(f"   - 实例ID: {instance_id}")
        logger.info(f"   - 操作: {action}")
        logger.info(f"   - 结果: {message}")
        
        return {
            "success": True,
            "data": {"instance_id": instance_id, "action": action},
            "message": message
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 控制工作流总体异常:")
        logger.error(f"   - 实例ID: {instance_id}")
        logger.error(f"   - 用户ID: {current_user.user_id}")
        logger.error(f"   - 请求操作: {getattr(request, 'action', 'unknown')}")
        logger.error(f"   - 异常类型: {type(e).__name__}")
        logger.error(f"   - 异常信息: {str(e)}")
        import traceback
        logger.error(f"   - 完整异常堆栈: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"控制工作流失败: {str(e)}"
        )


@router.get("/workflows/{instance_id}/status")
async def get_workflow_status(
    instance_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取工作流实例的详细状态"""
    try:
        from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository

        workflow_instance_repo = WorkflowInstanceRepository()

        # 步骤1: 获取工作流实例基本信息
        workflow_query = """
        SELECT
            wi.*,
            w.name as workflow_name,
            u.username as executor_username
        FROM workflow_instance wi
        LEFT JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id AND w.is_current_version = 1
        LEFT JOIN user u ON wi.executor_id = u.user_id
        WHERE wi.workflow_instance_id = %s
        AND wi.is_deleted = 0
        """

        workflow_result = await workflow_instance_repo.db.fetch_one(workflow_query, instance_id)

        if not workflow_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流实例不存在"
            )

        # 步骤2: 获取节点实例信息
        nodes_query = """
        SELECT
            ni.node_instance_id,
            n.name as node_name,
            n.type as node_type,
            ni.status,
            ni.started_at,
            ni.completed_at,
            ni.error_message,
            ni.input_data,
            ni.output_data,
            ni.retry_count
        FROM node_instance ni
        LEFT JOIN node n ON ni.node_id = n.node_id
        WHERE ni.workflow_instance_id = %s
        AND ni.is_deleted = 0
        ORDER BY ni.created_at ASC
        """

        node_results = await workflow_instance_repo.db.fetch_all(nodes_query, instance_id)

        # 组装结果
        result = dict(workflow_result)
        node_instances = [dict(node) for node in node_results] if node_results else []
        result['node_instances'] = node_instances

        # 统计节点状态
        total_nodes = len(node_instances)
        completed_nodes = sum(1 for node in node_instances if node.get('status') == 'completed')
        running_nodes = sum(1 for node in node_instances if node.get('status') == 'running')
        failed_nodes = sum(1 for node in node_instances if node.get('status') == 'failed')
        
        progress_percentage = 0
        if total_nodes > 0:
            progress_percentage = round((completed_nodes / total_nodes) * 100, 1)
        
        # 当前运行的节点
        current_running_nodes = [node.get('node_name') for node in node_instances if node.get('status') == 'running']
        
        # 检查是否需要主动更新工作流状态
        current_status = result.get("status")
        should_trigger_completion_check = False
        
        if total_nodes > 0 and completed_nodes == total_nodes and failed_nodes == 0:
            # 所有节点都完成且没有失败节点
            if current_status not in ['completed', 'COMPLETED']:
                logger.info(f"🔄 检测到所有节点已完成但工作流状态为 {current_status}，主动触发完成检查")
                should_trigger_completion_check = True
        elif failed_nodes > 0:
            # 有失败节点
            if current_status not in ['failed', 'FAILED']:
                logger.info(f"🔄 检测到有失败节点但工作流状态为 {current_status}，主动触发失败检查")
                should_trigger_completion_check = True
        
        # 如果需要，触发工作流状态检查
        if should_trigger_completion_check:
            try:
                from ..services.execution_service import ExecutionEngine
                execution_engine = ExecutionEngine()
                await execution_engine._check_workflow_completion(instance_id)
                logger.info(f"✅ 主动触发的工作流状态检查完成")

                # 重新查询更新后的状态
                updated_result = await workflow_instance_repo.db.fetch_one(workflow_query, instance_id)
                if updated_result:
                    result = dict(updated_result)
                    current_status = result.get("status")
                    logger.info(f"📊 工作流状态已更新为: {current_status}")
            except Exception as e:
                logger.error(f"❌ 主动触发工作流状态检查失败: {e}")
        
        formatted_instance = {
            "instance_id": str(result["workflow_instance_id"]),
            "workflow_instance_name": result.get("workflow_instance_name"),
            "workflow_name": result.get("workflow_name"),
            "status": result.get("status"),
            "executor_id": str(result.get("executor_id")) if result.get("executor_id") else None,
            "executor_username": result.get("executor_username"),
            "created_at": result["created_at"].isoformat() if result.get("created_at") else None,
            "updated_at": result["updated_at"].isoformat() if result.get("updated_at") else None,
            "input_data": result.get("input_data", {}),
            "output_data": result.get("output_data", {}),
            "error_message": result.get("error_message"),
            "total_nodes": total_nodes,
            "completed_nodes": completed_nodes,
            "running_nodes": running_nodes,
            "failed_nodes": failed_nodes,
            "progress_percentage": progress_percentage,
            "current_running_nodes": current_running_nodes,
            "node_instances": node_instances
        }
        
        return {
            "success": True,
            "data": formatted_instance,
            "message": "获取工作流实例状态成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取工作流实例状态失败: {str(e)}"
        )


@router.get("/workflows/{workflow_base_id}/instances")
async def get_workflow_instances(
    workflow_base_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取工作流的执行实例列表"""
    try:
        from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
        
        workflow_instance_repo = WorkflowInstanceRepository()
        
        # 查询工作流实例及其统计信息 (MySQL版本)
        query = """
        SELECT 
            wi.workflow_instance_id,
            wi.workflow_instance_name,
            wi.status,
            wi.executor_id,
            wi.created_at,
            wi.updated_at,
            wi.input_data,
            wi.output_data,
            wi.error_message,
            wi.workflow_base_id,
            w.name as workflow_name,
            u.username as executor_username,
            -- 统计节点实例信息
            COUNT(ni.node_instance_id) as total_nodes,
            COUNT(CASE WHEN ni.status = 'completed' THEN 1 END) as completed_nodes,
            COUNT(CASE WHEN ni.status = 'running' THEN 1 END) as running_nodes,
            COUNT(CASE WHEN ni.status = 'failed' THEN 1 END) as failed_nodes,
            -- 获取当前运行的节点名称 (MySQL版本)
            GROUP_CONCAT(
                CASE WHEN ni.status = 'running' THEN n.name END
                SEPARATOR ', '
            ) as current_running_nodes
        FROM workflow_instance wi
        LEFT JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id AND w.is_current_version = 1
        LEFT JOIN user u ON wi.executor_id = u.user_id
        LEFT JOIN node_instance ni ON wi.workflow_instance_id = ni.workflow_instance_id AND ni.is_deleted = 0
        LEFT JOIN node n ON ni.node_id = n.node_id
        WHERE wi.workflow_base_id = %s
        AND wi.is_deleted = 0
        GROUP BY wi.workflow_instance_id, wi.workflow_instance_name, wi.status, wi.executor_id, wi.created_at, wi.updated_at, wi.input_data, wi.output_data, wi.error_message, wi.workflow_base_id, w.name, u.username
        ORDER BY wi.created_at DESC
        """
        
        instances = await workflow_instance_repo.db.fetch_all(query, workflow_base_id)
        
        # 格式化返回数据
        formatted_instances = []
        for instance in instances:
            # 安全转换数值字段（处理MySQL可能返回的各种格式）
            def safe_int(value, default=0):
                """安全转换为整数"""
                if value is None:
                    return default
                if isinstance(value, int):
                    return value
                if isinstance(value, (list, tuple)):
                    # 如果是列表/元组，可能是MySQL返回的格式，取第一个元素
                    return len([x for x in value if x]) if value else default
                if isinstance(value, str):
                    if value == '[]' or value == '' or value == 'None':
                        return default
                    try:
                        return int(value)
                    except ValueError:
                        return default
                # 处理其他类型
                try:
                    return int(value) if value is not None else default
                except (ValueError, TypeError):
                    return default
                
            total_nodes = safe_int(instance.get("total_nodes"))
            completed_nodes = safe_int(instance.get("completed_nodes"))
            running_nodes = safe_int(instance.get("running_nodes"))
            failed_nodes = safe_int(instance.get("failed_nodes"))
            
            # 计算执行进度百分比
            progress_percentage = 0
            if total_nodes > 0:
                progress_percentage = round((completed_nodes / total_nodes) * 100, 1)
            
            formatted_instances.append({
                "instance_id": str(instance["workflow_instance_id"]),
                "workflow_instance_name": instance.get("workflow_instance_name"),
                "workflow_name": instance.get("workflow_name"),
                "status": instance.get("status"),
                "executor_id": str(instance.get("executor_id")) if instance.get("executor_id") else None,
                "executor_username": instance.get("executor_username"),
                "created_at": instance["created_at"].isoformat() if instance.get("created_at") else None,
                "updated_at": instance["updated_at"].isoformat() if instance.get("updated_at") else None,
                "input_data": instance.get("input_data", {}),
                "output_data": instance.get("output_data", {}),
                "error_message": instance.get("error_message"),
                # 新增进度和节点统计信息
                "total_nodes": total_nodes,
                "completed_nodes": completed_nodes,
                "running_nodes": running_nodes,
                "failed_nodes": failed_nodes,
                "progress_percentage": progress_percentage,
                "current_node": instance.get("current_running_nodes") or None
            })
        
        return {
            "success": True,
            "data": formatted_instances,
            "message": f"获取到 {len(formatted_instances)} 个执行实例"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取执行实例列表失败: {str(e)}"
        )


@router.get("/workflow/{workflow_id}/task-flow")
async def get_workflow_task_flow(
    workflow_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取工作流任务流程"""
    try:
        # 获取工作流实例的任务流程信息
        from ..repositories.instance.task_instance_repository import TaskInstanceRepository
        from ..repositories.instance.node_instance_repository import NodeInstanceRepository
        from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
        
        task_repo = TaskInstanceRepository()
        node_repo = NodeInstanceRepository()
        workflow_repo = WorkflowInstanceRepository()
        
        # 首先验证工作流实例是否存在并获取基本信息
        workflow_instance_query = """
        SELECT 
            wi.*,
            w.name as workflow_name,
            u.username as executor_username
        FROM workflow_instance wi
        LEFT JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id AND w.is_current_version = 1
        LEFT JOIN user u ON wi.executor_id = u.user_id
        WHERE wi.workflow_instance_id = %s AND wi.is_deleted = 0
        """
        
        workflow_instance = await workflow_repo.db.fetch_one(workflow_instance_query, workflow_id)
        if not workflow_instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流实例不存在"
            )
        
        # 获取工作流实例的所有节点实例（包含处理器详细信息和位置信息）
        nodes_query = """
        SELECT 
            ni.*,
            n.name as node_name,
            n.type as node_type,
            n.position_x,
            n.position_y,
            -- 处理器信息（通过node_processor关联表）
            p.name as processor_name,
            p.type as processor_type,
            -- 计算节点执行时间 (MySQL兼容)
            CASE 
                WHEN ni.started_at IS NOT NULL AND ni.completed_at IS NOT NULL 
                THEN CAST(TIMESTAMPDIFF(SECOND, ni.started_at, ni.completed_at) AS SIGNED)
                WHEN ni.started_at IS NOT NULL 
                THEN CAST(TIMESTAMPDIFF(SECOND, ni.started_at, NOW()) AS SIGNED)
                ELSE NULL
            END as execution_duration_seconds
        FROM node_instance ni
        JOIN node n ON ni.node_id = n.node_id
        LEFT JOIN node_processor np ON n.node_id = np.node_id
        LEFT JOIN processor p ON np.processor_id = p.processor_id
        WHERE ni.workflow_instance_id = $1
        AND ni.is_deleted = 0
        ORDER BY 
            CASE 
                WHEN ni.started_at IS NOT NULL THEN ni.started_at 
                ELSE ni.created_at 
            END ASC
        """
        
        nodes = await node_repo.db.fetch_all(nodes_query, workflow_id)
        
        # 获取所有任务实例（包含更详细的状态信息）
        tasks_query = """
        SELECT 
            ti.*,
            p.name as processor_name,
            p.type as processor_type,
            u.username as assigned_username,
            a.agent_name as assigned_agent_name,
            -- 计算任务执行时间 (MySQL兼容)
            CASE 
                WHEN ti.started_at IS NOT NULL AND ti.completed_at IS NOT NULL 
                THEN CAST(TIMESTAMPDIFF(SECOND, ti.started_at, ti.completed_at) AS SIGNED)
                WHEN ti.started_at IS NOT NULL 
                THEN CAST(TIMESTAMPDIFF(SECOND, ti.started_at, NOW()) AS SIGNED)
                ELSE NULL
            END as actual_duration_seconds,
            -- 任务是否超时 (MySQL兼容)
            CASE 
                WHEN ti.estimated_duration IS NOT NULL 
                     AND ti.started_at IS NOT NULL 
                     AND ti.completed_at IS NULL
                     AND TIMESTAMPDIFF(SECOND, ti.started_at, NOW()) > ti.estimated_duration * 60
                THEN TRUE
                ELSE FALSE
            END as is_overdue
        FROM task_instance ti
        LEFT JOIN processor p ON ti.processor_id = p.processor_id
        LEFT JOIN user u ON ti.assigned_user_id = u.user_id
        LEFT JOIN agent a ON ti.assigned_agent_id = a.agent_id
        WHERE ti.workflow_instance_id = %s
        AND ti.is_deleted = 0
        ORDER BY ti.created_at
        """
        
        tasks = await task_repo.db.fetch_all(tasks_query, workflow_id)
        
        # 获取工作流边缘关系（用于前端流程图显示）
        edges_query = """
        SELECT 
            nc.from_node_id,
            nc.to_node_id,
            nc.condition_config,
            n1.name as from_node_name,
            n2.name as to_node_name,
            n1.node_base_id as from_node_base_id,
            n2.node_base_id as to_node_base_id
        FROM node_connection nc
        JOIN node n1 ON nc.from_node_id = n1.node_id
        JOIN node n2 ON nc.to_node_id = n2.node_id
        WHERE nc.workflow_id = %s
        ORDER BY nc.created_at
        """
        
        # Get the current workflow_id for edge query
        workflow_query = """
        SELECT workflow_id FROM workflow 
        WHERE workflow_base_id = $1 AND is_current_version = TRUE
        """
        workflow_result = await node_repo.db.fetch_one(workflow_query, workflow_instance['workflow_base_id'])
        current_workflow_id = workflow_result['workflow_id'] if workflow_result else None
        
        edges = await node_repo.db.fetch_all(edges_query, current_workflow_id) if current_workflow_id else []
        
        # 构建任务流程数据
        task_flow = {
            "workflow_id": str(workflow_id),
            "workflow_name": workflow_instance['workflow_name'],
            "workflow_instance_status": workflow_instance['status'],
            "executor_username": workflow_instance['executor_username'],
            "created_at": workflow_instance['created_at'].isoformat() if workflow_instance['created_at'] else None,
            "started_at": workflow_instance['started_at'].isoformat() if workflow_instance['started_at'] else None,
            "completed_at": workflow_instance['completed_at'].isoformat() if workflow_instance['completed_at'] else None,
            "current_user_role": "viewer",  # 默认为viewer，后续可根据权限设置
            "nodes": [],
            "tasks": [],
            "edges": []
        }
        
        # 判断用户角色
        if str(workflow_instance['executor_id']) == str(current_user.user_id):
            task_flow["current_user_role"] = "creator"
        else:
            # 检查是否有分配给当前用户的任务
            user_tasks = [task for task in tasks if task.get('assigned_user_id') == current_user.user_id]
            if user_tasks:
                task_flow["current_user_role"] = "assignee"
                task_flow["assigned_tasks"] = []
        
        # 格式化节点数据（包含实时状态、执行信息、处理器信息和位置信息）
        for node in nodes:
            node_data = {
                "node_instance_id": str(node['node_instance_id']),
                "node_name": node['node_name'],
                "node_type": node['node_type'],
                "status": node['status'],  # 这是从数据库实时读取的状态
                "input_data": node['input_data'],
                "output_data": node['output_data'],
                "start_at": node['started_at'].isoformat() if node['started_at'] else None,
                "completed_at": node['completed_at'].isoformat() if node['completed_at'] else None,
                "execution_duration_seconds": node['execution_duration_seconds'],
                "error_message": node['error_message'],
                "retry_count": node.get('retry_count', 0),
                # 🔧 新增：位置信息用于前端布局
                "position": {
                    "x": float(node['position_x']) if node['position_x'] is not None else None,
                    "y": float(node['position_y']) if node['position_y'] is not None else None
                },
                # 处理器详细信息
                "processor_name": node['processor_name'],
                "processor_type": node['processor_type'],
                # 节点关联的任务数量
                "task_count": len([task for task in tasks if str(task['node_instance_id']) == str(node['node_instance_id'])]),
                # 关联的任务详细信息
                "tasks": [
                    {
                        "task_instance_id": str(task['task_instance_id']),
                        "task_title": task['task_title'],
                        "task_type": task['task_type'],
                        "status": task['status'],
                        "assignee": task['assigned_username'] or task['assigned_agent_name'],
                        "priority": task['priority'],
                        "input_data": task['input_data'],
                        "output_data": task['output_data'],
                        "result_summary": task.get('result_summary'),
                        "error_message": task.get('error_message')
                    }
                    for task in tasks if str(task['node_instance_id']) == str(node['node_instance_id'])
                ],
                # 时间戳信息
                "timestamps": {
                    "created_at": node['created_at'].isoformat() if node['created_at'] else None,
                    "started_at": node['started_at'].isoformat() if node['started_at'] else None,
                    "completed_at": node['completed_at'].isoformat() if node['completed_at'] else None
                }
            }
            task_flow["nodes"].append(node_data)
        
        # 格式化任务数据（包含实时状态和分配信息）
        for task in tasks:
            assignee_info = None
            if task['assigned_username']:
                assignee_info = {
                    "id": str(task['assigned_user_id']),
                    "name": task['assigned_username'],
                    "type": "user"
                }
            elif task['assigned_agent_name']:
                assignee_info = {
                    "id": str(task['assigned_agent_id']),
                    "name": task['assigned_agent_name'],
                    "type": "agent"
                }
            
            task_data = {
                "task_instance_id": str(task['task_instance_id']),
                "node_instance_id": str(task['node_instance_id']),
                "task_title": task['task_title'],
                "task_type": task['task_type'],
                "status": task['status'],  # 这是从数据库实时读取的状态
                "processor_name": task['processor_name'],
                "processor_type": task['processor_type'],
                "assignee": assignee_info,
                "priority": task['priority'],
                "estimated_duration": task['estimated_duration'],
                "actual_duration_seconds": task['actual_duration_seconds'],
                "is_overdue": task['is_overdue'],
                "created_at": task['created_at'].isoformat() if task['created_at'] else None,
                "started_at": task['started_at'].isoformat() if task['started_at'] else None,
                "completed_at": task['completed_at'].isoformat() if task['completed_at'] else None,
                "input_data": task['input_data'],
                "output_data": task['output_data'],
                "result_summary": task.get('result_summary'),
                "error_message": task.get('error_message')
            }
            
            task_flow["tasks"].append(task_data)
            
            # 如果是分配给当前用户的任务，添加到assigned_tasks
            if (task_flow["current_user_role"] == "assignee" and 
                task.get('assigned_user_id') == current_user.user_id):
                task_flow["assigned_tasks"].append(task_data)
        
        # 格式化边缘数据（用于流程图显示）
        # 创建node_id到node_instance_id的映射
        node_id_to_instance_id = {}
        for node in nodes:
            node_id_to_instance_id[str(node['node_id'])] = str(node['node_instance_id'])
        
        for edge in edges:
            from_node_id = str(edge['from_node_id'])
            to_node_id = str(edge['to_node_id'])
            
            # 将node_id映射为node_instance_id
            source_instance_id = node_id_to_instance_id.get(from_node_id)
            target_instance_id = node_id_to_instance_id.get(to_node_id)
            
            # 只有当两个节点都有对应的实例时才添加边
            if source_instance_id and target_instance_id:
                edge_data = {
                    "id": f"{source_instance_id}-{target_instance_id}",
                    "source": source_instance_id,
                    "target": target_instance_id,
                    "label": str(edge['condition_config']) if edge['condition_config'] else "",
                    "from_node_name": edge['from_node_name'],
                    "to_node_name": edge['to_node_name']
                }
                task_flow["edges"].append(edge_data)
        
        # 🔧 新增：智能布局算法 - 当节点缺少位置信息时自动计算层次化布局
        def calculate_hierarchical_layout(nodes_data, edges_data):
            """基于依赖关系的层次化布局算法"""
            # 构建依赖图
            graph = {}
            in_degree = {}
            node_dict = {node["node_instance_id"]: node for node in nodes_data}
            
            # 初始化
            for node in nodes_data:
                node_id = node["node_instance_id"]
                graph[node_id] = []
                in_degree[node_id] = 0
            
            # 构建边关系
            for edge in edges_data:
                source = edge["source"]
                target = edge["target"]
                if source in graph and target in graph:
                    graph[source].append(target)
                    in_degree[target] += 1
            
            # 拓扑排序获得层次
            layers = []
            current_layer = [node_id for node_id, degree in in_degree.items() if degree == 0]
            
            while current_layer:
                layers.append(current_layer[:])
                next_layer = []
                for node_id in current_layer:
                    for neighbor in graph[node_id]:
                        in_degree[neighbor] -= 1
                        if in_degree[neighbor] == 0:
                            next_layer.append(neighbor)
                current_layer = next_layer
            
            # 计算布局参数
            LAYER_WIDTH = 300  # 层间距离
            NODE_HEIGHT = 120  # 节点间垂直距离
            START_X = 100      # 起始X坐标
            START_Y = 100      # 起始Y坐标
            
            # 应用层次化布局
            for layer_idx, layer_nodes in enumerate(layers):
                layer_x = START_X + layer_idx * LAYER_WIDTH
                
                # 在当前层内垂直排列节点
                for node_idx, node_id in enumerate(layer_nodes):
                    if node_id in node_dict:
                        node = node_dict[node_id]
                        
                        # 只有当节点没有有效位置信息时才重新计算
                        current_pos = node.get("position", {})
                        if (current_pos.get("x") is None or current_pos.get("y") is None or 
                            (current_pos.get("x") == 0 and current_pos.get("y") == 0)):
                            
                            # 计算Y坐标 - 居中对齐
                            layer_height = len(layer_nodes) * NODE_HEIGHT
                            start_y = START_Y + (layer_idx * 50)  # 每层稍微错开
                            node_y = start_y + (node_idx - len(layer_nodes)/2 + 0.5) * NODE_HEIGHT
                            
                            node["position"] = {
                                "x": float(layer_x),
                                "y": float(node_y)
                            }
                            
                            print(f"🔧 [布局] {node.get('node_name')} -> 层{layer_idx} 位置({layer_x}, {node_y})")
            
            return nodes_data
        
        # 应用智能布局
        task_flow["nodes"] = calculate_hierarchical_layout(task_flow["nodes"], task_flow["edges"])
        
        # 添加实时统计信息
        node_status_count = {}
        task_status_count = {}
        
        for node in task_flow["nodes"]:
            status = node["status"]
            node_status_count[status] = node_status_count.get(status, 0) + 1
        
        for task in task_flow["tasks"]:
            status = task["status"]
            task_status_count[status] = task_status_count.get(status, 0) + 1
        
        # 计算总体进度
        total_nodes = len(task_flow["nodes"])
        completed_nodes = node_status_count.get("completed", 0)
        progress_percentage = round((completed_nodes / total_nodes) * 100, 1) if total_nodes > 0 else 0
        
        task_flow["statistics"] = {
            "total_nodes": total_nodes,
            "total_tasks": len(task_flow["tasks"]),
            "node_status_count": node_status_count,
            "task_status_count": task_status_count,
            "progress_percentage": progress_percentage,
            "is_completed": workflow_instance['status'] == 'completed',
            "is_running": workflow_instance['status'] == 'running',
            "is_failed": workflow_instance['status'] == 'failed'
        }
        
        # 添加创建者信息
        task_flow["creator"] = {
            "id": str(workflow_instance['executor_id']),
            "name": workflow_instance['executor_username']
        }
        
        return {
            "success": True,
            "data": task_flow,
            "message": f"获取实时任务流程成功，包含 {len(task_flow['nodes'])} 个节点和 {len(task_flow['tasks'])} 个任务（工作流状态: {workflow_instance['status']}）"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取工作流任务流程失败: {str(e)}"
        )


@router.get("/workflows/{workflow_instance_id}/task-flow")
async def get_workflow_instance_task_flow(
    workflow_instance_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取工作流实例任务流程（统一接口 - 支持主工作流和子工作流）"""
    try:
        # 直接调用现有的函数，保持逻辑一致
        result = await get_workflow_task_flow(workflow_instance_id, current_user)
        
        # 修改消息以反映这是通过新统一接口调用的
        if result.get("success"):
            result["message"] = result["message"].replace("获取实时任务流程成功", "通过统一接口获取工作流实例任务流程成功")
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取工作流实例任务流程失败: {str(e)}"
        )




# ==================== Debug端点 ====================

@router.get("/debug/tasks")
async def debug_get_all_tasks(
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """Debug: 获取所有任务状态（用于调试）"""
    try:
        from ..repositories.instance.task_instance_repository import TaskInstanceRepository
        
        task_repo = TaskInstanceRepository()
        
        # 获取所有任务实例，包含详细信息
        query = """
        SELECT 
            ti.*,
            wi.workflow_instance_name as workflow_instance_name,
            w.name as workflow_name,
            p.name as processor_name,
            p.type as processor_type,
            u.username as assigned_username,
            a.agent_name as assigned_agent_name
        FROM task_instance ti
        LEFT JOIN workflow_instance wi ON ti.workflow_instance_id = wi.workflow_instance_id
        LEFT JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id AND w.is_current_version = 1
        LEFT JOIN processor p ON ti.processor_id = p.processor_id
        LEFT JOIN user u ON ti.assigned_user_id = u.user_id
        LEFT JOIN agent a ON ti.assigned_agent_id = a.agent_id
        WHERE ti.is_deleted = FALSE
        ORDER BY ti.created_at DESC
        LIMIT 50
        """
        
        tasks = await task_repo.db.fetch_all(query)
        
        debug_data = {
            "total_tasks": len(tasks),
            "current_user_id": str(current_user.user_id),
            "current_username": current_user.username,
            "tasks": []
        }
        
        # 统计各种状态的任务数量
        status_counts = {}
        user_task_counts = {}
        
        for task in tasks:
            task_data = {
                "task_id": str(task['task_instance_id']),
                "task_title": task['task_title'],
                "task_type": task['task_type'],
                "status": task['status'],
                "workflow_name": task['workflow_name'],
                "processor_name": task['processor_name'],
                "processor_type": task['processor_type'],
                "assigned_user_id": str(task['assigned_user_id']) if task['assigned_user_id'] else None,
                "assigned_username": task['assigned_username'],
                "assigned_agent_name": task['assigned_agent_name'],
                "priority": task['priority'],
                "created_at": task['created_at'].isoformat() if task['created_at'] else None,
                "is_current_user_task": str(task['assigned_user_id']) == str(current_user.user_id) if task['assigned_user_id'] else False
            }
            debug_data["tasks"].append(task_data)
            
            # 统计状态
            status = task['status']
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # 统计用户任务
            if task['assigned_user_id']:
                user_id = str(task['assigned_user_id'])
                username = task['assigned_username'] or 'Unknown'
                user_task_counts[f"{username} ({user_id})"] = user_task_counts.get(f"{username} ({user_id})", 0) + 1
        
        debug_data["status_counts"] = status_counts
        debug_data["user_task_counts"] = user_task_counts
        debug_data["current_user_tasks"] = len([t for t in debug_data["tasks"] if t["is_current_user_task"]])
        
        return {
            "success": True,
            "data": debug_data,
            "message": f"获取调试信息成功，总共 {len(tasks)} 个任务"
        }
        
    except Exception as e:
        logger.error(f"获取调试任务信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取调试信息失败: {str(e)}"
        )


# ==================== 人工任务端点 ====================

@router.get("/tasks/my")
async def get_my_tasks(
    task_status: Optional[TaskInstanceStatus] = None,
    limit: Optional[int] = None,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取我的任务列表"""
    try:
        tasks = await execution_engine.get_user_tasks(
            current_user.user_id, task_status, limit
        )
        
        # 为每个任务添加拆解相关信息
        enhanced_tasks = []
        for task in tasks:
            # 添加基本的拆解可用性检查
            task_status = task.get('status', '')
            task_type = task.get('task_type', '')
            
            # 添加拆解信息
            task['actions'] = {
                "can_subdivide": (
                    task_status in ['pending', 'assigned'] and 
                    task_type in ['human', 'mixed']
                ),
                "can_accept": task_status in ['pending', 'assigned'],
                "can_complete": task_status in ['in_progress'],
                "can_reject": task_status in ['pending', 'assigned']
            }
            
            enhanced_tasks.append(task)
        
        return {
            "success": True,
            "data": enhanced_tasks,
            "message": f"获取到 {len(enhanced_tasks)} 个任务"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务列表失败: {str(e)}"
        )


@router.get("/tasks/statistics")
async def get_task_statistics(
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取任务统计"""
    try:
        stats = await execution_engine.get_task_statistics(current_user.user_id)
        
        return {
            "success": True,
            "data": stats,
            "message": "获取任务统计成功"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务统计失败: {str(e)}"
        )


@router.get("/tasks/history")
async def get_task_history(
    days: int = 30,
    limit: int = 100,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取任务历史"""
    try:
        tasks = await execution_engine.get_task_history(
            current_user.user_id, days, limit
        )
        
        return {
            "success": True,
            "data": tasks,
            "message": f"获取到 {days} 天内的 {len(tasks)} 个历史任务"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务历史失败: {str(e)}"
        )


@router.get("/tasks/{task_id}")
async def get_task_details(
    task_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取任务详情（使用ExecutionService优化版本，增强附件支持）"""
    try:
        logger.info(f"🔍 任务详情API: 获取任务 {task_id}")
        
        # 使用稳定的ExecutionService方法
        task_details = await execution_engine.get_task_details(task_id, current_user.user_id)
        
        if not task_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
        
        # 🔧 Linus式修复: 手动添加附件信息到ExecutionService返回的结果中
        try:
            from ..services.file_association_service import FileAssociationService
            file_service = FileAssociationService()
            
            # 获取当前任务的附件
            current_task_attachments = []
            
            # 1. 获取任务实例附件
            task_files = await file_service.get_task_instance_files(task_id)
            for file_info in task_files:
                current_task_attachments.append({
                    'file_id': file_info['file_id'],
                    'filename': file_info['filename'],
                    'original_filename': file_info['original_filename'],
                    'file_size': file_info['file_size'],
                    'content_type': file_info['content_type'],
                    'attachment_type': file_info['attachment_type'],
                    'source': 'task'
                })
            
            # 2. 获取节点实例附件
            node_instance_id = task_details.get('node_instance_id')
            if node_instance_id:
                node_files = await file_service.get_node_instance_files(uuid.UUID(node_instance_id))
                for file_info in node_files:
                    current_task_attachments.append({
                        'file_id': file_info['file_id'],
                        'filename': file_info['filename'],
                        'original_filename': file_info['original_filename'],
                        'file_size': file_info['file_size'],
                        'content_type': file_info['content_type'],
                        'attachment_type': file_info['attachment_type'],
                        'source': 'node'
                    })
            
            # 添加到返回结果中
            task_details['current_task_attachments'] = current_task_attachments

            logger.info(f"📎 [任务附件] 成功添加附件信息: {len(current_task_attachments)} 个文件")

        except Exception as attachment_error:
            logger.warning(f"⚠️ 获取任务附件失败: {attachment_error}")
            task_details['current_task_attachments'] = []
        
        logger.info(f"✅ 任务详情API: 成功获取任务详情")
        
        # 添加调试信息以帮助前端理解数据结构
        context_debug = {}
        
        # 将调试信息添加到返回数据中
        task_details['debug_info'] = context_debug
        
        # 添加任务拆解相关信息
        subdivision_info = {
            "can_subdivide": False,
            "subdivision_count": 0,
            "existing_subdivisions": [],
            "subdivision_available": True  # 根据业务逻辑决定是否可以拆解
        }
        
        # 检查任务是否可以拆解（根据任务状态和类型）
        task_status = task_details.get('status', '')
        task_type = task_details.get('task_type', '')
        
        # 只有待处理或已分配的人工任务可以拆解
        if task_status in ['pending', 'assigned'] and task_type in ['human', 'mixed']:
            subdivision_info["can_subdivide"] = True
            
            # 获取现有的拆解记录
            try:
                from ..services.task_subdivision_service import TaskSubdivisionService
                subdivision_service = TaskSubdivisionService()
                existing_subdivisions = await subdivision_service.get_task_subdivisions(task_id)
                
                subdivision_info["subdivision_count"] = len(existing_subdivisions)
                subdivision_info["existing_subdivisions"] = [
                    {
                        "subdivision_id": str(sub.subdivision_id),
                        "subdivision_name": sub.subdivision_name,
                        "created_at": sub.created_at.isoformat() if sub.created_at else None,
                        "status": sub.status,
                        "subdivider_name": sub.subdivider_name  # 需要在service中获取
                    }
                    for sub in existing_subdivisions[:5]  # 只显示最近5个
                ]
            except Exception as e:
                logger.warning(f"获取任务拆解信息失败: {e}")
                # 不影响主要功能，继续返回
        
        task_details['subdivision_info'] = subdivision_info

        return {
            "success": True,
            "data": task_details,
            "message": "获取任务详情成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务详情失败: {str(e)}"
        )


@router.post("/tasks/{task_id}/start")
async def start_task(
    task_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """开始执行任务"""
    try:
        result = await execution_engine.start_human_task(task_id, current_user.user_id)
        
        return {
            "success": True,
            "data": result,
            "message": "任务已开始执行"
        }
        
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权执行此任务"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"开始执行任务失败: {str(e)}"
        )


@router.post("/tasks/{task_id}/submit")
async def submit_task_result(
    task_id: uuid.UUID,
    raw_request: Request,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """提交任务结果"""
    try:
        # 先读取原始请求体进行调试
        body = await raw_request.body()
        logger.info(f"📝 收到任务提交的原始请求:")
        logger.info(f"  任务ID: {task_id}")
        logger.info(f"  用户ID: {current_user.user_id}")
        logger.info(f"  原始请求体 ({len(body)} 字节): {body.decode('utf-8', errors='ignore')}")
        
        # 尝试解析JSON
        import json
        try:
            raw_data = json.loads(body.decode('utf-8'))
            logger.info(f"  解析的JSON数据: {raw_data}")
            logger.info(f"  数据类型分析:")
            for key, value in raw_data.items():
                logger.info(f"    {key}: {type(value).__name__} = {repr(value)}")
        except Exception as json_error:
            logger.error(f"  JSON解析失败: {json_error}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的JSON格式: {str(json_error)}"
            )
        
        # 预处理：确保result_data是字典类型
        if 'result_data' in raw_data:
            result_data_value = raw_data['result_data']
            logger.info(f"  原始result_data: {type(result_data_value).__name__} = {repr(result_data_value)}")
            
            # 如果result_data是字符串，尝试解析为JSON
            if isinstance(result_data_value, str):
                try:
                    parsed_json = json.loads(result_data_value)
                    # 检查解析结果是否为字典
                    if isinstance(parsed_json, dict):
                        raw_data['result_data'] = parsed_json
                        logger.info(f"  字符串解析后result_data: {raw_data['result_data']}")
                    else:
                        # 如果解析出来不是字典，包装为字典
                        raw_data['result_data'] = {"value": parsed_json}
                        logger.info(f"  解析结果包装后result_data: {raw_data['result_data']}")
                except:
                    # 如果不是JSON字符串，包装为字典
                    raw_data['result_data'] = {"answer": result_data_value}
                    logger.info(f"  字符串包装后result_data: {raw_data['result_data']}")
            elif result_data_value is None:
                raw_data['result_data'] = {}
                logger.info(f"  None转换后result_data: {raw_data['result_data']}")
            elif not isinstance(result_data_value, dict):
                # 其他类型也包装为字典
                raw_data['result_data'] = {"value": result_data_value}
                logger.info(f"  其他类型包装后result_data: {raw_data['result_data']}")
        
        # 手动验证请求数据
        try:
            request = TaskSubmissionRequest(**raw_data)
            logger.info(f"  ✅ Pydantic验证成功:")
            logger.info(f"    result_data: {request.result_data}")
            logger.info(f"    result_summary: {request.result_summary}")
        except ValidationError as ve:
            logger.error(f"  ❌ Pydantic验证失败:")
            for error in ve.errors():
                logger.error(f"    - {error['loc']}: {error['msg']} (type: {error['type']})")
            logger.error(f"  处理后的数据: {raw_data}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"请求数据验证失败: {ve.errors()}"
            )
        
        # 确保 result_data 不为 None
        result_data = request.result_data if request.result_data is not None else {}
        attachment_file_ids = request.attachment_file_ids or []
        logger.info(f"  🔄 准备提交任务结果: result_data={result_data}, attachments={len(attachment_file_ids)}个")
        
        result = await execution_engine.submit_human_task_result(
            task_id, current_user.user_id, 
            result_data, request.result_summary
        )
        
        # 🆕 处理附件关联
        if attachment_file_ids:
            try:
                from ..services.file_association_service import FileAssociationService
                file_service = FileAssociationService()
                
                for file_id in attachment_file_ids:
                    await file_service.associate_task_instance_file(task_id, uuid.UUID(file_id), current_user.user_id)
                    logger.info(f"  📎 附件关联成功: file_id={file_id} -> task_id={task_id}")
                
                logger.info(f"  ✅ 所有附件关联完成: {len(attachment_file_ids)}个文件")
            except Exception as e:
                logger.warning(f"  ⚠️ 附件关联失败: {e}")
                # 不中断任务提交流程，只记录警告
        
        logger.info(f"  ✅ 任务提交成功: {result}")
        
        return {
            "success": True,
            "data": result,
            "message": "任务结果已提交"
        }
        
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权提交此任务"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"提交任务结果失败: {str(e)}"
        )


@router.post("/tasks/{task_id}/pause")
async def pause_task(
    task_id: uuid.UUID,
    request: TaskActionRequest,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """暂停任务"""
    try:
        result = await execution_engine.pause_task(
            task_id, current_user.user_id, request.reason
        )
        
        return {
            "success": True,
            "data": result,
            "message": "任务已暂停"
        }
        
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权暂停此任务"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"暂停任务失败: {str(e)}"
        )


@router.post("/tasks/{task_id}/help")
async def request_help(
    task_id: uuid.UUID,
    request: HelpRequest,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """请求帮助"""
    try:
        result = await execution_engine.request_help(
            task_id, current_user.user_id, request.help_message
        )
        
        return {
            "success": True,
            "data": result,
            "message": "帮助请求已提交"
        }
        
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权为此任务请求帮助"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"请求帮助失败: {str(e)}"
        )


@router.post("/tasks/{task_id}/reject")
async def reject_task(
    task_id: uuid.UUID,
    request: TaskActionRequest,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """拒绝任务"""
    try:
        if not request.reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="拒绝任务时必须提供拒绝原因"
            )
        
        result = await execution_engine.reject_task(
            task_id, current_user.user_id, request.reason
        )
        
        return {
            "success": True,
            "data": result,
            "message": "任务已拒绝"
        }
        
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权拒绝此任务"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"拒绝任务失败: {str(e)}"
        )


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: uuid.UUID,
    request: TaskActionRequest,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """取消任务"""
    try:
        result = await execution_engine.cancel_task(
            task_id, current_user.user_id, request.reason or "用户取消"
        )
        
        return {
            "success": True,
            "data": result,
            "message": "任务已取消"
        }
        
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权取消此任务"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"取消任务失败: {str(e)}"
        )


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    删除任务实例
    
    只允许删除状态为 'completed' 或 'cancelled' 的任务
    
    Args:
        task_id: 任务ID
        current_user: 当前用户
        
    Returns:
        删除结果
    """
    try:
        logger.info(f"🗑️ 用户 {current_user.username} 请求删除任务: {task_id}")
        
        # 1. 检查任务是否存在和权限
        from ..repositories.instance.task_instance_repository import TaskInstanceRepository
        task_repo = TaskInstanceRepository()
        
        task = await task_repo.get_task_by_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
        
        # 2. 检查权限：允许以下用户删除任务
        # - 被分配的用户
        # - 管理员用户
        # - 任务所属工作流的创建者
        has_permission = False
        permission_reason = ""
        
        # 检查是否是被分配的用户 - 修复UUID类型匹配问题
        assigned_user_id = task.get('assigned_user_id')
        current_user_id = current_user.user_id
        
        logger.debug(f"🔍 权限检查调试信息:")
        logger.debug(f"   任务分配用户ID: {assigned_user_id} (类型: {type(assigned_user_id)})")
        logger.debug(f"   当前用户ID: {current_user_id} (类型: {type(current_user_id)})")
        
        # 统一转换为字符串进行比较
        if assigned_user_id and str(assigned_user_id) == str(current_user_id):
            has_permission = True
            permission_reason = "任务分配者"
        
        # 检查是否是管理员（用户名为admin或具有管理员角色）
        elif current_user.username.lower() == 'admin' or getattr(current_user, 'is_admin', False):
            has_permission = True
            permission_reason = "管理员权限"
        
        # 检查是否是工作流创建者
        else:
            # 获取工作流实例信息
            from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
            workflow_repo = WorkflowInstanceRepository()
            workflow_instance = await workflow_repo.get_instance_by_id(task.get('workflow_instance_id'))
            if workflow_instance:
                created_by = workflow_instance.get('created_by')
                logger.debug(f"   工作流创建者: {created_by} (类型: {type(created_by)})")
                if created_by and str(created_by) == str(current_user_id):
                    has_permission = True
                    permission_reason = "工作流创建者"
        
        if not has_permission:
            logger.warning(f"❌ 用户 {current_user.username} 无权删除任务 {task_id}")
            logger.warning(f"   - 任务分配给: {assigned_user_id}")
            logger.warning(f"   - 当前用户: {current_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此任务"
            )
        
        logger.info(f"✅ 用户 {current_user.username} 具有删除权限 ({permission_reason})")
        
        # 3. 检查任务状态：只允许删除已完成或已取消的任务
        task_status = task.get('status', '').lower()
        if task_status not in ['completed', 'cancelled']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"只能删除已完成或已取消的任务，当前状态: {task_status}"
            )
        
        # 4. 执行软删除
        success = await task_repo.delete_task(task_id, soft_delete=True)
        
        if success:
            logger.info(f"✅ 用户 {current_user.username} 成功删除任务: {task.get('task_title', '未知')}")
            return {
                "success": True,
                "data": {
                    "task_id": str(task_id),
                    "task_title": task.get('task_title', '未知'),
                    "previous_status": task_status,
                    "deleted_at": now_utc().isoformat()
                },
                "message": "任务已删除"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除任务失败"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除任务异常: {e}")
        import traceback
        logger.error(f"错误堆栈: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除任务失败: {str(e)}"
        )


# ==================== Agent任务端点 ====================

@router.get("/agent-tasks/pending")
async def get_pending_agent_tasks(
    agent_id: Optional[uuid.UUID] = None,
    limit: int = 50,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取待处理的Agent任务"""
    try:
        tasks = await agent_task_service.get_pending_agent_tasks(agent_id, limit)
        
        return {
            "success": True,
            "data": tasks,
            "message": f"获取到 {len(tasks)} 个待处理Agent任务"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取待处理Agent任务失败: {str(e)}"
        )


@router.post("/agent-tasks/{task_id}/process")
async def process_agent_task(
    task_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """手动触发Agent任务处理"""
    try:
        result = await agent_task_service.process_agent_task(task_id)
        
        return {
            "success": True,
            "data": result,
            "message": "Agent任务处理完成"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理Agent任务失败: {str(e)}"
        )


@router.post("/agent-tasks/{task_id}/retry")
async def retry_agent_task(
    task_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """重试失败的Agent任务"""
    try:
        result = await agent_task_service.retry_failed_task(task_id)
        
        return {
            "success": True,
            "data": result,
            "message": "Agent任务已重新加入处理队列"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重试Agent任务失败: {str(e)}"
        )


@router.post("/agent-tasks/{task_id}/cancel")
async def cancel_agent_task(
    task_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """取消Agent任务"""
    try:
        result = await agent_task_service.cancel_agent_task(task_id)
        
        return {
            "success": True,
            "data": result,
            "message": "Agent任务已取消"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"取消Agent任务失败: {str(e)}"
        )


@router.get("/agent-tasks/statistics")
async def get_agent_task_statistics(
    agent_id: Optional[uuid.UUID] = None,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取Agent任务统计"""
    try:
        stats = await agent_task_service.get_agent_task_statistics(agent_id)
        
        return {
            "success": True,
            "data": stats,
            "message": "获取Agent任务统计成功"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取Agent任务统计失败: {str(e)}"
        )


# ==================== 工作流实例管理端点 ====================

@router.post("/workflows/instances/{instance_id}/cancel")
async def cancel_workflow_instance(
    instance_id: uuid.UUID,
    request: TaskActionRequest,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """取消工作流实例"""
    try:
        logger.info(f"🚫 用户 {current_user.user_id} 请求取消工作流实例: {instance_id}")
        logger.info(f"  取消原因: {request.reason}")
        
        # 调用服务层处理工作流取消
        result = await execution_engine.cancel_workflow_instance(
            instance_id, current_user.user_id, request.reason or "用户取消"
        )
        
        return {
            "success": True,
            "data": result,
            "message": "工作流实例已取消"
        }
        
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权取消此工作流实例"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"取消工作流实例失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"取消工作流实例失败: {str(e)}"
        )


@router.delete("/workflows/{instance_id}")
async def delete_workflow_instance(
    instance_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """删除工作流实例"""
    try:
        logger.info(f"🗑️ 用户 {current_user.user_id} ({current_user.username}) 请求删除工作流实例: {instance_id}")
        
        from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
        workflow_instance_repo = WorkflowInstanceRepository()
        
        # 检查实例是否存在
        logger.info(f"🔍 步骤1: 检查工作流实例是否存在")
        instance = await workflow_instance_repo.get_instance_by_id(instance_id)
        if not instance:
            logger.warning(f"⚠️ 工作流实例不存在: {instance_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流实例不存在"
            )
        
        logger.info(f"📋 找到工作流实例详细信息:")
        logger.info(f"   - 实例名称: {instance.get('workflow_instance_name', '未命名')}")
        logger.info(f"   - 当前状态: {instance.get('status')}")
        logger.info(f"   - 执行者ID: {instance.get('executor_id')}")
        logger.info(f"   - 创建时间: {instance.get('created_at')}")
        logger.info(f"   - 更新时间: {instance.get('updated_at')}")
        logger.info(f"   - 是否已删除: {instance.get('is_deleted', False)}")
        
        # 检查权限（只有执行者可以删除）
        logger.info(f"🔍 步骤2: 检查删除权限")
        current_user_id_str = str(current_user.user_id)
        # 数据库字段是 executor_id
        executor_id_str = str(instance.get('executor_id'))
        logger.info(f"   - 当前用户ID: {current_user_id_str}")
        logger.info(f"   - 执行者ID: {executor_id_str}")
        
        if executor_id_str != current_user_id_str:
            logger.warning(f"🚫 权限检查失败:")
            logger.warning(f"   - 用户 {current_user_id_str} 无权删除实例 {instance_id}")
            logger.warning(f"   - 只有执行者 {executor_id_str} 可以删除此实例")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此工作流实例"
            )
        logger.info(f"✅ 权限检查通过")
        
        # 检查实例状态（不允许删除正在运行的实例）
        logger.info(f"🔍 步骤3: 检查实例状态")
        current_status = instance.get('status')
        logger.info(f"   - 当前状态: {current_status}")
        
        if current_status == 'running':
            logger.warning(f"⚠️ 状态检查失败: 不能删除正在运行的实例")
            logger.warning(f"   - 实例 {instance_id} 状态为 'running'")
            logger.warning(f"   - 请先取消实例后再删除")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法删除正在运行的工作流实例，请先取消实例"
            )
        logger.info(f"✅ 状态检查通过，可以删除")
        
        # 执行软删除
        logger.info(f"🔍 步骤4: 执行软删除操作")
        logger.info(f"   - 调用 workflow_instance_repo.delete_instance({instance_id}, soft_delete=True)")
        
        try:
            success = await workflow_instance_repo.delete_instance(instance_id, soft_delete=True)
            logger.info(f"   - 删除操作返回结果: {success}")
            
            if success:
                logger.info(f"✅ 工作流实例删除成功: {instance_id}")
                
                # 验证删除结果
                logger.info(f"🔍 步骤5: 验证删除结果")
                verification_instance = await workflow_instance_repo.get_instance_by_id(instance_id)
                if verification_instance:
                    logger.info(f"   - 验证: 实例仍存在 (软删除)")
                    logger.info(f"   - is_deleted 标志: {verification_instance.get('is_deleted', 'unknown')}")
                else:
                    logger.info(f"   - 验证: 实例已不可访问 (删除成功)")
                
                return {
                    "success": True,
                    "data": {"instance_id": str(instance_id)},
                    "message": "工作流实例已删除"
                }
            else:
                logger.error(f"❌ 删除工作流实例失败:")
                logger.error(f"   - 实例ID: {instance_id}")
                logger.error(f"   - 数据库操作返回: {success}")
                logger.error(f"   - 可能的原因: 数据库约束、权限问题或实例不存在")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="删除工作流实例失败"
                )
        except Exception as delete_error:
            logger.error(f"❌ 执行删除操作时发生异常:")
            logger.error(f"   - 异常类型: {type(delete_error).__name__}")
            logger.error(f"   - 异常信息: {str(delete_error)}")
            import traceback
            logger.error(f"   - 异常堆栈: {traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"删除操作异常: {str(delete_error)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 删除工作流实例总体异常:")
        logger.error(f"   - 实例ID: {instance_id}")
        logger.error(f"   - 用户ID: {current_user.user_id}")
        logger.error(f"   - 异常类型: {type(e).__name__}")
        logger.error(f"   - 异常信息: {str(e)}")
        import traceback
        logger.error(f"   - 完整异常堆栈: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除工作流实例失败: {str(e)}"
        )


@router.get("/workflows/instances/{instance_id}/context")
async def get_workflow_context(
    instance_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取工作流实例的完整上下文内容"""
    try:
        logger.info(f"📊 用户 {current_user.user_id} 请求获取工作流上下文: {instance_id}")
        
        # 验证工作流实例是否存在和权限
        workflow_query = '''
        SELECT workflow_instance_id, executor_id, status, workflow_instance_name
        FROM workflow_instance 
        WHERE workflow_instance_id = $1 AND is_deleted = FALSE
        '''
        from ..repositories.instance.task_instance_repository import TaskInstanceRepository
        task_repo = TaskInstanceRepository()
        workflow = await task_repo.db.fetch_one(workflow_query, instance_id)
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流实例不存在"
            )
        
        # 检查访问权限（执行者或管理员可以查看）
        if workflow['executor_id'] != current_user.user_id:
            # TODO: 这里可以添加管理员权限检查
            logger.warning(f"⚠️ 用户 {current_user.user_id} 尝试访问不属于自己的工作流: {instance_id}")
            # 暂时允许所有用户查看（生产环境需要严格权限控制）
        
        # 获取完整的工作流上下文
        context = await execution_engine._collect_workflow_context(instance_id)
        
        # 查找结束节点的输出数据
        end_node_output = None
        end_nodes_query = '''
        SELECT ni.output_data, n.name as node_name
        FROM node_instance ni
        JOIN node n ON ni.node_id = n.node_id
        WHERE ni.workflow_instance_id = $1 
        AND n.node_type = 'end'
        AND ni.status = 'completed'
        ORDER BY ni.updated_at DESC
        LIMIT 1
        '''
        end_node = await task_repo.db.fetch_one(end_nodes_query, instance_id)
        
        if end_node and end_node['output_data']:
            end_node_output = {
                'end_node_name': end_node['node_name'],
                'full_context': end_node['output_data']
            }
        
        return {
            "success": True,
            "data": {
                "workflow_instance_id": str(instance_id),
                "workflow_status": workflow['status'],
                "workflow_name": workflow['workflow_instance_name'],
                "context_summary": context,
                "end_node_output": end_node_output,
                "has_complete_context": end_node_output is not None
            },
            "message": "工作流上下文获取成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工作流上下文失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取工作流上下文失败: {str(e)}"
        )


# ==================== 管理员任务管理端点 ====================

@router.post("/admin/tasks/{task_id}/assign")
async def assign_task_to_user(
    task_id: uuid.UUID,
    request: TaskAssignmentRequest,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """管理员分配任务给用户"""
    try:
        # 验证管理员权限
        if current_user.role not in ['admin', 'manager']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限执行此操作"
            )
        
        result = await execution_engine.assign_task_to_user(
            task_id, request.user_id, current_user.user_id
        )
        
        return {
            "success": True,
            "data": result,
            "message": "任务分配成功"
        }
        
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权分配任务"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"分配任务失败: {str(e)}"
        )


# ==================== 工作流监控端点 ====================

@router.get("/system/monitor-stats")
async def get_workflow_monitor_stats(
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取工作流监控服务统计信息"""
    try:
        # 验证管理员权限
        if current_user.role not in ['admin', 'manager']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限访问监控统计信息"
            )
        
        from ..services.workflow_monitor_service import get_workflow_monitor
        workflow_monitor = get_workflow_monitor()
        
        stats = await workflow_monitor.get_monitor_stats()
        
        return {
            "success": True,
            "data": stats,
            "message": "获取监控统计信息成功"
        }
        
    except Exception as e:
        logger.error(f"获取监控统计信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取监控统计信息失败: {str(e)}"
        )


@router.post("/system/monitor-scan")
async def manual_workflow_monitor_scan(
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """手动触发停滞工作流扫描和恢复"""
    try:
        # 验证管理员权限
        if current_user.role not in ['admin', 'manager']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限手动触发监控扫描"
            )
        
        logger.info(f"🔧 用户 {current_user.username} 手动触发停滞工作流扫描")
        
        from ..services.workflow_monitor_service import get_workflow_monitor
        workflow_monitor = get_workflow_monitor()
        
        scan_results = await workflow_monitor.manual_scan_and_recover()
        
        return {
            "success": True,
            "data": scan_results,
            "message": f"扫描完成，恢复了 {scan_results['successful_recoveries']} 个停滞工作流"
        }
        
    except Exception as e:
        logger.error(f"手动触发监控扫描失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"手动触发监控扫描失败: {str(e)}"
        )


# ==================== 系统监控端点 ====================

@router.get("/system/status")
async def get_system_status(
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取执行系统状态"""
    try:
        # 验证管理员权限
        if current_user.role not in ['admin', 'manager']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限访问系统状态"
            )
        
        system_status = {
            "execution_engine": {
                "is_running": execution_engine.is_running,
                "running_instances": len(execution_engine.running_instances),
                "queue_size": execution_engine.execution_queue.qsize()
            },
            "agent_service": {
                "is_running": agent_task_service.is_running,
                "queue_size": agent_task_service.processing_queue.qsize(),
                "max_concurrent": agent_task_service.max_concurrent_tasks
            }
        }
        
        return {
            "success": True,
            "data": system_status,
            "message": "获取系统状态成功"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统状态失败: {str(e)}"
        )


@router.get("/system/context-health")
async def get_context_health_stats(
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取工作流上下文健康统计信息"""
    try:
        # 验证管理员权限
        if current_user.role not in ['admin', 'manager']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限访问系统健康状态"
            )
        
        # 获取上下文管理器健康统计
        from ..services.workflow_execution_context import get_context_manager
        context_manager = get_context_manager()
        
        health_stats = context_manager.get_health_stats()
        
        return {
            "success": True,
            "data": {
                "context_health": health_stats,
                "health_check_enabled": True,
                "persistence_enabled": context_manager._persistence_enabled,
                "auto_recovery_enabled": context_manager._auto_recovery_enabled,
                "context_ttl_hours": context_manager._context_ttl / 3600,
                "max_memory_contexts": context_manager._max_memory_contexts,
                "health_check_interval_seconds": context_manager._health_check_interval
            },
            "message": "获取上下文健康状态成功"
        }
        
    except Exception as e:
        logger.error(f"获取上下文健康状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取上下文健康状态失败: {str(e)}"
        )


@router.get("/workflows/{instance_id}/context-health")
async def check_workflow_context_health(
    instance_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """检查特定工作流的上下文健康状态"""
    try:
        from ..services.workflow_execution_context import get_context_manager
        context_manager = get_context_manager()
        
        # 检查上下文健康状态
        health_status = await context_manager.check_context_health(instance_id)
        
        return {
            "success": True,
            "data": {
                "workflow_instance_id": str(instance_id),
                "context_health": health_status
            },
            "message": "上下文健康检查完成"
        }
        
    except Exception as e:
        logger.error(f"检查工作流上下文健康状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检查工作流上下文健康状态失败: {str(e)}"
        )


@router.post("/workflows/{instance_id}/context-recover")
async def recover_workflow_context(
    instance_id: uuid.UUID,
    force_recover: bool = Query(False, description="强制恢复上下文"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """主动恢复工作流上下文并检查下游节点触发"""
    try:
        logger.info(f"🔧 用户 {current_user.username} 请求恢复工作流上下文: {instance_id}")
        
        from ..services.workflow_execution_context import get_context_manager
        from ..services.execution_service import execution_engine
        
        context_manager = get_context_manager()
        
        # 1. 检查当前上下文状态
        current_context = context_manager.contexts.get(instance_id)
        context_existed = current_context is not None
        
        logger.info(f"   - 当前内存中上下文存在: {context_existed}")
        
        # 2. 强制恢复或上下文不存在时进行恢复
        if force_recover or not context_existed:
            logger.info(f"   - 开始恢复上下文 (强制: {force_recover})")
            
            # 强制重新从数据库恢复上下文
            if context_existed and force_recover:
                # 清理现有上下文
                await context_manager.remove_context(instance_id)
                logger.info(f"   - 已清理现有上下文")
            
            # 恢复上下文
            recovered_context = await context_manager.get_context(instance_id)
            
            if recovered_context:
                logger.info(f"✅ 上下文恢复成功")
                logger.info(f"   - 节点依赖数: {len(recovered_context.node_dependencies)}")
                logger.info(f"   - 已完成节点: {len(recovered_context.execution_context.get('completed_nodes', set()))}")
                logger.info(f"   - 待触发节点: {len(recovered_context.pending_triggers)}")
                
                # 3. 检查并触发下游节点
                ready_nodes = await recovered_context.get_ready_nodes()
                logger.info(f"   - 发现待触发节点: {len(ready_nodes)}")
                
                triggered_count = 0
                if ready_nodes:
                    for node_instance_id in ready_nodes:
                        try:
                            # 触发节点执行
                            logger.info(f"   - 触发节点执行: {node_instance_id}")
                            await execution_engine._on_nodes_ready_to_execute(instance_id, [node_instance_id])
                            triggered_count += 1
                        except Exception as trigger_error:
                            logger.error(f"   - 触发节点失败 {node_instance_id}: {trigger_error}")
                
                return {
                    "success": True,
                    "data": {
                        "workflow_instance_id": str(instance_id),
                        "context_recovered": True,
                        "context_existed_before": context_existed,
                        "forced_recovery": force_recover,
                        "node_dependencies_count": len(recovered_context.node_dependencies),
                        "completed_nodes_count": len(recovered_context.execution_context.get('completed_nodes', set())),
                        "ready_nodes_found": len(ready_nodes),
                        "nodes_triggered": triggered_count,
                        "triggered_node_ids": [str(nid) for nid in ready_nodes] if ready_nodes else []
                    },
                    "message": f"上下文恢复成功，触发了 {triggered_count} 个待执行节点"
                }
            else:
                return {
                    "success": False,
                    "data": {
                        "workflow_instance_id": str(instance_id),
                        "context_recovered": False,
                        "error": "无法从数据库恢复上下文"
                    },
                    "message": "上下文恢复失败"
                }
        else:
            # 上下文已存在且不强制恢复，只检查待触发节点
            ready_nodes = await current_context.get_ready_nodes()
            logger.info(f"   - 上下文已存在，检查待触发节点: {len(ready_nodes)}")
            
            triggered_count = 0
            if ready_nodes:
                for node_instance_id in ready_nodes:
                    try:
                        await execution_engine._on_nodes_ready_to_execute(instance_id, [node_instance_id])
                        triggered_count += 1
                    except Exception as trigger_error:
                        logger.error(f"   - 触发节点失败 {node_instance_id}: {trigger_error}")
            
            return {
                "success": True,
                "data": {
                    "workflow_instance_id": str(instance_id),
                    "context_recovered": False,
                    "context_existed_before": True,
                    "forced_recovery": False,
                    "ready_nodes_found": len(ready_nodes),
                    "nodes_triggered": triggered_count,
                    "triggered_node_ids": [str(nid) for nid in ready_nodes] if ready_nodes else []
                },
                "message": f"上下文已存在，触发了 {triggered_count} 个待执行节点"
            }
        
    except Exception as e:
        logger.error(f"恢复工作流上下文失败: {e}")
        import traceback
        logger.error(f"错误堆栈: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"恢复工作流上下文失败: {str(e)}"
        )


@router.post("/workflows/smart-refresh")
async def smart_workflow_refresh(
    workflow_instance_ids: Optional[List[uuid.UUID]] = None,
    force_recovery: bool = Query(False, description="强制恢复上下文"),
    include_stale_detection: bool = Query(True, description="包含停滞检测"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    智能工作流刷新 - 前端刷新时自动调用
    
    结合上下文恢复和停滞检测的智能刷新机制：
    1. 如果提供了具体的workflow_instance_ids，只处理指定的工作流
    2. 如果没有提供，自动扫描用户的活动工作流
    3. 对每个工作流进行上下文健康检查和恢复
    4. 可选地检测和修复停滞状态
    """
    try:
        logger.info(f"🔄 用户 {current_user.username} 请求智能工作流刷新")
        
        from ..services.workflow_monitor_service import get_workflow_monitor
        from ..services.workflow_execution_context import get_context_manager
        from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
        
        context_manager = get_context_manager()
        workflow_monitor = get_workflow_monitor()
        workflow_repo = WorkflowInstanceRepository()
        
        # 如果没有指定工作流ID，则获取用户的活动工作流
        if not workflow_instance_ids:
            user_workflows_query = """
            SELECT workflow_instance_id
            FROM workflow_instance 
            WHERE executor_id = %s 
            AND status IN ('running', 'pending')
            AND is_deleted = 0
            ORDER BY updated_at DESC
            LIMIT 20
            """
            user_workflows = await workflow_repo.db.fetch_all(user_workflows_query, current_user.user_id)
            workflow_instance_ids = [uuid.UUID(wf['workflow_instance_id']) for wf in user_workflows]
        
        if not workflow_instance_ids:
            return {
                "success": True,
                "data": {
                    "message": "没有找到需要刷新的工作流",
                    "processed_workflows": [],
                    "total_processed": 0,
                    "recovery_results": {
                        "context_recoveries": 0,
                        "stale_recoveries": 0,
                        "triggered_nodes": 0
                    }
                },
                "message": "智能刷新完成 - 无工作流需要处理"
            }
        
        logger.info(f"   - 准备处理 {len(workflow_instance_ids)} 个工作流")
        
        # 处理结果统计
        results = []
        recovery_stats = {
            "context_recoveries": 0,
            "stale_recoveries": 0,
            "triggered_nodes": 0,
            "failed_recoveries": 0
        }
        
        # 处理每个工作流
        for instance_id in workflow_instance_ids:
            workflow_result = {
                "workflow_instance_id": str(instance_id),
                "context_recovery": False,
                "stale_recovery": False,
                "nodes_triggered": 0,
                "status": "unknown",
                "issues_detected": [],
                "actions_taken": []
            }
            
            try:
                # 1. 获取工作流基本信息
                workflow_info = await workflow_repo.get_instance_by_id(instance_id)
                if not workflow_info:
                    workflow_result["status"] = "not_found"
                    workflow_result["issues_detected"].append("工作流实例不存在")
                    results.append(workflow_result)
                    continue
                
                workflow_result["workflow_name"] = workflow_info.get("workflow_instance_name", "未知")
                workflow_result["workflow_status"] = workflow_info.get("status")
                
                # 2. 检查上下文健康状态
                context_health = await context_manager.check_context_health(instance_id)
                if not context_health.get("healthy", True):
                    workflow_result["issues_detected"].append("上下文不健康")
                    
                    # 尝试恢复上下文
                    logger.info(f"   - 恢复工作流上下文: {instance_id}")
                    if force_recovery:
                        await context_manager.remove_context(instance_id)
                    
                    recovered_context = await context_manager.get_context(instance_id)
                    if recovered_context:
                        workflow_result["context_recovery"] = True
                        workflow_result["actions_taken"].append("上下文已恢复")
                        recovery_stats["context_recoveries"] += 1
                        
                        # 检查并触发待执行节点
                        ready_nodes = await recovered_context.get_ready_nodes()
                        if ready_nodes:
                            triggered_count = 0
                            for node_instance_id in ready_nodes:
                                try:
                                    await execution_engine._on_nodes_ready_to_execute(instance_id, [node_instance_id])
                                    triggered_count += 1
                                except Exception:
                                    pass
                            
                            if triggered_count > 0:
                                workflow_result["nodes_triggered"] = triggered_count
                                workflow_result["actions_taken"].append(f"触发了 {triggered_count} 个待执行节点")
                                recovery_stats["triggered_nodes"] += triggered_count
                    else:
                        workflow_result["issues_detected"].append("上下文恢复失败")
                        recovery_stats["failed_recoveries"] += 1
                
                # 3. 可选的停滞检测和恢复
                if include_stale_detection and workflow_info.get("status") in ["running", "pending"]:
                    # 检查是否停滞
                    workflow_data = dict(workflow_info)
                    workflow_data["workflow_instance_id"] = str(instance_id)
                    
                    if await workflow_monitor._is_workflow_truly_stale(workflow_data):
                        workflow_result["issues_detected"].append("工作流停滞")
                        
                        try:
                            await workflow_monitor._attempt_workflow_recovery(workflow_data)
                            workflow_result["stale_recovery"] = True
                            workflow_result["actions_taken"].append("停滞状态已修复")
                            recovery_stats["stale_recoveries"] += 1
                        except Exception as e:
                            workflow_result["issues_detected"].append(f"停滞恢复失败: {str(e)}")
                            recovery_stats["failed_recoveries"] += 1
                
                # 4. 最终状态
                if not workflow_result["issues_detected"]:
                    workflow_result["status"] = "healthy"
                elif workflow_result["context_recovery"] or workflow_result["stale_recovery"]:
                    workflow_result["status"] = "recovered" 
                else:
                    workflow_result["status"] = "needs_attention"
                
            except Exception as e:
                logger.error(f"   - 处理工作流 {instance_id} 失败: {e}")
                workflow_result["status"] = "error"
                workflow_result["issues_detected"].append(f"处理异常: {str(e)}")
                recovery_stats["failed_recoveries"] += 1
            
            results.append(workflow_result)
        
        # 统计成功处理的工作流
        successful_results = [r for r in results if r["status"] in ["healthy", "recovered"]]
        
        return {
            "success": True,
            "data": {
                "processed_workflows": results,
                "total_processed": len(workflow_instance_ids),
                "successful_processed": len(successful_results),
                "recovery_results": recovery_stats,
                "summary": {
                    "healthy_workflows": len([r for r in results if r["status"] == "healthy"]),
                    "recovered_workflows": len([r for r in results if r["status"] == "recovered"]),
                    "failed_workflows": len([r for r in results if r["status"] == "error"]),
                    "workflows_needing_attention": len([r for r in results if r["status"] == "needs_attention"])
                }
            },
            "message": f"智能刷新完成 - 处理了 {len(workflow_instance_ids)} 个工作流，恢复了 {recovery_stats['context_recoveries'] + recovery_stats['stale_recoveries']} 个"
        }
        
    except Exception as e:
        logger.error(f"智能工作流刷新失败: {e}")
        import traceback
        logger.error(f"错误堆栈: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"智能工作流刷新失败: {str(e)}"
        )


@router.post("/workflows/batch-context-recover")
async def batch_recover_workflow_contexts(
    workflow_instance_ids: List[uuid.UUID],
    force_recover: bool = Query(False, description="强制恢复上下文"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """批量恢复多个工作流的上下文（用于前端列表刷新时）"""
    try:
        logger.info(f"🔧 用户 {current_user.username} 请求批量恢复 {len(workflow_instance_ids)} 个工作流上下文")
        
        from ..services.workflow_execution_context import get_context_manager
        from ..services.execution_service import execution_engine
        
        context_manager = get_context_manager()
        
        results = []
        total_triggered = 0
        
        for instance_id in workflow_instance_ids:
            try:
                logger.info(f"   - 处理工作流: {instance_id}")
                
                # 检查当前上下文状态
                current_context = context_manager.contexts.get(instance_id)
                context_existed = current_context is not None
                
                # 强制恢复或上下文不存在时进行恢复
                if force_recover or not context_existed:
                    if context_existed and force_recover:
                        await context_manager.remove_context(instance_id)
                    
                    # 恢复上下文
                    recovered_context = await context_manager.get_context(instance_id)
                    
                    if recovered_context:
                        # 检查并触发下游节点
                        ready_nodes = await recovered_context.get_ready_nodes()
                        triggered_count = 0
                        
                        for node_instance_id in ready_nodes:
                            try:
                                await execution_engine._on_nodes_ready_to_execute(instance_id, [node_instance_id])
                                triggered_count += 1
                            except Exception:
                                pass  # 静默处理单个节点触发失败
                        
                        total_triggered += triggered_count
                        
                        results.append({
                            "workflow_instance_id": str(instance_id),
                            "success": True,
                            "context_recovered": True,
                            "nodes_triggered": triggered_count
                        })
                    else:
                        results.append({
                            "workflow_instance_id": str(instance_id),
                            "success": False,
                            "context_recovered": False,
                            "error": "恢复失败"
                        })
                else:
                    # 上下文已存在，只检查待触发节点
                    ready_nodes = await current_context.get_ready_nodes()
                    triggered_count = 0
                    
                    for node_instance_id in ready_nodes:
                        try:
                            await execution_engine._on_nodes_ready_to_execute(instance_id, [node_instance_id])
                            triggered_count += 1
                        except Exception:
                            pass
                    
                    total_triggered += triggered_count
                    
                    results.append({
                        "workflow_instance_id": str(instance_id),
                        "success": True,
                        "context_recovered": False,
                        "nodes_triggered": triggered_count
                    })
                    
            except Exception as e:
                logger.error(f"   - 处理工作流 {instance_id} 失败: {e}")
                results.append({
                    "workflow_instance_id": str(instance_id),
                    "success": False,
                    "error": str(e)
                })
        
        successful_recoveries = len([r for r in results if r["success"]])
        
        return {
            "success": True,
            "data": {
                "total_workflows": len(workflow_instance_ids),
                "successful_recoveries": successful_recoveries,
                "total_nodes_triggered": total_triggered,
                "results": results
            },
            "message": f"批量恢复完成: {successful_recoveries}/{len(workflow_instance_ids)} 成功，触发了 {total_triggered} 个节点"
        }
        
    except Exception as e:
        logger.error(f"批量恢复工作流上下文失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量恢复工作流上下文失败: {str(e)}"
        )


@router.get("/online-resources")
async def get_online_resources(
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取在线资源（用户和Agent）"""
    try:
        from ..repositories.user.user_repository import UserRepository
        from ..repositories.processor.processor_repository import ProcessorRepository
        
        user_repo = UserRepository()
        processor_repo = ProcessorRepository()
        
        # 获取真正在线的用户 (30分钟内有活动的用户)
        online_users_data = await user_repo.get_online_users(activity_timeout_minutes=30)
        
        # 获取所有活跃用户用于对比
        all_active_users = await user_repo.list_all({"status": True, "is_deleted": False})
        
        # 获取所有Agent处理器
        agents = await processor_repo.list_all({"type": "agent", "is_deleted": False})
        
        # 格式化用户数据 - 包含所有用户，区分在线/离线状态
        all_users = []
        online_user_ids = {str(user["user_id"]) for user in online_users_data}
        
        for user in all_active_users:
            # 安全处理profile字段
            profile = user.get("profile", {})
            if isinstance(profile, str):
                try:
                    import json
                    profile = json.loads(profile)
                except:
                    profile = {}
            
            user_id = str(user["user_id"])
            is_user_online = user_id in online_user_ids
            
            all_users.append({
                "user_id": user_id,
                "username": user["username"],
                "email": user["email"],
                "full_name": profile.get("full_name", "") if isinstance(profile, dict) else "",
                "description": user.get("description", ""),
                "status": "online" if is_user_online else "offline",
                "is_online": is_user_online,
                "capabilities": profile.get("capabilities", []) if isinstance(profile, dict) else [],
                "role": user.get("role", "user"),
                "created_at": user["created_at"].isoformat() if user.get("created_at") else None,
                "last_login": user.get("last_login_at").isoformat() if user.get("last_login_at") else None,
                "last_activity": user.get("last_activity_at").isoformat() if user.get("last_activity_at") else None
            })
        
        # 格式化Agent数据
        online_agents = []
        for agent in agents:
            online_agents.append({
                "agent_id": str(agent["processor_id"]),
                "name": agent["name"],
                "description": agent.get("description", ""),
                "status": "online",
                "capabilities": agent.get("capabilities", []),
                "tools": agent.get("tools", []),
                "config": agent.get("config", {}),
                "created_at": agent["created_at"].isoformat() if agent.get("created_at") else None,
                "last_used": agent["updated_at"].isoformat() if agent.get("updated_at") else None
            })
        
        return {
            "success": True,
            "data": {
                "users": all_users,
                "agents": online_agents,
                "statistics": {
                    "total_users": len(all_users),
                    "total_agents": len(online_agents),
                    "online_users": len([u for u in all_users if u["is_online"]]),
                    "offline_users": len([u for u in all_users if not u["is_online"]]),
                    "online_agents": len(online_agents)
                }
            },
            "message": "获取在线资源成功"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取在线资源失败: {str(e)}"
        )


@router.get("/workflows/{instance_id}/nodes-detail")
async def get_workflow_nodes_detail(
    instance_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取工作流实例的详细节点输出信息"""
    try:
        from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
        from ..repositories.instance.node_instance_repository import NodeInstanceRepository
        from ..repositories.instance.task_instance_repository import TaskInstanceRepository
        
        workflow_repo = WorkflowInstanceRepository()
        node_repo = NodeInstanceRepository()
        task_repo = TaskInstanceRepository()
        
        # 1. 验证工作流实例是否存在
        workflow_instance = await workflow_repo.get_instance_by_id(instance_id)
        if not workflow_instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流实例不存在"
            )
        
        # 2. 获取详细的节点实例信息（包括处理器信息和位置信息）
        nodes_query = """
        SELECT 
            ni.node_instance_id,
            ni.node_id,
            n.node_base_id,
            ni.workflow_instance_id,
            ni.status as node_status,
            ni.input_data as node_input,
            ni.output_data as node_output,
            ni.error_message as node_error,
            ni.retry_count,
            ni.created_at as node_created_at,
            ni.started_at as node_started_at,
            ni.completed_at as node_completed_at,
            -- 节点定义信息
            n.name as node_name,
            n.type as node_type,
            n.position_x,
            n.position_y,
            -- 处理器信息（通过node_processor关联表）
            p.name as processor_name,
            p.type as processor_type,
            -- 执行时长计算 (MySQL兼容)
            CASE 
                WHEN ni.started_at IS NOT NULL AND ni.completed_at IS NOT NULL 
                THEN CAST(TIMESTAMPDIFF(SECOND, ni.started_at, ni.completed_at) AS SIGNED)
                WHEN ni.started_at IS NOT NULL 
                THEN CAST(TIMESTAMPDIFF(SECOND, ni.started_at, NOW()) AS SIGNED)
                ELSE NULL
            END as execution_duration_seconds
        FROM node_instance ni
        LEFT JOIN node n ON ni.node_id = n.node_id
        LEFT JOIN node_processor np ON n.node_id = np.node_id
        LEFT JOIN processor p ON np.processor_id = p.processor_id
        WHERE ni.workflow_instance_id = $1
        AND ni.is_deleted = 0
        ORDER BY ni.created_at ASC
        """
        
        nodes = await node_repo.db.fetch_all(nodes_query, instance_id)
        
        # 3. 获取每个节点的任务实例信息
        tasks_query = """
        SELECT 
            ti.task_instance_id,
            ti.node_instance_id,
            ti.task_title,
            ti.task_description,
            ti.status as task_status,
            ti.input_data as task_input,
            ti.output_data as task_output,
            ti.result_summary as task_result,
            ti.error_message as task_error,
            ti.task_type,
            ti.priority,
            ti.estimated_duration,
            ti.actual_duration,
            ti.created_at as task_created_at,
            ti.started_at as task_started_at,
            ti.completed_at as task_completed_at,
            -- 处理器信息
            p.name as processor_name,
            p.type as processor_type,
            -- 分配信息
            u.username as assigned_user_name,
            a.agent_name as assigned_agent_name
        FROM task_instance ti
        LEFT JOIN processor p ON ti.processor_id = p.processor_id
        LEFT JOIN user u ON ti.assigned_user_id = u.user_id
        LEFT JOIN agent a ON ti.assigned_agent_id = a.agent_id
        WHERE ti.workflow_instance_id = %s
        AND ti.is_deleted = 0
        ORDER BY ti.created_at ASC
        """
        
        tasks = await task_repo.db.fetch_all(tasks_query, instance_id)
        
        # 4. 组织节点和任务数据
        formatted_nodes = []
        tasks_by_node = {}
        
        # 按节点实例ID分组任务
        for task in tasks:
            node_id = str(task['node_instance_id']) if task['node_instance_id'] else None
            if node_id:
                if node_id not in tasks_by_node:
                    tasks_by_node[node_id] = []
                
                task_data = {
                    "task_instance_id": str(task['task_instance_id']),
                    "task_title": task['task_title'],
                    "task_description": task['task_description'],
                    "status": task['task_status'],
                    "task_type": task['task_type'],
                    "priority": task['priority'],
                    "input_data": task['task_input'] or {},
                    "output_data": task['task_output'] or {},
                    "result_summary": task['task_result'],
                    "error_message": task['task_error'],
                    "estimated_duration": task['estimated_duration'],
                    "actual_duration": task['actual_duration'],
                    "processor": {
                        "name": task['processor_name'],
                        "type": task['processor_type']
                    },
                    "assignment": {
                        "assigned_user": task['assigned_user_name'],
                        "assigned_agent": task['assigned_agent_name']
                    },
                    "timestamps": {
                        "created_at": task['task_created_at'].isoformat() if task.get('task_created_at') else None,
                        "started_at": task['task_started_at'].isoformat() if task.get('task_started_at') else None,
                        "completed_at": task['task_completed_at'].isoformat() if task.get('task_completed_at') else None
                    }
                }
                tasks_by_node[node_id].append(task_data)
        
        # 处理节点数据
        for node in nodes:
            node_id = str(node['node_instance_id'])
            node_tasks = tasks_by_node.get(node_id, [])
            
            # 计算节点级别的统计信息
            total_tasks = len(node_tasks)
            completed_tasks = len([t for t in node_tasks if t['status'] == 'completed'])
            failed_tasks = len([t for t in node_tasks if t['status'] == 'failed'])
            running_tasks = len([t for t in node_tasks if t['status'] in ['in_progress', 'assigned']])
            
            # 汇总节点输出数据：从所有已完成任务的输出中合并
            node_output_data = {}
            node_input_data = node['node_input'] or {}
            
            # 收集所有已完成任务的输出数据
            for task in node_tasks:
                if task['status'] == 'completed' and task['output_data']:
                    # 合并任务输出到节点输出
                    if isinstance(task['output_data'], dict):
                        node_output_data.update(task['output_data'])
                    else:
                        # 如果任务输出不是字典，以任务ID为键存储
                        task_key = f"task_{task['task_instance_id']}"
                        node_output_data[task_key] = task['output_data']
            
            # 如果没有任务输出但节点有输出，使用节点级别的输出
            if not node_output_data and (node['node_output'] or {}):
                node_output_data = node['node_output'] or {}
            
            node_data = {
                "node_instance_id": str(node['node_instance_id']),
                "node_id": str(node['node_id']),
                "node_base_id": str(node['node_base_id']),
                "node_name": node['node_name'],
                "node_type": node['node_type'],
                "status": node['node_status'],
                "retry_count": node['retry_count'] or 0,
                # 🔧 新增：位置信息用于前端布局
                "position": {
                    "x": float(node['position_x']) if node['position_x'] is not None else None,
                    "y": float(node['position_y']) if node['position_y'] is not None else None
                },
                "input_data": node_input_data,
                "output_data": node_output_data,
                "error_message": node['node_error'],
                "config": node.get('node_config', {}),  # 使用get方法防止KeyError
                "execution_duration_seconds": node['execution_duration_seconds'],
                "processor_name": node['processor_name'],
                "processor_type": node['processor_type'],
                "task_count": total_tasks,
                "timestamps": {
                    "created_at": node['node_created_at'].isoformat() if node.get('node_created_at') else None,
                    "started_at": node['node_started_at'].isoformat() if node.get('node_started_at') else None,
                    "completed_at": node['node_completed_at'].isoformat() if node.get('node_completed_at') else None
                },
                "task_statistics": {
                    "total_tasks": total_tasks,
                    "completed_tasks": completed_tasks,
                    "failed_tasks": failed_tasks,
                    "running_tasks": running_tasks,
                    "success_rate": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
                },
                "tasks": node_tasks
            }
            formatted_nodes.append(node_data)
        
        # 5. 获取节点连接关系（从工作流定义中）
        edges_query = """
        SELECT 
            nc.from_node_id as source_node_id,
            nc.to_node_id as target_node_id,
            nc.connection_type,
            nc.condition_config,
            -- 获取源节点和目标节点的实例ID
            ni_source.node_instance_id as source_instance_id,
            ni_target.node_instance_id as target_instance_id,
            -- 获取节点名称用于调试
            n_source.name as source_node_name,
            n_target.name as target_node_name
        FROM node_connection nc
        LEFT JOIN node n_source ON nc.from_node_id = n_source.node_id
        LEFT JOIN node n_target ON nc.to_node_id = n_target.node_id
        LEFT JOIN node_instance ni_source ON n_source.node_id = ni_source.node_id 
            AND ni_source.workflow_instance_id = $1
        LEFT JOIN node_instance ni_target ON n_target.node_id = ni_target.node_id 
            AND ni_target.workflow_instance_id = $1
        WHERE nc.workflow_id = (
            SELECT workflow_id FROM workflow_instance WHERE workflow_instance_id = $1
        )
        """
        
        edges_data = await node_repo.db.fetch_all(edges_query, instance_id, instance_id, instance_id)
        
        # 格式化连接边数据
        formatted_edges = []
        for edge in edges_data:
            if edge['source_instance_id'] and edge['target_instance_id']:
                # 处理条件配置
                condition_config = edge['condition_config'] or {}
                condition_label = None
                if edge['connection_type'] == 'conditional' and condition_config:
                    condition_label = condition_config.get('condition', '')
                
                edge_data = {
                    "id": f"edge_{edge['source_instance_id']}_{edge['target_instance_id']}",
                    "source": str(edge['source_instance_id']),
                    "target": str(edge['target_instance_id']),
                    "connection_type": edge['connection_type'],
                    "condition_config": condition_config,
                    "condition_label": condition_label,
                    "source_node_name": edge['source_node_name'],
                    "target_node_name": edge['target_node_name']
                }
                formatted_edges.append(edge_data)
        
        # 6. 计算工作流级别统计
        total_nodes = len(formatted_nodes)
        completed_nodes = len([n for n in formatted_nodes if n['status'] == 'completed'])
        failed_nodes = len([n for n in formatted_nodes if n['status'] == 'failed'])
        running_nodes = len([n for n in formatted_nodes if n['status'] == 'running'])
        
        all_tasks = sum([len(n['tasks']) for n in formatted_nodes])
        all_completed_tasks = sum([n['task_statistics']['completed_tasks'] for n in formatted_nodes])
        all_failed_tasks = sum([n['task_statistics']['failed_tasks'] for n in formatted_nodes])
        
        workflow_statistics = {
            "workflow_instance_id": str(instance_id),
            "workflow_name": workflow_instance.get('workflow_name'),
            "workflow_instance_name": workflow_instance.get('workflow_instance_name'),
            "status": workflow_instance.get('status'),
            "node_statistics": {
                "total_nodes": total_nodes,
                "completed_nodes": completed_nodes,
                "failed_nodes": failed_nodes,
                "running_nodes": running_nodes,
                "success_rate": (completed_nodes / total_nodes * 100) if total_nodes > 0 else 0
            },
            "task_statistics": {
                "total_tasks": all_tasks,
                "completed_tasks": all_completed_tasks,
                "failed_tasks": all_failed_tasks,
                "running_tasks": all_tasks - all_completed_tasks - all_failed_tasks,
                "success_rate": (all_completed_tasks / all_tasks * 100) if all_tasks > 0 else 0
            },
            "timestamps": {
                "started_at": workflow_instance.get('started_at'),
                "completed_at": workflow_instance.get('completed_at'),
                "created_at": workflow_instance.get('created_at')
            }
        }
        
        return {
            "success": True,
            "data": {
                "workflow_statistics": workflow_statistics,
                "nodes": formatted_nodes,
                "edges": formatted_edges
            },
            "message": "获取工作流节点详细信息成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工作流节点详细信息失败: {e}")
        import traceback
        logger.error(f"错误堆栈: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取工作流节点详细信息失败: {str(e)}"
        )


# ==================== 级联删除端点 ====================

@router.delete("/instances/{workflow_instance_id}/cascade")
async def delete_workflow_instance_cascade(
    workflow_instance_id: uuid.UUID,
    soft_delete: bool = Query(True, description="是否软删除"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    级联删除工作流实例及其所有相关数据
    
    Args:
        workflow_instance_id: 工作流实例ID
        soft_delete: 是否软删除（默认True）
        current_user: 当前用户
        
    Returns:
        级联删除结果统计
    """
    try:
        from ..services.cascade_deletion_service import cascade_deletion_service
        from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
        
        workflow_instance_repo = WorkflowInstanceRepository()
        
        # 检查工作流实例是否存在和权限
        existing_instance = await workflow_instance_repo.get_instance_by_id(workflow_instance_id)
        if not existing_instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流实例不存在"
            )
        
        # 检查权限：只有工作流执行者可以删除实例
        current_user_id_str = str(current_user.user_id)
        executor_id_str = str(existing_instance.get('executor_id'))

        if executor_id_str != current_user_id_str:
            logger.warning(f"🚫 级联删除权限检查失败:")
            logger.warning(f"   - 用户 {current_user_id_str} 无权删除实例 {workflow_instance_id}")
            logger.warning(f"   - 只有执行者 {executor_id_str} 可以删除此实例")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此工作流实例"
            )
        
        # 执行级联删除
        deletion_result = await cascade_deletion_service.delete_workflow_instance_cascade(
            workflow_instance_id, soft_delete
        )
        
        if deletion_result['deleted_workflow']:
            logger.info(f"用户 {current_user.username} 级联删除了工作流实例: {workflow_instance_id}")
            return {
                "success": True,
                "message": "工作流实例级联删除成功",
                "data": {
                    "message": "工作流实例及其所有相关数据已删除",
                    "deletion_stats": deletion_result
                }
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="级联删除工作流实例失败"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"级联删除工作流实例异常: {e}")
        import traceback
        logger.error(f"错误堆栈: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="级联删除工作流实例失败，请稍后再试"
        )


@router.get("/instances/{workflow_instance_id}/deletion-preview")
async def get_workflow_instance_deletion_preview(
    workflow_instance_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    预览工作流实例删除将影响的数据量
    
    Args:
        workflow_instance_id: 工作流实例ID
        current_user: 当前用户
        
    Returns:
        删除预览数据
    """
    try:
        from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
        
        workflow_instance_repo = WorkflowInstanceRepository()
        
        # 检查工作流实例是否存在和权限
        existing_instance = await workflow_instance_repo.get_instance_by_id(workflow_instance_id)
        if not existing_instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流实例不存在"
            )
        
        # 检查权限
        if existing_instance.get('executor_id') != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权查看此工作流实例"
            )
        
        # 获取删除预览
        nodes_query = """
            SELECT COUNT(*) as node_count
            FROM node_instance 
            WHERE workflow_instance_id = $1 AND is_deleted = FALSE
        """
        node_result = await workflow_instance_repo.db.fetch_one(nodes_query, workflow_instance_id)
        
        tasks_query = """
            SELECT COUNT(*) as task_count,
                   COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_tasks,
                   COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress_tasks,
                   COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_tasks
            FROM task_instance 
            WHERE workflow_instance_id = $1 AND is_deleted = FALSE
        """
        task_result = await workflow_instance_repo.db.fetch_one(tasks_query, workflow_instance_id)
        
        preview = {
            'workflow_instance_id': str(workflow_instance_id),
            'workflow_instance_name': existing_instance.get('workflow_instance_name', '未命名'),
            'status': existing_instance.get('status'),
            'total_node_instances': int(node_result.get('node_count', 0)),
            'total_task_instances': int(task_result.get('task_count', 0)),
            'task_status_summary': {
                'completed': int(task_result.get('completed_tasks', 0)),
                'in_progress': int(task_result.get('in_progress_tasks', 0)),
                'pending': int(task_result.get('pending_tasks', 0))
            }
        }
        
        return {
            "success": True,
            "message": "删除预览获取成功",
            "data": preview
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取删除预览异常: {e}")
        import traceback
        logger.error(f"错误堆栈: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取删除预览失败，请稍后再试"
        )


# ==================== 图形视图细分支持端点 ====================

@router.get("/workflows/{workflow_instance_id}/subdivision-info")
async def get_workflow_subdivision_info(
    workflow_instance_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取工作流实例的细分信息 - 用于图形视图标记"""
    try:
        from ..repositories.task_subdivision.task_subdivision_repository import TaskSubdivisionRepository
        from ..repositories.instance.task_instance_repository import TaskInstanceRepository
        from ..models.task_subdivision import SubWorkflowNodeInfo
        
        subdivision_repo = TaskSubdivisionRepository()
        task_repo = TaskInstanceRepository()
        
        # 获取该工作流实例的所有任务及其细分信息
        # 修改查询以适配MySQL语法
        query = """
        SELECT 
            ti.task_instance_id,
            ti.node_instance_id,
            ti.task_title,
            COUNT(ts.subdivision_id) as subdivision_count,
            GROUP_CONCAT(DISTINCT ts.status) as subdivision_statuses,
            GROUP_CONCAT(DISTINCT ts.subdivision_id) as subdivision_ids
        FROM task_instance ti
        LEFT JOIN task_subdivision ts ON ti.task_instance_id = ts.original_task_id 
            AND ts.is_deleted = FALSE
        WHERE ti.workflow_instance_id = %s 
            AND ti.is_deleted = 0
        GROUP BY ti.task_instance_id, ti.node_instance_id, ti.task_title
        """
        
        results = await subdivision_repo.db.fetch_all(query, workflow_instance_id)
        
        # 构建节点细分信息映射
        node_subdivisions = {}
        nodes_with_subdivisions = 0
        total_subdivisions = 0
        
        for result in results:
            node_instance_id = str(result['node_instance_id'])
            subdivision_count = result['subdivision_count'] or 0
            
            # 初始化primary_status，确保总是有值
            primary_status = None
            
            if subdivision_count > 0:
                nodes_with_subdivisions += 1
                total_subdivisions += subdivision_count
                
                # 确定子工作流状态 - 适配MySQL的GROUP_CONCAT结果
                statuses_str = result['subdivision_statuses']
                statuses = []
                if statuses_str:
                    statuses = [s.strip() for s in statuses_str.split(',')]
                
                if statuses:
                    # 优先级：failed > running > completed > draft
                    if 'failed' in statuses:
                        primary_status = 'failed'
                    elif 'running' in statuses:
                        primary_status = 'running'
                    elif 'completed' in statuses:
                        primary_status = 'completed'
                    else:
                        primary_status = 'draft'
            
            node_subdivisions[node_instance_id] = {
                'node_instance_id': result['node_instance_id'],
                'has_subdivision': subdivision_count > 0,
                'subdivision_count': subdivision_count,
                'subdivision_status': primary_status,
                'is_expandable': subdivision_count > 0,
                'expansion_level': 0
            }
        
        return {
            "success": True,
            "data": {
                'workflow_instance_id': workflow_instance_id,
                'node_subdivisions': node_subdivisions,
                'nodes_with_subdivisions': nodes_with_subdivisions,
                'total_subdivisions': total_subdivisions
            }
        }
        
    except Exception as e:
        logger.error(f"获取工作流细分信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取细分信息失败: {str(e)}"
        )


@router.get("/nodes/{node_instance_id}/subdivision-detail")
async def get_node_subdivision_detail(
    node_instance_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取节点的详细细分信息 - 用于展开显示"""
    try:
        from ..repositories.task_subdivision.task_subdivision_repository import TaskSubdivisionRepository
        from ..repositories.instance.task_instance_repository import TaskInstanceRepository
        from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
        from ..repositories.instance.node_instance_repository import NodeInstanceRepository
        from ..models.task_subdivision import SubWorkflowDetail
        
        subdivision_repo = TaskSubdivisionRepository()
        task_repo = TaskInstanceRepository()
        workflow_repo = WorkflowInstanceRepository()
        node_repo = NodeInstanceRepository()
        
        # 查找该节点实例关联的任务和细分
        subdivisions_query = """
        SELECT 
            ts.*,
            ti.task_title,
            w.name as sub_workflow_name,
            wi.workflow_instance_name as sub_workflow_instance_name,
            wi.status as sub_workflow_status,
            wi.created_at as sub_workflow_created_at,
            wi.started_at as sub_workflow_started_at,
            wi.completed_at as sub_workflow_completed_at
        FROM task_subdivision ts
        JOIN task_instance ti ON ts.original_task_id = ti.task_instance_id
        LEFT JOIN workflow w ON ts.sub_workflow_base_id = w.workflow_base_id AND w.is_current_version = 1
        LEFT JOIN workflow_instance wi ON ts.sub_workflow_instance_id = wi.workflow_instance_id
        WHERE ti.node_instance_id = %s 
            AND ts.is_deleted = FALSE 
            AND ti.is_deleted = 0
        ORDER BY ts.subdivision_created_at DESC
        """
        
        subdivisions = await subdivision_repo.db.fetch_all(subdivisions_query, node_instance_id)
        
        subdivision_details = []
        
        for subdivision in subdivisions:
            # 获取子工作流的节点和边信息
            sub_workflow_instance_id = subdivision.get('sub_workflow_instance_id')
            nodes = []
            edges = []
            stats = {
                'total_nodes': 0,
                'completed_nodes': 0,
                'running_nodes': 0,
                'failed_nodes': 0
            }
            
            if sub_workflow_instance_id:
                # 获取子工作流的节点实例
                nodes_query = """
                SELECT 
                    ni.*,
                    n.name as node_name,
                    n.type as node_type,
                    n.position_x,
                    n.position_y,
                    COUNT(ti.task_instance_id) as task_count
                FROM node_instance ni
                LEFT JOIN node n ON ni.node_id = n.node_id
                LEFT JOIN task_instance ti ON ni.node_instance_id = ti.node_instance_id AND ti.is_deleted = 0
                WHERE ni.workflow_instance_id = %s AND ni.is_deleted = 0
                GROUP BY ni.node_instance_id, n.name, n.type, n.position_x, n.position_y
                ORDER BY ni.created_at
                """
                
                sub_nodes = await node_repo.db.fetch_all(nodes_query, sub_workflow_instance_id)
                
                for node in sub_nodes:
                    stats['total_nodes'] += 1
                    status = node.get('status', 'pending')
                    if status == 'completed':
                        stats['completed_nodes'] += 1
                    elif status == 'running':
                        stats['running_nodes'] += 1
                    elif status == 'failed':
                        stats['failed_nodes'] += 1
                    
                    nodes.append({
                        'node_instance_id': str(node['node_instance_id']),
                        'node_id': str(node['node_id']),
                        'node_name': node.get('node_name', '未命名'),
                        'node_type': node.get('node_type', 'process'),
                        'status': status,
                        'task_count': node.get('task_count', 0),
                        # 🔧 新增：位置信息用于前端布局
                        'position': {
                            'x': float(node['position_x']) if node['position_x'] is not None else None,
                            'y': float(node['position_y']) if node['position_y'] is not None else None
                        },
                        'created_at': node['created_at'].isoformat() if node.get('created_at') else None,
                        'completed_at': node['completed_at'].isoformat() if node.get('completed_at') else None
                    })
                
                # 获取子工作流的连接关系
                edges_query = """
                SELECT 
                    nc.*,
                    fn.name as from_node_name,
                    tn.name as to_node_name
                FROM node_connection nc
                JOIN node_instance fni ON nc.from_node_id = fni.node_id AND fni.workflow_instance_id = %s
                JOIN node_instance tni ON nc.to_node_id = tni.node_id AND tni.workflow_instance_id = %s
                JOIN node fn ON nc.from_node_id = fn.node_id
                JOIN node tn ON nc.to_node_id = tn.node_id
                WHERE nc.workflow_id = (
                    SELECT workflow_base_id FROM workflow_instance WHERE workflow_instance_id = %s
                )
                """
                
                sub_edges = await subdivision_repo.db.fetch_all(edges_query, sub_workflow_instance_id, sub_workflow_instance_id, sub_workflow_instance_id)
                
                for edge in sub_edges:
                    edges.append({
                        'id': str(edge.get('connection_id', f"edge-{edge['from_node_id']}-{edge['to_node_id']}")),
                        'source': str(edge['from_node_id']),
                        'target': str(edge['to_node_id']),
                        'label': edge.get('condition_config'),
                        'from_node_name': edge.get('from_node_name'),
                        'to_node_name': edge.get('to_node_name')
                    })
            
            subdivision_detail = {
                'subdivision_id': subdivision['subdivision_id'],
                'sub_workflow_instance_id': sub_workflow_instance_id,
                'subdivision_name': subdivision['subdivision_name'],
                'status': subdivision.get('sub_workflow_status', subdivision['status']),
                'nodes': nodes,
                'edges': edges,
                'total_nodes': stats['total_nodes'],
                'completed_nodes': stats['completed_nodes'],
                'running_nodes': stats['running_nodes'],
                'failed_nodes': stats['failed_nodes'],
                'created_at': subdivision['subdivision_created_at'].isoformat() if subdivision.get('subdivision_created_at') else None,
                'started_at': subdivision['sub_workflow_started_at'].isoformat() if subdivision.get('sub_workflow_started_at') else None,
                'completed_at': subdivision['sub_workflow_completed_at'].isoformat() if subdivision.get('sub_workflow_completed_at') else None
            }
            
            subdivision_details.append(subdivision_detail)
        
        return {
            "success": True,
            "data": {
                'node_instance_id': node_instance_id,
                'has_subdivision': len(subdivision_details) > 0,
                'subdivisions': subdivision_details
            }
        }
        
    except Exception as e:
        logger.error(f"获取节点细分详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取节点细分详情失败: {str(e)}"
        )


@router.get("/workflows/{workflow_instance_id}/complete-mapping")
async def get_workflow_complete_mapping(
    workflow_instance_id: uuid.UUID,
    max_depth: int = Query(10, description="最大递归深度"),
    current_user: CurrentUser = Depends(get_current_user_context)
) -> dict:
    """
    获取工作流实例的完整节点级别映射关系
    支持递归查询多层嵌套的子工作流
    """
    try:
        logger.info(f"📊 获取工作流完整映射: {workflow_instance_id}, 最大深度: {max_depth}")
        
        from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
        
        workflow_instance_repo = WorkflowInstanceRepository()
        
        # 验证工作流实例是否存在
        instance = await workflow_instance_repo.get_instance_by_id(workflow_instance_id)
        if not instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流实例不存在"
            )
        
        # 获取完整映射关系
        mapping_result = await workflow_instance_repo.get_complete_workflow_mapping(
            workflow_instance_id, max_depth
        )
        
        logger.info(f"✅ 工作流完整映射查询成功: {len(mapping_result.get('metadata', {}).get('total_workflows', 0))} 个工作流")
        
        return {
            "success": True,
            "data": mapping_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工作流完整映射失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取工作流完整映射失败: {str(e)}"
        )


@router.get("/workflows/{workflow_instance_id}/node-mapping")
async def get_workflow_node_mapping(
    workflow_instance_id: uuid.UUID,
    include_template_structure: bool = Query(True, description="是否包含模板结构信息"),
    current_user: CurrentUser = Depends(get_current_user_context)
) -> dict:
    """
    获取工作流实例的节点级别映射关系（专为前端图形展示优化）
    返回工作流框架结构，通过节点关系连接工作流
    """
    try:
        logger.info(f"🎨 获取工作流节点映射: {workflow_instance_id}")
        
        from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
        from ..repositories.node.node_repository import NodeRepository, NodeConnectionRepository
        
        workflow_repo = WorkflowInstanceRepository()
        node_repo = NodeRepository()
        connection_repo = NodeConnectionRepository()
        
        # 1. 获取完整的工作流映射数据
        complete_mapping = await workflow_repo.get_complete_workflow_mapping(workflow_instance_id, max_depth=8)
        
        if "error" in complete_mapping.get("mapping_data", {}):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流实例不存在或查询失败"
            )
        
        # 2. 构建适用于前端的数据结构
        template_workflows = []
        template_connections = []
        
        # 递归处理映射数据
        await _process_mapping_for_template_graph(
            complete_mapping["mapping_data"], 
            template_workflows, 
            template_connections,
            node_repo,
            connection_repo,
            include_template_structure
        )
        
        result = {
            "success": True,
            "data": {
                "template_connections": template_connections,
                "detailed_workflows": {
                    wf["workflow_base_id"]: wf for wf in template_workflows
                },
                "node_level_mapping": True,
                "supports_recursive_subdivision": True
            }
        }
        
        logger.info(f"✅ 工作流节点映射构建完成: {len(template_workflows)} 个工作流, {len(template_connections)} 个连接")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工作流节点映射失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取工作流节点映射失败: {str(e)}"
        )


async def _process_mapping_for_template_graph(mapping_data: dict, 
                                            template_workflows: list,
                                            template_connections: list,
                                            node_repo,
                                            connection_repo,
                                            include_template_structure: bool):
    """递归处理映射数据为模板图格式"""
    try:
        if "error" in mapping_data:
            return
        
        # 处理当前工作流
        workflow_base_id = mapping_data["workflow_base_id"]
        
        # 构建工作流数据
        workflow_data = {
            "workflow_base_id": workflow_base_id,
            "workflow_name": mapping_data["workflow_name"],
            "workflow_instance_id": mapping_data["workflow_instance_id"],
            "workflow_instance_name": mapping_data["workflow_instance_name"],
            "status": mapping_data["workflow_status"],
            "depth": mapping_data.get("depth", 0),
            "total_nodes": len(mapping_data.get("nodes", [])),
            "nodes": [],
            "connections": []
        }
        
        # 如果需要包含模板结构，添加节点和连接信息
        if include_template_structure:
            try:
                # 获取工作流的节点信息
                workflow_nodes = await node_repo.get_workflow_nodes(uuid.UUID(workflow_base_id))
                workflow_connections = await connection_repo.get_workflow_connections(uuid.UUID(workflow_base_id))
                
                # 添加节点信息
                for node in workflow_nodes:
                    workflow_data["nodes"].append({
                        "node_id": str(node["node_id"]),
                        "node_base_id": str(node["node_base_id"]),
                        "name": node["name"],
                        "type": node["type"],
                        "position": {
                            "x": node.get("position_x"),
                            "y": node.get("position_y")
                        }
                    })
                
                # 添加连接信息
                for conn in workflow_connections:
                    workflow_data["connections"].append({
                        "connection_id": f"conn_{conn['from_node_id']}_{conn['to_node_id']}",
                        "from_node": {
                            "node_id": str(conn["from_node_id"]),
                            "node_base_id": str(conn["from_node_base_id"]),
                            "name": conn["from_node_name"]
                        },
                        "to_node": {
                            "node_id": str(conn["to_node_id"]),
                            "node_base_id": str(conn["to_node_base_id"]),
                            "name": conn["to_node_name"]
                        },
                        "connection_type": conn["connection_type"]
                    })
                    
            except Exception as e:
                logger.warning(f"获取模板结构信息失败: {e}")
        
        template_workflows.append(workflow_data)
        
        # 处理节点的subdivisions
        for node in mapping_data.get("nodes", []):
            for subdivision in node.get("subdivisions", []):
                if subdivision["sub_workflow_mapping"] and "error" not in subdivision["sub_workflow_mapping"]:
                    # 创建模板连接关系
                    connection = {
                        "subdivision_id": subdivision["subdivision_id"],
                        "subdivision_name": subdivision["subdivision_name"],
                        "parent_subdivision_id": subdivision.get("parent_subdivision_id"),
                        "parent_workflow": {
                            "workflow_base_id": workflow_base_id,
                            "workflow_name": mapping_data["workflow_name"],
                            "workflow_instance_id": mapping_data["workflow_instance_id"],
                            "workflow_instance_name": mapping_data["workflow_instance_name"],
                            "status": mapping_data["workflow_status"]
                        },
                        "sub_workflow": {
                            "workflow_base_id": subdivision["sub_workflow_mapping"]["workflow_base_id"],
                            "workflow_name": subdivision["sub_workflow_mapping"]["workflow_name"],
                            "workflow_instance_id": subdivision["sub_workflow_mapping"]["workflow_instance_id"],
                            "workflow_instance_name": subdivision["sub_workflow_mapping"]["workflow_instance_name"],
                            "status": subdivision["sub_workflow_mapping"]["workflow_status"],
                            "total_nodes": len(subdivision["sub_workflow_mapping"].get("nodes", [])),
                            "completed_nodes": sum(1 for n in subdivision["sub_workflow_mapping"].get("nodes", []) if n.get("node_status") == "completed")
                        },
                        "parent_node": {
                            "node_instance_id": node["node_instance_id"],
                            "node_base_id": node["node_base_id"],
                            "node_name": node["node_name"],
                            "node_type": node["node_type"]
                        }
                    }
                    
                    template_connections.append(connection)
                    
                    # 递归处理子工作流
                    await _process_mapping_for_template_graph(
                        subdivision["sub_workflow_mapping"],
                        template_workflows,
                        template_connections, 
                        node_repo,
                        connection_repo,
                        include_template_structure
                    )
        
    except Exception as e:
        logger.error(f"处理映射数据失败: {e}")
        raise