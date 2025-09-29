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
from .workflow_context_manager import WorkflowContextManager
from .feishu_bot_service import feishu_bot_service


class HumanTaskService:
    """人工任务处理服务"""
    
    def __init__(self):
        self.task_repo = TaskInstanceRepository()
        self.workflow_instance_repo = WorkflowInstanceRepository()
        self.user_repo = UserRepository()
        # 集成统一的上下文管理器
        self.context_manager = WorkflowContextManager()
    
    async def get_user_tasks(self, user_id: uuid.UUID, 
                           status: Optional[TaskInstanceStatus] = None,
                           limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户的任务列表"""
        try:
            logger.info(f"🔍 [任务查询] 开始查询用户任务:")
            logger.info(f"   - 用户ID: {user_id}")
            logger.info(f"   - 状态过滤: {status.value if status else '全部'}")
            logger.info(f"   - 限制数量: {limit}")
            
            tasks = await self.task_repo.get_human_tasks_for_user(user_id, status, limit)
            
            logger.info(f"📊 [任务查询] 查询结果: 找到 {len(tasks)} 个任务")
            
            # 添加任务优先级和截止时间等附加信息
            for i, task in enumerate(tasks, 1):
                logger.info(f"   任务{i}: {task.get('task_title')} | 状态: {task.get('status')} | ID: {task.get('task_instance_id')}")
                task = await self._enrich_task_info(task)
            
            if len(tasks) == 0:
                logger.warning(f"⚠️ [任务查询] 用户 {user_id} 没有找到任何任务")
                
                # 额外诊断：查询该用户的所有任务（不限类型）
                logger.info(f"🔧 [诊断] 查询用户的所有类型任务...")
                try:
                    debug_query = """
                        SELECT task_instance_id, task_title, task_type, assigned_user_id, status
                        FROM task_instance 
                        WHERE assigned_user_id = $1 AND is_deleted = FALSE
                        ORDER BY created_at DESC LIMIT 10
                    """
                    debug_results = await self.task_repo.db.fetch_all(debug_query, user_id)
                    logger.info(f"🔧 [诊断] 用户所有任务数量: {len(debug_results)}")
                    for task in debug_results:
                        logger.info(f"   - {task['task_title']} | 类型: {task['task_type']} | 状态: {task['status']}")
                except Exception as debug_e:
                    logger.error(f"🔧 [诊断] 诊断查询失败: {debug_e}")
            
            logger.info(f"✅ [任务查询] 获取用户 {user_id} 的任务列表完成，共 {len(tasks)} 个任务")
            # 发送飞书机器人通知
            await self._send_feishu_notifications(user_id, tasks)
            return tasks
            
        except Exception as e:
            logger.error(f"❌ [任务查询] 获取用户任务列表失败: {e}")
            raise
    
    async def get_task_details(self, task_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取任务详细信息"""
        try:
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                return None
            
            # 验证任务是否分配给当前用户
            if task.get('assigned_user_id') != str(user_id):
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
            
            # 解析上游上下文数据（如果存在）
            parsed_context_data = self._parse_context_data(task.get('context_data', ''))
            upstream_context = await self._get_upstream_context(task)
            
            # 🆕 获取当前任务的附件
            current_task_attachments = await self._get_current_task_attachments(task)
            
            # 创建增强的任务描述（结合原始描述和上游上下文）
            enhanced_description = self._create_enhanced_description(
                task.get('task_description', ''), 
                parsed_context_data, 
                upstream_context
            )
            
            # 返回与所有processor统一的任务结构，但增加前端需要的结构化数据
            task_details = {
                # ===== 核心任务信息（与Agent processor完全一致）=====
                'task_instance_id': task['task_instance_id'],
                'task_title': task.get('task_title', ''),
                'task_description': task.get('task_description', ''),
                'enhanced_description': enhanced_description,  # 增强版描述，包含上游上下文
                'input_data': task.get('input_data', ''),      # 统一文本格式
                'context_data': parsed_context_data,           # 解析后的结构化数据
                
                # ===== 前端结构化数据 =====
                'parsed_context_data': parsed_context_data,    # 解析后的上下文对象
                'upstream_context': upstream_context,          # 格式化的上游上下文
                
                # ===== 任务状态和分配 =====
                'task_type': task.get('task_type', 'HUMAN'),
                'status': task.get('status', 'PENDING'),
                'assigned_user_id': task.get('assigned_user_id'),
                'processor_id': task.get('processor_id'),
                
                # ===== 时间信息 =====
                'created_at': task.get('created_at'),
                'assigned_at': task.get('assigned_at'),
                'started_at': task.get('started_at'),
                'completed_at': task.get('completed_at'),
                'estimated_duration': task.get('estimated_duration', 0),
                'actual_duration': task.get('actual_duration'),
                
                # ===== 执行结果 =====
                'output_data': task.get('output_data', ''),
                'result_summary': task.get('result_summary', ''),
                'error_message': task.get('error_message', ''),
                'retry_count': task.get('retry_count', 0),
                
                # ===== 附加信息（仅为人类用户提供更好的UI体验）=====
                'workflow_name': workflow_base.get('name', '') if workflow_base else '',
                'node_name': node_info.get('node_name', '') if node_info else '',
                'processor_name': processor_info.get('name', '') if processor_info else '',
                
                # 🆕 任务附件信息
                'current_task_attachments': current_task_attachments,  # 当前任务的附件
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
                   n.type as node_type
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.node_instance_id = $1
            """
            
            result = await node_instance_repo.db.fetch_one(query, node_instance_id)
            return dict(result) if result else None
            
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
        """获取任务的上游上下文信息（支持全局上下文和附件）"""
        try:
            # 从context_data中获取上游数据（需要先解析JSON字符串）
            raw_context_data = task.get('context_data', '')
            context_data = self._parse_context_data(raw_context_data)
            logger.info(f"获取上游上下文 - context_data keys: {list(context_data.keys()) if isinstance(context_data, dict) else 'not dict'}")
            
            # 🆕 支持新的全局上下文结构
            immediate_upstream_results = context_data.get('immediate_upstream_results', {})
            all_upstream_results = context_data.get('all_upstream_results', {})
            
            # 兼容旧格式：处理老的upstream_outputs字段
            upstream_outputs = context_data.get('upstream_outputs', [])
            formatted_immediate_upstream = {}
            
            if upstream_outputs:
                logger.info(f"🔄 [兼容模式] 处理旧格式upstream_outputs，共{len(upstream_outputs) if isinstance(upstream_outputs, (list, dict)) else 0}个节点")
                
                # 处理列表格式的upstream_outputs
                if isinstance(upstream_outputs, list):
                    for i, node_data in enumerate(upstream_outputs):
                        if isinstance(node_data, dict):
                            node_base_id = node_data.get('node_base_id', f'unknown_{i}')
                            output_data = node_data.get('output_data', {})
                            
                            if output_data:  # 只有当节点有输出数据时才包含
                                formatted_immediate_upstream[node_base_id] = {
                                    'node_name': node_data.get('node_name', f'节点_{node_base_id[:8]}'),
                                    'output_data': output_data,
                                    'completed_at': node_data.get('completed_at', ''),
                                    'status': node_data.get('status', ''),
                                    'node_description': node_data.get('node_description', ''),
                                    'source': node_data.get('source', 'unknown'),
                                    'summary': self._extract_data_summary(output_data)
                                }
                                logger.info(f"找到上游节点数据: {node_base_id} - {node_data.get('node_name', '未知节点')}")
                
                # 兼容字典格式
                elif isinstance(upstream_outputs, dict):
                    for node_base_id, node_data in upstream_outputs.items():
                        if isinstance(node_data, dict):
                            output_data = node_data.get('output_data', {})
                            if output_data:  # 只有当节点有输出数据时才包含
                                formatted_immediate_upstream[node_base_id] = {
                                    'node_name': node_data.get('node_name', f'节点_{node_base_id[:8]}'),
                                    'output_data': output_data,
                                    'completed_at': node_data.get('completed_at', ''),
                                    'status': node_data.get('status', ''),
                                    'summary': self._extract_data_summary(output_data)
                                }
            else:
                # 🆕 使用新格式的immediate_upstream_results
                formatted_immediate_upstream = immediate_upstream_results
                logger.info(f"🆕 [新格式] 使用immediate_upstream_results，共{len(immediate_upstream_results)}个直接上游节点")
            
            # 🆕 格式化全局上游结果
            formatted_all_upstream = all_upstream_results
            logger.info(f"🌐 [全局上下文] 全局上游节点数: {len(all_upstream_results)}")
            
            # 从input_data获取补充信息（处理文本格式）
            input_data_raw = task.get('input_data', '{}')
            try:
                # 尝试将字符串解析为字典
                if isinstance(input_data_raw, str):
                    import json
                    input_data = json.loads(input_data_raw) if input_data_raw.strip() else {}
                else:
                    input_data = input_data_raw if isinstance(input_data_raw, dict) else {}
            except (json.JSONDecodeError, AttributeError):
                logger.warning(f"无法解析input_data: {input_data_raw}")
                input_data = {}
                
            workflow_global = input_data.get('workflow_global', {})
            workflow_info = context_data.get('workflow', {})
            
            # 🆕 获取上下文中的附件信息
            context_attachments = await self._get_context_attachments(task)
            
            result = {
                'immediate_upstream_results': formatted_immediate_upstream,
                'all_upstream_results': formatted_all_upstream,  # 🆕 全局上游结果
                'upstream_node_count': len(formatted_immediate_upstream),
                'all_upstream_node_count': len(formatted_all_upstream),  # 🆕 全局上游计数
                'workflow_global_data': workflow_global,
                'workflow_execution_path': workflow_global.get('execution_path', []),
                'workflow_start_time': workflow_info.get('created_at', ''),
                'workflow_name': workflow_info.get('name', ''),
                'has_upstream_data': len(formatted_immediate_upstream) > 0,
                'has_global_upstream_data': len(formatted_all_upstream) > 0,  # 🆕 全局上游数据标识
                'context_attachments': context_attachments  # 🆕 上下文附件
            }
            
            logger.info(f"上游上下文结果: immediate={result['upstream_node_count']}, global={result['all_upstream_node_count']}, attachments={len(context_attachments)}")
            return result
            
        except Exception as e:
            logger.error(f"获取上游上下文失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return {
                'immediate_upstream_results': {},
                'all_upstream_results': {},
                'upstream_node_count': 0,
                'all_upstream_node_count': 0,
                'workflow_global_data': {},
                'workflow_execution_path': [],
                'workflow_start_time': '',
                'workflow_name': '',
                'has_upstream_data': False,
                'has_global_upstream_data': False,
                'context_attachments': []
            }
    
    async def _get_context_attachments(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取任务上下文中的附件信息"""
        try:
            context_attachments = []
            
            # 从任务的node_instance_id获取关联的附件
            node_instance_id = task.get('node_instance_id')
            workflow_instance_id = task.get('workflow_instance_id')
            
            if node_instance_id or workflow_instance_id:
                from ..services.file_association_service import FileAssociationService
                file_service = FileAssociationService()
                
                # 获取节点关联的附件
                if node_instance_id:
                    node_files = await file_service.get_node_instance_files(node_instance_id)
                    for file_info in node_files:
                        context_attachments.append({
                            'file_id': file_info['file_id'],
                            'filename': file_info['original_filename'],
                            'file_size': file_info['file_size'],
                            'content_type': file_info['content_type'],
                            'created_at': file_info['created_at'],
                            'association_type': 'node',
                            'association_id': str(node_instance_id)
                        })
                
                # 获取工作流关联的附件（暂时注释掉，因为FileAssociationService暂无此方法）
                # if workflow_instance_id:
                #     workflow_files = await file_service.get_files_by_association('workflow', str(workflow_instance_id))
                #     for file_info in workflow_files:
                #         context_attachments.append({
                #             'file_id': file_info['file_id'],
                #             'filename': file_info['original_filename'],
                #             'file_size': file_info['file_size'],
                #             'content_type': file_info['content_type'],
                #             'created_at': file_info['created_at'],
                #             'association_type': 'workflow',
                #             'association_id': str(workflow_instance_id)
                #         })
                
                logger.info(f"🔗 [附件收集] 为任务 {task.get('task_instance_id')} 收集了 {len(context_attachments)} 个上下文附件")
            
            return context_attachments
            
        except Exception as e:
            logger.error(f"获取上下文附件失败: {e}")
            return []
    
    async def _get_current_task_attachments(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取当前任务的附件信息"""
        try:
            current_task_attachments = []
            
            # 获取任务ID
            task_id = task.get('task_instance_id')
            node_instance_id = task.get('node_instance_id')
            
            if task_id or node_instance_id:
                from ..services.file_association_service import FileAssociationService
                file_service = FileAssociationService()
                
                # 获取直接与任务关联的附件
                if task_id:
                    task_files = await file_service.get_task_instance_files(task_id)
                    for file_info in task_files:
                        current_task_attachments.append({
                            'file_id': file_info['file_id'],
                            'filename': file_info['original_filename'],
                            'file_size': file_info['file_size'],
                            'content_type': file_info['content_type'],
                            'created_at': file_info['created_at'],
                            'association_type': 'task_direct',
                            'association_id': str(task_id)
                        })
                
                # 获取节点绑定的附件
                if node_instance_id:
                    node_files = await file_service.get_node_instance_files(node_instance_id)
                    for file_info in node_files:
                        current_task_attachments.append({
                            'file_id': file_info['file_id'],
                            'filename': file_info['original_filename'],
                            'file_size': file_info['file_size'],
                            'content_type': file_info['content_type'],
                            'created_at': file_info['created_at'],
                            'association_type': 'node_binding',
                            'association_id': str(node_instance_id)
                        })
                
                logger.info(f"🔗 [当前任务附件] 为任务 {task_id} 收集了 {len(current_task_attachments)} 个附件")
            
            return current_task_attachments
            
        except Exception as e:
            logger.error(f"获取当前任务附件失败: {e}")
            return []
    
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
            
            if task.get('assigned_user_id') != str(user_id):
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
            
            if task.get('assigned_user_id') != str(user_id):
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
            
            # 转换结果数据为字符串格式（与现有任务字段对齐）
            output_data_str = self._format_data_to_string(result_data)
            
            # 更新任务状态为已完成
            logger.info(f"📝 准备更新任务状态为已完成...")
            update_data = TaskInstanceUpdate(
                status=TaskInstanceStatus.COMPLETED,
                output_data=output_data_str,
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
                
                # 检查是否需要触发下游任务 - 使用统一的依赖管理
                logger.info(f"🔄 通过WorkflowContextManager检查下游任务...")
                await self._handle_task_completion_through_context_manager(task, updated_task, output_data_str)
                
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
            
            if task.get('assigned_user_id') != str(user_id):
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
            
            if task.get('assigned_user_id') != str(user_id):
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
            
            if task.get('assigned_user_id') != str(user_id):
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
            
            if task.get('assigned_user_id') != str(user_id):
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
    
    async def _handle_task_completion_through_context_manager(self, task: dict, updated_task: dict, output_data: str = None):
        """通过WorkflowContextManager统一处理任务完成"""
        try:
            logger.info(f"🔄 通过统一上下文管理器处理任务完成: {task['task_instance_id']}")
            
            # 获取节点基础信息用于mark_node_completed
            node_query = '''
            SELECT n.node_id 
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.node_instance_id = $1
            '''
            node_info = await self.task_repo.db.fetch_one(node_query, task['node_instance_id'])
            
            if not node_info:
                logger.error(f"❌ 无法找到节点信息: {task['node_instance_id']}")
                return
            
            # 构造输出数据
            output_data = {
                "message": "人工任务完成",
                "task_type": "human",
                "output_data": output_data if output_data else "{}",
                "completed_at": updated_task.get('completed_at').isoformat() if updated_task.get('completed_at') else None
            }
            
            # 使用WorkflowContextManager统一处理任务完成
            await self.context_manager.mark_node_completed(
                workflow_instance_id=task['workflow_instance_id'],
                node_id=node_info['node_id'],
                node_instance_id=task['node_instance_id'],
                output_data=output_data
            )
            
            logger.info(f"✅ 统一上下文管理器已完成任务处理")
            
        except Exception as e:
            logger.error(f"💥 统一上下文管理器处理失败: {e}")
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
            SELECT workflow_instance_id, executor_id, status, workflow_instance_name
            FROM workflow_instance 
            WHERE workflow_instance_id = $1 AND is_deleted = FALSE
            '''
            workflow = await self.task_repo.db.fetch_one(workflow_query, instance_id)
            
            if not workflow:
                logger.error(f"❌ 工作流实例不存在: {instance_id}")
                raise ValueError("工作流实例不存在")
            
            logger.info(f"✅ 工作流实例查询成功:")
            logger.info(f"  实例名称: {workflow['workflow_instance_name']}")
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
            
            # 获取任务信息验证类型
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                raise ValueError("任务不存在")
            
            # 验证任务类型：只有HUMAN和MIXED类型可以分配给用户
            if task.get('task_type') not in [TaskInstanceType.HUMAN.value, TaskInstanceType.MIXED.value]:
                raise ValueError(f"任务类型 {task.get('task_type')} 不能分配给用户")
            
            # 使用现有的分配方法（保持与现有架构一致）
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
    
    def _format_data_to_string(self, data) -> str:
        """将任意数据格式化为纯文本字符串"""
        if data is None:
            return "无结果数据"
        
        if isinstance(data, str):
            return data.strip()
        
        if isinstance(data, dict):
            # 尝试提取有意义的文本内容
            text_fields = ['result', 'content', 'message', 'answer', 'output', 'description', 'summary']
            for field in text_fields:
                if field in data and data[field]:
                    return str(data[field]).strip()
            
            # 如果没有标准字段，将字典转换为可读文本
            parts = []
            for key, value in data.items():
                if value is not None and str(value).strip():
                    parts.append(f"{key}: {value}")
            return "; ".join(parts) if parts else "任务完成"
        
        if isinstance(data, list):
            # 将列表转换为文本
            if all(isinstance(item, str) for item in data):
                return "; ".join(data)
            else:
                return "; ".join(str(item) for item in data)
        
        return str(data).strip()
    
    def _parse_context_data(self, context_data_str: str) -> dict:
        """解析context_data JSON字符串为字典对象"""
        if not context_data_str or not context_data_str.strip():
            return {}
        
        try:
            import json
            parsed_data = json.loads(context_data_str)
            logger.debug(f"成功解析context_data: {len(context_data_str)} 字符")
            return parsed_data if isinstance(parsed_data, dict) else {}
        except json.JSONDecodeError as e:
            logger.warning(f"解析context_data JSON失败: {e}")
            return {}
        except Exception as e:
            logger.warning(f"处理context_data时出错: {e}")
            return {}
    
    def _create_enhanced_description(self, original_description: str, 
                                   parsed_context: dict, 
                                   upstream_context: dict) -> str:
        """创建增强的任务描述，结合原始描述和上游上下文"""
        if not original_description:
            original_description = "请完成此任务"
        
        enhanced_parts = [original_description]
        
        # 添加工作流上下文信息
        if parsed_context.get('workflow'):
            workflow_info = parsed_context['workflow']
            if workflow_info.get('name'):
                enhanced_parts.append(f"\n📋 **工作流**: {workflow_info['name']}")
                if workflow_info.get('workflow_instance_name'):
                    enhanced_parts.append(f"   实例: {workflow_info['workflow_instance_name']}")
        
        # 添加上游节点输出信息
        upstream_outputs = parsed_context.get('upstream_outputs', [])
        if upstream_outputs:
            enhanced_parts.append(f"\n🔗 **上游节点输出** ({len(upstream_outputs)}个):")
            for i, output in enumerate(upstream_outputs[:3], 1):  # 最多显示3个
                node_name = output.get('node_name', f'节点{i}')
                if output.get('output_data'):
                    # 尝试解析输出数据
                    try:
                        import json
                        output_data = json.loads(output['output_data']) if isinstance(output['output_data'], str) else output['output_data']
                        if isinstance(output_data, dict):
                            # 获取最重要的字段显示
                            key_fields = ['result', 'answer', 'output', 'content', 'message']
                            display_value = None
                            for field in key_fields:
                                if field in output_data:
                                    display_value = str(output_data[field])[:100]
                                    break
                            if not display_value and output_data:
                                # 取第一个非空值
                                for key, value in output_data.items():
                                    if value and str(value).strip():
                                        display_value = f"{key}: {str(value)[:100]}"
                                        break
                            if display_value:
                                enhanced_parts.append(f"   {i}. **{node_name}**: {display_value}")
                            else:
                                enhanced_parts.append(f"   {i}. **{node_name}**: 已完成")
                        else:
                            enhanced_parts.append(f"   {i}. **{node_name}**: {str(output_data)[:100]}")
                    except:
                        enhanced_parts.append(f"   {i}. **{node_name}**: {str(output.get('output_data', ''))[:100]}")
                else:
                    enhanced_parts.append(f"   {i}. **{node_name}**: 已完成")
            
            if len(upstream_outputs) > 3:
                enhanced_parts.append(f"   ... 还有 {len(upstream_outputs) - 3} 个上游节点")
        
        # 添加当前节点信息
        if parsed_context.get('current_node'):
            current_node = parsed_context['current_node']
            if current_node.get('name'):
                enhanced_parts.append(f"\n🎯 **当前节点**: {current_node['name']}")
                if current_node.get('description'):
                    enhanced_parts.append(f"   说明: {current_node['description']}")
        
        return '\n'.join(enhanced_parts)
    
    def _parse_context_data(self, context_data: str) -> dict:
        """解析上下文数据字符串为结构化对象"""
        try:
            if not context_data:
                return {}
            
            # 如果已经是字典，直接返回
            if isinstance(context_data, dict):
                return context_data
            
            # 尝试解析JSON字符串
            if isinstance(context_data, str):
                import json
                try:
                    parsed = json.loads(context_data)
                    logger.info(f"成功解析context_data，包含键: {list(parsed.keys()) if isinstance(parsed, dict) else 'not dict'}")
                    return parsed if isinstance(parsed, dict) else {}
                except json.JSONDecodeError as e:
                    logger.warning(f"无法解析context_data为JSON: {e}")
                    return {}
            
            logger.warning(f"不支持的context_data类型: {type(context_data)}")
            return {}
            
        except Exception as e:
            logger.error(f"解析context_data失败: {e}")
            return {}
    


    async def _send_feishu_notifications(self, user_id: uuid.UUID, tasks: List[Dict[str, Any]]):
        """发送飞书机器人通知"""
        try:
            if not tasks:
                return
            
            # 获取用户信息
            user_info = await self.user_repo.get_user_by_id(user_id)
            if not user_info:
                logger.warning(f"用户 {user_id} 不存在，无法发送飞书通知")
                return
            
            # 为每个任务发送通知
            for task in tasks:
                task_info = {
                    "task_title": task.get("task_title", "未命名任务"),
                    "workflow_name": task.get("workflow_name", "未知工作流"),
                    "priority": task.get("priority", "普通"),
                    "deadline": task.get("deadline"),
                    "status": task.get("status")
                }
                
                # 发送飞书通知
                await feishu_bot_service.send_task_notification(str(user_id), task_info)
            
            logger.info(f"成功发送 {len(tasks)} 个任务的飞书通知给用户 {user_id}")
            
        except Exception as e:
            logger.error(f"发送飞书通知失败: {e}")
