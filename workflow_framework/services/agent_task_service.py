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
            logger.info(f"🔍 [AGENT-SERVICE] 开始获取待处理Agent任务")
            logger.info(f"   - Agent ID: {agent_id if agent_id else '所有Agent'}")  
            logger.info(f"   - 限制数量: {limit}")
            
            tasks = await self.task_repo.get_agent_tasks_for_processing(agent_id, limit)
            
            logger.info(f"📋 [AGENT-SERVICE] 获取待处理Agent任务完成")
            logger.info(f"   - 找到任务数量: {len(tasks)}")
            
            if tasks:
                logger.info(f"   - 任务详情:")
                for i, task in enumerate(tasks[:3]):  # 只显示前3个任务
                    task_id = task.get('task_instance_id', 'unknown')
                    task_title = task.get('task_title', 'unknown')
                    task_status = task.get('status', 'unknown')
                    logger.info(f"     {i+1}. {task_title} (ID: {task_id}, 状态: {task_status})")
                if len(tasks) > 3:
                    logger.info(f"     ... 还有 {len(tasks) - 3} 个任务")
            else:
                logger.warning(f"⚠️ [AGENT-SERVICE] 没有找到待处理的Agent任务")
                logger.info(f"   - 可能原因:")
                logger.info(f"     1. 没有创建Agent类型的任务")
                logger.info(f"     2. Agent任务状态不是PENDING")
                logger.info(f"     3. Agent任务没有正确分配assigned_agent_id")
                
            return tasks
            
        except Exception as e:
            logger.error(f"❌ [AGENT-SERVICE] 获取待处理Agent任务失败: {e}")
            import traceback
            logger.error(f"   - 错误堆栈: {traceback.format_exc()}")
            raise
    
    async def submit_task_to_agent(self, task_id: uuid.UUID) -> Dict[str, Any]:
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
            logger.info(f"🚀 [AGENT-PROCESS] 开始处理Agent任务: {task_id}")
            
            # 获取任务详情
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                logger.error(f"❌ [AGENT-PROCESS] 任务不存在: {task_id}")
                raise ValueError("任务不存在")
            
            logger.info(f"📋 [AGENT-PROCESS] 任务详情获取成功:")
            logger.info(f"   - 任务标题: {task['task_title']}")
            logger.info(f"   - 任务类型: {task.get('task_type', 'unknown')}")
            logger.info(f"   - 当前状态: {task.get('status', 'unknown')}")
            logger.info(f"   - 处理器ID: {task.get('processor_id', 'none')}")
            logger.info(f"   - 分配Agent ID: {task.get('assigned_agent_id', 'none')}")
            logger.info(f"   - 优先级: {task.get('priority', 0)}")
            
            # 更新任务状态为进行中
            logger.info(f"⏳ [AGENT-PROCESS] 更新任务状态为IN_PROGRESS")
            update_data = TaskInstanceUpdate(status=TaskInstanceStatus.IN_PROGRESS)
            await self.task_repo.update_task(task_id, update_data)
            logger.info(f"✅ [AGENT-PROCESS] 任务状态更新成功")
            
            start_time = datetime.now()
            logger.info(f"⏰ [AGENT-PROCESS] 任务开始时间: {start_time.isoformat()}")
            
            # 获取Agent信息
            agent_id = task.get('assigned_agent_id')
            logger.info(f"🔍 [AGENT-PROCESS] 检查Agent分配: {agent_id}")
            
            # 如果任务没有直接分配Agent，尝试从processor获取
            if not agent_id:
                processor_id = task.get('processor_id')
                logger.warning(f"⚠️ [AGENT-PROCESS] 任务未直接分配Agent，尝试从processor获取: {processor_id}")
                
                if processor_id:
                    # 从processor获取关联的agent
                    from ..repositories.processor.processor_repository import ProcessorRepository
                    processor_repo = ProcessorRepository()
                    processor = await processor_repo.get_processor_with_details(processor_id)
                    if processor and processor.get('agent_id'):
                        agent_id = processor['agent_id']
                        logger.info(f"✅ [AGENT-PROCESS] 从processor获取到Agent ID: {agent_id}")
                    else:
                        logger.error(f"❌ [AGENT-PROCESS] Processor未关联Agent: {processor_id}")
                        raise ValueError(f"Processor {processor_id} 未关联Agent")
                else:
                    logger.error(f"❌ [AGENT-PROCESS] 任务既没有assigned_agent_id也没有processor_id")
                    raise ValueError("任务未分配Agent")
            
            logger.info(f"🤖 [AGENT-PROCESS] 获取Agent详情: {agent_id}")
            agent = await self.agent_repo.get_agent_by_id(agent_id)
            if not agent:
                logger.error(f"❌ [AGENT-PROCESS] Agent不存在: {agent_id}")
                raise ValueError(f"Agent不存在: {agent_id}")
            
            logger.info(f"✅ [AGENT-PROCESS] Agent详情获取成功:")
            logger.info(f"   - Agent名称: {agent.get('agent_name', 'unknown')}")
            logger.info(f"   - 模型: {agent.get('model_name', 'unknown')}")
            logger.info(f"   - Base URL: {agent.get('base_url', 'none')}")
            logger.info(f"   - API Key存在: {'是' if agent.get('api_key') else '否'}")
            
            # 准备AI任务数据（现在input_data是文本格式）
            input_data = task.get('input_data', '')
            logger.info(f"📊 [AGENT-PROCESS] 准备任务数据:")
            logger.info(f"   - 输入数据大小: {len(input_data)} 字符")
            logger.info(f"   - 输入数据类型: {type(input_data)}")
            if input_data and len(input_data) > 0:
                logger.info(f"   - 输入数据预览: {input_data[:100]}...")
            
            # 构建系统 Prompt（使用任务的详细描述）
            logger.info(f"🔨 [AGENT-PROCESS] 构建系统Prompt")
            system_prompt = self._build_system_prompt(task)
            logger.info(f"   - 系统Prompt长度: {len(system_prompt)} 字符")
            logger.info(f"   - 系统Prompt预览: {system_prompt[:200]}...")
            
            # 预处理上游上下文（整理成补充信息）
            logger.info(f"🔄 [AGENT-PROCESS] 预处理上游上下文")
            context_info = self._preprocess_upstream_context(input_data)
            logger.info(f"   - 上下文信息长度: {len(context_info)} 字符")
            logger.info(f"   - 上下文信息预览: {context_info[:200]}...")
            
            # 构建用户消息（作为任务输入）
            logger.info(f"✉️ [AGENT-PROCESS] 构建用户消息")
            user_message = self._build_user_message(task, context_info)
            logger.info(f"   - 用户消息长度: {len(user_message)} 字符")
            logger.info(f"   - 用户消息预览: {user_message[:200]}...")
            
            # 整理成AI Client可接收的数据结构
            ai_client_data = {
                'task_id': str(task_id),
                'system_prompt': system_prompt,
                'user_message': user_message,
                'task_metadata': {
                    'task_title': task['task_title'],
                    'estimated_duration': task.get('estimated_duration', 30)
                }
            }
            
            logger.info(f"📦 [AGENT-PROCESS] AI Client数据准备完成:")
            logger.info(f"   - 任务ID: {ai_client_data['task_id']}")
            logger.info(f"   - 系统Prompt: {len(ai_client_data['system_prompt'])} 字符")
            logger.info(f"   - 用户消息: {len(ai_client_data['user_message'])} 字符")
            logger.info(f"   - 元数据: {ai_client_data['task_metadata']}")
            
            # 调用Agent处理
            logger.info(f"🚀 [AGENT-PROCESS] 开始调用Agent API")
            result = await self._call_agent_api(agent, ai_client_data)
            logger.info(f"✅ [AGENT-PROCESS] Agent API调用成功")
            logger.info(f"   - 结果类型: {type(result)}")
            logger.info(f"   - 结果键: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
            
            # 计算执行时间
            end_time = datetime.now()
            actual_duration = int((end_time - start_time).total_seconds() / 60)
            
            logger.info(f"⏰ [AGENT-PROCESS] 任务执行完成:")
            logger.info(f"   - 开始时间: {start_time.isoformat()}")
            logger.info(f"   - 结束时间: {end_time.isoformat()}")
            logger.info(f"   - 实际用时: {actual_duration} 分钟")
            
            # 更新任务状态为已完成（将结果转换为文本格式）
            logger.info(f"💾 [AGENT-PROCESS] 更新任务状态为COMPLETED")
            
            # 将结果转换为文本格式存储
            output_text = result['result'] if isinstance(result, dict) and 'result' in result else str(result)
            result_summary = output_text[:500] + '...' if len(output_text) > 500 else output_text  # 摘要为前500字符
            
            complete_update = TaskInstanceUpdate(
                status=TaskInstanceStatus.COMPLETED,
                output_data=output_text,
                result_summary=result_summary,
                actual_duration=actual_duration
            )
            
            updated_task = await self.task_repo.update_task(task_id, complete_update)
            logger.info(f"✅ [AGENT-PROCESS] 任务状态更新为COMPLETED成功")
            
            if updated_task:
                logger.info(f"📋 [AGENT-PROCESS] 更新后任务状态: {updated_task.get('status', 'unknown')}")
            else:
                logger.warning(f"⚠️ [AGENT-PROCESS] 任务更新返回空结果")
            
            # 显示Agent输出结果
            logger.info(f"🎯 [AGENT-PROCESS] === AGENT输出结果 ===")
            logger.info(f"   📝 任务标题: {task['task_title']}")
            logger.info(f"   ⏱️  处理时长: {actual_duration}分钟")
            logger.info(f"   📊 结果内容:")
            
            # 显示文本结果
            logger.info(f"      📄 输出内容: {output_text[:300]}{'...' if len(output_text) > 300 else ''}")
            
            # 显示模型使用信息
            if isinstance(result, dict):
                model_used = result.get('model_used', 'N/A')
                if model_used and model_used != 'N/A':
                    logger.info(f"      🤖 使用模型: {model_used}")
                
                token_usage = result.get('token_usage', {})
                if token_usage:
                    logger.info(f"      💰 Token使用: {token_usage}")
            
            logger.info(f"🎉 [AGENT-PROCESS] Agent任务处理完成: {task['task_title']}")
            
            # 通知任务完成回调
            completion_result = {
                'task_id': task_id,
                'status': TaskInstanceStatus.COMPLETED.value,
                'result': output_text,  # 使用文本格式的结果
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
            logger.info(f"🔌 [AGENT-API] 开始调用Agent API")
            logger.info(f"   - Agent: {agent.get('agent_name', 'unknown')}")
            logger.info(f"   - 模型: {agent.get('model_name', 'unknown')}")
            logger.info(f"   - Base URL: {agent.get('base_url', 'none')}")
            logger.info(f"   - 任务ID: {ai_client_data.get('task_id', 'unknown')}")
            
            # 统一使用OpenAI规范格式处理所有AI任务
            result = await self._process_with_openai_format(agent, ai_client_data)
            
            logger.info(f"✅ [AGENT-API] Agent API调用成功")
            logger.info(f"   - 返回结果类型: {type(result)}")
            if isinstance(result, dict):
                logger.info(f"   - 结果包含的键: {list(result.keys())}")
                logger.info(f"   - 置信度: {result.get('confidence_score', 'N/A')}")
                
            return result
                
        except Exception as e:
            logger.error(f"❌ [AGENT-API] 调用Agent API失败: {e}")
            import traceback
            logger.error(f"   - 错误堆栈: {traceback.format_exc()}")
            raise
    
    async def _process_with_openai_format(self, agent: Dict[str, Any], 
                                        ai_client_data: Dict[str, Any]) -> Dict[str, Any]:
        """使用OpenAI规范格式处理任务"""
        try:
            task_title = ai_client_data['task_metadata']['task_title']
            logger.info(f"🚀 [OPENAI-FORMAT] 使用OpenAI规范处理任务: {task_title}")
            
            # 构建符合OpenAI API规范的请求数据
            logger.info(f"🛠️ [OPENAI-FORMAT] 构建 OpenAI API 请求数据")
            
            # 从 agent 的 parameters 中获取参数
            agent_params = agent.get('parameters') or {}
            model_name = agent.get('model_name', 'gpt-3.5-turbo')
            temperature = agent_params.get('temperature', 0.7)
            max_tokens = agent_params.get('max_tokens', 2000)
            
            # 添加调试日志
            logger.info(f"🔧 [OPENAI-FORMAT] Agent参数:")
            logger.info(f"   - model_name: {model_name}")
            logger.info(f"   - agent_params: {agent_params}")
            logger.info(f"   - temperature: {temperature}")
            logger.info(f"   - max_tokens: {max_tokens}")
            
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
                'model': model_name,
                'temperature': temperature,
                'max_tokens': max_tokens
            }
            
            logger.info(f"   - 模型: {model_name}")
            logger.info(f"   - 温度: {temperature}")
            logger.info(f"   - 最大token: {max_tokens}")
            logger.info(f"   - 消息数量: {len(openai_request['messages'])}")
            logger.info(f"   - 系统消息长度: {len(openai_request['messages'][0]['content'])}")
            logger.info(f"   - 用户消息长度: {len(openai_request['messages'][1]['content'])}")
            
            # 调用OpenAI客户端处理任务
            logger.info(f"🔄 [OPENAI-FORMAT] 调用OpenAI客户端")
            logger.info(f"   - 使用模型: {openai_request['model']}")
            logger.info(f"   - Base URL: {agent.get('base_url', 'default')}")
            logger.info(f"   - API Key存在: {'是' if agent.get('api_key') else '否'}")
            
            # 设置超时时间（防止卡死）
            try:
                openai_result = await asyncio.wait_for(
                    openai_client.process_task(openai_request),
                    timeout=300  # 5分钟超时
                )
                logger.info(f"✅ [OPENAI-FORMAT] OpenAI客户端调用成功")
            except asyncio.TimeoutError:
                logger.error(f"⏰ [OPENAI-FORMAT] OpenAI API调用超时（5分钟）")
                raise RuntimeError("OpenAI API调用超时")
            except Exception as api_e:
                logger.error(f"❌ [OPENAI-FORMAT] OpenAI API调用异常: {api_e}")
                raise
            
            if openai_result['success']:
                # 从OpenAI格式的回复中提取文本结果
                ai_response = openai_result['result']
                response_content = ai_response.get('content', '')
                
                # 直接返回文本结果，不要求特定格式
                result = {
                    'result': response_content,  # Agent的原始输出
                    'model_used': openai_result.get('model', agent.get('model')),
                    'token_usage': openai_result.get('usage', {})
                }
                
                logger.info(f"OpenAI规范处理完成，返回文本结果")
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
            await self.submit_task_to_agent(task_id)
            
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
        """构建系统Prompt（仅包含任务描述）"""
        try:
            task_description = task.get('task_description', '无任务描述')
            
            # 简化的系统prompt，只提供任务描述
            system_prompt = f"""你是一个专业的AI助手。请完成以下任务：

{task_description}

请根据提供的上下文信息，以自然、准确的方式完成任务。"""

            return system_prompt.strip()
            
        except Exception as e:
            logger.error(f"构建系统prompt失败: {e}")
            return "你是一个专业的AI助手，请帮助完成分配的任务。"
    
    def _preprocess_upstream_context(self, input_data: str) -> str:
        """预处理上游上下文信息（仅包含工作流描述、节点名称、任务title、节点输出内容）"""
        try:
            context_parts = []
            
            # 尝试解析JSON字符串
            try:
                if input_data and input_data.strip():
                    data_dict = json.loads(input_data)
                else:
                    data_dict = {}
            except json.JSONDecodeError:
                logger.warning(f"无法解析输入数据为JSON: {input_data[:100]}...")
                return "上下文信息格式错误，请基于任务描述进行处理。"
            
            # 1. 工作流描述
            workflow_global = data_dict.get('workflow_global', {})
            if workflow_global:
                workflow_description = workflow_global.get('workflow_description', '')
                if workflow_description:
                    context_parts.append(f"工作流描述：{workflow_description}")
            
            # 2. 上游节点信息（节点名称、任务title、节点输出内容）
            immediate_upstream = data_dict.get('immediate_upstream', {})
            if immediate_upstream:
                context_parts.append("\n上游节点信息：")
                
                for node_id, node_data in immediate_upstream.items():
                    node_name = node_data.get('node_name', f'节点_{node_id[:8]}')
                    task_title = node_data.get('task_title', '')
                    output_data = node_data.get('output_data', {})
                    
                    context_parts.append(f"\n节点：{node_name}")
                    if task_title:
                        context_parts.append(f"任务：{task_title}")
                    
                    # 输出内容（简化展示）
                    if output_data:
                        context_parts.append("输出内容：")
                        if isinstance(output_data, dict):
                            for key, value in output_data.items():
                                context_parts.append(f"- {key}: {self._format_simple_output(value)}")
                        else:
                            context_parts.append(f"- {self._format_simple_output(output_data)}")
                    else:
                        context_parts.append("- 无输出内容")
            
            return "\n".join(context_parts) if context_parts else "无上游上下文数据。"
            
        except Exception as e:
            logger.error(f"预处理上游上下文失败: {e}")
            return "上下文信息处理失败，请基于任务描述进行处理。"
    
    def _format_simple_output(self, data) -> str:
        """格式化输出数据为简单文本形式"""
        try:
            if isinstance(data, dict):
                # 对于字典，尝试找到最重要的字段
                if 'result' in data:
                    return str(data['result'])
                elif 'content' in data:
                    return str(data['content'])
                elif 'value' in data:
                    return str(data['value'])
                elif len(data) == 1:
                    # 如果只有一个键值对，直接返回值
                    return str(list(data.values())[0])
                else:
                    # 返回简化的字典表示
                    return str(data)
            elif isinstance(data, list):
                if len(data) <= 3:
                    return str(data)
                else:
                    return f"包含{len(data)}个项目的列表"
            else:
                return str(data)
        except:
            return "数据"
    
    def _build_user_message(self, task: Dict[str, Any], context_info: str) -> str:
        """构建用户消息（包含任务标题和上游节点信息）"""
        try:
            message_parts = []
            
            # 任务标题
            logger.info(f"上下文信息: {context_info}")
            task_title = task.get('task_title', '未命名任务')
            message_parts.append(f"任务：{task_title}")
            
            # 添加上下文信息（上游节点信息）
            if context_info and context_info.strip() != "无上游上下文数据。":
                message_parts.append("\n上下文信息：")
                message_parts.append(context_info)
            else:
                message_parts.append("\n当前没有上游节点数据。")
            
            return "\n".join(message_parts)
            
        except Exception as e:
            logger.error(f"构建用户消息失败: {e}")
            return f"任务：{task.get('task_title', '未知任务')}"


# 全局Agent任务服务实例
agent_task_service = AgentTaskService()