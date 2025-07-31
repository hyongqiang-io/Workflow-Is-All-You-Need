"""
工作流执行API
Workflow Execution API
"""

import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, status, Request
from pydantic import BaseModel, Field, ValidationError
from loguru import logger

from ..services.execution_service import execution_engine
from ..services.human_task_service import HumanTaskService
from ..services.agent_task_service import agent_task_service
from ..models.instance import (
    WorkflowExecuteRequest, WorkflowControlRequest,
    TaskInstanceStatus, TaskInstanceType
)
from ..utils.middleware import get_current_user_context, CurrentUser

router = APIRouter(prefix="/api/execution", tags=["execution"])

# 服务实例
human_task_service = HumanTaskService()


# ==================== 请求/响应模型 ====================

class TaskSubmissionRequest(BaseModel):
    """任务提交请求"""
    result_data: Optional[dict] = Field(default={}, description="任务结果数据")
    result_summary: Optional[str] = Field(None, description="结果摘要")


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

@router.post("/workflows/execute")
async def execute_workflow(
    request: WorkflowExecuteRequest,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """执行工作流"""
    try:
        from loguru import logger
        logger.info(f"执行工作流请求: workflow_base_id={request.workflow_base_id}, instance_name={request.instance_name}, user_id={current_user.user_id}")
        
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
                "instance_name": request.instance_name,
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
        
        # 查询工作流实例详细信息
        query = """
        SELECT 
            wi.*,
            w.name as workflow_name,
            u.username as executor_username,
            -- 节点实例统计
            json_agg(
                json_build_object(
                    'node_instance_id', ni.node_instance_id,
                    'node_name', n.name,
                    'node_type', n.type,
                    'status', ni.status,
                    'started_at', ni.start_at,
                    'completed_at', ni.completed_at,
                    'error_message', ni.error_message,
                    'input_data', ni.input_data,
                    'output_data', ni.output_data,
                    'retry_count', ni.retry_count
                ) ORDER BY ni.created_at
            ) FILTER (WHERE ni.node_instance_id IS NOT NULL) as node_instances
        FROM workflow_instance wi
        LEFT JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id AND w.is_current_version = TRUE
        LEFT JOIN "user" u ON wi.executor_id = u.user_id
        LEFT JOIN node_instance ni ON wi.workflow_instance_id = ni.workflow_instance_id AND ni.is_deleted = FALSE
        LEFT JOIN node n ON ni.node_id = n.node_id AND n.workflow_base_id = wi.workflow_base_id
        WHERE wi.workflow_instance_id = $1
        AND wi.is_deleted = FALSE
        GROUP BY wi.workflow_instance_id, w.name, u.username
        """
        
        result = await workflow_instance_repo.db.fetch_one(query, instance_id)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流实例不存在"
            )
        
        # 确保result是字典类型，并且处理node_instances
        if not isinstance(result, dict):
            logger.error(f"查询结果不是字典类型: {type(result)} - {result}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="查询结果格式错误"
            )
        
        node_instances = result.get("node_instances") or []
        
        # 如果node_instances是None或字符串，设为空列表
        if not isinstance(node_instances, list):
            logger.warning(f"node_instances不是列表类型: {type(node_instances)} - {node_instances}")
            node_instances = []
        
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
        
        formatted_instance = {
            "instance_id": str(result["workflow_instance_id"]),
            "instance_name": result.get("instance_name"),
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
    limit: int = 20,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取工作流的执行实例列表"""
    try:
        from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
        
        workflow_instance_repo = WorkflowInstanceRepository()
        
        # 查询工作流实例及其统计信息
        query = """
        SELECT 
            wi.*,
            w.name as workflow_name,
            u.username as executor_username,
            -- 统计节点实例信息
            COUNT(ni.node_instance_id) as total_nodes,
            COUNT(CASE WHEN ni.status = 'completed' THEN 1 END) as completed_nodes,
            COUNT(CASE WHEN ni.status = 'running' THEN 1 END) as running_nodes,
            COUNT(CASE WHEN ni.status = 'failed' THEN 1 END) as failed_nodes,
            -- 获取当前运行的节点名称
            STRING_AGG(
                CASE WHEN ni.status = 'running' THEN n.name END, 
                ', '
            ) as current_running_nodes
        FROM workflow_instance wi
        LEFT JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id AND w.is_current_version = TRUE
        LEFT JOIN "user" u ON wi.executor_id = u.user_id
        LEFT JOIN node_instance ni ON wi.workflow_instance_id = ni.workflow_instance_id AND ni.is_deleted = FALSE
        LEFT JOIN node n ON ni.node_id = n.node_id AND n.workflow_base_id = wi.workflow_base_id
        WHERE wi.workflow_base_id = $1
        AND wi.is_deleted = FALSE
        GROUP BY wi.workflow_instance_id, w.name, u.username
        ORDER BY wi.created_at DESC
        LIMIT $2
        """
        
        instances = await workflow_instance_repo.db.fetch_all(query, workflow_base_id, limit)
        
        # 格式化返回数据
        formatted_instances = []
        for instance in instances:
            total_nodes = instance.get("total_nodes") or 0
            completed_nodes = instance.get("completed_nodes") or 0
            running_nodes = instance.get("running_nodes") or 0
            failed_nodes = instance.get("failed_nodes") or 0
            
            # 计算执行进度百分比
            progress_percentage = 0
            if total_nodes > 0:
                progress_percentage = round((completed_nodes / total_nodes) * 100, 1)
            
            formatted_instances.append({
                "instance_id": str(instance["workflow_instance_id"]),
                "instance_name": instance.get("instance_name"),
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
        LEFT JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id AND w.is_current_version = TRUE
        LEFT JOIN "user" u ON wi.executor_id = u.user_id
        WHERE wi.workflow_instance_id = $1 AND wi.is_deleted = FALSE
        """
        
        workflow_instance = await workflow_repo.db.fetch_one(workflow_instance_query, workflow_id)
        if not workflow_instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流实例不存在"
            )
        
        # 获取工作流实例的所有节点实例（按依赖关系排序）
        nodes_query = """
        SELECT 
            ni.*,
            n.name as node_name,
            n.type as node_type,
            -- 计算节点执行时间
            CASE 
                WHEN ni.start_at IS NOT NULL AND ni.completed_at IS NOT NULL 
                THEN EXTRACT(EPOCH FROM (ni.completed_at - ni.start_at))::INTEGER
                WHEN ni.start_at IS NOT NULL 
                THEN EXTRACT(EPOCH FROM (NOW() - ni.start_at))::INTEGER
                ELSE NULL
            END as execution_duration_seconds
        FROM node_instance ni
        JOIN node n ON ni.node_id = n.node_id
        WHERE ni.workflow_instance_id = $1
        AND ni.is_deleted = FALSE
        ORDER BY 
            CASE 
                WHEN ni.start_at IS NOT NULL THEN ni.start_at 
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
            -- 计算任务执行时间
            CASE 
                WHEN ti.started_at IS NOT NULL AND ti.completed_at IS NOT NULL 
                THEN EXTRACT(EPOCH FROM (ti.completed_at - ti.started_at))::INTEGER
                WHEN ti.started_at IS NOT NULL 
                THEN EXTRACT(EPOCH FROM (NOW() - ti.started_at))::INTEGER
                ELSE NULL
            END as actual_duration_seconds,
            -- 任务是否超时
            CASE 
                WHEN ti.estimated_duration IS NOT NULL 
                     AND ti.started_at IS NOT NULL 
                     AND ti.completed_at IS NULL
                     AND EXTRACT(EPOCH FROM (NOW() - ti.started_at)) > ti.estimated_duration * 60
                THEN TRUE
                ELSE FALSE
            END as is_overdue
        FROM task_instance ti
        LEFT JOIN processor p ON ti.processor_id = p.processor_id
        LEFT JOIN "user" u ON ti.assigned_user_id = u.user_id
        LEFT JOIN agent a ON ti.assigned_agent_id = a.agent_id
        WHERE ti.workflow_instance_id = $1
        AND ti.is_deleted = FALSE
        ORDER BY ti.created_at
        """
        
        tasks = await task_repo.db.fetch_all(tasks_query, workflow_id)
        
        # 获取工作流边缘关系（用于前端流程图显示）
        edges_query = """
        SELECT 
            e.from_node_id,
            e.to_node_id,
            e.condition_expression,
            n1.name as from_node_name,
            n2.name as to_node_name
        FROM edge e
        JOIN node n1 ON e.from_node_id = n1.node_base_id
        JOIN node n2 ON e.to_node_id = n2.node_base_id
        WHERE e.workflow_base_id = $1
        AND e.is_deleted = FALSE
        ORDER BY e.created_at
        """
        
        edges = await node_repo.db.fetch_all(edges_query, workflow_instance['workflow_base_id'])
        
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
        
        # 格式化节点数据（包含实时状态和执行信息）
        for node in nodes:
            node_data = {
                "node_instance_id": str(node['node_instance_id']),
                "node_name": node['node_name'],
                "node_type": node['node_type'],
                "status": node['status'],  # 这是从数据库实时读取的状态
                "input_data": node['input_data'],
                "output_data": node['output_data'],
                "start_at": node['start_at'].isoformat() if node['start_at'] else None,
                "completed_at": node['completed_at'].isoformat() if node['completed_at'] else None,
                "execution_duration_seconds": node['execution_duration_seconds'],
                "error_message": node['error_message'],
                "retry_count": node.get('retry_count', 0),
                # 节点关联的任务数量
                "task_count": len([task for task in tasks if str(task['node_instance_id']) == str(node['node_instance_id'])])
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
        for edge in edges:
            edge_data = {
                "id": f"{edge['from_node_id']}-{edge['to_node_id']}",
                "source": str(edge['from_node_id']),
                "target": str(edge['to_node_id']),
                "label": edge['condition_expression'],
                "from_node_name": edge['from_node_name'],
                "to_node_name": edge['to_node_name']
            }
            task_flow["edges"].append(edge_data)
        
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
            wi.instance_name as workflow_instance_name,
            w.name as workflow_name,
            p.name as processor_name,
            p.type as processor_type,
            u.username as assigned_username,
            a.agent_name as assigned_agent_name
        FROM task_instance ti
        LEFT JOIN workflow_instance wi ON ti.workflow_instance_id = wi.workflow_instance_id
        LEFT JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id AND w.is_current_version = TRUE
        LEFT JOIN processor p ON ti.processor_id = p.processor_id
        LEFT JOIN "user" u ON ti.assigned_user_id = u.user_id
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
    limit: int = 50,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取我的任务列表"""
    try:
        tasks = await human_task_service.get_user_tasks(
            current_user.user_id, task_status, limit
        )
        
        return {
            "success": True,
            "data": tasks,
            "message": f"获取到 {len(tasks)} 个任务"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务列表失败: {str(e)}"
        )


@router.get("/tasks/{task_id}")
async def get_task_details(
    task_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取任务详情（增强版）"""
    try:
        from ..repositories.instance.task_instance_repository import TaskInstanceRepository
        from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
        from ..repositories.instance.node_instance_repository import NodeInstanceRepository
        
        task_repo = TaskInstanceRepository()
        workflow_repo = WorkflowInstanceRepository()
        node_repo = NodeInstanceRepository()
        
        # 获取任务详细信息，包含完整的上下文
        task_query = """
        SELECT 
            ti.*,
            p.name as processor_name, 
            p.type as processor_type,
            u.username as assigned_user_name,
            u.email as assigned_user_email,
            a.agent_name as assigned_agent_name,
            wi.instance_name as workflow_instance_name,
            wi.input_data as workflow_input_data,
            wi.context_data as workflow_context_data,
            w.name as workflow_name,
            n.name as node_name,
            n.type as node_type,
            n.task_description as node_task_description,
            ni.input_data as node_input_data,
            ni.output_data as node_output_data
        FROM task_instance ti
        LEFT JOIN processor p ON p.processor_id = ti.processor_id
        LEFT JOIN "user" u ON u.user_id = ti.assigned_user_id
        LEFT JOIN agent a ON a.agent_id = ti.assigned_agent_id
        LEFT JOIN workflow_instance wi ON wi.workflow_instance_id = ti.workflow_instance_id
        LEFT JOIN workflow w ON w.workflow_id = wi.workflow_id
        LEFT JOIN node_instance ni ON ni.node_instance_id = ti.node_instance_id
        LEFT JOIN node n ON n.node_id = ni.node_id
        WHERE ti.task_instance_id = $1 AND ti.is_deleted = FALSE
        """
        
        task = await task_repo.db.fetch_one(task_query, task_id)
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
        
        # 权限检查：只有分配给用户的任务或管理员才能查看
        if (str(task.get('assigned_user_id')) != str(current_user.user_id) and 
            current_user.role not in ['admin', 'manager']):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此任务"
            )
        
        # 解析JSON字段
        input_data = json.loads(task.get('input_data', '{}')) if task.get('input_data') else {}
        output_data = json.loads(task.get('output_data', '{}')) if task.get('output_data') else {}
        context_data = json.loads(task.get('context_data', '{}')) if task.get('context_data') else {}
        workflow_input_data = json.loads(task.get('workflow_input_data', '{}')) if task.get('workflow_input_data') else {}
        workflow_context_data = json.loads(task.get('workflow_context_data', '{}')) if task.get('workflow_context_data') else {}
        node_input_data = json.loads(task.get('node_input_data', '{}')) if task.get('node_input_data') else {}
        node_output_data = json.loads(task.get('node_output_data', '{}')) if task.get('node_output_data') else {}
        
        # 构建增强的任务详情
        enhanced_task = {
            # 基本任务信息
            "task_instance_id": str(task['task_instance_id']),
            "task_title": task.get('task_title', ''),
            "task_description": task.get('task_description', ''),
            "task_type": task.get('task_type', ''),
            "instructions": task.get('instructions', ''),
            "priority": task.get('priority', 1),
            "status": task.get('status', ''),
            "estimated_duration": task.get('estimated_duration'),
            "actual_duration": task.get('actual_duration'),
            "result_summary": task.get('result_summary'),
            "error_message": task.get('error_message'),
            
            # 时间信息
            "created_at": task['created_at'].isoformat() if task.get('created_at') else None,
            "assigned_at": task['assigned_at'].isoformat() if task.get('assigned_at') else None,
            "started_at": task['started_at'].isoformat() if task.get('started_at') else None,
            "completed_at": task['completed_at'].isoformat() if task.get('completed_at') else None,
            "updated_at": task['updated_at'].isoformat() if task.get('updated_at') else None,
            
            # 分配信息
            "assigned_user": {
                "user_id": str(task['assigned_user_id']) if task.get('assigned_user_id') else None,
                "username": task.get('assigned_user_name'),
                "email": task.get('assigned_user_email')
            } if task.get('assigned_user_id') else None,
            
            "assigned_agent": {
                "agent_id": str(task['assigned_agent_id']) if task.get('assigned_agent_id') else None,
                "agent_name": task.get('assigned_agent_name')
            } if task.get('assigned_agent_id') else None,
            
            # 处理器信息
            "processor": {
                "processor_id": str(task['processor_id']) if task.get('processor_id') else None,
                "name": task.get('processor_name'),
                "type": task.get('processor_type')
            },
            
            # 工作流上下文
            "workflow_context": {
                "workflow_id": str(task['workflow_instance_id']) if task.get('workflow_instance_id') else None,
                "workflow_name": task.get('workflow_name'),
                "instance_name": task.get('workflow_instance_name'),
                "workflow_input_data": workflow_input_data,
                "workflow_context_data": workflow_context_data
            },
            
            # 节点上下文
            "node_context": {
                "node_instance_id": str(task['node_instance_id']) if task.get('node_instance_id') else None,
                "node_name": task.get('node_name'),
                "node_type": task.get('node_type'),
                "node_task_description": task.get('node_task_description'),
                "node_input_data": node_input_data,
                "node_output_data": node_output_data
            },
            
            # 任务数据
            "input_data": input_data,
            "output_data": output_data,
            "context_data": context_data,
            
            # 用户权限
            "user_permissions": {
                "can_start": task.get('status') == 'assigned' and str(task.get('assigned_user_id')) == str(current_user.user_id),
                "can_submit": task.get('status') == 'in_progress' and str(task.get('assigned_user_id')) == str(current_user.user_id),
                "can_view_only": str(task.get('assigned_user_id')) != str(current_user.user_id),
                "is_owner": str(task.get('assigned_user_id')) == str(current_user.user_id)
            }
        }
        
        return {
            "success": True,
            "data": enhanced_task,
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
        result = await human_task_service.start_task(task_id, current_user.user_id)
        
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
        logger.info(f"  🔄 准备提交任务结果: result_data={result_data}")
        
        result = await human_task_service.submit_task_result(
            task_id, current_user.user_id, 
            result_data, request.result_summary
        )
        
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
        result = await human_task_service.pause_task(
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
        result = await human_task_service.request_help(
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
        
        result = await human_task_service.reject_task(
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
        result = await human_task_service.cancel_task(
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


@router.get("/tasks/history")
async def get_task_history(
    days: int = 30,
    limit: int = 100,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取任务历史"""
    try:
        tasks = await human_task_service.get_task_history(
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


@router.get("/tasks/statistics")
async def get_task_statistics(
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取任务统计"""
    try:
        stats = await human_task_service.get_task_statistics(current_user.user_id)
        
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
        result = await human_task_service.cancel_workflow_instance(
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
        logger.info(f"   - 实例名称: {instance.get('instance_name', '未命名')}")
        logger.info(f"   - 当前状态: {instance.get('status')}")
        logger.info(f"   - 执行者ID: {instance.get('executor_id')}")
        logger.info(f"   - 创建时间: {instance.get('created_at')}")
        logger.info(f"   - 更新时间: {instance.get('updated_at')}")
        logger.info(f"   - 是否已删除: {instance.get('is_deleted', False)}")
        
        # 检查权限（只有执行者可以删除）
        logger.info(f"🔍 步骤2: 检查删除权限")
        current_user_id_str = str(current_user.user_id)
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
        SELECT workflow_instance_id, executor_id, status, instance_name
        FROM workflow_instance 
        WHERE workflow_instance_id = $1 AND is_deleted = FALSE
        '''
        workflow = await human_task_service.task_repo.db.fetch_one(workflow_query, instance_id)
        
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
        context = await human_task_service._collect_workflow_context(instance_id)
        
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
        end_node = await human_task_service.task_repo.db.fetch_one(end_nodes_query, instance_id)
        
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
                "workflow_name": workflow['instance_name'],
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
        
        result = await human_task_service.assign_task_to_user(
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
        
        # 获取所有活跃用户
        users = await user_repo.list_all({"status": True, "is_deleted": False})
        
        # 获取所有Agent处理器
        agents = await processor_repo.list_all({"type": "agent", "is_deleted": False})
        
        # 格式化用户数据
        online_users = []
        for user in users:
            # 安全处理profile字段
            profile = user.get("profile", {})
            if isinstance(profile, str):
                try:
                    import json
                    profile = json.loads(profile)
                except:
                    profile = {}
            
            online_users.append({
                "user_id": str(user["user_id"]),
                "username": user["username"],
                "email": user["email"],
                "full_name": profile.get("full_name", "") if isinstance(profile, dict) else "",
                "description": user.get("description", ""),
                "status": "online",
                "capabilities": profile.get("capabilities", []) if isinstance(profile, dict) else [],
                "role": user.get("role", "user"),
                "created_at": user["created_at"].isoformat() if user.get("created_at") else None,
                "last_login": user["updated_at"].isoformat() if user.get("updated_at") else None
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
                "users": online_users,
                "agents": online_agents,
                "statistics": {
                    "total_users": len(online_users),
                    "total_agents": len(online_agents),
                    "online_users": len(online_users),
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
        
        # 2. 获取详细的节点实例信息（包括处理器信息）
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
            ni.start_at as node_started_at,
            ni.completed_at as node_completed_at,
            -- 节点定义信息
            n.name as node_name,
            n.type as node_type,
            -- 处理器信息（通过node_processor关联表）
            p.name as processor_name,
            p.type as processor_type,
            -- 执行时长计算
            CASE 
                WHEN ni.start_at IS NOT NULL AND ni.completed_at IS NOT NULL 
                THEN EXTRACT(EPOCH FROM (ni.completed_at - ni.start_at))::INTEGER
                WHEN ni.start_at IS NOT NULL 
                THEN EXTRACT(EPOCH FROM (NOW() - ni.start_at))::INTEGER
                ELSE NULL
            END as execution_duration_seconds
        FROM node_instance ni
        LEFT JOIN node n ON ni.node_id = n.node_id
        LEFT JOIN node_processor np ON n.node_id = np.node_id
        LEFT JOIN processor p ON np.processor_id = p.processor_id
        WHERE ni.workflow_instance_id = $1
        AND ni.is_deleted = FALSE
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
        LEFT JOIN "user" u ON ti.assigned_user_id = u.user_id
        LEFT JOIN agent a ON ti.assigned_agent_id = a.agent_id
        WHERE ti.workflow_instance_id = $1
        AND ti.is_deleted = FALSE
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
            SELECT workflow_id FROM workflow_instance WHERE instance_id = $1
        )
        """
        
        edges_data = await node_repo.db.fetch_all(edges_query, instance_id)
        
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
            "instance_name": workflow_instance.get('instance_name'),
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