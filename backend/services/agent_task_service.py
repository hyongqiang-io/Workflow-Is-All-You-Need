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
            logger.trace(f"full task:{task}")
            task_input_data = task.get('input_data', '')
            task_context_data = task.get('context_data', '')
            
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
                        logger.trace(f"   - 从节点实例获取输入数据: {len(node_input_data)} 字符")
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
            user_message = self._build_user_message(task, context_info)
            logger.trace(f"   - 用户消息长度: {len(user_message)} 字符")
            logger.trace(f"   - 用户消息预览: {user_message[:200]}...")
        
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
            
            logger.trace(f"📦 [AGENT-PROCESS] AI Client数据准备完成:")
            logger.trace(f"   - 任务ID: {ai_client_data['task_id']}")
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
            logger.trace(f"🚀 [OPENAI-FORMAT] 使用OpenAI规范处理任务: {task_title}")
            
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
                    
                    mcp_tools = await mcp_service.get_agent_tools(agent_id)
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
            
            # 获取Base URL和API Key（兼容字典和对象）
            base_url = 'default'
            has_api_key = False
            if isinstance(agent, dict):
                base_url = agent.get('base_url', 'default')
                has_api_key = bool(agent.get('api_key'))
            elif hasattr(agent, 'base_url'):
                base_url = getattr(agent, 'base_url', 'default')
                has_api_key = bool(getattr(agent, 'api_key', None))
                
            logger.trace(f"   - Base URL: {base_url}")
            logger.trace(f"   - API Key存在: {'是' if has_api_key else '否'}")
            logger.trace(f" 系统消息：{openai_request['messages'][0]['content']}")
            logger.trace(f" 用户消息：{openai_request['messages'][1]['content']}")
            
            # 设置超时时间（防止卡死）
            try:
                openai_result = await asyncio.wait_for(
                    self._process_with_tools(agent, openai_request, mcp_tools),
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
            immediate_upstream = data_dict.get('immediate_upstream', {})
            upstream_outputs = data_dict.get('upstream_outputs', [])
            
            logger.debug(f"🔍 [上下文预处理] immediate_upstream类型: {type(immediate_upstream)}, 内容: {immediate_upstream}")
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
    
    def _build_user_message(self, task: Dict[str, Any], context_info: str) -> str:
        """构建用户消息（包含任务标题和上游节点信息）"""
        try:
            message_parts = []
            
            # 任务标题
            logger.trace(f"上下文信息: {context_info}")
            task_title = task.get('task_title', '未命名任务')
            message_parts.append(f"任务：{task_title}")
            
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
            
            return "\n".join(message_parts)
            
        except Exception as e:
            logger.error(f"构建用户消息失败: {e}")
            return f"任务：{task.get('task_title', '未知任务')}"
    
    async def _process_with_tools(self, agent: Dict[str, Any], 
                                openai_request: Dict[str, Any], 
                                mcp_tools: List) -> Dict[str, Any]:
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
                            tool_result = await asyncio.wait_for(
                                mcp_service.call_tool(tool_name, tool.server_name, arguments),
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


# 全局Agent任务服务实例
agent_task_service = AgentTaskService()