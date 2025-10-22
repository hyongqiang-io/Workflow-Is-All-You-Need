"""
Agent任务处理服务
Agent Task Processing Service
"""

import uuid
import json
import sys
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger
logger.remove()
logger.add(sys.stderr, level="DEBUG", enqueue=True)  # 修复Windows GBK编码问题

from ..repositories.instance.task_instance_repository import TaskInstanceRepository
from ..repositories.agent.agent_repository import AgentRepository
from ..models.instance import (
    TaskInstanceUpdate, TaskInstanceStatus, TaskInstanceType
)
from ..utils.helpers import now_utc
from ..utils.openai_client import openai_client
from .mcp_service import mcp_service


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
        logger.trace(f"注册任务完成回调: {callback}")
    
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
        logger.trace("Agent任务处理服务启动")
        
        # 启动任务处理协程
        for i in range(self.max_concurrent_tasks):
            asyncio.create_task(self._process_agent_tasks())
        
        # 启动任务监控协程
        asyncio.create_task(self._monitor_pending_tasks())
    
    async def stop_service(self):
        """停止Agent任务处理服务"""
        self.is_running = False
        logger.trace("Agent任务处理服务停止")
    
    async def _has_active_workflows(self) -> bool:
        """检查是否有活跃的工作流"""
        try:
            from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
            workflow_repo = WorkflowInstanceRepository()
            
            # 查询运行中的工作流
            active_workflows = await workflow_repo.db.fetch_all("""
                SELECT workflow_instance_id, status 
                FROM workflow_instance 
                WHERE status IN ('RUNNING', 'PENDING') 
                AND is_deleted = FALSE
                LIMIT 1
            """)
            
            return len(active_workflows) > 0
        except Exception as e:
            logger.error(f"检查活跃工作流失败: {e}")
            return True  # 出错时假设有活跃工作流，继续监控
    
    async def get_pending_agent_tasks(self, agent_id: Optional[uuid.UUID] = None, 
                                    limit: int = 50) -> List[Dict[str, Any]]:
        """获取待处理的Agent任务"""
        try:
            logger.trace(f"🔍 [AGENT-SERVICE] 开始获取待处理Agent任务")
            logger.trace(f"   - Agent ID: {agent_id if agent_id else '所有Agent'}")  
            logger.trace(f"   - 限制数量: {limit}")
            
            tasks = await self.task_repo.get_agent_tasks_for_processing(agent_id, limit)
            
            logger.trace(f"📋 [AGENT-SERVICE] 获取待处理Agent任务完成")
            logger.trace(f"   - 找到任务数量: {len(tasks)}")
            
            if tasks:
                logger.trace(f"   - 任务详情:")
                for i, task in enumerate(tasks[:3]):  # 只显示前3个任务
                    task_id = task.get('task_instance_id', 'unknown')
                    task_title = task.get('task_title', 'unknown')
                    task_status = task.get('status', 'unknown')
                    logger.trace(f"     {i+1}. {task_title} (ID: {task_id}, 状态: {task_status})")
                if len(tasks) > 3:
                    logger.trace(f"     ... 还有 {len(tasks) - 3} 个任务")
            else:
                # 减少日志频率，避免刷屏
                pass  # 在监控器中会统一处理空检查的日志
                
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
            
            logger.trace(f"任务 {task_id} 已提交给Agent处理队列")
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
            logger.trace(f"🚀 [AGENT-PROCESS] 开始处理Agent任务: {task_id}")
            
            # 获取任务详情
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                logger.error(f"❌ [AGENT-PROCESS] 任务不存在: {task_id}")
                raise ValueError("任务不存在")
            
            logger.trace(f"📋 [AGENT-PROCESS] 任务详情获取成功:")
            logger.trace(f"   - 任务标题: {task['task_title']}")
            logger.trace(f"   - 任务类型: {task.get('task_type', 'unknown')}")
            logger.trace(f"   - 当前状态: {task.get('status', 'unknown')}")
            logger.trace(f"   - 处理器ID: {task.get('processor_id', 'none')}")
            logger.trace(f"   - 分配Agent ID: {task.get('assigned_agent_id', 'none')}")
            logger.trace(f"   - 优先级: {task.get('priority', 0)}")
            
            # 更新任务状态为进行中
            logger.trace(f"⏳ [AGENT-PROCESS] 更新任务状态为IN_PROGRESS")
            update_data = TaskInstanceUpdate(status=TaskInstanceStatus.IN_PROGRESS)
            await self.task_repo.update_task(task_id, update_data)
            logger.trace(f"✅ [AGENT-PROCESS] 任务状态更新成功")
            
            start_time = datetime.now()
            logger.trace(f"⏰ [AGENT-PROCESS] 任务开始时间: {start_time.isoformat()}")
            
            # 获取Agent信息
            agent_id = task.get('assigned_agent_id')
            logger.trace(f"🔍 [AGENT-PROCESS] 检查Agent分配: {agent_id}")
            
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
                        logger.trace(f"✅ [AGENT-PROCESS] 从processor获取到Agent ID: {agent_id}")
                    else:
                        logger.error(f"❌ [AGENT-PROCESS] Processor未关联Agent: {processor_id}")
                        raise ValueError(f"Processor {processor_id} 未关联Agent")
                else:
                    logger.error(f"❌ [AGENT-PROCESS] 任务既没有assigned_agent_id也没有processor_id")
                    raise ValueError("任务未分配Agent")
            
            logger.trace(f"🤖 [AGENT-PROCESS] 获取Agent详情: {agent_id}")
            agent = await self.agent_repo.get_agent_by_id(agent_id)
            if not agent:
                logger.error(f"❌ [AGENT-PROCESS] Agent不存在: {agent_id}")
                raise ValueError(f"Agent不存在: {agent_id}")
            
            logger.trace(f"✅ [AGENT-PROCESS] Agent详情获取成功:")
            logger.trace(f"   - Agent名称: {agent.get('agent_name', 'unknown')}")
            logger.trace(f"   - 模型: {agent.get('model_name', 'unknown')}")
            logger.trace(f"   - Base URL: {agent.get('base_url', 'none')}")
            logger.trace(f"   - API Key存在: {'是' if agent.get('api_key') else '否'}")

            # 详细调试任务数据字段
            logger.trace(f"🔍 [AGENT-PROCESS] 详细调试任务数据字段:")
            logger.trace(f"   - 任务字典所有键: {list(task.keys())}")
            for key, value in task.items():
                if key in ['input_data', 'context_data', 'output_data']:
                    logger.trace(f"   - {key}: 类型={type(value)}, 长度={len(str(value)) if value else 0}, 值='{str(value)[:100]}{'...' if value and len(str(value)) > 100 else ''}'")
                elif key in ['task_title', 'task_description', 'status']:
                    logger.trace(f"   - {key}: '{value}'")
            
            # 准备AI任务数据 - 多数据源智能选择
            logger.info(f"📊 [AGENT-CONTEXT] 开始分析任务上下文数据")
            logger.trace(f"full task:{task}")
            task_input_data = task.get('input_data', '')
            task_context_data = task.get('context_data', '')
            
            logger.info(f"📊 [AGENT-CONTEXT] 初始数据源:")
            logger.info(f"   - task_input_data: {len(str(task_input_data))} 字符, 类型: {type(task_input_data)}")
            logger.info(f"   - task_context_data: {len(str(task_context_data))} 字符, 类型: {type(task_context_data)}")
            if task_context_data:
                logger.info(f"   - context_data 预览: {str(task_context_data)[:300]}...")
            
            # 尝试从节点实例获取数据（这是UI显示的数据源）
            node_input_data = ""
            node_instance_id = task.get('node_instance_id')
            if node_instance_id:
                try:
                    from ..repositories.instance.node_instance_repository import NodeInstanceRepository
                    node_repo = NodeInstanceRepository()
                    node_instance = await node_repo.get_instance_by_id(node_instance_id)
                    if node_instance and node_instance.get('input_data'):
                        node_input_data = node_instance['input_data']
                        logger.info(f"   - 从节点实例获取输入数据: {len(node_input_data)} 字符")
                        logger.info(f"   - 节点输入数据预览: {str(node_input_data)[:300]}...")
                except Exception as e:
                    logger.warning(f"   - 获取节点实例数据失败: {e}")
            
            # 整合所有可用数据源
            data_sources = [
                ("node_input_data", node_input_data),
                ("task_context_data", task_context_data), 
                ("task_input_data", task_input_data)
            ]
            
            logger.trace(f"📊 [AGENT-PROCESS] 多数据源分析:")
            for source_name, source_data in data_sources:
                data_str = str(source_data) if source_data is not None else ""
                logger.trace(f"   - {source_name}: 大小={len(data_str)} 字符, 类型={type(source_data)}")
                if data_str and len(data_str) > 0:
                    logger.trace(f"     预览: {data_str[:100]}{'...' if len(data_str) > 100 else ''}")
            
            # 智能选择最佳数据源：优先选择内容最丰富的
            actual_data = ""
            data_source = "none"
            
            for source_name, source_data in data_sources:
                # 将数据转换为字符串进行处理
                data_str = str(source_data) if source_data is not None else ""
                if data_str and data_str.strip() and data_str.strip() != '{}' and data_str.strip() != 'None':
                    actual_data = data_str
                    data_source = source_name
                    logger.trace(f"   ✅ 选择{source_name}作为数据源")
                    break
            
            if not actual_data:
                logger.warning(f"   ❌ 所有数据源都为空")
                
            logger.trace(f"   - 实际使用数据源: {data_source}")
            logger.trace(f"   - 实际数据大小: {len(actual_data)} 字符")
            if actual_data and len(actual_data) > 0:
                logger.trace(f"   - 实际数据预览: {actual_data[:200]}...")
            
            # 构建系统 Prompt（使用任务的详细描述）
            logger.trace(f"🔨 [AGENT-PROCESS] 构建系统Prompt")
            system_prompt = self._build_system_prompt(task)
            logger.trace(f"   - 系统Prompt长度: {len(system_prompt)} 字符")
            logger.trace(f"   - 系统Prompt预览: {system_prompt[:200]}...")
            
            # 预处理上游上下文（整理成补充信息）
            logger.trace(f"🔄 [AGENT-PROCESS] 预处理上游上下文")
            logger.trace(f"   - 传入预处理的actual_data: {actual_data[:500] if actual_data else 'None'}...")
            context_info = self._preprocess_upstream_context(actual_data)
            logger.trace(f"   - 上下文信息长度: {len(context_info)} 字符")
            logger.trace(f"   - 上下文信息预览: {context_info[:200]}...")
            logger.trace(f"   - 上下文信息完整内容: '{context_info}'")
            
            # 构建用户消息（作为任务输入）
            logger.trace(f"✉️ [AGENT-PROCESS] 构建用户消息")
            message_data = await self._build_user_message(task, context_info, agent)
            user_message = message_data['text_message']
            images = message_data.get('images', [])
            has_multimodal = message_data.get('has_multimodal_content', False)

            logger.trace(f"   - 用户消息长度: {len(user_message)} 字符")
            logger.trace(f"   - 用户消息预览: {user_message[:200]}...")
            if has_multimodal:
                logger.trace(f"   - 包含多模态内容: {len(images)} 个图片")

            # 整理成AI Client可接收的数据结构
            ai_client_data = {
                'task_id': str(task_id),
                'system_prompt': system_prompt,
                'user_message': user_message,
                'images': images,  # 新增：多模态图片数据
                'has_multimodal_content': has_multimodal,  # 新增：多模态标识
                'task_metadata': {
                    'task_title': task['task_title'],
                    'task_description': task.get('task_description', '') or task.get('description', ''),
                    'estimated_duration': task.get('estimated_duration', 30)
                }
            }
            
            logger.trace(f"📦 [AGENT-PROCESS] AI Client数据准备完成:")
            logger.trace(f"   - 任务ID: {ai_client_data['task_id']}")
            logger.trace(f"   - 任务标题: {ai_client_data['task_metadata']['task_title']}")
            logger.trace(f"   - 任务描述: {ai_client_data['task_metadata']['task_description'][:100] if ai_client_data['task_metadata']['task_description'] else '无'}")
            logger.trace(f"   - 系统Prompt: {len(ai_client_data['system_prompt'])} 字符")
            logger.trace(f"   - 用户消息: {len(ai_client_data['user_message'])} 字符")
            logger.trace(f"   - 元数据: {ai_client_data['task_metadata']}")
            
            # 调用Agent处理
            logger.trace(f"🚀 [AGENT-PROCESS] 开始调用Agent API")
            result = await self._call_agent_api(agent, ai_client_data)
            logger.trace(f"✅ [AGENT-PROCESS] Agent API调用成功")
            logger.trace(f"   - 结果类型: {type(result)}")
            logger.trace(f"   - 结果键: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
            
            # 计算执行时间
            end_time = datetime.now()
            actual_duration = int((end_time - start_time).total_seconds() / 60)
            
            logger.trace(f"⏰ [AGENT-PROCESS] 任务执行完成:")
            logger.trace(f"   - 开始时间: {start_time.isoformat()}")
            logger.trace(f"   - 结束时间: {end_time.isoformat()}")
            logger.trace(f"   - 实际用时: {actual_duration} 分钟")
            
            # 处理AI生成的图片内容（如果有）
            logger.trace(f"🖼️ [AI-IMAGE] 检查AI响应中的图片内容")
            await self._process_ai_generated_images(task_id, result, agent)

            # 更新任务状态为已完成（将结果转换为文本格式）
            logger.trace(f"💾 [AGENT-PROCESS] 更新任务状态为COMPLETED")

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
            logger.trace(f"✅ [AGENT-PROCESS] 任务状态更新为COMPLETED成功")
            
            if updated_task:
                logger.trace(f"📋 [AGENT-PROCESS] 更新后任务状态: {updated_task.get('status', 'unknown')}")
            else:
                logger.warning(f"⚠️ [AGENT-PROCESS] 任务更新返回空结果")
            
            # 显示Agent输出结果
            logger.trace(f"🎯 [AGENT-PROCESS] === AGENT输出结果 ===")
            logger.trace(f"   📝 任务标题: {task['task_title']}")
            logger.trace(f"   ⏱️  处理时长: {actual_duration}分钟")
            logger.trace(f"   📊 结果内容:")
            
            # 显示文本结果
            logger.trace(f"      📄 输出内容: {output_text[:300]}{'...' if len(output_text) > 300 else ''}")
            
            # 显示模型使用信息
            if isinstance(result, dict):
                model_used = result.get('model_used', 'N/A')
                if model_used and model_used != 'N/A':
                    logger.trace(f"      🤖 使用模型: {model_used}")
                
                token_usage = result.get('token_usage', {})
                if token_usage:
                    logger.trace(f"      💰 Token使用: {token_usage}")
            
            logger.trace(f"🎉 [AGENT-PROCESS] Agent任务处理完成: {task['task_title']}")
            
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
            logger.trace(f"🔌 [AGENT-API] 开始调用Agent API")
            
            # 兼容不同Agent对象格式
            agent_name = 'unknown'
            model_name = 'unknown'  
            base_url = 'none'
            
            if isinstance(agent, dict):
                agent_name = agent.get('agent_name', 'unknown')
                model_name = agent.get('model_name', 'unknown')
                base_url = agent.get('base_url', 'none')
            elif hasattr(agent, 'agent_name'):
                agent_name = getattr(agent, 'agent_name', 'unknown')
                model_name = getattr(agent, 'model_name', 'unknown')
                base_url = getattr(agent, 'base_url', 'none')
            
            logger.trace(f"   - Agent: {agent_name}")
            logger.trace(f"   - 模型: {model_name}")
            logger.trace(f"   - Base URL: {base_url}")
            logger.trace(f"   - 任务ID: {ai_client_data.get('task_id', 'unknown')}")
            
            # 统一使用OpenAI规范格式处理所有AI任务
            result = await self._process_with_openai_format(agent, ai_client_data)
            
            logger.trace(f"✅ [AGENT-API] Agent API调用成功")
            logger.trace(f"   - 返回结果类型: {type(result)}")
            if isinstance(result, dict):
                logger.trace(f"   - 结果包含的键: {list(result.keys())}")
                logger.trace(f"   - 置信度: {result.get('confidence_score', 'N/A')}")
                
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
            user_message = ai_client_data.get('user_message', '')
            logger.trace(f"🚀 [OPENAI-FORMAT] 使用OpenAI规范处理任务: {task_title}")

            # 检查是否为图像生成请求
            is_image_request = self._is_image_generation_request(user_message)

            if is_image_request:
                logger.info(f"🎨 [IMAGE-GEN] 检测到图像生成请求")

                # 检查Agent是否有图像生成权限
                agent_tags = agent.get('tags', []) if isinstance(agent, dict) else []
                has_image_permission = 'image-generation' in agent_tags

                if not has_image_permission:
                    logger.warning(f"⚠️ [IMAGE-GEN] Agent缺少图像生成权限，标签: {agent_tags}")
                    return {
                        'success': False,
                        'error': '该Agent没有图像生成权限。请为Agent添加 "image-generation" 标签以启用图像生成功能。',
                        'content': '抱歉，我无法生成图像。管理员需要为我添加图像生成权限。',
                        'permission_required': 'image-generation'
                    }

                # 执行图像生成 - 传递任务元数据
                logger.info(f"✅ [IMAGE-GEN] Agent具有图像生成权限，开始生成图像")
                task_id = ai_client_data.get('task_id')
                task_metadata = ai_client_data.get('task_metadata', {})
                if task_id and isinstance(task_id, str):
                    task_id = uuid.UUID(task_id)
                return await self._handle_image_generation(user_message, agent, task_id, task_metadata)

            # 构建符合OpenAI API规范的请求数据
            logger.trace(f"🛠️ [OPENAI-FORMAT] 构建 OpenAI API 请求数据")
            
            # 从 agent 的 parameters 中获取参数
            if isinstance(agent, dict):
                agent_params = agent.get('parameters') or {}
                model_name = agent.get('model_name', 'gpt-3.5-turbo')
            elif hasattr(agent, 'parameters'):
                agent_params = agent.parameters or {}
                model_name = getattr(agent, 'model_name', 'gpt-3.5-turbo')
            else:
                logger.warning(f"⚠️ [OPENAI-FORMAT] 无法获取Agent参数，使用默认值")
                agent_params = {}
                model_name = 'gpt-3.5-turbo'
                
            temperature = agent_params.get('temperature', 0.7) if isinstance(agent_params, dict) else 0.7
            max_tokens = agent_params.get('max_tokens', 2000) if isinstance(agent_params, dict) else 2000
            
            # 添加调试日志
            logger.trace(f"🔧 [OPENAI-FORMAT] Agent参数:")
            logger.trace(f"   - model_name: {model_name}")
            logger.trace(f"   - agent_params: {agent_params}")
            logger.trace(f"   - temperature: {temperature}")
            logger.trace(f"   - max_tokens: {max_tokens}")
            logger.trace(f"   - Agent完整信息: {agent}")
            
            # 获取Agent的MCP工具
            agent_id = None
            if isinstance(agent, dict):
                agent_id = agent.get('agent_id')
            elif hasattr(agent, 'agent_id'):
                agent_id = agent.agent_id
            else:
                logger.warning(f"⚠️ [MCP-TOOLS] Agent对象类型无法识别: {type(agent)}, 跳过工具获取")
                
            mcp_tools = []
            if agent_id:
                try:
                    logger.trace(f"🔧 [MCP-TOOLS] 获取Agent的MCP工具: {agent_id}")
                    logger.trace(f"   - Agent对象类型: {type(agent)}")
                    logger.trace(f"   - Agent是否为字典: {isinstance(agent, dict)}")
                    if isinstance(agent, dict):
                        logger.trace(f"   - Agent字典键: {list(agent.keys())}")
                    
                    logger.info(f"🔧 [AGENT-TASK] 开始加载Agent工具")
                    logger.info(f"   - Agent ID: {agent_id}")
                    logger.info(f"   - Agent名称: {agent.get('agent_name', 'Unknown') if isinstance(agent, dict) else 'Unknown'}")
                    
                    mcp_tools = await mcp_service.get_agent_tools(agent_id)
                    
                    logger.info(f"🔧 [AGENT-TASK] MCP工具加载完成")
                    logger.info(f"   - 加载到的工具数量: {len(mcp_tools)}")
                    
                    for i, tool in enumerate(mcp_tools):
                        logger.info(f"   - 工具 {i+1}: {tool.name if hasattr(tool, 'name') else tool.get('name', 'Unknown') if isinstance(tool, dict) else str(tool)}")
                        logger.info(f"     * 描述: {tool.description if hasattr(tool, 'description') else tool.get('description', 'No description') if isinstance(tool, dict) else 'No description'}")
                        if hasattr(tool, 'server_name'):
                            logger.info(f"     * 服务器: {tool.server_name}")
                        elif isinstance(tool, dict) and 'server_name' in tool:
                            logger.info(f"     * 服务器: {tool['server_name']}")
                    
                    if len(mcp_tools) == 0:
                        logger.warning(f"⚠️ [AGENT-TASK] Agent没有可用的工具，将使用普通模式")
                    else:
                        logger.info(f"✅ [AGENT-TASK] Agent工具加载成功，进入工具调用模式")
                    
                    logger.trace(f"   - 找到MCP工具数量: {len(mcp_tools)}")
                    
                    # 检查工具选择模式
                    tool_config = {}
                    if isinstance(agent, dict):
                        tool_config = agent.get('tool_config', {}) or {}
                    elif hasattr(agent, 'tool_config'):
                        tool_config = getattr(agent, 'tool_config', {}) or {}
                    
                    # 确保tool_config是字典类型
                    if not isinstance(tool_config, dict):
                        logger.warning(f"⚠️ [MCP-TOOLS] tool_config不是字典类型: {type(tool_config)}, 使用默认配置")
                        tool_config = {}
                        
                    tool_selection = tool_config.get('tool_selection', 'auto')
                    
                    logger.trace(f"   - 工具选择模式: {tool_selection}")
                    
                    if tool_selection == 'disabled':
                        logger.trace(f"   - 工具调用已禁用，清空工具列表")
                        mcp_tools = []
                    elif tool_selection == 'manual':
                        # 应用工具过滤
                        allowed_tools = tool_config.get('allowed_tools', [])
                        blocked_tools = tool_config.get('blocked_tools', [])
                        
                        if allowed_tools:
                            mcp_tools = [tool for tool in mcp_tools if tool.name in allowed_tools]
                            logger.trace(f"   - 应用允许列表后工具数量: {len(mcp_tools)}")
                        
                        if blocked_tools:
                            mcp_tools = [tool for tool in mcp_tools if tool.name not in blocked_tools]
                            logger.trace(f"   - 应用禁用列表后工具数量: {len(mcp_tools)}")
                    
                    # 显示最终工具列表
                    if mcp_tools:
                        logger.trace(f"   - 可用工具:")
                        for i, tool in enumerate(mcp_tools[:5]):  # 只显示前5个
                            logger.trace(f"     {i+1}. {tool.name} ({tool.server_name})")
                        if len(mcp_tools) > 5:
                            logger.trace(f"     ... 还有 {len(mcp_tools) - 5} 个工具")
                    
                except Exception as e:
                    logger.warning(f"⚠️ [MCP-TOOLS] 获取MCP工具失败: {e}")
                    mcp_tools = []
            
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
            
            # 如果有MCP工具，添加到请求中
            if mcp_tools:
                openai_tools = [tool.to_openai_format() for tool in mcp_tools]
                openai_request['tools'] = openai_tools
                openai_request['tool_choice'] = 'auto'
                logger.trace(f"🔧 [MCP-TOOLS] 添加工具到OpenAI请求: {len(openai_tools)} 个工具")
            
            logger.trace(f"   - 模型: {model_name}")
            logger.trace(f"   - 温度: {temperature}")
            logger.trace(f"   - 最大token: {max_tokens}")
            logger.trace(f"   - 消息数量: {len(openai_request['messages'])}")
            logger.trace(f"   - 工具数量: {len(openai_request.get('tools', []))}")
            logger.trace(f"   - 系统消息长度: {len(openai_request['messages'][0]['content'])}")
            logger.trace(f"   - 用户消息长度: {len(openai_request['messages'][1]['content'])}")
            
            # 调用OpenAI客户端处理任务（支持工具调用）
            logger.trace(f"🔄 [OPENAI-FORMAT] 调用OpenAI客户端")
            logger.trace(f"   - 使用模型: {openai_request['model']}")

            # 获取Agent的配置信息创建专用客户端
            agent_api_key = None
            agent_base_url = None

            if isinstance(agent, dict):
                agent_api_key = agent.get('api_key')
                agent_base_url = agent.get('base_url')
            elif hasattr(agent, 'api_key'):
                agent_api_key = getattr(agent, 'api_key', None)
                agent_base_url = getattr(agent, 'base_url', None)

            logger.trace(f"   - Agent Base URL: {agent_base_url}")
            logger.trace(f"   - Agent API Key存在: {'是' if agent_api_key else '否'}")

            # 🔥 关键修复：为每个Agent创建专用的OpenAIClient
            from ..utils.openai_client import OpenAIClient

            agent_openai_client = OpenAIClient(
                api_key=agent_api_key,
                base_url=agent_base_url,
                model=model_name,
                temperature=temperature
            )

            logger.info(f"🔧 [AGENT-CLIENT] 为Agent创建专用OpenAI客户端")
            logger.info(f"   - Base URL: {agent_base_url}")
            logger.info(f"   - 模型: {model_name}")
            logger.info(f"   - API Key存在: {'是' if agent_api_key else '否'}")
            logger.info(f"   - Agent原始model_name: {agent.get('model_name') if isinstance(agent, dict) else getattr(agent, 'model_name', 'N/A')}")

            # 设置超时时间（防止卡死）
            try:
                openai_result = await asyncio.wait_for(
                    self._process_with_tools(agent, openai_request, mcp_tools, agent_openai_client),
                    timeout=600  # 10分钟超时（工具调用可能需要更长时间）
                )
                logger.trace(f"✅ [OPENAI-FORMAT] OpenAI客户端调用成功")
            except asyncio.TimeoutError:
                logger.error(f"⏰ [OPENAI-FORMAT] OpenAI API调用超时（10分钟）")
                raise RuntimeError("OpenAI API调用超时")
            except Exception as api_e:
                logger.error(f"❌ [OPENAI-FORMAT] OpenAI API调用异常: {api_e}")
                raise
            
            if openai_result['success']:
                # 从OpenAI格式的回复中提取文本结果
                ai_response = openai_result['result']
                response_content = ai_response.get('content', '')
                
                # 直接返回文本结果，不要求特定格式
                model_used = openai_result.get('model', model_name)  # 使用之前获取的model_name
                result = {
                    'result': response_content,  # Agent的原始输出
                    'model_used': model_used,
                    'token_usage': openai_result.get('usage', {})
                }
                
                logger.trace(f"OpenAI规范处理完成，返回文本结果")
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
                logger.trace(f"从队列取出Agent任务: {task_id}")
                
                # 处理任务
                await self.process_agent_task(task_id)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"处理Agent任务协程出错: {e}")
                await asyncio.sleep(1)
    
    async def _monitor_pending_tasks(self):
        """监控待处理任务的协程（智能调度版本）"""
        consecutive_empty_checks = 0
        base_sleep_interval = 15  # 基础检查间隔（秒）- 优化为更频繁
        max_sleep_interval = 120  # 最大检查间隔（2分钟）- 减少最大延迟
        
        while self.is_running:
            try:
                # 动态调整检查间隔
                if consecutive_empty_checks == 0:
                    sleep_interval = base_sleep_interval
                elif consecutive_empty_checks <= 3:
                    sleep_interval = base_sleep_interval * 2  # 60秒
                elif consecutive_empty_checks <= 6:
                    sleep_interval = base_sleep_interval * 4  # 120秒
                else:
                    sleep_interval = max_sleep_interval  # 300秒
                
                await asyncio.sleep(sleep_interval)
                
                # 获取待处理的Agent任务
                pending_tasks = await self.get_pending_agent_tasks(limit=10)
                
                if pending_tasks:
                    # 有待处理任务，重置计数器
                    consecutive_empty_checks = 0
                    
                    # 将待处理任务加入队列
                    for task in pending_tasks:
                        if task['status'] == TaskInstanceStatus.PENDING.value:
                            queue_item = {
                                'task_id': task['task_instance_id'],
                                'submitted_at': now_utc()
                            }
                            await self.processing_queue.put(queue_item)
                            
                            logger.trace(f"自动加入Agent任务到处理队列: {task['task_instance_id']}")
                else:
                    # 没有待处理任务，增加空检查计数
                    consecutive_empty_checks += 1
                    
                    # 检查是否有活跃的工作流
                    has_active_workflows = await self._has_active_workflows()
                    
                    # 如果没有活跃工作流，进一步延长检查间隔
                    if not has_active_workflows and consecutive_empty_checks > 10:
                        sleep_interval = min(sleep_interval * 2, 600)  # 最长10分钟
                    
                    # 每隔一定次数才输出一次警告，避免日志刷屏
                    if consecutive_empty_checks in [1, 5, 10, 20] or consecutive_empty_checks % 50 == 0:
                        status_msg = "无活跃工作流" if not has_active_workflows else "有活跃工作流"
                        logger.trace(f"🔍 [AGENT-MONITOR] 连续 {consecutive_empty_checks} 次未找到待处理任务，{status_msg}，检查间隔已调整为 {sleep_interval} 秒")
                
            except Exception as e:
                logger.error(f"监控待处理任务失败: {e}")
                await asyncio.sleep(10)
                consecutive_empty_checks = 0  # 重置计数器
    
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
            
            logger.trace(f"生成Agent任务统计，成功率: {stats['success_rate']:.1f}%")
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
            
            logger.trace(f"重试失败任务: {task_id}")
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
            
            logger.trace(f"取消Agent任务: {task_id}")
            return {
                'task_id': task_id,
                'status': TaskInstanceStatus.CANCELLED.value,
                'message': '任务已取消'
            }
            
        except Exception as e:
            logger.error(f"取消Agent任务失败: {e}")
            raise
    
    def _build_system_prompt(self, task: Dict[str, Any]) -> str:
        """构建系统Prompt（包含任务描述和工具使用指导）"""
        try:
            task_description = task.get('task_description', '无任务描述')
            
            # 增强的系统prompt，包含工具使用指导
            system_prompt = f"""你是一个专业的AI助手，拥有多种工具来帮助完成任务。请完成以下任务：

{task_description}

重要提示：
1. 你有可用的工具来获取实时信息或执行特定操作
2. 当需要获取最新数据、执行计算或调用外部服务时，请主动使用相应的工具
3. 如果任务涉及天气、搜索、数据查询等，优先使用工具获取准确信息
4. 使用工具获取信息后，请基于结果为用户提供有用的回答
5. 如果工具调用失败，请说明情况并尽可能提供替代方案

请根据提供的上下文信息，以自然、准确的方式完成任务。如有必要，请使用可用的工具来获取最新、最准确的信息。"""

            return system_prompt.strip()
            
        except Exception as e:
            logger.error(f"构建系统prompt失败: {e}")
            return "你是一个专业的AI助手，拥有多种工具来帮助完成任务。当需要获取实时信息时，请主动使用可用的工具。请帮助完成分配的任务。"
    
    def _preprocess_upstream_context(self, input_data: str) -> str:
        """预处理上游上下文信息（仅包含工作流描述、节点名称、任务title、节点输出内容）"""
        try:
            logger.debug(f"🔍 [上下文预处理] ===== 开始预处理上游上下文 =====")
            logger.debug(f"  - 输入数据类型: {type(input_data)}")
            
            # 安全地计算长度和预览
            input_str = str(input_data) if input_data is not None else ""
            logger.debug(f"  - 输入数据长度: {len(input_str)}")
            logger.debug(f"  - 输入数据是否为空: {not input_data}")
            logger.debug(f"  - 输入数据预览: {input_str[:200]}{'...' if len(input_str) > 200 else ''}")
            logger.debug(f"  - 输入数据完整内容: '{input_data}'")
            
            context_parts = []
            
            # 智能处理输入数据：支持字典、JSON字符串和普通字符串
            data_dict = {}
            try:
                if input_data:
                    # 首先检查是否已经是字典类型
                    if isinstance(input_data, dict):
                        data_dict = input_data
                        logger.debug(f"  - 输入数据已是字典类型，直接使用")
                        logger.debug(f"  - 字典顶级键: {list(data_dict.keys())}")
                    elif isinstance(input_data, str) and input_data.strip():
                        # 尝试解析JSON字符串
                        try:
                            data_dict = json.loads(input_data)
                            logger.debug(f"  - JSON解析成功，数据类型: {type(data_dict)}")
                            logger.debug(f"  - JSON解析后顶级键: {list(data_dict.keys()) if isinstance(data_dict, dict) else 'Not a dict'}")
                        except json.JSONDecodeError:
                            # 如果不是有效JSON，将整个字符串作为简单上下文
                            logger.debug(f"  - 输入不是有效JSON，作为普通文本处理")
                            context_parts.append(f"上下文信息：{input_data}")
                            return "\n".join(context_parts)
                    else:
                        # 其他类型转为字符串处理
                        input_str = str(input_data)
                        logger.debug(f"  - 其他类型数据转为字符串: {input_str[:100]}...")
                        context_parts.append(f"上下文信息：{input_str}")
                        return "\n".join(context_parts)
                else:
                    data_dict = {}
                    logger.debug(f"  - 输入数据为空，使用空字典")
            except Exception as e:
                logger.error(f"处理输入数据失败: {e}")
                return "上下文信息处理失败，请基于任务描述进行处理。"
            
            # 1. 工作流描述
            workflow_global = data_dict.get('workflow_global', {})
            if workflow_global:
                workflow_description = workflow_global.get('workflow_description', '')
                if workflow_description:
                    context_parts.append(f"工作流描述：{workflow_description}")
            
            # 2. 上游节点信息（节点名称、任务title、节点输出内容）
            logger.debug(f"🔍 [上下文预处理] 输入数据结构: {data_dict}")
            
            # 兼容不同的上游数据字段名
            immediate_upstream = data_dict.get('immediate_upstream_results', {})  # 修复：使用正确的字段名
            upstream_outputs = data_dict.get('upstream_outputs', [])
            
            logger.debug(f"🔍 [上下文预处理] immediate_upstream_results类型: {type(immediate_upstream)}, 内容: {immediate_upstream}")
            logger.debug(f"🔍 [上下文预处理] upstream_outputs类型: {type(upstream_outputs)}, 内容: {upstream_outputs}")
            
            # 处理immediate_upstream格式（旧格式）
            if immediate_upstream:
                context_parts.append("\n上游节点信息：")
                
                for node_id, node_data in immediate_upstream.items():
                    logger.trace(f"📋 [上下文预处理] 处理节点 {node_id[:8]}...")
                    logger.trace(f"  - 原始数据类型: {type(node_data)}")
                    logger.trace(f"  - 原始数据内容: {node_data}")
                    
                    # 检查node_data是否已经是字典类型
                    if isinstance(node_data, str):
                        try:
                            node_data = json.loads(node_data)
                            logger.trace(f"  - 解析后数据: {node_data}")
                        except json.JSONDecodeError:
                            logger.warning(f"  ❌ 无法解析节点数据: {node_data[:100]}...")
                            continue
                    elif not isinstance(node_data, dict):
                        logger.warning(f"  ❌ 节点数据类型不正确: {type(node_data)}")
                        continue
                    
                    node_name = node_data.get('node_name', f'节点_{node_id[:8]}')
                    
                    # 检查多种可能的输出字段 - 修复逻辑，确保正确提取数据
                    output_data = None
                    if 'task_result' in node_data:
                        output_data = node_data['task_result']
                    elif 'output_data' in node_data:
                        output_data = node_data['output_data']
                    elif 'result' in node_data:
                        output_data = node_data['result']
                    elif 'task_description' in node_data:
                        output_data = node_data['task_description']
                    
                    logger.trace(f"  - 节点名称: {node_name}")
                    logger.trace(f"  - 输出数据: {output_data}")
                    logger.trace(f"  - 输出数据类型: {type(output_data)}")
                    logger.trace(f"  - 节点完整数据: {node_data}")
                    
                    context_parts.append(f"\n节点：{node_name}")
                   
                    # 输出内容（简化展示）
                    if output_data is not None:
                        if isinstance(output_data, dict):
                            # 对于字典类型，尝试提取最重要的数据
                            context_parts.append("输出数据：")
                            for key, value in output_data.items():
                                formatted_value = self._format_simple_output(value)
                                context_parts.append(f"- {key}: {formatted_value}")
                                logger.trace(f"  - 添加字段 {key}: {formatted_value[:100]}...")
                        else:
                            # 对于简单类型，直接显示
                            formatted_output = self._format_simple_output(output_data)
                            context_parts.append(f"输出数据：{formatted_output}")
                            logger.trace(f"  - 添加输出: {formatted_output}")
                            
                            # 如果是数字，额外提示
                            try:
                                num_value = float(output_data)
                                context_parts.append(f"（这是一个数值：{num_value}）")
                                logger.trace(f"  - 识别为数值: {num_value}")
                            except (ValueError, TypeError):
                                logger.trace(f"  - 非数值类型: {type(output_data)}")
                                pass
                    else:
                        context_parts.append("- 无输出内容")
                        logger.trace(f"  - 该节点无输出内容")
            
            # 处理upstream_outputs格式（新格式）
            elif upstream_outputs and isinstance(upstream_outputs, list):
                context_parts.append("\n上游节点信息：")
                
                for i, upstream_node in enumerate(upstream_outputs):
                    logger.trace(f"📋 [上下文预处理] 处理上游节点 {i+1}...")
                    logger.trace(f"  - 节点数据: {upstream_node}")
                    
                    if isinstance(upstream_node, dict):
                        node_name = upstream_node.get('node_name', f'上游节点_{i+1}')
                        output_data = upstream_node.get('output_data', '')
                        
                        context_parts.append(f"\n节点：{node_name}")
                        
                        if output_data:
                            formatted_output = self._format_simple_output(output_data)
                            context_parts.append(f"输出数据：{formatted_output}")
                            logger.trace(f"  - 添加输出: {formatted_output[:100]}...")
                        else:
                            context_parts.append("- 无输出内容")
                            logger.trace(f"  - 该节点无输出内容")
                    else:
                        logger.warning(f"  ❌ 上游节点数据格式不正确: {upstream_node}")
            else:
                logger.debug(f"🔍 [上下文预处理] 没有找到上游节点信息")
            
            final_context = "\n".join(context_parts) if context_parts else "无上游上下文数据。"
            logger.trace(f"🎯 [上下文预处理] context_parts长度: {len(context_parts)}")
            logger.trace(f"🎯 [上下文预处理] context_parts内容: {context_parts}")
            logger.trace(f"🎯 [上下文预处理] 最终生成的上下文长度: {len(final_context)}")
            logger.trace(f"🎯 [上下文预处理] 最终生成的上下文: {final_context}")
            return final_context
            
        except Exception as e:
            logger.error(f"❌ [上下文预处理] 预处理上游上下文失败: {e}")
            import traceback
            logger.error(f"❌ [上下文预处理] 错误堆栈: {traceback.format_exc()}")
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
    
    async def _build_user_message(self, task: Dict[str, Any], context_info: str, agent: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建用户消息（包含任务标题、上游节点信息和附件内容）
        支持多模态内容传输

        Returns:
            包含text_message、images等的字典
        """
        try:
            message_parts = []

            # 任务标题和描述
            logger.trace(f"上下文信息: {context_info}")
            task_title = task.get('task_title', '未命名任务')
            task_description = task.get('task_description', '') or task.get('description', '')

            message_parts.append(f"任务：{task_title}")
            if task_description and task_description.strip():
                message_parts.append(f"任务描述：{task_description.strip()}")
                logger.debug(f"✅ [消息构建] 添加任务描述: {task_description[:100]}...")
            else:
                logger.debug(f"⚠️ [消息构建] 任务缺少描述信息")

            # 添加上下文信息（上游节点信息）
            # 检查是否有有效的上下文信息
            invalid_context_messages = [
                "无上游上下文数据。",
                "上下文信息处理失败，请基于任务描述进行处理。",
                "上下文信息格式错误，请基于任务描述进行处理。"
            ]

            logger.debug(f"🔍 [消息构建] 检查上下文信息有效性...")
            logger.debug(f"  - context_info存在: {bool(context_info)}")
            logger.debug(f"  - context_info长度: {len(context_info) if context_info else 0}")
            logger.debug(f"  - context_info内容: '{context_info}'")
            logger.debug(f"  - context_info.strip(): '{context_info.strip() if context_info else ''}'")
            logger.debug(f"  - 是否在无效消息列表中: {context_info.strip() in invalid_context_messages if context_info else False}")

            if context_info and context_info.strip() and context_info.strip() not in invalid_context_messages:
                message_parts.append("\n上下文信息：")
                message_parts.append(context_info)
                logger.debug(f"✅ [消息构建] 添加了有效的上下文信息，长度: {len(context_info)}")
            else:
                message_parts.append("\n当前没有上游节点数据。")
                logger.warning(f"⚠️ [消息构建] 上下文信息无效或为空: '{context_info}'")

            # 处理任务附件内容（多模态支持）
            images = []
            try:
                task_id = task.get('task_instance_id')
                if task_id:
                    logger.debug(f"📎 [附件处理] 开始处理任务附件, task_id: {task_id}")
                    attachment_result = await self._process_task_attachments(uuid.UUID(task_id), agent)

                    if attachment_result['has_content']:
                        if attachment_result['text_content']:
                            message_parts.append("\n附件内容：")
                            message_parts.append(attachment_result['text_content'])
                            logger.debug(f"✅ [附件处理] 成功添加附件文本内容，长度: {len(attachment_result['text_content'])}")

                        # 提取图片数据用于多模态传输
                        images = attachment_result.get('images', [])
                        if images:
                            logger.debug(f"📷 [附件处理] 提取到 {len(images)} 个图片用于多模态传输")
                    else:
                        logger.debug(f"ℹ️ [附件处理] 当前任务无附件")
                else:
                    logger.debug(f"⚠️ [附件处理] 任务缺少task_instance_id，跳过附件处理")
            except Exception as e:
                logger.error(f"❌ [附件处理] 处理附件时出错: {e}")
                # 附件处理失败不应该影响主流程
                pass

            text_message = "\n".join(message_parts)

            # 添加用户消息构建完成的日志
            logger.info(f"📝 [消息构建] === 用户消息构建完成 ===")
            logger.info(f"📝 [消息构建] 任务标题: {task_title}")
            logger.info(f"📝 [消息构建] 任务描述: {task_description if task_description else '无'}")
            logger.info(f"📝 [消息构建] 最终用户消息长度: {len(text_message)} 字符")
            logger.info(f"📝 [消息构建] 完整用户消息内容:")
            logger.info(f"--- 开始 ---")
            logger.info(text_message)
            logger.info(f"--- 结束 ---")

            return {
                'text_message': text_message,
                'images': images,
                'has_multimodal_content': bool(images)
            }

        except Exception as e:
            logger.error(f"构建用户消息失败: {e}")
            return {
                'text_message': f"任务：{task.get('task_title', '未知任务')}",
                'images': [],
                'has_multimodal_content': False
            }
    
    async def _process_with_tools(self, agent: Dict[str, Any],
                                openai_request: Dict[str, Any],
                                mcp_tools: List,
                                openai_client: 'OpenAIClient') -> Dict[str, Any]:
        """处理带有工具调用的OpenAI请求"""
        try:
            # 如果没有工具，直接调用普通API
            if not mcp_tools:
                return await openai_client.process_task(openai_request)
            
            logger.trace(f"🔧 [TOOL-PROCESS] 开始处理带工具的请求")
            logger.trace(f"   - 可用工具数量: {len(mcp_tools)}")
            
            # 获取工具配置
            tool_config = {}
            if isinstance(agent, dict):
                tool_config = agent.get('tool_config', {})
            elif hasattr(agent, 'tool_config'):
                tool_config = getattr(agent, 'tool_config', {}) or {}
                
            max_tool_calls = tool_config.get('max_tool_calls', 5) if isinstance(tool_config, dict) else 5
            tool_timeout = tool_config.get('timeout', 30) if isinstance(tool_config, dict) else 30
            
            logger.trace(f"   - 最大工具调用次数: {max_tool_calls}")
            logger.trace(f"   - 工具超时时间: {tool_timeout}秒")
            
            # 创建工具映射表
            tool_map = {tool.name: tool for tool in mcp_tools}
            
            messages = openai_request['messages'].copy()
            tool_call_count = 0
            
            while tool_call_count < max_tool_calls:
                # 调用OpenAI API
                logger.trace(f"🚀 [TOOL-PROCESS] 调用OpenAI API (轮次 {tool_call_count + 1})")
                response = await openai_client.process_task(openai_request)
                
                if not response['success']:
                    return response
                
                ai_response = response['result']
                assistant_message = ai_response.get('message', {})
                
                # 检查是否有工具调用
                tool_calls = assistant_message.get('tool_calls', [])
                
                if not tool_calls:
                    # 没有工具调用，返回最终结果
                    logger.trace(f"✅ [TOOL-PROCESS] 对话完成，无工具调用")
                    return response
                
                logger.trace(f"🔧 [TOOL-PROCESS] 检测到工具调用: {len(tool_calls)} 个")
                
                # 添加助手消息到对话历史
                messages.append({
                    'role': 'assistant',
                    'content': assistant_message.get('content'),
                    'tool_calls': tool_calls
                })
                
                # 执行工具调用
                tool_responses = []
                for tool_call in tool_calls:
                    tool_call_id = tool_call.get('id')
                    function_call = tool_call.get('function', {})
                    tool_name = function_call.get('name')
                    
                    logger.trace(f"🔧 [TOOL-CALL] 调用工具: {tool_name}")
                    
                    if tool_name in tool_map:
                        try:
                            tool = tool_map[tool_name]
                            arguments = json.loads(function_call.get('arguments', '{}'))
                            
                            # 调用MCP工具
                            logger.trace(f"   - 参数: {arguments}")
                            logger.trace(f"🔧 [AGENT-TOOL-CALL] Agent调用工具")
                            logger.trace(f"   - Agent权限已通过get_agent_tools验证")
                            logger.trace(f"   - 跳过用户权限验证，使用系统调用")
                            
                            tool_result = await asyncio.wait_for(
                                mcp_service.call_tool(
                                    tool_name, 
                                    tool.server_name, 
                                    arguments
                                    # 注意：不传递user_id，让系统识别为Agent调用
                                ),
                                timeout=tool_timeout
                            )
                            
                            if tool_result['success']:
                                logger.trace(f"   ✅ 工具调用成功")
                                # 工具结果可能是字符串或对象，统一处理
                                result_data = tool_result['result']
                                if isinstance(result_data, str):
                                    response_content = result_data
                                else:
                                    response_content = json.dumps(result_data)
                            else:
                                logger.warning(f"   ❌ 工具调用失败: {tool_result['error']}")
                                response_content = f"错误: {tool_result['error']}"
                            
                        except asyncio.TimeoutError:
                            logger.warning(f"   ⏰ 工具调用超时: {tool_name}")
                            response_content = f"工具调用超时 ({tool_timeout}秒)"
                        except Exception as e:
                            logger.error(f"   ❌ 工具调用异常: {e}")
                            response_content = f"工具调用异常: {str(e)}"
                    else:
                        logger.warning(f"   ❌ 未找到工具: {tool_name}")
                        response_content = f"未找到工具: {tool_name}"
                    
                    # 添加工具响应
                    tool_responses.append({
                        'role': 'tool',
                        'content': response_content,
                        'tool_call_id': tool_call_id
                    })
                
                # 将工具响应添加到消息历史
                messages.extend(tool_responses)
                
                # 更新请求消息
                openai_request['messages'] = messages
                tool_call_count += 1
                
                logger.trace(f"🔄 [TOOL-PROCESS] 工具调用完成，准备下一轮对话")
            
            # 达到最大工具调用次数
            logger.warning(f"⚠️ [TOOL-PROCESS] 达到最大工具调用次数: {max_tool_calls}")
            
            # 进行最后一次调用获取最终结果
            final_response = await openai_client.process_task(openai_request)
            return final_response
            
        except Exception as e:
            logger.error(f"❌ [TOOL-PROCESS] 工具调用处理失败: {e}")
            import traceback
            logger.error(f"   - 错误堆栈: {traceback.format_exc()}")
            return {
                'success': False,
                'error': f'工具调用处理失败: {str(e)}'
            }

    async def _process_task_attachments(self, task_id: uuid.UUID, agent: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理任务附件，根据agent的能力提取内容
        支持多模态AI的图片base64传输

        Args:
            task_id: 任务实例ID
            agent: Agent信息，包含tags等能力标识

        Returns:
            包含文本内容和图片内容的字典
        """
        try:
            from .file_content_extractor import FileContentExtractor

            logger.debug(f"📎 [附件处理] 开始处理任务附件: {task_id}")

            # 检查agent是否支持多模态
            agent_tags = agent.get('tags', [])
            if isinstance(agent_tags, str):
                import json
                try:
                    agent_tags = json.loads(agent_tags)
                except:
                    agent_tags = []

            supports_multimodal = 'multimodal' in agent_tags or 'vision' in agent_tags
            logger.debug(f"🔍 [附件处理] Agent多模态支持: {supports_multimodal}, 标签: {agent_tags}")

            # 使用支持节点级别附件传递的提取器
            extractor = FileContentExtractor()

            if supports_multimodal:
                # 多模态模式：分别处理文本和图片
                result = await self._extract_multimodal_attachments(extractor, task_id)
            else:
                # 文本模式：所有附件转为文本
                attachments_content = await extractor.extract_task_attachments(task_id)
                result = {
                    'has_content': bool(attachments_content),
                    'text_content': attachments_content,
                    'images': [],
                    'mode': 'text_only'
                }

            if result['has_content']:
                logger.debug(f"✅ [附件处理] 成功处理附件，模式: {result['mode']}")
                if result.get('images'):
                    logger.debug(f"📷 [附件处理] 包含 {len(result['images'])} 个图片")
            else:
                logger.debug(f"📎 [附件处理] 任务 {task_id} 没有附件内容")

            return result

        except Exception as e:
            logger.error(f"❌ [附件处理] 处理附件失败: {e}")
            import traceback
            logger.error(f"   错误堆栈: {traceback.format_exc()}")
            return {
                'has_content': False,
                'text_content': f"附件处理失败: {str(e)}",
                'images': [],
                'mode': 'error'
            }

    async def _extract_multimodal_attachments(self, extractor: 'FileContentExtractor', task_id: uuid.UUID) -> Dict[str, Any]:
        """
        提取多模态附件内容

        Args:
            extractor: 文件内容提取器
            task_id: 任务实例ID

        Returns:
            包含文本和图片的多模态内容
        """
        try:
            # 获取任务的所有附件文件
            from .file_association_service import FileAssociationService
            file_service = FileAssociationService()

            # 1. 首先查询直接关联的任务附件
            task_files = await file_service.get_task_instance_files(task_id)

            # 2. 如果没有直接任务附件，查询节点级别的附件
            if not task_files:
                try:
                    from ..repositories.instance.task_instance_repository import TaskInstanceRepository
                    task_repo = TaskInstanceRepository()
                    task_info = await task_repo.get_task_by_id(task_id)

                    if task_info and task_info.get('node_instance_id'):
                        node_instance_id = task_info['node_instance_id']
                        task_files = await file_service.get_node_instance_files(uuid.UUID(str(node_instance_id)))

                except Exception as e:
                    logger.warning(f"⚠️ [多模态附件] 查询节点附件失败: {e}")

            if not task_files:
                return {
                    'has_content': False,
                    'text_content': '',
                    'images': [],
                    'mode': 'multimodal'
                }

            logger.debug(f"📎 [多模态附件] 找到 {len(task_files)} 个文件")

            text_parts = []
            images = []

            # 处理每个文件
            for file_info in task_files:
                try:
                    file_path = file_info.get('file_path', '')
                    file_name = file_info.get('file_name', '') or file_info.get('original_filename', 'unknown')
                    content_type = file_info.get('content_type', '')

                    logger.debug(f"📄 [多模态附件] 处理文件: {file_name}")

                    if not os.path.exists(file_path):
                        logger.warning(f"⚠️ [多模态附件] 文件不存在: {file_path}")
                        text_parts.append(f"## 文件: {file_name}\n[文件不存在或路径无效]")
                        continue

                    # 使用多模态提取器
                    result = await extractor.extract_content_for_multimodal(file_path, content_type)

                    if result['success']:
                        if result['is_image']:
                            # 图片文件：添加到images列表
                            images.append({
                                'name': file_name,
                                'content_type': result['content_type'],
                                'base64_data': result['content'],
                                'metadata': result.get('metadata', {})
                            })
                            # 在文本中也添加图片引用
                            text_parts.append(f"## 图片: {file_name}\n[图片已以多模态方式处理]")
                        else:
                            # 文本文件：添加到文本内容
                            text_parts.append(f"## 文件: {file_name}\n{result['content']}")

                        logger.debug(f"✅ [多模态附件] 文件 {file_name} 处理成功")
                    else:
                        logger.warning(f"⚠️ [多模态附件] 文件 {file_name} 处理失败: {result.get('error', 'unknown')}")
                        text_parts.append(f"## 文件: {file_name}\n[处理失败: {result.get('error', 'unknown')}]")

                except Exception as e:
                    logger.error(f"❌ [多模态附件] 处理单个文件失败: {e}")
                    text_parts.append(f"## 文件: {file_name if 'file_name' in locals() else 'unknown'}\n[处理异常: {str(e)}]")

            # 整合结果
            text_content = "\n\n".join(text_parts) if text_parts else ""
            has_content = bool(text_content or images)

            logger.info(f"📊 [多模态附件] 处理完成 - 文本: {len(text_content)} 字符, 图片: {len(images)} 个")

            return {
                'has_content': has_content,
                'text_content': text_content,
                'images': images,
                'mode': 'multimodal'
            }

        except Exception as e:
            logger.error(f"❌ [多模态附件] 提取失败: {e}")
            import traceback
            logger.error(f"   错误堆栈: {traceback.format_exc()}")
            return {
                'has_content': False,
                'text_content': f"多模态附件提取失败: {str(e)}",
                'images': [],
                'mode': 'error'
            }

    async def _process_ai_generated_images(self, task_id: uuid.UUID, ai_result: Dict[str, Any], agent: Dict[str, Any]) -> None:
        """
        处理AI生成的图片内容，保存到本地并关联到任务和节点实例

        Args:
            task_id: 任务实例ID
            ai_result: AI响应结果
            agent: Agent信息
        """
        try:
            logger.info(f"🖼️ [AI-IMAGE-SAVE] 开始处理AI生成的图片内容")

            # 检测AI响应中的图片内容
            images_to_save = await self._extract_images_from_ai_response(ai_result)

            if not images_to_save:
                logger.debug(f"📝 [AI-IMAGE-SAVE] AI响应中没有检测到图片内容")
                return

            logger.info(f"🖼️ [AI-IMAGE-SAVE] 检测到 {len(images_to_save)} 个图片")

            # 获取任务信息以便关联到节点实例
            task_info = await self.task_repo.get_task_by_id(task_id)
            node_instance_id = task_info.get('node_instance_id') if task_info else None

            # 获取系统用户ID（用于标记为AI生成）
            system_user_id = await self._get_system_user_id()

            # 保存和关联每个图片
            for i, image_data in enumerate(images_to_save):
                try:
                    logger.info(f"💾 [AI-IMAGE-SAVE] 处理第 {i+1} 个图片")

                    # 保存图片到本地文件系统
                    saved_file_info = await self._save_ai_generated_image(
                        image_data,
                        f"ai_generated_{i+1}",
                        system_user_id
                    )

                    if saved_file_info:
                        logger.info(f"✅ [AI-IMAGE-SAVE] 图片保存成功: {saved_file_info['filename']}")

                        # 创建workflow_file记录
                        file_record = await self._create_workflow_file_record(saved_file_info)

                        if file_record:
                            file_id = uuid.UUID(file_record['file_id'])

                            # 只关联到任务实例 - 移除节点绑定
                            await self._associate_image_to_task(task_id, file_id, system_user_id)

                            logger.info(f"🔗 [AI-IMAGE-SAVE] 图片关联到任务完成: task={task_id}, file={file_id}")
                        else:
                            logger.error(f"❌ [AI-IMAGE-SAVE] 创建文件记录失败")
                    else:
                        logger.error(f"❌ [AI-IMAGE-SAVE] 图片保存失败")

                except Exception as e:
                    logger.error(f"❌ [AI-IMAGE-SAVE] 处理第 {i+1} 个图片失败: {e}")
                    continue

            logger.info(f"🎉 [AI-IMAGE-SAVE] AI生成图片处理完成")

        except Exception as e:
            logger.error(f"❌ [AI-IMAGE-SAVE] 处理AI生成图片失败: {e}")
            import traceback
            logger.error(f"   错误堆栈: {traceback.format_exc()}")

    async def _extract_images_from_ai_response(self, ai_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        从AI响应中提取图片内容

        Args:
            ai_result: AI响应结果

        Returns:
            图片数据列表，每个包含base64_data、content_type等信息
        """
        images = []

        try:
            # 方案1: 检查结果文本中的base64图片
            result_text = ai_result.get('result', '') if isinstance(ai_result, dict) else str(ai_result)

            # 查找base64图片标识
            import re

            # 匹配 data:image/xxx;base64,xxxx 格式
            base64_pattern = r'data:image/([^;]+);base64,([A-Za-z0-9+/=]+)'
            matches = re.findall(base64_pattern, result_text)

            for i, (image_type, base64_data) in enumerate(matches):
                images.append({
                    'base64_data': base64_data,
                    'content_type': f'image/{image_type}',
                    'source': 'inline_base64',
                    'index': i
                })
                logger.debug(f"📷 [IMAGE-EXTRACT] 找到内联base64图片: image/{image_type}")

            # 方案2: 检查是否有专门的图片字段（某些AI可能会单独返回图片）
            if isinstance(ai_result, dict):
                # 检查常见的图片字段名
                image_fields = ['images', 'generated_images', 'image_outputs', 'pictures']
                for field in image_fields:
                    if field in ai_result and ai_result[field]:
                        field_images = ai_result[field]
                        if isinstance(field_images, list):
                            for i, img in enumerate(field_images):
                                if isinstance(img, dict):
                                    images.append({
                                        'base64_data': img.get('data', img.get('base64', '')),
                                        'content_type': img.get('content_type', img.get('format', 'image/png')),
                                        'source': f'field_{field}',
                                        'index': i
                                    })
                                    logger.debug(f"📷 [IMAGE-EXTRACT] 找到字段图片: {field}[{i}]")

            # 方案3: 检查OpenAI风格的工具调用结果（可能包含图片生成）
            if isinstance(ai_result, dict) and 'message' in ai_result:
                message = ai_result['message']
                if isinstance(message, dict) and 'tool_calls' in message:
                    # 这里可以扩展处理特定的图片生成工具调用结果
                    pass

            logger.info(f"🔍 [IMAGE-EXTRACT] 从AI响应中提取到 {len(images)} 个图片")
            return images

        except Exception as e:
            logger.error(f"❌ [IMAGE-EXTRACT] 提取AI响应图片失败: {e}")
            return []

    async def _save_ai_generated_image(self, image_data: Dict[str, Any], base_filename: str,
                                     uploaded_by: uuid.UUID) -> Optional[Dict[str, Any]]:
        """
        保存AI生成的图片到本地文件系统

        Args:
            image_data: 图片数据，包含base64_data、content_type等
            base_filename: 基础文件名
            uploaded_by: 上传者ID

        Returns:
            保存的文件信息字典
        """
        try:
            import base64
            import os
            from pathlib import Path
            import hashlib
            from datetime import datetime

            base64_data = image_data.get('base64_data', '')
            content_type = image_data.get('content_type', 'image/png')

            if not base64_data:
                logger.error(f"❌ [AI-IMAGE-SAVE] 图片数据为空")
                return None

            # 确定文件扩展名
            type_map = {
                'image/png': '.png',
                'image/jpeg': '.jpg',
                'image/jpg': '.jpg',
                'image/gif': '.gif',
                'image/webp': '.webp',
                'image/bmp': '.bmp'
            }
            file_ext = type_map.get(content_type, '.png')

            # 生成唯一文件名
            unique_id = str(uuid.uuid4())
            filename = f"{base_filename}_{unique_id}{file_ext}"

            # 确保上传目录存在
            from ..config.settings import get_settings
            settings = get_settings()
            upload_root = Path(settings.upload_root_dir if hasattr(settings, 'upload_root_dir') else "./uploads")

            now = datetime.now()
            date_path = upload_root / str(now.year) / f"{now.month:02d}" / f"{now.day:02d}"
            date_path.mkdir(parents=True, exist_ok=True)

            file_path = date_path / filename

            # 解码并保存图片
            try:
                image_bytes = base64.b64decode(base64_data)
            except Exception as e:
                logger.error(f"❌ [AI-IMAGE-SAVE] Base64解码失败: {e}")
                return None

            # 写入文件
            with open(file_path, 'wb') as f:
                f.write(image_bytes)

            # 计算文件哈希
            hash_sha256 = hashlib.sha256()
            hash_sha256.update(image_bytes)
            file_hash = hash_sha256.hexdigest()

            file_size = len(image_bytes)

            logger.info(f"💾 [AI-IMAGE-SAVE] 图片保存成功: {filename} ({file_size} bytes)")

            return {
                'filename': filename,
                'original_filename': f"{base_filename}_ai_generated{file_ext}",
                'file_path': str(file_path),
                'file_size': file_size,
                'content_type': content_type,
                'file_hash': file_hash,
                'uploaded_by': uploaded_by
            }

        except Exception as e:
            logger.error(f"❌ [AI-IMAGE-SAVE] 保存AI图片失败: {e}")
            return None

    async def _create_workflow_file_record(self, file_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        创建workflow_file数据库记录

        Args:
            file_info: 文件信息字典

        Returns:
            创建的文件记录
        """
        try:
            from .file_association_service import FileAssociationService
            from ..models.file_attachment import WorkflowFileCreate

            file_service = FileAssociationService()

            # 创建文件记录对象
            file_create = WorkflowFileCreate(
                filename=file_info['filename'],
                original_filename=file_info['original_filename'],
                file_path=file_info['file_path'],
                file_size=file_info['file_size'],
                content_type=file_info['content_type'],
                file_hash=file_info['file_hash'],
                uploaded_by=file_info['uploaded_by']
            )

            # 创建数据库记录
            file_record = await file_service.create_workflow_file(file_create)

            if file_record:
                logger.info(f"✅ [AI-IMAGE-SAVE] 文件记录创建成功: {file_record['file_id']}")
                return file_record
            else:
                logger.error(f"❌ [AI-IMAGE-SAVE] 文件记录创建失败")
                return None

        except Exception as e:
            logger.error(f"❌ [AI-IMAGE-SAVE] 创建文件记录失败: {e}")
            return None

    async def _associate_image_to_task(self, task_id: uuid.UUID, file_id: uuid.UUID,
                                     uploaded_by: uuid.UUID) -> bool:
        """
        关联图片到任务实例

        Args:
            task_id: 任务实例ID
            file_id: 文件ID
            uploaded_by: 上传者ID

        Returns:
            是否成功关联
        """
        try:
            from .file_association_service import FileAssociationService
            from ..models.file_attachment import AttachmentType

            file_service = FileAssociationService()

            # 关联为输出附件
            success = await file_service.associate_task_instance_file(
                task_id,
                file_id,
                uploaded_by,
                AttachmentType.OUTPUT
            )

            if success:
                logger.info(f"✅ [AI-IMAGE-SAVE] 图片关联到任务成功: task={task_id}, file={file_id}")
            else:
                logger.error(f"❌ [AI-IMAGE-SAVE] 图片关联到任务失败: task={task_id}, file={file_id}")

            return success

        except Exception as e:
            logger.error(f"❌ [AI-IMAGE-SAVE] 关联图片到任务失败: {e}")
            return False

    async def _associate_image_to_node_instance(self, node_instance_id: uuid.UUID,
                                              file_id: uuid.UUID) -> bool:
        """
        关联图片到节点实例

        Args:
            node_instance_id: 节点实例ID
            file_id: 文件ID

        Returns:
            是否成功关联
        """
        try:
            from .file_association_service import FileAssociationService
            from ..models.file_attachment import AttachmentType

            file_service = FileAssociationService()

            # 关联为输出附件
            success = await file_service.associate_node_instance_file(
                node_instance_id,
                file_id,
                AttachmentType.OUTPUT
            )

            if success:
                logger.info(f"✅ [AI-IMAGE-SAVE] 图片关联到节点实例成功: node={node_instance_id}, file={file_id}")
            else:
                logger.error(f"❌ [AI-IMAGE-SAVE] 图片关联到节点实例失败: node={node_instance_id}, file={file_id}")

            return success

        except Exception as e:
            logger.error(f"❌ [AI-IMAGE-SAVE] 关联图片到节点实例失败: {e}")
            return False

    async def _get_system_user_id(self) -> uuid.UUID:
        """
        获取系统用户ID，用于标记AI生成的文件

        Returns:
            系统用户ID
        """
        try:
            # 查询系统用户
            system_user_query = """
                SELECT user_id FROM user
                WHERE username = 'system' OR username = 'ai_agent'
                LIMIT 1
            """

            result = await self.task_repo.db.fetch_one(system_user_query)

            if result:
                return uuid.UUID(str(result['user_id']))
            else:
                # 如果没有系统用户，创建一个
                logger.warning(f"⚠️ [AI-IMAGE-SAVE] 未找到系统用户，创建默认系统用户")
                return await self._create_system_user()

        except Exception as e:
            logger.error(f"❌ [AI-IMAGE-SAVE] 获取系统用户ID失败: {e}")
            # 返回一个默认的UUID
            return uuid.UUID('00000000-0000-0000-0000-000000000001')

    async def _create_system_user(self) -> uuid.UUID:
        """
        创建系统用户

        Returns:
            系统用户ID
        """
        try:
            system_user_id = uuid.uuid4()

            create_user_query = """
                INSERT INTO user (user_id, username, email, password_hash, status, created_at, updated_at)
                VALUES (%s, 'ai_agent', 'ai@system.local', 'system_generated', 1, NOW(), NOW())
                ON DUPLICATE KEY UPDATE user_id = user_id
            """

            await self.task_repo.db.execute(create_user_query, system_user_id)

            logger.info(f"✅ [AI-IMAGE-SAVE] 系统用户创建成功: {system_user_id}")
            return system_user_id

        except Exception as e:
            logger.error(f"❌ [AI-IMAGE-SAVE] 创建系统用户失败: {e}")
            # 返回一个默认的UUID
            return uuid.UUID('00000000-0000-0000-0000-000000000001')

    def _is_image_generation_request(self, user_message: str) -> bool:
        """
        检测用户消息是否为图像生成请求

        Args:
            user_message: 用户消息内容

        Returns:
            是否为图像生成请求
        """
        # 图像生成关键词
        image_keywords = [
            '生成图片', '生成图像', '画', '画一个', '画一张', '绘制', '创建图片', '创建图像',
            'generate image', 'generate picture', 'create image', 'draw', 'paint',
            '制作图片', '生成', '图片', '图像', 'picture', 'image'
        ]

        # 转换为小写进行匹配
        message_lower = user_message.lower()

        # 检查是否包含图像生成关键词
        for keyword in image_keywords:
            if keyword in message_lower:
                logger.debug(f"🔍 [IMAGE-DETECT] 匹配到关键词: {keyword}")
                return True

        return False

    async def _handle_image_generation(self, user_message: str, agent: Dict[str, Any],
                                     task_id: uuid.UUID = None, task_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        处理图像生成请求

        Args:
            user_message: 用户消息
            agent: Agent信息
            task_id: 任务ID（用于关联生成的图片）
            task_metadata: 任务元数据（包含任务标题和描述）

        Returns:
            图像生成结果
        """
        try:
            from ..utils.openai_client import openai_client

            logger.info(f"🎨 [IMAGE-GEN] 开始处理图像生成请求")
            logger.info(f"🎨 [IMAGE-GEN] === PROMPT处理流程 ===")
            logger.info(f"🎨 [IMAGE-GEN] 1. 原始用户输入: {user_message}")
            logger.info(f"🎨 [IMAGE-GEN] 2. 任务元数据: {task_metadata}")

            # 提取图像描述提示
            image_prompt = self._extract_image_prompt(user_message)
            logger.info(f"🎨 [IMAGE-GEN] 3. 提取后的基础提示: {image_prompt}")

            # 增强提示：加入任务上下文信息
            if task_metadata:
                task_title = task_metadata.get('task_title', '')
                task_description = task_metadata.get('task_description', '')

                logger.info(f"🎨 [IMAGE-GEN] 4. 任务上下文信息:")
                logger.info(f"   - 任务标题: {task_title}")
                logger.info(f"   - 任务描述: {task_description}")

                if task_title or task_description:
                    context_parts = []
                    if task_title:
                        context_parts.append(f"任务：{task_title}")
                    if task_description:
                        context_parts.append(f"描述：{task_description}")

                    context_info = "，".join(context_parts)
                    enhanced_prompt = f"{image_prompt}。任务背景：{context_info}"

                    logger.info(f"🎨 [IMAGE-GEN] 5. 增强后的最终提示: {enhanced_prompt}")
                    image_prompt = enhanced_prompt
                else:
                    logger.info(f"🎨 [IMAGE-GEN] 5. 无任务上下文，使用基础提示: {image_prompt}")
            else:
                logger.info(f"🎨 [IMAGE-GEN] 4. 无任务元数据，使用基础提示: {image_prompt}")
            logger.info(f"🎨 [IMAGE-GEN] === API调用准备 ===")
            logger.info(f"🎨 [IMAGE-GEN] 6. 发送到图像生成API的最终prompt: {image_prompt}")

            # 调用图像生成API
            image_result = await openai_client.generate_image(
                prompt=image_prompt,
                model="black-forest-labs/FLUX.1-schnell",  # SiliconFlow支持的模型
                size="1024x1024",
                quality="standard",
                n=1
            )

            if image_result['success']:
                logger.info(f"✅ [IMAGE-GEN] 图像生成成功")

                # 下载并保存生成的图片
                saved_images = await self._download_and_save_images(
                    image_result.get('images', []),
                    task_id,
                    image_prompt
                )

                # 构建响应消息
                response_content = f"我为您生成了图像：\n\n描述：{image_prompt}\n\n"

                if saved_images:
                    response_content += f"已保存 {len(saved_images)} 张图片到本地。\n"
                    for i, saved_img in enumerate(saved_images):
                        response_content += f"图片 {i+1}: {saved_img['filename']}\n"
                else:
                    # 如果保存失败，仍显示原始URL或Base64
                    if 'images' in image_result and image_result['images']:
                        first_image = image_result['images'][0]
                        if 'url' in first_image:
                            response_content += f"图像链接：{first_image['url']}\n\n"
                            response_content += "注意：图像链接有效期为1小时，请及时保存。"
                        elif 'b64_json' in first_image:
                            response_content += f"data:image/png;base64,{first_image['b64_json']}"

                return {
                    'success': True,
                    'content': response_content,
                    'image_data': image_result.get('images', []),
                    'saved_images': saved_images,
                    'prompt': image_prompt,
                    'model': image_result.get('model', 'unknown'),
                    'usage': {'total_tokens': 100}  # 估算
                }
            else:
                logger.error(f"❌ [IMAGE-GEN] 图像生成失败: {image_result.get('error')}")
                return {
                    'success': False,
                    'error': f"图像生成失败: {image_result.get('error')}",
                    'content': '抱歉，图像生成过程中出现了错误，请稍后再试。'
                }

        except Exception as e:
            logger.error(f"❌ [IMAGE-GEN] 处理图像生成请求失败: {e}")
            import traceback
            logger.error(f"   错误堆栈: {traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e),
                'content': '抱歉，图像生成功能暂时不可用，请稍后再试。'
            }

    def _extract_image_prompt(self, user_message: str) -> str:
        """
        从用户消息中提取图像描述提示

        Args:
            user_message: 用户消息

        Returns:
            图像描述提示
        """
        logger.info(f"🔍 [PROMPT-EXTRACT] === 提示词提取过程 ===")
        logger.info(f"🔍 [PROMPT-EXTRACT] 原始输入: {user_message}")

        # 移除常见的指令词
        prompt_text = user_message

        # 移除指令性词汇
        remove_patterns = [
            r'生成图片.*?[:：]\s*',
            r'生成图像.*?[:：]\s*',
            r'画.*?[:：]\s*',
            r'绘制.*?[:：]\s*',
            r'create\s+image.*?[:：]\s*',
            r'generate\s+image.*?[:：]\s*',
            r'请.*?画',
            r'请.*?生成',
            r'帮我.*?画',
            r'帮我.*?生成'
        ]

        import re
        for i, pattern in enumerate(remove_patterns):
            before = prompt_text
            prompt_text = re.sub(pattern, '', prompt_text, flags=re.IGNORECASE)
            if before != prompt_text:
                logger.info(f"🔍 [PROMPT-EXTRACT] 规则 {i+1} 匹配: {pattern}")
                logger.info(f"   - 处理前: {before}")
                logger.info(f"   - 处理后: {prompt_text}")

        # 清理多余的空白字符
        cleaned_prompt = prompt_text.strip()
        logger.info(f"🔍 [PROMPT-EXTRACT] 清理空白字符后: {cleaned_prompt}")

        # 如果提取后为空，使用默认提示
        if not cleaned_prompt:
            cleaned_prompt = "生成一个图像"
            logger.info(f"🔍 [PROMPT-EXTRACT] 提取结果为空，使用默认提示: {cleaned_prompt}")

        logger.info(f"🔍 [PROMPT-EXTRACT] 最终提取结果: {cleaned_prompt}")
        return cleaned_prompt

    async def _download_and_save_images(self, images: List[Dict[str, Any]],
                                      task_id: uuid.UUID = None,
                                      prompt: str = "") -> List[Dict[str, Any]]:
        """
        下载并保存图片到本地，支持URL和Base64格式

        Args:
            images: 图片数据列表
            task_id: 任务ID
            prompt: 图片生成提示

        Returns:
            保存的图片信息列表
        """
        saved_images = []

        try:
            for i, image_data in enumerate(images):
                try:
                    logger.info(f"📥 [IMAGE-SAVE] 处理第 {i+1} 张图片")

                    # 确定图片来源和数据
                    image_bytes = None
                    original_url = None
                    content_type = 'image/png'  # 默认格式

                    if 'url' in image_data:
                        # URL格式 - 需要下载
                        original_url = image_data['url']
                        logger.info(f"🌐 [IMAGE-SAVE] 从URL下载图片: {original_url[:100]}...")
                        image_bytes = await self._download_image_from_url(original_url)
                        if not image_bytes:
                            logger.error(f"❌ [IMAGE-SAVE] URL图片下载失败")
                            continue

                    elif 'b64_json' in image_data:
                        # Base64格式
                        logger.info(f"📄 [IMAGE-SAVE] 处理Base64图片数据")
                        image_bytes = await self._decode_base64_image(image_data['b64_json'])
                        if not image_bytes:
                            logger.error(f"❌ [IMAGE-SAVE] Base64图片解码失败")
                            continue

                    else:
                        logger.warning(f"⚠️ [IMAGE-SAVE] 图片数据格式不支持: {list(image_data.keys())}")
                        continue

                    # 检测图片格式并转换为标准格式
                    image_format, processed_bytes = await self._process_image_format(image_bytes)
                    if not processed_bytes:
                        logger.error(f"❌ [IMAGE-SAVE] 图片格式处理失败")
                        continue

                    # 保存图片到本地
                    saved_info = await self._save_image_to_local(
                        processed_bytes,
                        image_format,
                        f"generated_{i+1}",
                        prompt
                    )

                    if saved_info:
                        # 关联到任务和节点
                        if task_id:
                            await self._associate_saved_image_to_task(saved_info, task_id)

                        saved_info['original_url'] = original_url
                        saved_info['index'] = i
                        saved_images.append(saved_info)
                        logger.info(f"✅ [IMAGE-SAVE] 图片 {i+1} 保存成功: {saved_info['filename']}")
                    else:
                        logger.error(f"❌ [IMAGE-SAVE] 图片 {i+1} 保存失败")

                except Exception as e:
                    logger.error(f"❌ [IMAGE-SAVE] 处理第 {i+1} 张图片失败: {e}")
                    continue

            logger.info(f"🎉 [IMAGE-SAVE] 图片保存完成，成功保存 {len(saved_images)} 张")
            return saved_images

        except Exception as e:
            logger.error(f"❌ [IMAGE-SAVE] 图片保存过程失败: {e}")
            import traceback
            logger.error(f"   错误堆栈: {traceback.format_exc()}")
            return []

    async def _download_image_from_url(self, url: str) -> Optional[bytes]:
        """
        从URL下载图片

        Args:
            url: 图片URL

        Returns:
            图片字节数据
        """
        try:
            import aiohttp
            import asyncio

            logger.debug(f"🌐 [URL-DOWNLOAD] 开始下载图片: {url}")

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        image_bytes = await response.read()
                        logger.info(f"✅ [URL-DOWNLOAD] 图片下载成功，大小: {len(image_bytes)} bytes")
                        return image_bytes
                    else:
                        logger.error(f"❌ [URL-DOWNLOAD] HTTP错误: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"❌ [URL-DOWNLOAD] 下载图片失败: {e}")
            return None

    async def _decode_base64_image(self, b64_data: str) -> Optional[bytes]:
        """
        解码Base64图片数据

        Args:
            b64_data: Base64编码的图片数据

        Returns:
            图片字节数据
        """
        try:
            import base64

            logger.debug(f"📄 [BASE64-DECODE] 开始解码Base64数据，长度: {len(b64_data)}")

            # 移除可能的data URL前缀
            if b64_data.startswith('data:'):
                if ',' in b64_data:
                    b64_data = b64_data.split(',', 1)[1]

            image_bytes = base64.b64decode(b64_data)
            logger.info(f"✅ [BASE64-DECODE] Base64解码成功，大小: {len(image_bytes)} bytes")
            return image_bytes

        except Exception as e:
            logger.error(f"❌ [BASE64-DECODE] Base64解码失败: {e}")
            return None

    async def _process_image_format(self, image_bytes: bytes) -> tuple:
        """
        处理图片格式，转换为JPG或PNG

        Args:
            image_bytes: 原始图片字节

        Returns:
            (格式名称, 处理后的字节数据)
        """
        try:
            from PIL import Image
            import io

            logger.debug(f"🔄 [FORMAT-PROCESS] 开始处理图片格式")

            # 加载图片
            with Image.open(io.BytesIO(image_bytes)) as img:
                # 检测原始格式
                original_format = img.format
                logger.debug(f"   - 原始格式: {original_format}")

                # 转换为RGB模式（去除透明度）
                if img.mode in ('RGBA', 'LA', 'P'):
                    # 有透明度，保存为PNG
                    target_format = 'PNG'
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                else:
                    # 无透明度，保存为JPG（更小的文件）
                    target_format = 'JPEG'
                    if img.mode != 'RGB':
                        img = img.convert('RGB')

                # 保存处理后的图片
                output_buffer = io.BytesIO()
                if target_format == 'JPEG':
                    img.save(output_buffer, format='JPEG', quality=95, optimize=True)
                    file_ext = 'jpg'
                else:
                    img.save(output_buffer, format='PNG', optimize=True)
                    file_ext = 'png'

                processed_bytes = output_buffer.getvalue()

                logger.info(f"✅ [FORMAT-PROCESS] 格式处理完成: {original_format} -> {target_format}")
                logger.info(f"   - 原始大小: {len(image_bytes)} bytes")
                logger.info(f"   - 处理后大小: {len(processed_bytes)} bytes")

                return file_ext, processed_bytes

        except Exception as e:
            logger.error(f"❌ [FORMAT-PROCESS] 图片格式处理失败: {e}")
            # 如果处理失败，返回原始数据和默认格式
            return 'png', image_bytes

    async def _save_image_to_local(self, image_bytes: bytes, file_ext: str,
                                 base_name: str, prompt: str = "") -> Optional[Dict[str, Any]]:
        """
        保存图片到本地文件系统

        Args:
            image_bytes: 图片字节数据
            file_ext: 文件扩展名
            base_name: 基础文件名
            prompt: 图片描述

        Returns:
            保存的文件信息
        """
        try:
            import os
            from pathlib import Path
            import hashlib
            from datetime import datetime

            logger.debug(f"💾 [LOCAL-SAVE] 开始保存图片到本地")

            # 生成唯一文件名
            unique_id = str(uuid.uuid4())
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{base_name}_{timestamp}_{unique_id[:8]}.{file_ext}"

            # 创建保存目录
            upload_root = Path("uploads")
            now = datetime.now()
            date_path = upload_root / str(now.year) / f"{now.month:02d}" / f"{now.day:02d}"
            date_path.mkdir(parents=True, exist_ok=True)

            file_path = date_path / filename

            # 写入文件
            with open(file_path, 'wb') as f:
                f.write(image_bytes)

            # 计算文件哈希
            hash_sha256 = hashlib.sha256()
            hash_sha256.update(image_bytes)
            file_hash = hash_sha256.hexdigest()

            file_size = len(image_bytes)

            logger.info(f"💾 [LOCAL-SAVE] 图片保存成功: {filename} ({file_size} bytes)")

            # 获取系统用户ID
            system_user_id = await self._get_system_user_id()

            return {
                'filename': filename,
                'original_filename': f"{base_name}_ai_generated.{file_ext}",
                'file_path': str(file_path),
                'content_type': f'image/{file_ext}',
                'file_size': file_size,
                'file_hash': file_hash,
                'uploaded_by': system_user_id,
                'description': prompt[:200] if prompt else f"AI生成的图片: {base_name}",
                'tags': ['ai-generated', 'image-generation']
            }

        except Exception as e:
            logger.error(f"❌ [LOCAL-SAVE] 保存图片到本地失败: {e}")
            return None

    async def _associate_saved_image_to_task(self, image_info: Dict[str, Any],
                                           task_id: uuid.UUID) -> bool:
        """
        关联保存的图片到任务和节点

        Args:
            image_info: 图片信息
            task_id: 任务ID

        Returns:
            是否成功关联
        """
        try:
            logger.info(f"🔗 [IMAGE-ASSOC] 开始关联图片到任务: {task_id}")

            # 创建workflow_file记录
            file_record = await self._create_workflow_file_record(image_info)
            if not file_record:
                logger.error(f"❌ [IMAGE-ASSOC] 创建文件记录失败")
                return False

            file_id = uuid.UUID(file_record['file_id'])
            system_user_id = image_info['uploaded_by']

            # 关联到任务实例
            task_success = await self._associate_image_to_task(task_id, file_id, system_user_id)

            # 只关联到任务实例 - 移除节点绑定
            if task_success:
                logger.info(f"✅ [IMAGE-ASSOC] 图片关联成功: file={file_id}, task={task_id}")
            else:
                logger.error(f"❌ [IMAGE-ASSOC] 图片关联失败")

            return task_success

        except Exception as e:
            logger.error(f"❌ [IMAGE-ASSOC] 关联图片到任务失败: {e}")
            return False

# 全局Agent任务服务实例
agent_task_service = AgentTaskService()