"""
人工任务处理服务
Human Task Processing Service
"""

import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from loguru import logger

from ..repositories.instance.task_instance_repository import TaskInstanceRepository
from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
from ..repositories.user.user_repository import UserRepository
from ..models.instance import (
    TaskInstanceUpdate, TaskInstanceStatus, TaskInstanceType
)
from ..utils.helpers import now_utc


class HumanTaskService:
    """人工任务处理服务"""
    
    def __init__(self):
        self.task_repo = TaskInstanceRepository()
        self.workflow_instance_repo = WorkflowInstanceRepository()
        self.user_repo = UserRepository()
    
    async def get_user_tasks(self, user_id: uuid.UUID, 
                           status: Optional[TaskInstanceStatus] = None,
                           limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户的任务列表"""
        try:
            tasks = await self.task_repo.get_human_tasks_for_user(user_id, status, limit)
            
            # 添加任务优先级和截止时间等附加信息
            for task in tasks:
                task = await self._enrich_task_info(task)
            
            logger.info(f"获取用户 {user_id} 的任务列表，共 {len(tasks)} 个任务")
            return tasks
            
        except Exception as e:
            logger.error(f"获取用户任务列表失败: {e}")
            raise
    
    async def get_task_details(self, task_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取任务详细信息"""
        try:
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                return None
            
            # 验证任务是否分配给当前用户
            if task.get('assigned_user_id') != user_id:
                raise PermissionError("无权访问此任务")
            
            # 丰富任务信息
            task = await self._enrich_task_info(task)
            
            # 获取工作流上下文信息
            workflow_instance = await self.workflow_instance_repo.get_instance_by_id(
                task['workflow_instance_id']
            )
            
            # 获取工作流基本信息
            workflow_base = None
            if workflow_instance:
                from ..repositories.workflow.workflow_repository import WorkflowRepository
                workflow_repo = WorkflowRepository()
                workflow_base = await workflow_repo.get_workflow_by_base_id(
                    workflow_instance.get('workflow_base_id')
                )
            
            # 获取节点信息
            node_info = await self._get_node_info(task.get('node_instance_id'))
            
            # 获取处理器信息
            processor_info = await self._get_processor_info(task.get('processor_id'))
            
            # 构建完整的任务详情
            task_details = {
                # ===== 任务基本信息 =====
                'task_instance_id': task['task_instance_id'],
                'task_title': task.get('task_title', '未命名任务'),
                'task_description': task.get('task_description', ''),
                'instructions': task.get('instructions', ''),
                'status': task.get('status', 'unknown'),
                'priority': task.get('priority', 0),
                'priority_label': task.get('priority_label', '普通优先级'),
                'estimated_duration': task.get('estimated_duration', 0),
                'actual_duration': task.get('actual_duration'),
                'current_duration': task.get('current_duration'),
                'estimated_deadline': task.get('estimated_deadline'),
                
                # ===== 时间信息 =====
                'created_at': task.get('created_at'),
                'assigned_at': task.get('assigned_at'),
                'started_at': task.get('started_at'),
                'completed_at': task.get('completed_at'),
                
                # ===== 工作流上下文 =====
                'workflow_context': {
                    'workflow_name': workflow_base.get('name', '未知工作流') if workflow_base else '未知工作流',
                    'workflow_description': workflow_base.get('description', '') if workflow_base else '',
                    'workflow_version': workflow_base.get('version', 1) if workflow_base else 1,
                    'instance_name': workflow_instance.get('instance_name', '') if workflow_instance else '',
                    'instance_description': workflow_instance.get('description', '') if workflow_instance else '',
                    'workflow_input_data': workflow_instance.get('input_data', {}) if workflow_instance else {},
                    'workflow_context_data': workflow_instance.get('context_data', {}) if workflow_instance else {}
                },
                
                # ===== 节点上下文 =====
                'node_context': {
                    'node_name': node_info.get('node_name', '未知节点') if node_info else '未知节点',
                    'node_description': node_info.get('node_description', '') if node_info else '',
                    'node_type': node_info.get('node_type', '') if node_info else '',
                    'node_instance_id': str(task.get('node_instance_id', '')) if task.get('node_instance_id') else ''
                },
                
                # ===== 处理器信息 =====
                'processor_context': {
                    'processor_name': processor_info.get('name', '未知处理器') if processor_info else '未知处理器',
                    'processor_type': processor_info.get('type', 'human') if processor_info else 'human',
                    'processor_description': processor_info.get('description', '') if processor_info else ''
                },
                
                # ===== 上游节点数据 =====
                'upstream_context': await self._get_upstream_context(task),
                
                # ===== 任务数据 =====
                'input_data': task.get('input_data', {}),
                'output_data': task.get('output_data', {}),
                'result_summary': task.get('result_summary', ''),
                'error_message': task.get('error_message', ''),
                
                # ===== 其他信息 =====
                'assigned_user_id': task.get('assigned_user_id'),
                'retry_count': task.get('retry_count', 0)
            }
            
            logger.info(f"获取任务详情: {task_details['task_title']} (ID: {task_id})")
            return task_details
            
        except Exception as e:
            logger.error(f"获取任务详情失败: {e}")
            raise
    
    async def _get_node_info(self, node_instance_id: Optional[uuid.UUID]) -> Optional[Dict[str, Any]]:
        """获取节点信息"""
        if not node_instance_id:
            return None
            
        try:
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_instance_repo = NodeInstanceRepository()
            
            query = """
            SELECT ni.*, n.name as node_name, n.task_description as node_description, 
                   n.type as node_type, n.task_description
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.node_instance_id = %s
            """
            
            result = await node_instance_repo.execute_query(query, [node_instance_id])
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"获取节点信息失败: {e}")
            return None
    
    async def _get_processor_info(self, processor_id: Optional[uuid.UUID]) -> Optional[Dict[str, Any]]:
        """获取处理器信息"""
        if not processor_id:
            return None
            
        try:
            from ..repositories.processor.processor_repository import ProcessorRepository
            processor_repo = ProcessorRepository()
            
            processor = await processor_repo.get_processor_by_id(processor_id)
            return processor
            
        except Exception as e:
            logger.error(f"获取处理器信息失败: {e}")
            return None
    
    async def _get_upstream_context(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """获取任务的上游上下文信息"""
        try:
            input_data = task.get('input_data', {})
            
            # 获取上游节点的直接数据
            immediate_upstream = input_data.get('immediate_upstream', {})
            
            # 获取工作流全局数据
            workflow_global = input_data.get('workflow_global', {})
            
            # 获取节点级别信息
            node_info = input_data.get('node_info', {})
            
            # 格式化上游数据以便前端展示
            formatted_upstream = {}
            for node_id, node_data in immediate_upstream.items():
                if isinstance(node_data, dict):
                    formatted_upstream[node_id] = {
                        'node_name': node_data.get('node_name', f'节点_{node_id[:8]}'),
                        'output_data': node_data.get('output_data', {}),
                        'completed_at': node_data.get('completed_at', ''),
                        'summary': self._extract_data_summary(node_data.get('output_data', {}))
                    }
            
            return {
                'immediate_upstream_results': formatted_upstream,
                'upstream_node_count': len(immediate_upstream),
                'workflow_global_data': workflow_global,
                'workflow_execution_path': workflow_global.get('execution_path', []),
                'workflow_start_time': workflow_global.get('execution_start_time', ''),
                'has_upstream_data': len(immediate_upstream) > 0
            }
            
        except Exception as e:
            logger.error(f"获取上游上下文失败: {e}")
            return {
                'immediate_upstream_results': {},
                'upstream_node_count': 0,
                'workflow_global_data': {},
                'workflow_execution_path': [],
                'workflow_start_time': '',
                'has_upstream_data': False
            }
    
    def _extract_data_summary(self, output_data: Dict[str, Any]) -> str:
        """从输出数据中提取摘要信息"""
        try:
            if not output_data:
                return "无输出数据"
            
            # 尝试提取常见的摘要字段
            if 'summary' in output_data:
                return str(output_data['summary'])
            elif 'result_summary' in output_data:
                return str(output_data['result_summary'])
            elif 'message' in output_data:
                return str(output_data['message'])
            elif 'description' in output_data:
                return str(output_data['description'])
            else:
                # 生成基于数据内容的简要摘要
                data_keys = list(output_data.keys())
                if len(data_keys) <= 3:
                    return f"包含数据: {', '.join(data_keys)}"
                else:
                    return f"包含 {len(data_keys)} 项数据: {', '.join(data_keys[:3])}..."
                    
        except Exception as e:
            logger.error(f"提取数据摘要失败: {e}")
            return "数据摘要不可用"
    
    async def start_task(self, task_id: uuid.UUID, user_id: uuid.UUID) -> Dict[str, Any]:
        """开始执行任务"""
        try:
            # 验证任务状态和权限
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                raise ValueError("任务不存在")
            
            if task.get('assigned_user_id') != user_id:
                raise PermissionError("无权执行此任务")
            
            if task['status'] not in [TaskInstanceStatus.ASSIGNED.value, TaskInstanceStatus.PENDING.value]:
                raise ValueError(f"任务状态不允许开始执行，当前状态: {task['status']}")
            
            # 更新任务状态为进行中
            update_data = TaskInstanceUpdate(status=TaskInstanceStatus.IN_PROGRESS)
            updated_task = await self.task_repo.update_task(task_id, update_data)
            
            if updated_task:
                logger.info(f"用户 {user_id} 开始执行任务: {updated_task['task_title']}")
                return {
                    'task_id': task_id,
                    'status': TaskInstanceStatus.IN_PROGRESS.value,
                    'started_at': updated_task.get('started_at'),
                    'message': '任务已开始执行'
                }
            else:
                raise RuntimeError("更新任务状态失败")
                
        except Exception as e:
            logger.error(f"开始执行任务失败: {e}")
            raise
    
    async def submit_task_result(self, task_id: uuid.UUID, user_id: uuid.UUID,
                               result_data: Dict[str, Any], 
                               result_summary: Optional[str] = None) -> Dict[str, Any]:
        """提交任务结果"""
        try:
            logger.info(f"🚀 开始处理任务提交:")
            logger.info(f"  任务ID: {task_id}")
            logger.info(f"  用户ID: {user_id}")
            logger.info(f"  结果数据: {result_data}")
            logger.info(f"  结果摘要: {result_summary}")
            
            # 验证任务状态和权限
            logger.info(f"📋 查询任务信息...")
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                logger.error(f"❌ 任务不存在: {task_id}")
                raise ValueError("任务不存在")
            
            logger.info(f"✅ 任务查询成功:")
            logger.info(f"  任务标题: {task.get('task_title')}")
            logger.info(f"  当前状态: {task['status']}")
            logger.info(f"  分配用户: {task.get('assigned_user_id')}")
            logger.info(f"  开始时间: {task.get('started_at')}")
            
            if task.get('assigned_user_id') != user_id:
                logger.error(f"❌ 权限不足: 任务分配给 {task.get('assigned_user_id')}，但提交用户为 {user_id}")
                raise PermissionError("无权提交此任务")
            
            if task['status'] != TaskInstanceStatus.IN_PROGRESS.value:
                logger.error(f"❌ 任务状态不允许提交: 期望 {TaskInstanceStatus.IN_PROGRESS.value}，实际 {task['status']}")
                raise ValueError(f"任务状态不允许提交结果，当前状态: {task['status']}")
            
            # 计算实际执行时间
            actual_duration = None
            if task.get('started_at'):
                try:
                    logger.info(f"📅 处理开始时间: {task['started_at']} (类型: {type(task['started_at'])})")
                    started_at = task['started_at']
                    
                    # 处理不同类型的时间数据
                    if isinstance(started_at, str):
                        # 字符串类型，需要解析
                        start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                    elif hasattr(started_at, 'replace'):
                        # 已经是datetime对象
                        start_time = started_at
                    else:
                        logger.warning(f"⚠️ 无法处理的开始时间类型: {type(started_at)}")
                        start_time = None
                    
                    if start_time:
                        # 确保时间有时区信息
                        if start_time.tzinfo is None:
                            from ..utils.helpers import now_utc
                            current_time = now_utc()
                        else:
                            current_time = datetime.now().replace(tzinfo=start_time.tzinfo)
                        
                        actual_duration = int((current_time - start_time).total_seconds() / 60)
                        logger.info(f"⏱️ 计算执行时间成功: {actual_duration} 分钟")
                    
                except Exception as time_error:
                    logger.error(f"❌ 时间计算失败: {time_error}")
                    logger.error(f"原始时间数据: {repr(task['started_at'])}")
                    actual_duration = None
            
            # 更新任务状态为已完成
            logger.info(f"📝 准备更新任务状态为已完成...")
            update_data = TaskInstanceUpdate(
                status=TaskInstanceStatus.COMPLETED,
                output_data=result_data,
                result_summary=result_summary or "人工任务完成",
                actual_duration=actual_duration
            )
            logger.info(f"  更新数据: {update_data}")
            
            updated_task = await self.task_repo.update_task(task_id, update_data)
            
            if updated_task:
                logger.info(f"✅ 任务状态更新成功:")
                logger.info(f"  任务标题: {updated_task['task_title']}")
                logger.info(f"  完成时间: {updated_task.get('completed_at')}")
                logger.info(f"  执行时长: {actual_duration} 分钟")
                
                # 检查是否需要触发下游任务
                logger.info(f"🔄 检查下游任务...")
                await self._check_downstream_tasks(task_id)
                
                result = {
                    'task_id': task_id,
                    'status': TaskInstanceStatus.COMPLETED.value,
                    'completed_at': updated_task.get('completed_at'),
                    'actual_duration': actual_duration,
                    'message': '任务结果已提交'
                }
                logger.info(f"🎉 任务提交完成，返回结果: {result}")
                return result
            else:
                logger.error(f"❌ 任务状态更新失败: update_task返回None")
                raise RuntimeError("更新任务状态失败")
                
        except Exception as e:
            logger.error(f"💥 提交任务结果失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            raise
    
    async def pause_task(self, task_id: uuid.UUID, user_id: uuid.UUID,
                        pause_reason: Optional[str] = None) -> Dict[str, Any]:
        """暂停任务"""
        try:
            # 验证任务状态和权限
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                raise ValueError("任务不存在")
            
            if task.get('assigned_user_id') != user_id:
                raise PermissionError("无权暂停此任务")
            
            if task['status'] != TaskInstanceStatus.IN_PROGRESS.value:
                raise ValueError(f"任务状态不允许暂停，当前状态: {task['status']}")
            
            # 更新任务状态为已分配（从进行中回到分配状态）
            update_data = TaskInstanceUpdate(
                status=TaskInstanceStatus.ASSIGNED,
                error_message=f"任务暂停: {pause_reason}" if pause_reason else "任务暂停"
            )
            
            updated_task = await self.task_repo.update_task(task_id, update_data)
            
            if updated_task:
                logger.info(f"用户 {user_id} 暂停任务: {updated_task['task_title']}")
                return {
                    'task_id': task_id,
                    'status': TaskInstanceStatus.ASSIGNED.value,
                    'message': '任务已暂停'
                }
            else:
                raise RuntimeError("更新任务状态失败")
                
        except Exception as e:
            logger.error(f"暂停任务失败: {e}")
            raise
    
    async def request_help(self, task_id: uuid.UUID, user_id: uuid.UUID,
                          help_message: str) -> Dict[str, Any]:
        """请求帮助"""
        try:
            # 验证任务权限
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                raise ValueError("任务不存在")
            
            if task.get('assigned_user_id') != user_id:
                raise PermissionError("无权为此任务请求帮助")
            
            # 记录帮助请求（这里简化处理，实际可以创建帮助请求表）
            help_request = {
                'task_id': task_id,
                'user_id': user_id,
                'help_message': help_message,
                'requested_at': now_utc(),
                'status': 'pending'
            }
            
            logger.info(f"用户 {user_id} 为任务 {task_id} 请求帮助: {help_message}")
            
            return {
                'task_id': task_id,
                'help_request_id': str(uuid.uuid4()),  # 模拟帮助请求ID
                'message': '帮助请求已提交'
            }
            
        except Exception as e:
            logger.error(f"请求帮助失败: {e}")
            raise
    
    async def reject_task(self, task_id: uuid.UUID, user_id: uuid.UUID,
                         reject_reason: str) -> Dict[str, Any]:
        """拒绝任务"""
        try:
            # 验证任务状态和权限
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                raise ValueError("任务不存在")
            
            if task.get('assigned_user_id') != user_id:
                raise PermissionError("无权拒绝此任务")
            
            if task['status'] not in [TaskInstanceStatus.ASSIGNED.value, TaskInstanceStatus.PENDING.value]:
                raise ValueError(f"任务状态不允许拒绝，当前状态: {task['status']}")
            
            # 更新任务状态为已拒绝（标记为失败状态，并记录拒绝原因）
            update_data = TaskInstanceUpdate(
                status=TaskInstanceStatus.FAILED,
                error_message=f"任务被拒绝: {reject_reason}",
                result_summary="任务被用户拒绝"
            )
            
            updated_task = await self.task_repo.update_task(task_id, update_data)
            
            if updated_task:
                logger.info(f"用户 {user_id} 拒绝任务: {updated_task['task_title']} - {reject_reason}")
                
                # 通知工作流引擎任务被拒绝，可能需要重新分配或处理
                await self._notify_task_rejected(task_id, reject_reason)
                
                return {
                    'task_id': task_id,
                    'status': TaskInstanceStatus.FAILED.value,
                    'message': '任务已拒绝'
                }
            else:
                raise RuntimeError("更新任务状态失败")
                
        except Exception as e:
            logger.error(f"拒绝任务失败: {e}")
            raise
    
    async def cancel_task(self, task_id: uuid.UUID, user_id: uuid.UUID,
                         cancel_reason: Optional[str] = "用户取消") -> Dict[str, Any]:
        """取消任务"""
        try:
            # 验证任务状态和权限
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                raise ValueError("任务不存在")
            
            if task.get('assigned_user_id') != user_id:
                raise PermissionError("无权取消此任务")
            
            if task['status'] in [TaskInstanceStatus.COMPLETED.value, TaskInstanceStatus.FAILED.value, TaskInstanceStatus.CANCELLED.value]:
                raise ValueError(f"任务已完结，无法取消。当前状态: {task['status']}")
            
            # 更新任务状态为已取消
            update_data = TaskInstanceUpdate(
                status=TaskInstanceStatus.CANCELLED,
                error_message=f"任务被取消: {cancel_reason}",
                result_summary="任务被用户取消"
            )
            
            updated_task = await self.task_repo.update_task(task_id, update_data)
            
            if updated_task:
                logger.info(f"用户 {user_id} 取消任务: {updated_task['task_title']} - {cancel_reason}")
                
                # 通知工作流引擎任务被取消
                await self._notify_task_cancelled(task_id, cancel_reason)
                
                return {
                    'task_id': task_id,
                    'status': TaskInstanceStatus.CANCELLED.value,
                    'message': '任务已取消'
                }
            else:
                raise RuntimeError("更新任务状态失败")
                
        except Exception as e:
            logger.error(f"取消任务失败: {e}")
            raise
    
    async def get_task_history(self, user_id: uuid.UUID, 
                             days: int = 30, limit: int = 100) -> List[Dict[str, Any]]:
        """获取用户任务历史"""
        try:
            # 获取指定天数内的已完成任务
            tasks = await self.task_repo.get_human_tasks_for_user(
                user_id, TaskInstanceStatus.COMPLETED, limit
            )
            
            # 过滤指定天数内的任务
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_tasks = []
            
            for task in tasks:
                if task.get('completed_at'):
                    completed_at = datetime.fromisoformat(task['completed_at'].replace('Z', '+00:00'))
                    if completed_at.replace(tzinfo=None) >= cutoff_date:
                        recent_tasks.append(task)
            
            logger.info(f"获取用户 {user_id} 的任务历史，{days}天内共 {len(recent_tasks)} 个任务")
            return recent_tasks
            
        except Exception as e:
            logger.error(f"获取任务历史失败: {e}")
            raise
    
    async def get_task_statistics(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """获取用户任务统计"""
        try:
            # 获取用户所有任务
            all_tasks = await self.task_repo.get_human_tasks_for_user(user_id, None, 1000)
            
            # 统计各种状态的任务数量
            stats = {
                'total_tasks': len(all_tasks),
                'pending_tasks': 0,
                'assigned_tasks': 0,
                'in_progress_tasks': 0,
                'completed_tasks': 0,
                'failed_tasks': 0,
                'cancelled_tasks': 0,
                'average_completion_time': 0,
                'completion_rate': 0
            }
            
            total_duration = 0
            completed_count = 0
            
            for task in all_tasks:
                status = task['status']
                if status == TaskInstanceStatus.PENDING.value:
                    stats['pending_tasks'] += 1
                elif status == TaskInstanceStatus.ASSIGNED.value:
                    stats['assigned_tasks'] += 1
                elif status == TaskInstanceStatus.IN_PROGRESS.value:
                    stats['in_progress_tasks'] += 1
                elif status == TaskInstanceStatus.COMPLETED.value:
                    stats['completed_tasks'] += 1
                    completed_count += 1
                    if task.get('actual_duration'):
                        total_duration += task['actual_duration']
                elif status == TaskInstanceStatus.FAILED.value:
                    stats['failed_tasks'] += 1
                elif status == TaskInstanceStatus.CANCELLED.value:
                    stats['cancelled_tasks'] += 1
            
            # 计算平均完成时间和完成率
            if completed_count > 0:
                stats['average_completion_time'] = total_duration / completed_count
                stats['completion_rate'] = (completed_count / len(all_tasks)) * 100
            
            logger.info(f"生成用户 {user_id} 的任务统计")
            return stats
            
        except Exception as e:
            logger.error(f"获取任务统计失败: {e}")
            raise
    
    async def _enrich_task_info(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """丰富任务信息"""
        try:
            # 计算任务优先级标签
            priority = task.get('priority', 0)
            if priority >= 3:
                task['priority_label'] = '高优先级'
            elif priority >= 2:
                task['priority_label'] = '中优先级'
            else:
                task['priority_label'] = '低优先级'
            
            # 计算任务耗时
            if task.get('started_at') and task.get('completed_at'):
                try:
                    # 处理不同类型的时间数据
                    started_at = task['started_at']
                    completed_at = task['completed_at']
                    
                    if isinstance(started_at, str):
                        start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                    else:
                        start_time = started_at
                    
                    if isinstance(completed_at, str):
                        end_time = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                    else:
                        end_time = completed_at
                    
                    task['total_duration'] = int((end_time - start_time).total_seconds() / 60)
                except Exception as time_error:
                    logger.error(f"计算总耗时失败: {time_error}")
                    task['total_duration'] = 0
                    
            elif task.get('started_at') and task['status'] == TaskInstanceStatus.IN_PROGRESS.value:
                try:
                    started_at = task['started_at']
                    
                    if isinstance(started_at, str):
                        start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                    else:
                        start_time = started_at
                    
                    now_time = datetime.now().replace(tzinfo=start_time.tzinfo if start_time.tzinfo else None)
                    task['current_duration'] = int((now_time - start_time).total_seconds() / 60)
                except Exception as time_error:
                    logger.error(f"计算当前耗时失败: {time_error}")
                    task['current_duration'] = 0
            
            # 添加截止时间（基于估计时长）
            if task.get('created_at') and task.get('estimated_duration'):
                try:
                    created_at = task['created_at']
                    
                    if isinstance(created_at, str):
                        created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    else:
                        created_time = created_at
                    
                    estimated_minutes = task['estimated_duration']
                    task['estimated_deadline'] = (created_time + timedelta(minutes=estimated_minutes)).isoformat()
                except Exception as time_error:
                    logger.error(f"计算截止时间失败: {time_error}")
                    task['estimated_deadline'] = None
            
            return task
            
        except Exception as e:
            logger.error(f"丰富任务信息失败: {e}")
            return task
    
    async def _check_downstream_tasks(self, completed_task_id: uuid.UUID):
        """检查并触发下游任务"""
        try:
            logger.info(f"🔄 任务 {completed_task_id} 完成，开始检查下游更新...")
            
            # 1. 获取任务信息和对应的节点实例
            task = await self.task_repo.get_task_by_id(completed_task_id)
            if not task:
                logger.error(f"❌ 无法找到任务: {completed_task_id}")
                return
            
            logger.info(f"📋 任务信息:")
            logger.info(f"  任务标题: {task.get('task_title')}")
            logger.info(f"  节点实例ID: {task.get('node_instance_id')}")
            logger.info(f"  工作流实例ID: {task.get('workflow_instance_id')}")
            
            # 2. 更新对应的节点实例状态
            await self._update_node_instance_status(task)
            
            # 3. 检查并更新工作流实例状态
            await self._update_workflow_instance_status(task['workflow_instance_id'])
            
            # 4. 触发下游节点（如果有的话）
            await self._trigger_downstream_nodes(task)
            
            logger.info(f"✅ 下游任务检查完成")
            
        except Exception as e:
            logger.error(f"💥 检查下游任务失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    async def _update_node_instance_status(self, task: dict):
        """更新节点实例状态"""
        try:
            node_instance_id = task.get('node_instance_id')
            if not node_instance_id:
                logger.warning(f"⚠️ 任务没有关联的节点实例ID")
                return
            
            logger.info(f"📦 更新节点实例状态: {node_instance_id}")
            
            # 检查该节点实例下的所有任务是否都已完成
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_repo = NodeInstanceRepository()
            
            # 查询该节点下的所有任务
            node_tasks_query = '''
            SELECT task_instance_id, status, task_title
            FROM task_instance 
            WHERE node_instance_id = $1 AND is_deleted = FALSE
            '''
            node_tasks = await self.task_repo.db.fetch_all(node_tasks_query, node_instance_id)
            
            logger.info(f"  节点下的任务数量: {len(node_tasks)}")
            
            # 统计任务状态
            completed_tasks = [t for t in node_tasks if t['status'] == 'completed']
            failed_tasks = [t for t in node_tasks if t['status'] == 'failed']
            
            logger.info(f"  已完成任务: {len(completed_tasks)}")
            logger.info(f"  失败任务: {len(failed_tasks)}")
            
            # 确定节点状态
            if len(failed_tasks) > 0:
                node_status = 'failed'
                logger.info(f"  🔴 节点状态设为: failed（有失败任务）")
            elif len(completed_tasks) == len(node_tasks):
                node_status = 'completed' 
                logger.info(f"  🟢 节点状态设为: completed（所有任务完成）")
            else:
                node_status = 'running'
                logger.info(f"  🟡 节点状态设为: running（部分任务完成）")
            
            # 更新节点实例状态
            update_query = '''
            UPDATE node_instance 
            SET status = $1, updated_at = $2
            WHERE node_instance_id = $3
            '''
            from ..utils.helpers import now_utc
            await self.task_repo.db.execute(update_query, node_status, now_utc(), node_instance_id)
            logger.info(f"  ✅ 节点实例状态更新成功: {node_status}")
            
        except Exception as e:
            logger.error(f"❌ 更新节点实例状态失败: {e}")
    
    async def _update_workflow_instance_status(self, workflow_instance_id: uuid.UUID):
        """更新工作流实例状态"""
        try:
            logger.info(f"🏭 更新工作流实例状态: {workflow_instance_id}")
            
            # 查询该工作流下的所有节点实例
            nodes_query = '''
            SELECT ni.node_instance_id, ni.status, n.name as node_name
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.workflow_instance_id = $1 AND ni.is_deleted = FALSE
            '''
            nodes = await self.task_repo.db.fetch_all(nodes_query, workflow_instance_id)
            
            logger.info(f"  工作流下的节点数量: {len(nodes)}")
            
            # 统计节点状态
            completed_nodes = [n for n in nodes if n['status'] == 'completed']
            failed_nodes = [n for n in nodes if n['status'] == 'failed']
            running_nodes = [n for n in nodes if n['status'] == 'running']
            
            logger.info(f"  已完成节点: {len(completed_nodes)}")
            logger.info(f"  失败节点: {len(failed_nodes)}")
            logger.info(f"  运行中节点: {len(running_nodes)}")
            
            # 确定工作流状态
            if len(failed_nodes) > 0:
                workflow_status = 'failed'
                logger.info(f"  🔴 工作流状态设为: failed（有失败节点）")
            elif len(completed_nodes) == len(nodes):
                workflow_status = 'completed'
                logger.info(f"  🟢 工作流状态设为: completed（所有节点完成）")
            else:
                workflow_status = 'running'
                logger.info(f"  🟡 工作流状态设为: running（部分节点完成）")
            
            # 更新工作流实例状态
            update_query = '''
            UPDATE workflow_instance 
            SET status = $1, updated_at = $2
            WHERE workflow_instance_id = $3
            '''
            from ..utils.helpers import now_utc
            await self.task_repo.db.execute(update_query, workflow_status, now_utc(), workflow_instance_id)
            logger.info(f"  ✅ 工作流实例状态更新成功: {workflow_status}")
            
        except Exception as e:
            logger.error(f"❌ 更新工作流实例状态失败: {e}")
    
    async def _trigger_downstream_nodes(self, task: dict):
        """触发下游节点执行"""
        try:
            logger.info(f"🚀 检查是否需要触发下游节点...")
            
            workflow_instance_id = task.get('workflow_instance_id')
            current_node_instance_id = task.get('node_instance_id')
            
            logger.info(f"  当前节点实例: {current_node_instance_id}")
            logger.info(f"  工作流实例: {workflow_instance_id}")
            
            # 1. 获取当前节点实例的信息
            current_node_query = '''
            SELECT ni.*, n.type as node_type, n.name as node_name
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.node_instance_id = $1
            '''
            current_node = await self.task_repo.db.fetch_one(current_node_query, current_node_instance_id)
            
            if not current_node:
                logger.warning(f"⚠️ 无法找到当前节点实例: {current_node_instance_id}")
                return
            
            logger.info(f"  当前节点类型: {current_node['node_type']}")
            logger.info(f"  当前节点名称: {current_node['node_name']}")
            
            # 2. 查找下游节点（通过node_connection表）
            downstream_nodes_query = '''
            SELECT ni.*, n.type as node_type, n.name as node_name
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id  
            JOIN node_connection nc ON nc.to_node_id = n.node_id
            JOIN node source_node ON nc.from_node_id = source_node.node_id
            JOIN node_instance source_ni ON source_ni.node_id = source_node.node_id
            WHERE source_ni.node_instance_id = $1 
            AND ni.workflow_instance_id = $2
            AND ni.status = 'pending'
            '''
            downstream_nodes = await self.task_repo.db.fetch_all(
                downstream_nodes_query, 
                current_node_instance_id, 
                workflow_instance_id
            )
            
            logger.info(f"  找到下游节点数量: {len(downstream_nodes)}")
            
            # 3. 处理每个下游节点
            for downstream_node in downstream_nodes:
                await self._process_downstream_node(downstream_node, workflow_instance_id)
            
            # 4. 检查是否触发了结束节点
            await self._check_and_execute_end_nodes(workflow_instance_id)
            
        except Exception as e:
            logger.error(f"❌ 触发下游节点失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    async def _process_downstream_node(self, node: dict, workflow_instance_id: uuid.UUID):
        """处理单个下游节点"""
        try:
            node_instance_id = node['node_instance_id']
            node_type = node['node_type']
            node_name = node['node_name']
            
            logger.info(f"📦 处理下游节点: {node_name} (类型: {node_type})")
            
            # 检查该节点的所有前置条件是否满足
            prerequisites_satisfied = await self._check_node_prerequisites(node_instance_id)
            
            if not prerequisites_satisfied:
                logger.info(f"  ⏳ 前置条件未满足，节点暂不执行: {node_name}")
                return
            
            logger.info(f"  ✅ 前置条件已满足，准备执行节点: {node_name}")
            
            # 根据节点类型执行不同的逻辑
            if node_type == 'end':
                # 结束节点自动执行
                await self._execute_end_node(node_instance_id, workflow_instance_id)
            elif node_type in ['human', 'agent', 'mix']:
                # 任务节点：创建任务实例
                await self._create_node_tasks(node_instance_id)
            else:
                logger.info(f"  ⚠️ 未知节点类型: {node_type}")
            
        except Exception as e:
            logger.error(f"❌ 处理下游节点失败: {e}")
    
    async def _check_node_prerequisites(self, node_instance_id: uuid.UUID) -> bool:
        """检查节点的前置条件是否满足"""
        try:
            # 查询该节点的所有前置节点（通过node_connection表）
            prerequisite_query = '''
            SELECT ni.node_instance_id, ni.status, n.name as node_name
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            JOIN node_connection nc ON nc.from_node_id = n.node_id
            JOIN node target_node ON nc.to_node_id = target_node.node_id
            JOIN node_instance target_ni ON target_ni.node_id = target_node.node_id
            WHERE target_ni.node_instance_id = $1
            '''
            prerequisites = await self.task_repo.db.fetch_all(prerequisite_query, node_instance_id)
            
            if not prerequisites:
                # 没有前置节点，可以执行
                logger.info(f"    📋 无前置节点，可以执行")
                return True
            
            # 检查所有前置节点是否都已完成
            completed_prerequisites = [p for p in prerequisites if p['status'] == 'completed']
            
            logger.info(f"    📋 前置节点: {len(prerequisites)} 个，已完成: {len(completed_prerequisites)} 个")
            
            for prereq in prerequisites:
                status_emoji = "✅" if prereq['status'] == 'completed' else "❌"
                logger.info(f"      {status_emoji} {prereq['node_name']}: {prereq['status']}")
            
            return len(completed_prerequisites) == len(prerequisites)
            
        except Exception as e:
            logger.error(f"❌ 检查前置条件失败: {e}")
            return False
    
    async def _execute_end_node(self, node_instance_id: uuid.UUID, workflow_instance_id: uuid.UUID):
        """自动执行结束节点"""
        try:
            logger.info(f"🏁 开始执行结束节点: {node_instance_id}")
            
            # 1. 更新结束节点状态为运行中
            update_query = '''
            UPDATE node_instance 
            SET status = 'running', updated_at = $1
            WHERE node_instance_id = $2
            '''
            from ..utils.helpers import now_utc
            await self.task_repo.db.execute(update_query, now_utc(), node_instance_id)
            
            # 2. 收集工作流的完整上下文
            workflow_context = await self._collect_workflow_context(workflow_instance_id)
            
            # 3. 更新结束节点状态为已完成，并保存上下文
            complete_query = '''
            UPDATE node_instance 
            SET status = 'completed', 
                output_data = $1,
                updated_at = $2
            WHERE node_instance_id = $3
            '''
            await self.task_repo.db.execute(
                complete_query, 
                workflow_context, 
                now_utc(), 
                node_instance_id
            )
            
            logger.info(f"  ✅ 结束节点执行完成，上下文已保存")
            logger.info(f"  📊 上下文数据大小: {len(str(workflow_context))} 字符")
            
            # 4. 更新工作流实例状态为已完成
            await self._update_workflow_instance_status(workflow_instance_id)
            
        except Exception as e:
            logger.error(f"❌ 执行结束节点失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    async def _collect_workflow_context(self, workflow_instance_id: uuid.UUID) -> dict:
        """收集工作流的完整上下文内容"""
        try:
            logger.info(f"📊 开始收集工作流上下文: {workflow_instance_id}")
            
            # 1. 获取工作流实例基本信息
            workflow_query = '''
            SELECT wi.*, w.name as workflow_name, w.description as workflow_description,
                   u.username as executor_username
            FROM workflow_instance wi
            JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id AND w.is_current_version = TRUE
            LEFT JOIN "user" u ON wi.executor_id = u.user_id
            WHERE wi.workflow_instance_id = $1
            '''
            workflow_info = await self.task_repo.db.fetch_one(workflow_query, workflow_instance_id)
            
            # 2. 获取所有节点实例及其输出数据
            nodes_query = '''
            SELECT ni.*, n.name as node_name, n.type
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.workflow_instance_id = $1
            ORDER BY ni.created_at
            '''
            nodes = await self.task_repo.db.fetch_all(nodes_query, workflow_instance_id)
            
            # 3. 获取所有任务实例及其输出数据
            tasks_query = '''
            SELECT ti.*, ni.node_name
            FROM task_instance ti
            JOIN node_instance ni ON ti.node_instance_id = ni.node_instance_id
            WHERE ni.workflow_instance_id = $1
            ORDER BY ti.created_at
            '''
            tasks = await self.task_repo.db.fetch_all(tasks_query, workflow_instance_id)
            
            # 4. 构建完整的上下文对象
            context = {
                'workflow_instance': {
                    'instance_id': str(workflow_instance_id),
                    'instance_name': workflow_info['instance_name'],
                    'workflow_name': workflow_info['workflow_name'],
                    'workflow_description': workflow_info['workflow_description'],
                    'executor_username': workflow_info['executor_username'],
                    'status': workflow_info['status'],
                    'created_at': workflow_info['created_at'].isoformat() if workflow_info['created_at'] else None,
                    'updated_at': workflow_info['updated_at'].isoformat() if workflow_info['updated_at'] else None,
                    'input_data': workflow_info.get('input_data', {}),
                    'context_data': workflow_info.get('context_data', {})
                },
                'execution_summary': {
                    'total_nodes': len(nodes),
                    'completed_nodes': len([n for n in nodes if n['status'] == 'completed']),
                    'total_tasks': len(tasks),
                    'completed_tasks': len([t for t in tasks if t['status'] == 'completed']),
                    'execution_duration_minutes': self._calculate_execution_duration(workflow_info),
                    'completion_time': now_utc().isoformat()
                },
                'nodes_execution': [],
                'tasks_results': [],
                'workflow_output': {}
            }
            
            # 5. 添加节点执行信息
            for node in nodes:
                node_info = {
                    'node_instance_id': str(node['node_instance_id']),
                    'node_name': node['node_name'],
                    'node_type': node['node_type'],
                    'status': node['status'],
                    'input_data': node.get('input_data', {}),
                    'output_data': node.get('output_data', {}),
                    'created_at': node['created_at'].isoformat() if node['created_at'] else None,
                    'updated_at': node['updated_at'].isoformat() if node['updated_at'] else None
                }
                context['nodes_execution'].append(node_info)
            
            # 6. 添加任务结果信息
            for task in tasks:
                task_info = {
                    'task_instance_id': str(task['task_instance_id']),
                    'task_title': task['task_title'],
                    'task_description': task['task_description'],
                    'node_name': task['node_name'],
                    'status': task['status'],
                    'input_data': task.get('input_data', {}),
                    'output_data': task.get('output_data', {}),
                    'result_summary': task.get('result_summary'),
                    'created_at': task['created_at'].isoformat() if task['created_at'] else None,
                    'completed_at': task['completed_at'].isoformat() if task['completed_at'] else None,
                    'actual_duration': task.get('actual_duration')
                }
                context['tasks_results'].append(task_info)
            
            # 7. 生成工作流输出摘要
            context['workflow_output'] = self._generate_workflow_output_summary(context)
            
            logger.info(f"  ✅ 上下文收集完成:")
            logger.info(f"    节点数量: {context['execution_summary']['total_nodes']}")
            logger.info(f"    任务数量: {context['execution_summary']['total_tasks']}")
            logger.info(f"    执行时长: {context['execution_summary']['execution_duration_minutes']} 分钟")
            
            return context
            
        except Exception as e:
            logger.error(f"❌ 收集工作流上下文失败: {e}")
            return {}
    
    def _calculate_execution_duration(self, workflow_info: dict) -> int:
        """计算工作流执行时长（分钟）"""
        try:
            if workflow_info.get('created_at'):
                from ..utils.helpers import now_utc
                start_time = workflow_info['created_at']
                end_time = now_utc()
                duration = (end_time - start_time).total_seconds() / 60
                return int(duration)
            return 0
        except:
            return 0
    
    def _generate_workflow_output_summary(self, context: dict) -> dict:
        """生成工作流输出摘要"""
        try:
            summary = {
                'execution_status': 'completed',
                'total_execution_time': context['execution_summary']['execution_duration_minutes'],
                'nodes_summary': {},
                'key_results': [],
                'completion_message': f"工作流 '{context['workflow_instance']['workflow_name']}' 执行完成"
            }
            
            # 按节点类型汇总
            for node in context['nodes_execution']:
                node_type = node['node_type']
                if node_type not in summary['nodes_summary']:
                    summary['nodes_summary'][node_type] = {'count': 0, 'completed': 0}
                summary['nodes_summary'][node_type]['count'] += 1
                if node['status'] == 'completed':
                    summary['nodes_summary'][node_type]['completed'] += 1
            
            # 提取关键结果
            for task in context['tasks_results']:
                if task['status'] == 'completed' and task.get('output_data'):
                    summary['key_results'].append({
                        'task': task['task_title'],
                        'node': task['node_name'],
                        'result': task.get('result_summary', '任务完成'),
                        'output_data': task['output_data']
                    })
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ 生成输出摘要失败: {e}")
            return {'execution_status': 'completed', 'error': str(e)}
    
    async def _check_and_execute_end_nodes(self, workflow_instance_id: uuid.UUID):
        """检查并执行准备好的结束节点"""
        try:
            # 查找所有结束节点
            end_nodes_query = '''
            SELECT ni.*, n.name as node_name
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.workflow_instance_id = $1 
            AND n.type = 'end'
            AND ni.status = 'pending'
            '''
            end_nodes = await self.task_repo.db.fetch_all(end_nodes_query, workflow_instance_id)
            
            logger.info(f"🏁 检查结束节点: 找到 {len(end_nodes)} 个待执行的结束节点")
            
            for end_node in end_nodes:
                node_instance_id = end_node['node_instance_id']
                node_name = end_node['node_name']
                
                # 检查前置条件
                if await self._check_node_prerequisites(node_instance_id):
                    logger.info(f"  🚀 执行结束节点: {node_name}")
                    await self._execute_end_node(node_instance_id, workflow_instance_id)
                else:
                    logger.info(f"  ⏳ 结束节点前置条件未满足: {node_name}")
            
        except Exception as e:
            logger.error(f"❌ 检查结束节点失败: {e}")
    
    async def _create_node_tasks(self, node_instance_id: uuid.UUID):
        """为节点创建任务实例"""
        try:
            logger.info(f"📋 为节点创建任务实例: {node_instance_id}")
            
            # 获取节点实例信息
            node_query = '''
            SELECT ni.*, n.name as node_name, n.type
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.node_instance_id = $1
            '''
            node = await self.task_repo.db.fetch_one(node_query, node_instance_id)
            
            if not node:
                logger.error(f"❌ 找不到节点实例: {node_instance_id}")
                return
            
            logger.info(f"  节点名称: {node['node_name']}")
            logger.info(f"  节点类型: {node['node_type']}")
            
            # 查询该节点绑定的处理器
            processors_query = '''
            SELECT p.*, nb.binding_type, nb.priority
            FROM processor p
            JOIN node_binding nb ON p.processor_id = nb.processor_id
            WHERE nb.node_id = $1 AND nb.is_active = TRUE
            ORDER BY nb.priority
            '''
            processors = await self.task_repo.db.fetch_all(processors_query, node['node_id'])
            
            logger.info(f"  绑定的处理器数量: {len(processors)}")
            
            if not processors:
                logger.warning(f"⚠️ 节点没有绑定处理器，无法创建任务")
                return
            
            # 更新节点状态为运行中
            update_node_query = '''
            UPDATE node_instance 
            SET status = 'running', updated_at = $1
            WHERE node_instance_id = $2
            '''
            from ..utils.helpers import now_utc
            await self.task_repo.db.execute(update_node_query, now_utc(), node_instance_id)
            
            # 为每个处理器创建任务实例
            created_tasks = []
            for processor in processors:
                task_data = {
                    'node_instance_id': node_instance_id,
                    'workflow_instance_id': node['workflow_instance_id'],
                    'task_title': f"{node['node_name']} - {processor['name']}",
                    'task_description': f"执行节点: {node['node_name']}",
                    'task_type': processor['processor_type'],
                    'processor_id': processor['processor_id'],
                    'priority': processor.get('priority', 1)
                }
                
                # 根据处理器类型分配任务
                if processor['processor_type'] == 'HUMAN':
                    # 分配给指定用户
                    if processor.get('assigned_user_id'):
                        task_data['assigned_user_id'] = processor['assigned_user_id']
                elif processor['processor_type'] == 'AGENT':
                    # 分配给指定代理
                    if processor.get('assigned_agent_id'):
                        task_data['assigned_agent_id'] = processor['assigned_agent_id']
                
                # 创建任务实例
                from ..models.instance import TaskInstanceCreate
                task_create = TaskInstanceCreate(**task_data)
                task_id = await self.task_repo.create_task(task_create)
                
                created_tasks.append({
                    'task_id': task_id,
                    'task_title': task_data['task_title'],
                    'processor_type': processor['processor_type'],
                    'processor_name': processor['name']
                })
                
                logger.info(f"    ✅ 创建任务: {task_data['task_title']} ({processor['processor_type']})")
            
            logger.info(f"  🎯 节点任务创建完成，共创建 {len(created_tasks)} 个任务")
            
        except Exception as e:
            logger.error(f"❌ 创建节点任务失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    async def cancel_workflow_instance(self, instance_id: uuid.UUID, user_id: uuid.UUID, 
                                     cancel_reason: str = "用户取消") -> Dict[str, Any]:
        """取消工作流实例并级联取消所有相关任务"""
        try:
            logger.info(f"🚫 开始取消工作流实例:")
            logger.info(f"  实例ID: {instance_id}")
            logger.info(f"  操作用户: {user_id}")
            logger.info(f"  取消原因: {cancel_reason}")
            
            # 1. 验证工作流实例是否存在和权限
            workflow_query = '''
            SELECT workflow_instance_id, executor_id, status, instance_name
            FROM workflow_instance 
            WHERE workflow_instance_id = $1 AND is_deleted = FALSE
            '''
            workflow = await self.task_repo.db.fetch_one(workflow_query, instance_id)
            
            if not workflow:
                logger.error(f"❌ 工作流实例不存在: {instance_id}")
                raise ValueError("工作流实例不存在")
            
            logger.info(f"✅ 工作流实例查询成功:")
            logger.info(f"  实例名称: {workflow['instance_name']}")
            logger.info(f"  当前状态: {workflow['status']}")
            logger.info(f"  执行者: {workflow['executor_id']}")
            
            # 检查权限（只有执行者或管理员可以取消）
            if workflow['executor_id'] != user_id:
                # TODO: 这里可以添加管理员权限检查
                logger.error(f"❌ 无权取消工作流: 执行者 {workflow['executor_id']}，操作者 {user_id}")
                raise PermissionError("无权取消此工作流实例")
            
            # 检查状态是否允许取消
            if workflow['status'] in ['completed', 'failed', 'cancelled']:
                logger.error(f"❌ 工作流状态不允许取消: {workflow['status']}")
                raise ValueError(f"工作流状态不允许取消，当前状态: {workflow['status']}")
            
            # 2. 获取工作流下的所有任务实例
            tasks_query = '''
            SELECT ti.task_instance_id, ti.status, ti.task_title, ti.assigned_user_id,
                   ni.node_instance_id, ni.node_name
            FROM task_instance ti
            JOIN node_instance ni ON ti.node_instance_id = ni.node_instance_id
            WHERE ni.workflow_instance_id = $1 AND ti.is_deleted = FALSE
            '''
            tasks = await self.task_repo.db.fetch_all(tasks_query, instance_id)
            
            logger.info(f"📋 工作流下的任务数量: {len(tasks)}")
            
            # 3. 批量取消所有相关任务
            cancelled_tasks = []
            for task in tasks:
                task_id = task['task_instance_id']
                task_status = task['status']
                
                logger.info(f"  处理任务: {task['task_title']} (状态: {task_status})")
                
                # 只取消未完成的任务
                if task_status not in ['completed', 'failed', 'cancelled']:
                    try:
                        # 更新任务状态为已取消
                        update_task_query = '''
                        UPDATE task_instance 
                        SET status = 'cancelled', 
                            result_summary = $1,
                            updated_at = $2
                        WHERE task_instance_id = $3
                        '''
                        from ..utils.helpers import now_utc
                        await self.task_repo.db.execute(
                            update_task_query, 
                            f"工作流取消: {cancel_reason}", 
                            now_utc(), 
                            task_id
                        )
                        
                        cancelled_tasks.append({
                            'task_id': task_id,
                            'task_title': task['task_title'],
                            'previous_status': task_status,
                            'assigned_user_id': task['assigned_user_id']
                        })
                        
                        logger.info(f"    ✅ 任务已取消: {task['task_title']}")
                        
                    except Exception as task_error:
                        logger.error(f"    ❌ 取消任务失败: {task_error}")
                else:
                    logger.info(f"    ⏭️ 任务已完成，跳过: {task['task_title']}")
            
            # 4. 更新所有节点实例状态为已取消
            nodes_query = '''
            UPDATE node_instance 
            SET status = 'cancelled', updated_at = $1
            WHERE workflow_instance_id = $2 AND status NOT IN ('completed', 'failed')
            '''
            from ..utils.helpers import now_utc
            await self.task_repo.db.execute(nodes_query, now_utc(), instance_id)
            logger.info(f"  ✅ 节点实例状态已更新为cancelled")
            
            # 5. 更新工作流实例状态为已取消
            workflow_update_query = '''
            UPDATE workflow_instance 
            SET status = 'cancelled', 
                error_message = $1,
                updated_at = $2
            WHERE workflow_instance_id = $3
            '''
            await self.task_repo.db.execute(
                workflow_update_query, 
                cancel_reason, 
                now_utc(), 
                instance_id
            )
            logger.info(f"  ✅ 工作流实例状态已更新为cancelled")
            
            # 6. 返回取消结果
            result = {
                'workflow_instance_id': instance_id,
                'status': 'cancelled',
                'cancel_reason': cancel_reason,
                'cancelled_tasks_count': len(cancelled_tasks),
                'cancelled_tasks': cancelled_tasks,
                'cancelled_at': now_utc().isoformat(),
                'message': f'工作流实例已取消，共取消 {len(cancelled_tasks)} 个任务'
            }
            
            logger.info(f"🎯 工作流取消完成:")
            logger.info(f"  取消的任务数量: {len(cancelled_tasks)}")
            logger.info(f"  结果: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"💥 取消工作流实例失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            raise
    
    async def _notify_task_rejected(self, task_id: uuid.UUID, reject_reason: str):
        """通知工作流引擎任务被拒绝"""
        try:
            logger.info(f"任务 {task_id} 被拒绝: {reject_reason}")
            
            # 这里可以实现以下逻辑：
            # 1. 通知工作流引擎任务失败
            # 2. 可能需要重新分配任务给其他用户
            # 3. 或者标记整个工作流为失败状态
            # 4. 发送通知给管理员或其他相关人员
            
        except Exception as e:
            logger.error(f"通知任务拒绝失败: {e}")
    
    async def _notify_task_cancelled(self, task_id: uuid.UUID, cancel_reason: str):
        """通知工作流引擎任务被取消"""
        try:
            logger.info(f"任务 {task_id} 被取消: {cancel_reason}")
            
            # 这里可以实现以下逻辑：
            # 1. 通知工作流引擎任务被取消
            # 2. 可能需要暂停或取消整个工作流实例
            # 3. 清理相关资源
            # 4. 发送通知给相关人员
            
        except Exception as e:
            logger.error(f"通知任务取消失败: {e}")
    
    async def assign_task_to_user(self, task_id: uuid.UUID, user_id: uuid.UUID, 
                                assigner_id: uuid.UUID) -> Dict[str, Any]:
        """将任务分配给用户（管理员功能）"""
        try:
            # 验证分配者权限（这里简化处理）
            assigner = await self.user_repo.get_user_by_id(assigner_id)
            if not assigner or assigner.get('role') not in ['admin', 'manager']:
                raise PermissionError("无权分配任务")
            
            # 验证被分配用户存在
            assignee = await self.user_repo.get_user_by_id(user_id)
            if not assignee:
                raise ValueError("被分配用户不存在")
            
            # 分配任务
            result = await self.task_repo.assign_task_to_user(task_id, user_id)
            
            if result:
                logger.info(f"管理员 {assigner_id} 将任务 {task_id} 分配给用户 {user_id}")
                return {
                    'task_id': task_id,
                    'assigned_user_id': user_id,
                    'assigned_user_name': assignee.get('username'),
                    'message': '任务分配成功'
                }
            else:
                raise RuntimeError("任务分配失败")
                
        except Exception as e:
            logger.error(f"分配任务失败: {e}")
            raise
    
    async def _check_downstream_tasks(self, task_id: uuid.UUID):
        """检查下游任务 - 延迟任务创建机制的核心触发点"""
        try:
            logger.info(f"🔄 检查下游任务: {task_id}")
            
            # 1. 获取任务信息和相关节点实例
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                logger.error(f"❌ 任务不存在: {task_id}")
                return
            
            node_instance_id = task['node_instance_id']
            logger.info(f"  任务所属节点实例: {node_instance_id}")
            
            # 2. 获取节点实例信息
            node_query = '''
            SELECT ni.workflow_instance_id, ni.node_id, ni.status as node_status,
                   n.name as node_name, n.type as node_type
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.node_instance_id = $1
            '''
            node_result = await self.task_repo.db.fetch_one(node_query, node_instance_id)
            
            if not node_result:
                logger.error(f"❌ 节点实例不存在: {node_instance_id}")
                return
            
            workflow_instance_id = node_result['workflow_instance_id']
            node_name = node_result['node_name']
            logger.info(f"  节点: {node_name}, 工作流实例: {workflow_instance_id}")
            
            # 3. 检查该节点的所有任务是否都已完成
            node_tasks_query = '''
            SELECT task_instance_id, status, task_title
            FROM task_instance
            WHERE node_instance_id = $1 AND is_deleted = FALSE
            '''
            node_tasks = await self.task_repo.db.fetch_all(node_tasks_query, node_instance_id)
            
            logger.info(f"  节点 {node_name} 的任务总数: {len(node_tasks)}")
            
            completed_tasks = [t for t in node_tasks if t['status'] == 'completed']
            failed_tasks = [t for t in node_tasks if t['status'] == 'failed']
            
            logger.info(f"    已完成任务: {len(completed_tasks)}")
            logger.info(f"    失败任务: {len(failed_tasks)}")
            
            # 4. 如果所有任务都已完成，更新节点状态并触发下游检查
            if len(completed_tasks) == len(node_tasks) and len(node_tasks) > 0:
                logger.info(f"  ✅ 节点 {node_name} 的所有任务已完成，更新节点状态")
                
                # 更新节点实例状态为已完成
                await self._update_node_instance_status(node_instance_id, 'completed')
                
                # 触发下游节点的任务创建检查
                from ..services.execution_service import execution_engine
                await execution_engine._check_downstream_nodes_for_task_creation(workflow_instance_id)
                
                # 检查工作流完成状态
                await execution_engine._check_workflow_completion(workflow_instance_id)
                
                logger.info(f"  🎯 下游任务检查已触发")
                
            elif len(failed_tasks) > 0:
                logger.info(f"  ❌ 节点 {node_name} 有任务失败，更新节点状态为失败")
                await self._update_node_instance_status(node_instance_id, 'failed')
                
                # 检查工作流完成状态（可能标记为失败）
                from ..services.execution_service import execution_engine
                await execution_engine._check_workflow_completion(workflow_instance_id)
                
            else:
                logger.info(f"  ⏳ 节点 {node_name} 还有任务未完成，等待中")
            
        except Exception as e:
            logger.error(f"❌ 检查下游任务失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    async def _update_node_instance_status(self, node_instance_id: uuid.UUID, status: str):
        """更新节点实例状态"""
        try:
            logger.info(f"📝 更新节点实例状态: {node_instance_id} -> {status}")
            
            from ..utils.helpers import now_utc
            update_query = '''
            UPDATE node_instance 
            SET status = $1, updated_at = $2
            WHERE node_instance_id = $3
            '''
            await self.task_repo.db.execute(update_query, status, now_utc(), node_instance_id)
            logger.info(f"  ✅ 节点实例状态更新成功")
            
        except Exception as e:
            logger.error(f"❌ 更新节点实例状态失败: {e}")
            raise