"""
Agent任务处理服务
Agent Task Processing Service
"""

import uuid
import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger

from ..repositories.instance.task_instance_repository import TaskInstanceRepository
from ..repositories.agent.agent_repository import AgentRepository
from ..models.instance import (
    TaskInstanceUpdate, TaskInstanceStatus, TaskInstanceType
)
from ..utils.helpers import now_utc
from ..utils.openai_client import openai_client


class AgentTaskService:
    """Agent任务处理服务"""
    
    def __init__(self):
        self.task_repo = TaskInstanceRepository()
        self.agent_repo = AgentRepository()
        
        # Agent任务处理队列
        self.processing_queue = asyncio.Queue()
        self.is_running = False
        self.max_concurrent_tasks = 5
        
        # 任务完成回调列表
        self.completion_callbacks = []
    
    def register_completion_callback(self, callback):
        """注册任务完成回调"""
        self.completion_callbacks.append(callback)
        logger.info(f"注册任务完成回调: {callback}")
    
    async def _notify_task_completion(self, task_id: uuid.UUID, result: Dict[str, Any]):
        """通知任务完成"""
        try:
            for callback in self.completion_callbacks:
                try:
                    await callback.on_task_completed(task_id, result)
                except Exception as e:
                    logger.error(f"回调执行失败: {e}")
        except Exception as e:
            logger.error(f"通知任务完成失败: {e}")
    
    async def _notify_task_failure(self, task_id: uuid.UUID, error_message: str):
        """通知任务失败"""
        try:
            for callback in self.completion_callbacks:
                try:
                    await callback.on_task_failed(task_id, error_message)
                except Exception as e:
                    logger.error(f"回调执行失败: {e}")
        except Exception as e:
            logger.error(f"通知任务失败失败: {e}")
    
    async def start_service(self):
        """启动Agent任务处理服务"""
        if self.is_running:
            logger.warning("Agent任务处理服务已在运行中")
            return
        
        self.is_running = True
        logger.info("Agent任务处理服务启动")
        
        # 启动任务处理协程
        for i in range(self.max_concurrent_tasks):
            asyncio.create_task(self._process_agent_tasks())
        
        # 启动任务监控协程
        asyncio.create_task(self._monitor_pending_tasks())
    
    async def stop_service(self):
        """停止Agent任务处理服务"""
        self.is_running = False
        logger.info("Agent任务处理服务停止")
    
    async def get_pending_agent_tasks(self, agent_id: Optional[uuid.UUID] = None, 
                                    limit: int = 50) -> List[Dict[str, Any]]:
        """获取待处理的Agent任务"""
        try:
            tasks = await self.task_repo.get_agent_tasks_for_processing(agent_id, limit)
            logger.info(f"获取待处理Agent任务 {len(tasks)} 个")
            return tasks
            
        except Exception as e:
            logger.error(f"获取待处理Agent任务失败: {e}")
            raise
    
    async def submit_task_to_agent(self, task_id: uuid.UUID, 
                                 priority: int = 1) -> Dict[str, Any]:
        """将任务提交给Agent处理"""
        try:
            # 获取任务信息
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                raise ValueError("任务不存在")
            
            # 验证任务类型和状态
            if task['task_type'] not in [TaskInstanceType.AGENT.value, TaskInstanceType.MIXED.value]:
                raise ValueError("任务类型不支持Agent处理")
            
            if task['status'] != TaskInstanceStatus.PENDING.value:
                raise ValueError(f"任务状态不允许提交给Agent，当前状态: {task['status']}")
            
            # 将任务加入处理队列
            queue_item = {
                'task_id': task_id,
                'priority': priority,
                'submitted_at': now_utc()
            }
            
            await self.processing_queue.put(queue_item)
            
            logger.info(f"任务 {task_id} 已提交给Agent处理队列")
            return {
                'task_id': task_id,
                'status': 'queued',
                'message': '任务已加入Agent处理队列'
            }
            
        except Exception as e:
            logger.error(f"提交任务给Agent失败: {e}")
            raise
    
    async def process_agent_task(self, task_id: uuid.UUID) -> Dict[str, Any]:
        """处理单个Agent任务"""
        try:
            # 获取任务详情
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                raise ValueError("任务不存在")
            
            # 更新任务状态为进行中
            update_data = TaskInstanceUpdate(status=TaskInstanceStatus.IN_PROGRESS)
            await self.task_repo.update_task(task_id, update_data)
            
            start_time = datetime.now()
            logger.info(f"开始处理Agent任务: {task['task_title']}")
            
            # 获取Agent信息
            agent_id = task.get('assigned_agent_id')
            if not agent_id:
                raise ValueError("任务未分配Agent")
            
            agent = await self.agent_repo.get_agent_by_id(agent_id)
            if not agent:
                raise ValueError("Agent不存在")
            
            # 准备AI任务数据（与人类任务一致的内容，但整理成AI可接收的形式）
            input_data = task.get('input_data', {})
            
            # 构建系统 Prompt（使用任务的详细描述）
            system_prompt = self._build_system_prompt(task)
            
            # 预处理上游上下文（整理成补充信息）
            context_info = self._preprocess_upstream_context(input_data)
            
            # 构建用户消息（作为任务输入）
            user_message = self._build_user_message(task, context_info)
            
            # 整理成AI Client可接收的数据结构
            ai_client_data = {
                'task_id': str(task_id),
                'system_prompt': system_prompt,
                'user_message': user_message,
                'task_metadata': {
                    'task_title': task['task_title'],
                    'priority': task.get('priority', 1),
                    'estimated_duration': task.get('estimated_duration', 30)
                }
            }
            
            # 调用Agent处理
            result = await self._call_agent_api(agent, ai_client_data)
            
            # 计算执行时间
            end_time = datetime.now()
            actual_duration = int((end_time - start_time).total_seconds() / 60)
            
            # 更新任务状态为已完成
            complete_update = TaskInstanceUpdate(
                status=TaskInstanceStatus.COMPLETED,
                output_data=result,
                result_summary=result.get('summary', 'Agent任务处理完成'),
                actual_duration=actual_duration
            )
            
            updated_task = await self.task_repo.update_task(task_id, complete_update)
            
            logger.info(f"Agent任务处理完成: {task['task_title']} (耗时: {actual_duration}分钟)")
            
            # 通知任务完成回调
            completion_result = {
                'task_id': task_id,
                'status': TaskInstanceStatus.COMPLETED.value,
                'result': result,
                'duration': actual_duration,
                'message': 'Agent任务处理完成'
            }
            await self._notify_task_completion(task_id, completion_result)
            
            return completion_result
            
        except Exception as e:
            logger.error(f"处理Agent任务失败: {e}")
            
            # 更新任务状态为失败
            fail_update = TaskInstanceUpdate(
                status=TaskInstanceStatus.FAILED,
                error_message=str(e)
            )
            await self.task_repo.update_task(task_id, fail_update)
            
            # 通知任务失败回调
            await self._notify_task_failure(task_id, str(e))
            
            raise
    
    async def _call_agent_api(self, agent: Dict[str, Any], 
                            ai_client_data: Dict[str, Any]) -> Dict[str, Any]:
        """调用Agent API处理任务（仅使用OpenAI规范）"""
        try:
            # 统一使用OpenAI规范格式处理所有AI任务
            return await self._process_with_openai_format(agent, ai_client_data)
                
        except Exception as e:
            logger.error(f"调用Agent API失败: {e}")
            raise
    
    async def _process_with_openai_format(self, agent: Dict[str, Any], 
                                        ai_client_data: Dict[str, Any]) -> Dict[str, Any]:
        """使用OpenAI规范格式处理任务"""
        try:
            task_title = ai_client_data['task_metadata']['task_title']
            logger.info(f"使用OpenAI规范处理任务: {task_title}")
            
            # 构建符合OpenAI API规范的请求数据
            openai_request = {
                'messages': [
                    {
                        'role': 'system',
                        'content': ai_client_data['system_prompt']
                    },
                    {
                        'role': 'user', 
                        'content': ai_client_data['user_message']
                    }
                ],
                'model': agent.get('model', 'gpt-3.5-turbo'),
                'temperature': agent.get('temperature', 0.7),
                'max_tokens': agent.get('max_tokens', 2000)
            }
            
            # 调用OpenAI客户端处理任务
            openai_result = await openai_client.process_task(openai_request)
            
            if openai_result['success']:
                # 从OpenAI格式的回复中提取结构化结果
                ai_response = openai_result['result']
                response_content = ai_response.get('content', '')
                
                # 尝试解析JSON结果
                try:
                    parsed_result = json.loads(response_content)
                    
                    result = {
                        'analysis_result': parsed_result.get('analysis_result', response_content),
                        'key_findings': parsed_result.get('key_findings', []),
                        'recommendations': parsed_result.get('recommendations', []),
                        'confidence_score': parsed_result.get('confidence_score', 0.85),
                        'summary': parsed_result.get('summary', 'AI任务处理完成'),
                        'model_used': openai_result.get('model', agent.get('model')),
                        'token_usage': openai_result.get('usage', {})
                    }
                except json.JSONDecodeError:
                    # 如果不是JSON格式，则直接使用文本结果
                    result = {
                        'analysis_result': response_content,
                        'key_findings': [],
                        'recommendations': [],
                        'confidence_score': 0.80,
                        'summary': 'AI任务处理完成',
                        'model_used': openai_result.get('model', agent.get('model')),
                        'token_usage': openai_result.get('usage', {})
                    }
                
                logger.info(f"OpenAI规范处理完成，置信度: {result['confidence_score']}")
                return result
            else:
                # 处理失败，抛出异常
                error_msg = openai_result.get('error', 'AI处理失败')
                raise RuntimeError(f"AI处理失败: {error_msg}")
            
        except Exception as e:
            logger.error(f"OpenAI规范处理失败: {e}")
            raise
    
    
    
    async def _process_agent_tasks(self):
        """处理Agent任务的工作协程"""
        while self.is_running:
            try:
                # 从队列获取任务
                queue_item = await asyncio.wait_for(
                    self.processing_queue.get(), timeout=5.0
                )
                
                task_id = queue_item['task_id']
                logger.info(f"从队列取出Agent任务: {task_id}")
                
                # 处理任务
                await self.process_agent_task(task_id)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"处理Agent任务协程出错: {e}")
                await asyncio.sleep(1)
    
    async def _monitor_pending_tasks(self):
        """监控待处理任务的协程"""
        while self.is_running:
            try:
                # 每30秒检查一次待处理任务
                await asyncio.sleep(30)
                
                # 获取待处理的Agent任务
                pending_tasks = await self.get_pending_agent_tasks(limit=10)
                
                # 将待处理任务加入队列
                for task in pending_tasks:
                    if task['status'] == TaskInstanceStatus.PENDING.value:
                        queue_item = {
                            'task_id': task['task_instance_id'],
                            'priority': task.get('priority', 1),
                            'submitted_at': now_utc()
                        }
                        await self.processing_queue.put(queue_item)
                        
                        logger.info(f"自动加入Agent任务到处理队列: {task['task_instance_id']}")
                
            except Exception as e:
                logger.error(f"监控待处理任务失败: {e}")
                await asyncio.sleep(10)
    
    async def get_agent_task_statistics(self, agent_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """获取Agent任务统计"""
        try:
            # 获取Agent的所有任务
            all_tasks = await self.task_repo.get_agent_tasks_for_processing(agent_id, 1000)
            
            # 统计信息
            stats = {
                'total_tasks': len(all_tasks),
                'pending_tasks': 0,
                'in_progress_tasks': 0,
                'completed_tasks': 0,
                'failed_tasks': 0,
                'average_processing_time': 0,
                'success_rate': 0,
                'queue_size': self.processing_queue.qsize()
            }
            
            total_duration = 0
            completed_count = 0
            
            for task in all_tasks:
                status = task['status']
                if status == TaskInstanceStatus.PENDING.value:
                    stats['pending_tasks'] += 1
                elif status == TaskInstanceStatus.IN_PROGRESS.value:
                    stats['in_progress_tasks'] += 1
                elif status == TaskInstanceStatus.COMPLETED.value:
                    stats['completed_tasks'] += 1
                    completed_count += 1
                    if task.get('actual_duration'):
                        total_duration += task['actual_duration']
                elif status == TaskInstanceStatus.FAILED.value:
                    stats['failed_tasks'] += 1
            
            # 计算平均处理时间和成功率
            if completed_count > 0:
                stats['average_processing_time'] = total_duration / completed_count
            
            if len(all_tasks) > 0:
                stats['success_rate'] = (completed_count / len(all_tasks)) * 100
            
            logger.info(f"生成Agent任务统计，成功率: {stats['success_rate']:.1f}%")
            return stats
            
        except Exception as e:
            logger.error(f"获取Agent任务统计失败: {e}")
            raise
    
    async def retry_failed_task(self, task_id: uuid.UUID) -> Dict[str, Any]:
        """重试失败的任务"""
        try:
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                raise ValueError("任务不存在")
            
            if task['status'] != TaskInstanceStatus.FAILED.value:
                raise ValueError("只能重试失败的任务")
            
            # 重置任务状态为待处理
            reset_update = TaskInstanceUpdate(
                status=TaskInstanceStatus.PENDING,
                error_message=None
            )
            await self.task_repo.update_task(task_id, reset_update)
            
            # 重新提交到处理队列
            await self.submit_task_to_agent(task_id, priority=2)  # 重试任务使用较高优先级
            
            logger.info(f"重试失败任务: {task_id}")
            return {
                'task_id': task_id,
                'status': 'retry_queued',
                'message': '失败任务已重新加入处理队列'
            }
            
        except Exception as e:
            logger.error(f"重试失败任务出错: {e}")
            raise
    
    async def cancel_agent_task(self, task_id: uuid.UUID) -> Dict[str, Any]:
        """取消Agent任务"""
        try:
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                raise ValueError("任务不存在")
            
            if task['status'] in [TaskInstanceStatus.COMPLETED.value, TaskInstanceStatus.CANCELLED.value]:
                raise ValueError("任务已完成或已取消，无法取消")
            
            # 更新任务状态为已取消
            cancel_update = TaskInstanceUpdate(
                status=TaskInstanceStatus.CANCELLED,
                error_message="任务被手动取消"
            )
            await self.task_repo.update_task(task_id, cancel_update)
            
            logger.info(f"取消Agent任务: {task_id}")
            return {
                'task_id': task_id,
                'status': TaskInstanceStatus.CANCELLED.value,
                'message': '任务已取消'
            }
            
        except Exception as e:
            logger.error(f"取消Agent任务失败: {e}")
            raise
    
    def _build_system_prompt(self, task: Dict[str, Any]) -> str:
        """构建系统Prompt（使用任务的详细描述）"""
        try:
            # 基础系统prompt
            system_prompt = f"""你是一个专业的AI助手，负责完成以下任务：

任务标题：{task.get('task_title', '未命名任务')}

任务描述：
{task.get('task_description', '无描述')}

具体指令：
{task.get('instructions', '无具体指令')}

工作要求：
1. 仔细分析提供的上游数据和上下文信息
2. 基于数据进行深入分析和处理
3. 提供结构化、准确的结果
4. 确保输出格式符合要求
5. 如有不确定的地方，请明确指出

请以专业、准确、有条理的方式完成任务。"""

            return system_prompt.strip()
            
        except Exception as e:
            logger.error(f"构建系统prompt失败: {e}")
            return "你是一个专业的AI助手，请帮助完成分配的任务。"
    
    def _preprocess_upstream_context(self, input_data: Dict[str, Any]) -> str:
        """预处理上游上下文信息（整理成补充信息）"""
        try:
            context_parts = []
            
            # 处理上游节点数据
            immediate_upstream = input_data.get('immediate_upstream', {})
            if immediate_upstream:
                context_parts.append("## 上游节点提供的数据：")
                
                for node_id, node_data in immediate_upstream.items():
                    node_name = node_data.get('node_name', f'节点_{node_id[:8]}')
                    output_data = node_data.get('output_data', {})
                    completed_at = node_data.get('completed_at', '')
                    
                    context_parts.append(f"\n### {node_name}")
                    if completed_at:
                        context_parts.append(f"完成时间: {completed_at}")
                    
                    # 格式化输出数据
                    if output_data:
                        context_parts.append("数据内容:")
                        for key, value in output_data.items():
                            if isinstance(value, (dict, list)):
                                context_parts.append(f"- {key}: {self._format_complex_data(value)}")
                            else:
                                context_parts.append(f"- {key}: {value}")
                    else:
                        context_parts.append("- 无输出数据")
            
            # 处理工作流全局信息
            workflow_global = input_data.get('workflow_global', {})
            if workflow_global:
                context_parts.append("\n## 工作流全局信息：")
                
                execution_path = workflow_global.get('execution_path', [])
                if execution_path:
                    context_parts.append(f"执行路径: {' → '.join(execution_path)}")
                
                global_data = workflow_global.get('global_data', {})
                if global_data:
                    context_parts.append("全局数据:")
                    for key, value in global_data.items():
                        context_parts.append(f"- {key}: {value}")
                
                start_time = workflow_global.get('execution_start_time', '')
                if start_time:
                    context_parts.append(f"工作流开始时间: {start_time}")
            
            # 处理节点信息
            node_info = input_data.get('node_info', {})
            if node_info:
                context_parts.append("\n## 当前节点信息：")
                for key, value in node_info.items():
                    if key == 'node_instance_id':
                        continue  # 跳过技术性ID
                    context_parts.append(f"- {key}: {value}")
            
            return "\n".join(context_parts) if context_parts else "无上游上下文数据。"
            
        except Exception as e:
            logger.error(f"预处理上游上下文失败: {e}")
            return "上下文信息处理失败，请基于任务描述进行处理。"
    
    def _format_complex_data(self, data) -> str:
        """格式化复杂数据结构"""
        try:
            if isinstance(data, dict):
                if len(data) <= 3:
                    return str(data)
                else:
                    keys = list(data.keys())[:3]
                    return f"包含 {len(data)} 项数据，主要字段: {', '.join(keys)}..."
            elif isinstance(data, list):
                if len(data) <= 5:
                    return str(data)
                else:
                    return f"列表包含 {len(data)} 项数据"
            else:
                return str(data)
        except:
            return "复杂数据结构"
    
    def _build_user_message(self, task: Dict[str, Any], context_info: str) -> str:
        """构建用户消息（作为任务输入）"""
        try:
            message_parts = []
            
            # 任务基本信息
            task_title = task.get('task_title', '未命名任务')
            message_parts.append(f"请帮我完成以下任务：{task_title}")
            
            # 添加上下文信息
            if context_info and context_info.strip() != "无上游上下文数据。":
                message_parts.append("\n以下是可用的上下文信息，请充分利用：")
                message_parts.append(context_info)
            
            # 添加特殊要求（如果有）
            priority = task.get('priority', 1)
            if priority >= 3:
                message_parts.append("\n注意：这是一个高优先级任务，请优先处理。")
            
            estimated_duration = task.get('estimated_duration', 0)
            if estimated_duration > 0:
                message_parts.append(f"\n预估处理时间：{estimated_duration} 分钟。")
            
            # 输出格式要求
            message_parts.append("""
请按照以下JSON格式返回结果：
{
  "analysis_result": "你的分析结果",
  "key_findings": ["关键发现1", "关键发现2"],
  "recommendations": ["建议1", "建议2"],
  "confidence_score": 0.85,
  "summary": "结果总结"
}""")
            
            return "\n".join(message_parts)
            
        except Exception as e:
            logger.error(f"构建用户消息失败: {e}")
            return f"请完成任务：{task.get('task_title', '未知任务')}"


# 全局Agent任务服务实例
agent_task_service = AgentTaskService()