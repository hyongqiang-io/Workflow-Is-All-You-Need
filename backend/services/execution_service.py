"""
工作流执行引擎服务
Workflow Execution Engine Service
"""

import uuid
import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import sys
from loguru import logger
logger.remove()
logger.add(sys.stderr,level="WARNING")

from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
from ..repositories.instance.task_instance_repository import TaskInstanceRepository
from ..repositories.workflow.workflow_repository import WorkflowRepository
from ..repositories.node.node_repository import NodeRepository
from ..repositories.processor.processor_repository import ProcessorRepository
from ..repositories.user.user_repository import UserRepository
from ..repositories.agent.agent_repository import AgentRepository
from ..models.instance import (
    WorkflowInstanceCreate, WorkflowInstanceUpdate, WorkflowInstanceStatus,
    TaskInstanceCreate, TaskInstanceUpdate, TaskInstanceStatus, TaskInstanceType,
    WorkflowExecuteRequest
)
from ..models.node import NodeType
from ..utils.helpers import now_utc
from .agent_task_service import agent_task_service
from .resource_cleanup_manager import ResourceCleanupManager

# 使用新的统一上下文管理器
from .workflow_execution_context import get_context_manager, WorkflowExecutionContext

def _json_serializer(obj):
    """自定义JSON序列化函数，处理datetime对象"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


class ExecutionEngine:
    """工作流执行引擎 - 简化版本
    
    负责：
    - 工作流实例的启动和管理
    - 节点实例的创建和执行
    - 任务实例的创建和调度
    - 工作流状态的统一管理
    """
    
    def __init__(self):
        # 数据访问层
        self.workflow_instance_repo = WorkflowInstanceRepository()
        self.task_instance_repo = TaskInstanceRepository()
        self.workflow_repo = WorkflowRepository()
        self.node_repo = NodeRepository()
        self.processor_repo = ProcessorRepository()
        self.user_repo = UserRepository()
        self.agent_repo = AgentRepository()
        
        # 执行队列和状态跟踪
        self.execution_queue = asyncio.Queue()
        self.running_instances = {}  # 运行中的实例跟踪
        self.is_running = False
        
        # 任务完成回调映射
        self.task_callbacks = {}
        
        # 系统组件
        self.resource_cleanup_manager = ResourceCleanupManager()
        
        # 上下文管理器 - 使用新的统一架构
        self.context_manager = get_context_manager()
        
        # 监听器跟踪
        self.active_monitors = set()
        
        logger.debug("🚀 初始化ExecutionEngine")
    
    async def start_engine(self):
        """启动执行引擎"""
        if self.is_running:
            logger.warning("执行引擎已在运行中")
            return
        
        self.is_running = True
        logger.trace("工作流执行引擎启动")
        
        # 向下兼容检查 - 确保context_manager已正确初始化
        if self.context_manager is None:
            logger.error("上下文管理器未正确初始化")
            raise RuntimeError("上下文管理器未正确初始化")
        
        # 注册上下文管理器的回调
        self.context_manager.register_completion_callback(self._on_nodes_ready_to_execute)
        
        # 注册为AgentTaskService的回调监听器
        agent_task_service.register_completion_callback(self)
        logger.trace("已注册回调监听器")
        
        # 启动任务处理协程
        asyncio.create_task(self._process_execution_queue())
        asyncio.create_task(self._monitor_running_instances())
    
    async def stop_engine(self):
        """停止执行引擎"""
        self.is_running = False
        
        # 停止资源清理管理器
        if self.resource_cleanup_manager:
            await self.resource_cleanup_manager.stop_manager()
        
        logger.trace("工作流执行引擎停止")
    
    async def execute_workflow(self, request: WorkflowExecuteRequest, 
                             executor_id: uuid.UUID) -> Dict[str, Any]:
        """执行工作流"""
        try:
            logger.trace(f"开始执行工作流: {request.workflow_base_id}, 执行者: {executor_id}")
            # 1. 验证工作流是否存在且可执行
            logger.trace(f"步骤1: 查询工作流 {request.workflow_base_id}")
            workflow = await self.workflow_repo.get_workflow_by_base_id(request.workflow_base_id)
            if not workflow:
                logger.error(f"工作流不存在: {request.workflow_base_id}")
                raise ValueError("工作流不存在")
            
            # 🔧 修复：使用具体的workflow_id而不是base_id
            workflow_id = workflow['workflow_id']
            logger.trace(f"✅ 工作流查询成功: {workflow.get('name', 'Unknown')} (版本ID: {workflow_id})")
            
            # 1.5. 检查是否已有正在运行的实例
            logger.trace(f"步骤1.5: 检查是否已有正在运行的工作流实例")
            existing_instances = await self._check_running_instances(request.workflow_base_id, executor_id)
            if existing_instances:
                logger.trace(f"✅ 发现已有正在运行的实例: {len(existing_instances)} 个")
                latest_instance = existing_instances[0]  # 获取最新的实例
                logger.trace(f"返回现有实例: {latest_instance['workflow_instance_name']} (ID: {latest_instance['workflow_instance_id']})")
                return {
                    'instance_id': latest_instance['workflow_instance_id'],
                    'status': latest_instance['status'],
                    'message': '工作流已在运行中，返回现有实例'
                }
            
            # 2. 创建工作流实例
            logger.trace(f"步骤2: 创建工作流实例 '{request.workflow_instance_name}'")
            instance_data = WorkflowInstanceCreate(
                workflow_base_id=request.workflow_base_id,
                executor_id=executor_id,
                workflow_instance_name=request.workflow_instance_name,
                input_data=request.input_data,
                context_data=request.context_data
            )
            
            instance = await self.workflow_instance_repo.create_instance(instance_data)
            if not instance:
                logger.error("创建工作流实例失败")
                raise RuntimeError("创建工作流实例失败")
            
            instance_id = instance['workflow_instance_id']
            logger.trace(f"✅ 工作流实例创建成功: {request.workflow_instance_name} (ID: {instance_id})")
            
            # 3. 获取工作流的所有节点（使用具体版本ID）
            logger.trace(f"步骤3: 查询工作流版本 {workflow_id} 的所有节点")
            nodes = await self._get_workflow_nodes_by_version_id(workflow_id)
            
            if not nodes:
                logger.error(f"工作流没有节点: {workflow_id}")
                raise ValueError("工作流没有节点")
            
            logger.trace(f"✅ 找到 {len(nodes)} 个节点:")
            for i, node in enumerate(nodes, 1):
                logger.trace(f"   节点{i}: {node['name']} (类型: {node['type']}, 具体ID: {node['node_id']})")
            
            # 4. 获取节点连接关系
            logger.trace(f"步骤4: 查询工作流节点连接关系")
            connections = []
            try:
                if hasattr(self.node_repo, 'get_workflow_connections'):
                    connections = await self.node_repo.get_workflow_connections(request.workflow_base_id)
                    logger.trace(f"✅ 找到 {len(connections)} 个连接:")
                    for i, conn in enumerate(connections, 1):
                        logger.trace(f"   连接{i}: {conn.get('from_node_name', 'Unknown')} -> {conn.get('to_node_name', 'Unknown')}")
                else:
                    logger.warning("节点仓库不支持获取连接关系")
            except Exception as e:
                logger.warning(f"获取工作流连接失败: {e}")
                connections = []
            
            # 5. 初始化工作流上下文
            logger.trace(f"步骤5: 初始化工作流上下文")
            try:
                await self.context_manager.initialize_workflow_context(instance_id)
                logger.trace(f"✅ 工作流上下文初始化成功")
            except Exception as e:
                logger.error(f"工作流上下文初始化失败: {e}")
                raise
            
            # 6. 创建节点实例和注册依赖关系（不创建任务实例）
            logger.trace(f"步骤6: 创建节点实例和依赖关系")
            try:
                await self._create_node_instances_with_dependencies(instance_id, workflow_id, nodes)
                logger.trace(f"✅ 节点实例和依赖关系创建完成")
            except Exception as e:
                logger.error(f"创建节点实例和依赖关系失败: {e}")
                raise
            
            # 7. 启动执行（只启动START节点）
            logger.trace(f"步骤7: 启动工作流执行")
            try:
                await self._start_workflow_execution_with_dependencies(instance_id, workflow_id)
                logger.trace(f"✅ 工作流执行启动完成")
                
                # 输出执行启动的完整状态
                print(f"\n🚀 【工作流启动成功】")
                print(f"工作流: {workflow.get('name', 'Unknown')}")
                print(f"实例名称: {request.workflow_instance_name}")
                print(f"实例ID: {instance_id} - 新架构")
                print(f"执行者: {executor_id}")
                print(f"节点数量: {len(nodes)}")
                print(f"状态: RUNNING")
                print(f"架构: 新一代上下文管理")
                print(f"启动时间: {now_utc().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"请关注后续的任务分配日志...")
                print("=" * 60)
                
                # 生成工作流执行摘要（延迟一点，让任务创建完成）
                try:
                    import asyncio
                    await asyncio.sleep(1)  # 等待1秒让任务创建完成
                    await self._log_workflow_execution_summary(instance_id)
                except Exception as e:
                    logger.warning(f"生成执行摘要失败: {e}")
                
            except Exception as e:
                logger.error(f"启动工作流执行失败: {e}")
                raise
            
            return {
                'instance_id': instance_id,
                'status': WorkflowInstanceStatus.RUNNING.value,
                'message': '工作流开始执行'
            }
            
        except Exception as e:
            logger.error(f"执行工作流失败: {e}")
            raise
    
    async def _get_workflow_nodes_by_version_id(self, workflow_id: uuid.UUID) -> List[Dict[str, Any]]:
        """通过工作流版本ID获取所有节点（修复版本 - 使用当前版本逻辑）"""
        try:
            # 首先获取workflow_base_id，然后查询当前版本的节点
            workflow_query = """
                SELECT workflow_base_id 
                FROM workflow 
                WHERE workflow_id = $1 AND is_deleted = FALSE
            """
            workflow_result = await self.node_repo.db.fetch_one(workflow_query, workflow_id)
            
            if not workflow_result:
                logger.error(f"工作流版本不存在: {workflow_id}")
                return []
            
            workflow_base_id = workflow_result['workflow_base_id']
            logger.trace(f"工作流版本 {workflow_id} 对应的base_id: {workflow_base_id}")
            
            # 查询当前版本的所有节点
            query = """
                SELECT 
                    n.*,
                    np.processor_id
                FROM "node" n
                LEFT JOIN node_processor np ON np.node_id = n.node_id
                WHERE n.workflow_base_id = $1 
                AND n.is_current_version = TRUE
                AND n.is_deleted = FALSE
                ORDER BY n.created_at ASC
            """
            results = await self.node_repo.db.fetch_all(query, workflow_base_id)
            logger.trace(f"✅ 通过base_id {workflow_base_id} 获取当前版本节点 {len(results)} 个")
            
            # 如果没有找到当前版本节点，尝试直接用workflow_id查询
            if not results:
                logger.warning(f"通过base_id未找到节点，尝试直接查询workflow_id: {workflow_id}")
                fallback_query = """
                    SELECT 
                        n.*,
                        np.processor_id
                    FROM "node" n
                    LEFT JOIN node_processor np ON np.node_id = n.node_id
                    WHERE n.workflow_id = $1 
                    AND n.is_deleted = FALSE
                    ORDER BY n.created_at ASC
                """
                results = await self.node_repo.db.fetch_all(fallback_query, workflow_id)
                logger.trace(f"✅ 通过workflow_id {workflow_id} fallback查询获取到 {len(results)} 个节点")
            
            return results
        except Exception as e:
            logger.error(f"获取工作流节点列表失败: {e}")
            raise
    
    async def _check_running_instances(self, workflow_base_id: uuid.UUID, executor_id: uuid.UUID) -> List[Dict]:
        """检查是否已有正在运行的工作流实例"""
        try:
            from ..models.instance import WorkflowInstanceStatus
            
            # 查询正在运行的工作流实例
            query = """
            SELECT wi.*
            FROM workflow_instance wi
            WHERE wi.workflow_base_id = $1
            AND wi.executor_id = $2
            AND wi.status IN ('RUNNING', 'PAUSED')
            AND wi.is_deleted = FALSE
            ORDER BY wi.created_at DESC
            """
            
            running_instances = await self.workflow_instance_repo.db.fetch_all(
                query, workflow_base_id, executor_id
            )
            
            logger.trace(f"找到 {len(running_instances)} 个正在运行的工作流实例")
            return running_instances
            
        except Exception as e:
            logger.error(f"检查运行实例失败: {e}")
            return []
    
    async def _create_node_instances(self, workflow_instance_id: uuid.UUID, nodes: List[Dict[str, Any]]):
        """创建节点实例"""
        try:
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            from ..models.instance import NodeInstanceCreate, NodeInstanceStatus
            
            node_instance_repo = NodeInstanceRepository()
            
            for node in nodes:
                # 1. 先创建节点实例
                node_instance_data = NodeInstanceCreate(
                    workflow_instance_id=workflow_instance_id,
                    node_id=node['node_id'],
                    node_base_id=node['node_base_id'],  # 添加缺失的node_base_id
                    node_instance_name=f"{node['name']}_instance",
                    task_description=node.get('task_description', ''),
                    status=NodeInstanceStatus.PENDING,
                    input_data={},
                    output_data={},
                    error_message=None,
                    retry_count=0
                )
                
                node_instance = await node_instance_repo.create_node_instance(node_instance_data)
                if not node_instance:
                    logger.error(f"创建节点实例失败: {node['name']}")
                    continue
                
                node_instance_id = node_instance['node_instance_id']
                logger.trace(f"创建节点实例: {node['name']} (ID: {node_instance_id})")
                
                # 2. 为处理器节点创建任务实例
                if node['type'] == NodeType.PROCESSOR.value:
                    # 获取节点的处理器（修复：使用node_id）
                    processors = await self._get_node_processors(node['node_id'])
                    
                    for processor in processors:
                        # 根据处理器类型确定任务类型和分配
                        processor_type = processor.get('processor_type', processor.get('type', 'HUMAN'))
                        task_type = self._determine_task_type(processor_type)
                        assigned_user_id = processor.get('user_id')
                        assigned_agent_id = processor.get('agent_id')
                        
                        # 创建任务实例
                        task_title = node['name']
                        task_description = node.get('task_description') or node.get('description') or f"执行节点 {node['name']} 的任务"
                        
                        # 收集任务上下文数据（使用WorkflowContextManager）
                        context_data = await self.context_manager.get_task_context_data(workflow_instance_id, node_instance_id)
                        
                        # 将上下文数据转换为文本格式
                        context_text = json.dumps(context_data, ensure_ascii=False, indent=2, default=_json_serializer) if context_data else ""
                        input_text = json.dumps(node.get('input_data', {}), ensure_ascii=False, indent=2, default=_json_serializer)
                        
                        task_data = TaskInstanceCreate(
                            node_instance_id=node_instance_id,  # 使用真实的节点实例ID
                            workflow_instance_id=workflow_instance_id,
                            processor_id=processor['processor_id'],
                            task_type=task_type,
                            task_title=task_title,
                            task_description=task_description,
                            input_data=input_text,
                            context_data=context_text,
                            assigned_user_id=assigned_user_id,
                            assigned_agent_id=assigned_agent_id,
                            estimated_duration=30
                        )
                        
                        task = await self.task_instance_repo.create_task(task_data)
                        if task:
                            logger.trace(f"创建任务实例: {task['task_title']} (ID: {task['task_instance_id']})")
                        
        except Exception as e:
            logger.error(f"创建节点实例失败: {e}")
            raise
    
    async def _get_node_processors(self, node_id: uuid.UUID):
        """获取节点的处理器列表（修复版本：使用具体node_id）"""
        try:
            query = """
                SELECT np.*, p.name as processor_name, p.type as processor_type,
                       u.username, a.agent_name, p.user_id, p.agent_id
                FROM node_processor np
                JOIN processor p ON p.processor_id = np.processor_id AND p.is_deleted = FALSE
                LEFT JOIN "user" u ON u.user_id = p.user_id AND u.is_deleted = FALSE
                LEFT JOIN agent a ON a.agent_id = p.agent_id AND a.is_deleted = FALSE
                WHERE np.node_id = $1
                ORDER BY np.created_at ASC
            """
            results = await self.processor_repo.db.fetch_all(query, node_id)
            return results
        except Exception as e:
            logger.error(f"获取节点处理器列表失败: {e}")
            return []
    
    async def _get_next_nodes(self, node_id: uuid.UUID):
        """获取节点的下游节点（修复版本：使用具体node_id）"""
        try:
            query = """
                SELECT tn.node_id as to_node_id
                FROM node_connection nc
                JOIN node tn ON tn.node_id = nc.to_node_id
                WHERE nc.from_node_id = $1
                ORDER BY nc.created_at ASC
            """
            results = await self.node_repo.db.fetch_all(query, node_id)
            return [result['to_node_id'] for result in results]
        except Exception as e:
            logger.error(f"获取节点下游节点失败: {e}")
            return []
    
    def _determine_task_type(self, processor_type: str) -> TaskInstanceType:
        """根据处理器类型确定任务类型"""
        processor_type_upper = processor_type.upper() if processor_type else ""
        
        if processor_type_upper == "HUMAN":
            return TaskInstanceType.HUMAN
        elif processor_type_upper == "AGENT":
            return TaskInstanceType.AGENT
        elif processor_type_upper == "MIX" or processor_type_upper == "MIXED":
            return TaskInstanceType.MIXED
        else:
            # 记录调试信息
            logger.warning(f"未知的处理器类型: '{processor_type}' (转换后: '{processor_type_upper}')，默认为人工任务")
            return TaskInstanceType.HUMAN  # 默认为人工任务
    
    def _determine_task_priority(self, task_type: TaskInstanceType, node_data: Dict[str, Any]) -> int:
        """确定任务优先级（已废弃，保留方法避免调用错误）"""
        try:
            # 优先级字段已废弃，返回默认值
            return 1
                
        except Exception as e:
            logger.warning(f"确定任务优先级失败，使用默认值: {e}")
            return 1
    
    def _determine_task_duration(self, task_type: TaskInstanceType, node_data: Dict[str, Any]) -> int:
        """根据任务类型和节点配置确定预估执行时间（分钟）"""
        try:
            # 从节点数据中获取预估时间配置
            node_duration = node_data.get('estimated_duration', None)
            if node_duration is not None:
                return max(5, min(480, int(node_duration)))  # 限制在5分钟到8小时之间
            
            # 根据任务类型设置默认预估时间
            if task_type == TaskInstanceType.HUMAN:
                return 60  # 人工任务默认1小时
            elif task_type == TaskInstanceType.AGENT:
                return 15  # Agent任务默认15分钟
            elif task_type == TaskInstanceType.MIXED:
                return 45  # 混合任务默认45分钟
            else:
                return 30  # 默认30分钟
                
        except Exception as e:
            logger.warning(f"确定任务预估时间失败，使用默认值: {e}")
            return 30
    
    async def _start_workflow_execution(self, instance_id: uuid.UUID, workflow_id: uuid.UUID):
        """启动工作流执行（修复版本：使用具体版本ID）"""
        try:
            # 更新工作流实例状态为运行中
            update_data = WorkflowInstanceUpdate(status=WorkflowInstanceStatus.RUNNING)
            await self.workflow_instance_repo.update_instance(instance_id, update_data)
            
            # 查找开始节点（使用具体版本ID）
            nodes = await self._get_workflow_nodes_by_version_id(workflow_id)
            start_nodes = [node for node in nodes if node['type'] == NodeType.START.value]
            
            if not start_nodes:
                raise ValueError("工作流没有开始节点")
            
            # 将工作流实例加入执行队列（使用具体node_id）
            execution_item = {
                'instance_id': instance_id,
                'workflow_id': workflow_id,
                'current_nodes': [node['node_id'] for node in start_nodes],
                'context_data': {}
            }
            
            await self.execution_queue.put(execution_item)
            self.running_instances[instance_id] = execution_item
            
            logger.trace(f"工作流实例 {instance_id} 开始执行")
            
        except Exception as e:
            logger.error(f"启动工作流执行失败: {e}")
            raise
    
    async def _process_execution_queue(self):
        """处理执行队列"""
        while self.is_running:
            try:
                # 从队列获取执行项目
                execution_item = await asyncio.wait_for(
                    self.execution_queue.get(), timeout=1.0
                )
                
                # 处理执行项目
                await self._process_workflow_step(execution_item)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"处理执行队列失败: {e}")
                await asyncio.sleep(1)
    
    async def _process_workflow_step(self, execution_item: Dict[str, Any]):
        """处理工作流步骤"""
        try:
            instance_id = execution_item['instance_id']
            workflow_id = execution_item['workflow_id']
            current_nodes = execution_item['current_nodes']
            
            logger.trace(f"处理工作流实例 {instance_id} 的节点: {current_nodes}")
            
            # 处理当前节点
            next_nodes = []
            for node_id in current_nodes:
                node_result = await self._process_node(instance_id, workflow_id, node_id)
                if node_result.get('next_nodes'):
                    next_nodes.extend(node_result['next_nodes'])
            
            # 如果有下一步节点，继续执行
            if next_nodes:
                execution_item['current_nodes'] = next_nodes
                await self.execution_queue.put(execution_item)
            else:
                # 工作流完成
                await self._complete_workflow(instance_id)
                
        except Exception as e:
            logger.error(f"处理工作流步骤失败: {e}")
            await self._fail_workflow(execution_item['instance_id'], str(e))
    
    async def _process_node(self, instance_id: uuid.UUID, workflow_id: uuid.UUID, 
                          node_id: uuid.UUID) -> Dict[str, Any]:
        """处理单个节点（修复版本：使用具体的node_id）"""
        try:
            # 🔧 修复：直接通过node_id获取节点信息
            node = await self.node_repo.get_node_by_id(node_id)
            if not node:
                raise ValueError(f"节点 {node_id} 不存在")
            
            node_type = node['type']
            logger.trace(f"处理节点: {node['name']} (类型: {node_type}, ID: {node_id})")
            
            if node_type == NodeType.START.value:
                # 开始节点直接完成
                return await self._handle_start_node(instance_id, workflow_id, node_id)
            elif node_type == NodeType.END.value:
                # 结束节点
                return await self._handle_end_node(instance_id, workflow_id, node_id)
            elif node_type == NodeType.PROCESSOR.value:
                # 处理器节点
                return await self._handle_processor_node(instance_id, workflow_id, node_id)
            else:
                logger.warning(f"未知节点类型: {node_type}")
                return {'next_nodes': []}
                
        except Exception as e:
            logger.error(f"处理节点失败: {e}")
            raise
    
    async def _handle_start_node(self, instance_id: uuid.UUID, workflow_id: uuid.UUID, 
                                node_id: uuid.UUID) -> Dict[str, Any]:
        """处理开始节点（修复版本）"""
        try:
            # 获取下游节点
            next_nodes = await self._get_next_nodes(node_id)
            
            logger.trace(f"开始节点处理完成，下一步节点: {next_nodes}")
            return {'next_nodes': next_nodes}
            
        except Exception as e:
            logger.error(f"处理开始节点失败: {e}")
            raise
    
    async def _handle_end_node(self, instance_id: uuid.UUID, workflow_id: uuid.UUID, 
                              node_id: uuid.UUID) -> Dict[str, Any]:
        """处理结束节点（修复版本）"""
        try:
            logger.trace(f"到达结束节点，工作流实例 {instance_id} 即将完成")
            return {'next_nodes': []}  # 没有下一步节点
            
        except Exception as e:
            logger.error(f"处理结束节点失败: {e}")
            raise
    
    async def _handle_processor_node(self, instance_id: uuid.UUID, workflow_id: uuid.UUID, 
                                   node_id: uuid.UUID) -> Dict[str, Any]:
        """处理处理器节点（修复版本）"""
        try:
            # 🔧 修复：通过node_id查找任务实例
            tasks = await self.task_instance_repo.get_tasks_by_workflow_instance(instance_id)
            node_tasks = [task for task in tasks if task.get('node_instance', {}).get('node_id') == node_id]
            
            if not node_tasks:
                logger.warning(f"节点 {node_id} 没有任务实例")
                return {'next_nodes': []}
            
            # 启动任务执行
            for task in node_tasks:
                await self._execute_task(task)
            
            # 等待任务完成（这里简化处理，实际应该异步等待）
            await asyncio.sleep(1)  # 模拟任务执行时间
            
            # 获取下游节点
            next_nodes = await self._get_next_nodes(node_id)
            
            logger.trace(f"处理器节点处理完成，下一步节点: {next_nodes}")
            return {'next_nodes': next_nodes}
            
        except Exception as e:
            logger.error(f"处理处理器节点失败: {e}")
            raise
    
    async def _execute_task(self, task: Dict[str, Any]):
        """执行单个任务"""
        try:
            task_id = task['task_instance_id']
            task_type = task['task_type']
            
            logger.trace(f"执行任务: {task['task_title']} (类型: {task_type})")
            
            if task_type == TaskInstanceType.HUMAN.value:
                # 人工任务：更新状态为已分配，等待人工处理
                logger.trace(f"👤 处理人工任务: {task['task_title']}")
                logger.trace(f"   - 任务ID: {task_id}")
                logger.trace(f"   - 分配目标用户: {task.get('assigned_user_id')}")
                
                # 检查任务是否有分配的用户
                assigned_user_id = task.get('assigned_user_id')
                if not assigned_user_id:
                    logger.warning(f"⚠️  人工任务没有分配用户，任务将保持PENDING状态")
                    logger.warning(f"   - 任务ID: {task_id}")
                    logger.warning(f"   - 任务标题: {task['task_title']}")
                    logger.warning(f"   - 建议: 请为该任务的处理器配置用户")
                    return
                
                # 任务创建时已经设置了正确的状态，这里不需要再更新
                # （任务创建时如果有assigned_user_id，状态就是ASSIGNED）
                logger.trace(f"   ✅ 任务已处于正确状态，无需更新")
                
                # 获取任务详细信息用于通知
                task_title = task.get('task_title', '未命名任务')
                workflow_name = task.get('workflow_name', '未命名工作流')
                estimated_duration = task.get('estimated_duration', 30)
                
                logger.trace(f"📋 人工任务分配详情:")
                logger.trace(f"   - 任务标题: {task_title}")
                logger.trace(f"   - 工作流: {workflow_name}")
                logger.trace(f"   - 分配给用户: {assigned_user_id}")
                logger.trace(f"   - 预估时长: {estimated_duration}分钟")
                logger.trace(f"   - 任务描述: {task.get('task_description', '无描述')[:100]}...")
                
                # 实时通知用户有新任务 - 重要改进！
                try:
                    await self._notify_user_new_task(assigned_user_id, task_id, task_title)
                    logger.trace(f"   📬 用户通知已发送")
                except Exception as e:
                    logger.error(f"   ❌ 发送用户通知失败: {e}")
                
                # 记录任务分配事件（用于后续分析和监控）
                await self._log_task_assignment_event(task_id, assigned_user_id, task_title)
                
                # 记录到控制台用于调试
                print(f"\n🎯 【任务推送】 新的人工任务已分配:")
                print(f"   用户ID: {assigned_user_id}")
                print(f"   任务ID: {task_id}")
                print(f"   任务标题: {task_title}")
                print(f"   工作流: {workflow_name}")
                print(f"   时间: {now_utc().strftime('%Y-%m-%d %H:%M:%S')}")
                print("=" * 60)
                
            elif task_type == TaskInstanceType.AGENT.value:
                # Agent任务：调用AI处理
                await self._process_agent_task(task)
                
            elif task_type == TaskInstanceType.MIXED.value:
                # 混合任务：同时提交给人工和Agent处理
                await self._process_mixed_task(task)
            
        except Exception as e:
            logger.error(f"执行任务失败: {e}")
            raise
    
    async def _process_agent_task(self, task: Dict[str, Any]):
        """处理Agent任务 - 集成AgentTaskService"""
        try:
            task_id = task['task_instance_id']
            logger.trace(f"集成Agent任务服务处理任务: {task['task_title']}")
            
            # 注册任务完成回调
            callback_future = asyncio.Future()
            self.task_callbacks[task_id] = callback_future
            
            # 提交任务到AgentTaskService进行处理
            result = await agent_task_service.submit_task_to_agent(task_id)
            
            if result['status'] == 'queued':
                logger.trace(f"Agent任务 {task_id} 已提交到服务队列")
                
                # 等待任务处理完成（通过回调机制）
                try:
                    await asyncio.wait_for(callback_future, timeout=300)  # 5分钟超时
                    logger.trace(f"Agent任务 {task_id} 通过回调机制完成")
                except asyncio.TimeoutError:
                    logger.error(f"Agent任务 {task_id} 处理超时")
                    raise TimeoutError("Agent任务处理超时")
                finally:
                    # 清理回调
                    self.task_callbacks.pop(task_id, None)
                
            else:
                logger.warning(f"Agent任务提交失败: {result}")
                # 清理回调
                self.task_callbacks.pop(task_id, None)
                raise RuntimeError(f"Agent任务提交失败: {result}")
            
        except Exception as e:
            logger.error(f"处理Agent任务失败: {e}")
            # 清理回调
            self.task_callbacks.pop(task.get('task_instance_id'), None)
            # 更新任务状态为失败
            fail_update = TaskInstanceUpdate(
                status=TaskInstanceStatus.FAILED,
                error_message=str(e)
            )
            await self.task_instance_repo.update_task(task['task_instance_id'], fail_update)
            raise
    
    async def on_task_completed(self, task_id: uuid.UUID, result: Dict[str, Any]):
        """任务完成回调处理"""
        try:
            logger.trace(f"收到任务完成回调: {task_id}")
            
            # 检查是否有等待的回调
            if task_id in self.task_callbacks:
                callback_future = self.task_callbacks[task_id]
                if not callback_future.done():
                    callback_future.set_result(result)
                    logger.trace(f"任务 {task_id} 回调已触发")
            else:
                # 这是正常情况：任务完成时等待的Future可能已经被处理并清理
                logger.debug(f"任务 {task_id} 完成，但回调已被处理（正常情况）")
            
            # 获取任务信息以便更新节点状态
            task_info = await self.task_instance_repo.get_task_by_id(task_id)
            if task_info:
                workflow_instance_id = task_info['workflow_instance_id']
                node_instance_id = task_info['node_instance_id']
                
                logger.trace(f"🎯 Agent任务完成，更新节点状态: workflow={workflow_instance_id}, node_instance={node_instance_id}")
                
                # 获取节点信息
                node_query = """
                SELECT n.node_id, n.name
                FROM node_instance ni
                JOIN node n ON ni.node_id = n.node_id
                WHERE ni.node_instance_id = $1
                """
                node_info = await self.task_instance_repo.db.fetch_one(node_query, node_instance_id)
                
                if node_info:
                    # 使用WorkflowContextManager标记节点完成
                    output_data = {
                        'task_result': result.get('result', ''),
                        'task_summary': result.get('message', ''),
                        'execution_time': result.get('duration', 0),
                        'completion_time': datetime.utcnow().isoformat()
                    }
                    
                    await self.context_manager.mark_node_completed(
                        workflow_instance_id=workflow_instance_id,
                        node_id=node_info['node_id'],
                        node_instance_id=node_instance_id,
                        output_data=output_data
                    )
                    
                    logger.trace(f"✅ Agent任务完成后节点状态更新完成")
                else:
                    logger.error(f"无法获取节点信息: node_instance_id={node_instance_id}")
            else:
                logger.error(f"无法获取任务信息: task_id={task_id}")
                
        except Exception as e:
            logger.error(f"处理任务完成回调失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    async def on_task_failed(self, task_id: uuid.UUID, error_message: str):
        """任务失败回调处理"""
        try:
            logger.trace(f"收到任务失败回调: {task_id} - {error_message}")
            
            # 检查是否有等待的回调
            if task_id in self.task_callbacks:
                callback_future = self.task_callbacks[task_id]
                if not callback_future.done():
                    callback_future.set_exception(RuntimeError(error_message))
                    logger.trace(f"任务 {task_id} 失败回调已触发")
            else:
                # 这是正常情况：任务失败时等待的Future可能已经被处理并清理
                logger.debug(f"任务 {task_id} 失败，但回调已被处理（正常情况）")
            
            # 获取任务信息以便更新节点状态为失败
            task_info = await self.task_instance_repo.get_task_by_id(task_id)
            if task_info:
                workflow_instance_id = task_info['workflow_instance_id']
                node_instance_id = task_info['node_instance_id']
                
                logger.trace(f"❌ Agent任务失败，标记节点失败: workflow={workflow_instance_id}, node_instance={node_instance_id}")
                
                # 获取节点信息
                node_query = """
                SELECT n.node_id, n.name
                FROM node_instance ni
                JOIN node n ON ni.node_id = n.node_id
                WHERE ni.node_instance_id = $1
                """
                node_info = await self.task_instance_repo.db.fetch_one(node_query, node_instance_id)
                
                if node_info:
                    # 使用WorkflowContextManager标记节点失败
                    await self.context_manager.mark_node_failed(
                        workflow_instance_id=workflow_instance_id,
                        node_id=node_info['node_id'],
                        node_instance_id=node_instance_id,
                        error_info={'error': error_message}
                    )
                    
                    logger.trace(f"❌ Agent任务失败后节点状态更新完成")
                else:
                    logger.error(f"无法获取节点信息: node_instance_id={node_instance_id}")
            else:
                logger.error(f"无法获取任务信息: task_id={task_id}")
                
        except Exception as e:
            logger.error(f"处理任务失败回调失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    async def _process_mixed_task(self, task: Dict[str, Any]):
        """处理混合任务 - 人机协作"""
        try:
            task_id = task['task_instance_id']
            logger.trace(f"处理混合任务: {task['task_title']}")
            
            # 1. 首先分配给人工用户处理
            human_update = TaskInstanceUpdate(status=TaskInstanceStatus.ASSIGNED)
            await self.task_instance_repo.update_task(task_id, human_update)
            logger.trace(f"混合任务 {task_id} 已分配给人工用户")
            
            # 2. 同时提交给Agent服务获取AI建议（不阻塞）
            try:
                # 创建AI建议任务的副本数据
                ai_suggestion_task = task.copy()
                ai_suggestion_task['task_title'] = f"[AI建议] {task['task_title']}"
                ai_suggestion_task['task_description'] = f"为人工任务提供AI建议: {task['task_description']}"
                
                # 异步提交到Agent服务获取建议
                asyncio.create_task(self._provide_ai_assistance(task_id, ai_suggestion_task))
                logger.trace(f"为混合任务 {task_id} 启动AI协助")
                
            except Exception as e:
                logger.warning(f"启动AI协助失败，继续人工处理: {e}")
            
            # 3. 混合任务主要等待人工完成，AI建议作为辅助
            logger.trace(f"混合任务 {task_id} 进入人机协作模式")
            
        except Exception as e:
            logger.error(f"处理混合任务失败: {e}")
            # 更新任务状态为失败
            fail_update = TaskInstanceUpdate(
                status=TaskInstanceStatus.FAILED,
                error_message=str(e)
            )
            await self.task_instance_repo.update_task(task['task_instance_id'], fail_update)
            raise
    
    async def _provide_ai_assistance(self, original_task_id: uuid.UUID, ai_task: Dict[str, Any]):
        """为人工任务提供AI协助建议"""
        try:
            logger.trace(f"为任务 {original_task_id} 生成AI建议")
            
            # 调用AgentTaskService生成AI建议
            ai_result = await agent_task_service.process_agent_task(original_task_id)
            
            # 将AI建议存储到原任务的上下文中
            if ai_result['status'] == TaskInstanceStatus.COMPLETED.value:
                ai_suggestions = {
                    'ai_analysis': ai_result['result'],
                    'suggestions_generated_at': now_utc().isoformat(),
                    'confidence_score': ai_result['result'].get('confidence_score', 0.8),
                    'ai_recommendations': ai_result['result'].get('recommendations', [])
                }
                
                # 更新原任务，添加AI建议到上下文
                update_data = TaskInstanceUpdate(
                    context_data={'ai_assistance': ai_suggestions}
                )
                await self.task_instance_repo.update_task(original_task_id, update_data)
                
                logger.trace(f"AI建议已添加到任务 {original_task_id} 的上下文中")
            
        except Exception as e:
            logger.warning(f"生成AI协助建议失败: {e}")
            # AI协助失败不影响主任务
    
    async def _complete_workflow(self, instance_id: uuid.UUID):
        """完成工作流"""
        try:
            logger.trace(f"🏁 开始完成工作流: {instance_id}")
            
            # 1. 生成标准化输出摘要
            logger.trace(f"📊 生成工作流输出摘要")
            try:
                from .output_data_processor import OutputDataProcessor
                output_processor = OutputDataProcessor()
                
                # 生成输出摘要
                output_summary = await output_processor.generate_workflow_output_summary(instance_id)
                if output_summary:
                    logger.trace(f"✅ 工作流输出摘要生成成功")
                    
                    # 准备结构化输出数据
                    summary_dict = output_summary.dict()
                    execution_summary = {
                        "execution_result": summary_dict.get("execution_result"),
                        "execution_stats": summary_dict.get("execution_stats")
                    }
                    quality_metrics = summary_dict.get("quality_metrics")
                    data_lineage = summary_dict.get("data_lineage")
                    
                    # 设置基础输出数据
                    basic_output_data = {
                        'message': '工作流执行完成',
                        'completion_time': datetime.utcnow().isoformat(),
                        'result_type': summary_dict.get("execution_result", {}).get("result_type", "success")
                    }
                    
                    # 如果有具体的业务输出数据，添加到基础输出中
                    if summary_dict.get("execution_result", {}).get("data_output"):
                        basic_output_data['workflow_results'] = summary_dict["execution_result"]["data_output"]
                    
                    logger.trace(f"💾 更新工作流实例状态和输出数据")
                    
                    # 2. 更新工作流实例状态为已完成，包含结构化输出
                    update_data = WorkflowInstanceUpdate(
                        status=WorkflowInstanceStatus.COMPLETED,
                        output_data=basic_output_data,
                        execution_summary=execution_summary,
                        quality_metrics=quality_metrics,
                        data_lineage=data_lineage,
                        output_summary=output_summary
                    )
                    
                else:
                    logger.warning(f"⚠️ 工作流输出摘要生成失败，使用基础输出数据")
                    # 使用基础输出数据
                    update_data = WorkflowInstanceUpdate(
                        status=WorkflowInstanceStatus.COMPLETED,
                        output_data={
                            'message': '工作流执行完成',
                            'completion_time': datetime.utcnow().isoformat(),
                            'result_type': 'success'
                        }
                    )
                    
            except Exception as output_error:
                logger.error(f"❌ 生成输出摘要异常: {output_error}")
                import traceback
                logger.error(f"异常堆栈: {traceback.format_exc()}")
                
                # 即使输出摘要生成失败，也要完成工作流
                update_data = WorkflowInstanceUpdate(
                    status=WorkflowInstanceStatus.COMPLETED,
                    output_data={
                        'message': '工作流执行完成',
                        'completion_time': datetime.utcnow().isoformat(),
                        'result_type': 'success',
                        'note': '输出摘要生成失败，但工作流正常完成'
                    }
                )
            
            # 3. 更新数据库
            await self.workflow_instance_repo.update_instance(instance_id, update_data)
            
            # 4. 从运行实例中移除
            self.running_instances.pop(instance_id, None)
            
            logger.trace(f"✅ 工作流实例 {instance_id} 执行完成")
            logger.trace(f"📋 工作流完成统计:")
            logger.trace(f"   - 实例ID: {instance_id}")
            logger.trace(f"   - 完成时间: {datetime.utcnow().isoformat()}")
            logger.trace(f"   - 输出摘要: {'已生成' if 'output_summary' in locals() and output_summary else '生成失败'}")
            
        except Exception as e:
            logger.error(f"❌ 完成工作流失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            raise
    
    async def _fail_workflow(self, instance_id: uuid.UUID, error_message: str):
        """工作流执行失败"""
        try:
            # 更新工作流实例状态为失败
            update_data = WorkflowInstanceUpdate(
                status=WorkflowInstanceStatus.FAILED,
                error_message=error_message
            )
            await self.workflow_instance_repo.update_instance(instance_id, update_data)
            
            # 从运行实例中移除
            self.running_instances.pop(instance_id, None)
            
            logger.error(f"工作流实例 {instance_id} 执行失败: {error_message}")
            
        except Exception as e:
            logger.error(f"标记工作流失败状态失败: {e}")
    
    async def _monitor_running_instances(self):
        """监控运行中的实例"""
        while self.is_running:
            try:
                # 检查超时的实例
                for instance_id, execution_item in list(self.running_instances.items()):
                    # 这里可以添加超时检查逻辑
                    pass
                
                # 检查并触发就绪的END节点
                await self._check_and_trigger_ready_end_nodes()
                
                await asyncio.sleep(15)  # 每15秒检查一次 - 优化为更频繁
                
            except Exception as e:
                logger.error(f"监控运行实例失败: {e}")
                await asyncio.sleep(10)
    
    async def _check_and_trigger_ready_end_nodes(self):
        """检查并触发就绪的END节点"""
        try:
            # 查找所有运行中的工作流实例
            running_workflows_query = """
            SELECT workflow_instance_id, workflow_instance_name
            FROM workflow_instance 
            WHERE status = 'running' AND is_deleted = 0
            """
            
            running_workflows = await self.task_instance_repo.db.fetch_all(running_workflows_query)
            
            for workflow in running_workflows:
                workflow_id = workflow['workflow_instance_id']
                
                # 查找pending状态的END节点
                end_nodes_query = """
                SELECT ni.node_instance_id, ni.node_instance_name, ni.status,
                       n.type as node_type, n.name as node_name
                FROM node_instance ni
                JOIN node n ON ni.node_id = n.node_id
                WHERE ni.workflow_instance_id = %s
                AND LOWER(n.type) = 'end'
                AND ni.status IN ('pending', 'waiting')
                AND ni.is_deleted = 0
                """
                
                end_nodes = await self.task_instance_repo.db.fetch_all(end_nodes_query, workflow_id)
                
                for end_node in end_nodes:
                    node_instance_id = end_node['node_instance_id']
                    node_name = end_node.get('node_instance_name', '未知END节点')
                    
                    # 🔍 检查END节点的状态，避免重复触发
                    try:
                        # 检查节点是否已经在执行或完成
                        current_state = self.context_manager.node_completion_status.get(node_instance_id, 'PENDING')
                        if current_state in ['EXECUTING', 'COMPLETED']:
                            logger.trace(f"🚫 [END节点检查] {node_name} 状态为 {current_state}，跳过触发")
                            continue
                        
                        # 检查数据库状态作为双重保险
                        from ..repositories.instance.node_instance_repository import NodeInstanceRepository
                        node_repo = NodeInstanceRepository()
                        db_node = await node_repo.get_instance_by_id(node_instance_id)
                        if db_node and db_node.get('status') in ['running', 'completed']:
                            logger.trace(f"🚫 [END节点检查-DB] {node_name} 数据库状态为 {db_node.get('status')}，跳过触发")
                            continue
                        
                        # 检查END节点的依赖是否满足
                        if await self._check_node_dependencies_satisfied(workflow_id, node_instance_id):
                            logger.info(f"🏁 发现就绪的END节点: {node_name} ({node_instance_id})")
                            
                            # 标记为即将执行，防止重复触发
                            self.context_manager.node_completion_status[node_instance_id] = 'EXECUTING'
                            
                            try:
                                # 触发END节点执行
                                await self._execute_node_when_ready(workflow_id, node_instance_id)
                                logger.info(f"✅ END节点 {node_name} 触发成功")
                            except Exception as e:
                                logger.error(f"❌ END节点 {node_name} 触发失败: {e}")
                                # 恢复状态
                                self.context_manager.node_completion_status[node_instance_id] = 'PENDING'
                        else:
                            logger.trace(f"⏳ [END节点检查] {node_name} 依赖尚未满足")
                            
                    except Exception as e:
                        logger.error(f"❌ [END节点检查] 检查END节点 {node_name} 失败: {e}")
                        # 确保状态正确
                        if node_instance_id in self.context_manager.node_completion_status:
                            current_state = self.context_manager.node_completion_status[node_instance_id]
                            if current_state == 'EXECUTING':
                                self.context_manager.node_completion_status[node_instance_id] = 'PENDING'
                            
        except Exception as e:
            logger.error(f"检查就绪END节点失败: {e}")
    
    async def pause_workflow(self, instance_id: uuid.UUID) -> bool:
        """暂停工作流"""
        try:
            update_data = WorkflowInstanceUpdate(status=WorkflowInstanceStatus.PAUSED)
            result = await self.workflow_instance_repo.update_instance(instance_id, update_data)
            
            if result:
                logger.trace(f"工作流实例 {instance_id} 已暂停")
                return True
            return False
            
        except Exception as e:
            logger.error(f"暂停工作流失败: {e}")
            return False
    
    async def resume_workflow(self, instance_id: uuid.UUID) -> bool:
        """恢复工作流"""
        try:
            update_data = WorkflowInstanceUpdate(status=WorkflowInstanceStatus.RUNNING)
            result = await self.workflow_instance_repo.update_instance(instance_id, update_data)
            
            if result:
                logger.trace(f"工作流实例 {instance_id} 已恢复")
                return True
            return False
            
        except Exception as e:
            logger.error(f"恢复工作流失败: {e}")
            return False
    
    async def cancel_workflow(self, instance_id: uuid.UUID) -> bool:
        """取消工作流"""
        try:
            logger.trace(f"🚫 开始取消工作流实例: {instance_id}")
            
            # 首先检查工作流实例是否存在
            instance = await self.workflow_instance_repo.get_instance_by_id(instance_id)
            if not instance:
                logger.error(f"❌ 工作流实例不存在: {instance_id}")
                return False
                
            logger.trace(f"📋 找到工作流实例: {instance.get('workflow_instance_name', '未命名')}")
            logger.trace(f"   - 当前状态: {instance.get('status')}")
            logger.trace(f"   - 执行者: {instance.get('executor_id')}")
            logger.trace(f"   - 创建时间: {instance.get('created_at')}")
            
            # 1. 取消正在运行的异步任务
            logger.trace(f"🎯 步骤1: 取消正在运行的异步任务")
            try:
                await self._cancel_running_tasks(instance_id)
                logger.trace(f"✅ 异步任务取消完成")
            except Exception as e:
                logger.error(f"❌ 取消异步任务失败: {e}")
            
            # 资源清理和状态同步
            logger.trace(f"🎯 步骤2: 清理实例状态")
            try:
                # 使用新的统一上下文管理器清理状态
                if hasattr(self.context_manager, 'cleanup_workflow_context'):
                    await self.context_manager.cleanup_workflow_context(instance_id)
                    logger.trace(f"✅ 已从统一上下文管理器中移除工作流: {instance_id}")
                else:
                    logger.trace(f"   - 上下文管理器不支持cleanup方法")
            except Exception as e:
                logger.error(f"❌ 清理实例状态失败: {e}")
            
            # 3. 更新数据库状态
            logger.trace(f"🎯 步骤3: 更新数据库状态为CANCELLED")
            try:
                update_data = WorkflowInstanceUpdate(status=WorkflowInstanceStatus.CANCELLED)
                logger.trace(f"   - 准备更新数据: {update_data}")
                result = await self.workflow_instance_repo.update_instance(instance_id, update_data)
                logger.trace(f"   - 数据库更新结果: {result}")
                
                if result:
                    logger.trace(f"✅ 数据库状态更新成功")
                    
                    # 从运行实例中移除
                    logger.trace(f"🎯 步骤4: 从运行实例列表中移除")
                    if hasattr(self, 'running_instances') and instance_id in self.running_instances:
                        self.running_instances.pop(instance_id, None)
                        logger.trace(f"   - 已从运行实例列表中移除")
                    else:
                        logger.trace(f"   - 实例不在运行列表中")
                    
                    # 5. 通知相关服务
                    logger.trace(f"🎯 步骤5: 通知相关服务")
                    try:
                        await self._notify_services_workflow_cancelled(instance_id)
                        logger.trace(f"✅ 服务通知完成")
                    except Exception as e:
                        logger.error(f"❌ 通知服务失败: {e}")
                    
                    logger.trace(f"✅ 工作流实例 {instance_id} 已成功取消 (所有步骤完成)")
                    return True
                else:
                    logger.error(f"❌ 更新工作流状态失败: {instance_id}")
                    return False
            except Exception as e:
                logger.error(f"❌ 数据库更新异常: {e}")
                import traceback
                logger.error(f"   - 更新异常堆栈: {traceback.format_exc()}")
                return False
            
        except Exception as e:
            logger.error(f"❌ 取消工作流失败: {e}")
            import traceback
            logger.error(f"   - 完整异常堆栈: {traceback.format_exc()}")
            return False
    
    async def get_workflow_status(self, instance_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取工作流状态"""
        try:
            instance = await self.workflow_instance_repo.get_instance_by_id(instance_id)
            if not instance:
                return None
            
            # 获取执行统计
            stats = await self.workflow_instance_repo.get_execution_statistics(instance_id)
            
            return {
                'instance': instance,
                'statistics': stats,
                'is_running': instance_id in self.running_instances
            }
            
        except Exception as e:
            logger.error(f"获取工作流状态失败: {e}")
            return None
    
    # =============================================================================
    # 新增：依赖等待和上下文管理方法
    # =============================================================================
    
    async def _create_node_instances_with_dependencies(self, 
                                                     workflow_instance_id: uuid.UUID,
                                                     workflow_base_id: uuid.UUID,
                                                     nodes: List[Dict[str, Any]]):
        """创建节点实例并注册依赖关系"""
        try:
            logger.trace(f"开始创建节点实例: 工作流实例 ID={workflow_instance_id}, 节点数量={len(nodes)}")
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            from ..models.instance import NodeInstanceCreate, NodeInstanceStatus
            
            node_instance_repo = NodeInstanceRepository()
            created_nodes = []
            
            # 1. 先创建所有节点实例
            logger.trace(f"阶段1: 创建 {len(nodes)} 个节点实例")
            for i, node in enumerate(nodes, 1):
                logger.trace(f"  正在创建节点实例 {i}/{len(nodes)}: {node['name']} (类型: {node['type']})")
                
                # 设置初始状态：START节点为PENDING，其他节点也为PENDING（等待前置条件满足）
                initial_status = NodeInstanceStatus.PENDING
                logger.trace(f"    初始状态: {initial_status.value}")
                
                node_instance_data = NodeInstanceCreate(
                    workflow_instance_id=workflow_instance_id,
                    node_id=node['node_id'],
                    node_base_id=node['node_base_id'],
                    node_instance_name=f"{node['name']}_instance",
                    task_description=node.get('task_description') or '',
                    status=initial_status,
                    input_data={},
                    output_data={},
                    error_message=None,
                    retry_count=0
                )
                
                node_instance = await node_instance_repo.create_node_instance(node_instance_data)
                if node_instance:
                    created_nodes.append({
                        'node_instance_id': node_instance['node_instance_id'],
                        'node_base_id': node['node_base_id'],
                        'node_type': node['type'],
                        'node_data': node
                    })
                    logger.trace(f"  ✅ 节点实例创建成功: {node['name']} (ID: {node_instance['node_instance_id']})")
                else:
                    logger.error(f"  ❌ 节点实例创建失败: {node['name']}")
            
            # 2. 为每个节点注册依赖关系
            logger.trace(f"阶段2: 注册 {len(created_nodes)} 个节点的依赖关系")
            for i, created_node in enumerate(created_nodes, 1):
                logger.trace(f"  正在注册节点 {i}/{len(created_nodes)} 的依赖: {created_node['node_data']['name']}")
                try:
                    # 直接从数据库查询连接关系，使用正确的workflow_id
                    from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
                    workflow_instance_repo = WorkflowInstanceRepository()
                    workflow_instance = await workflow_instance_repo.get_instance_by_id(workflow_instance_id)
                    current_workflow_id = workflow_instance['workflow_id'] if workflow_instance else None
                    
                    logger.trace(f"    🔍 查询节点 {created_node['node_data']['name']} 的依赖关系:")
                    logger.trace(f"      - node_id: {created_node['node_data']['node_id']}")
                    logger.trace(f"      - workflow_id: {current_workflow_id}")
                    
                    # 查询上游连接关系
                    upstream_query = """
                    SELECT DISTINCT 
                        nc.from_node_id as upstream_node_id,
                        n.name as upstream_node_name,
                        n.type as upstream_node_type
                    FROM node_connection nc
                    JOIN node n ON nc.from_node_id = n.node_id
                    WHERE nc.to_node_id = $1 
                    AND nc.workflow_id = $2
                    ORDER BY n.name
                    """
                    
                    upstream_connections = await self.workflow_instance_repo.db.fetch_all(
                        upstream_query, 
                        created_node['node_data']['node_id'],  # 使用node_id查询
                        current_workflow_id  # 使用workflow_id查询
                    )
                    
                    logger.trace(f"    🔍 查询到 {len(upstream_connections)} 个上游节点连接:")
                    upstream_node_ids = []
                    for upstream in upstream_connections:
                        upstream_node_id = upstream['upstream_node_id']
                        upstream_node_ids.append(upstream_node_id)
                        logger.trace(f"      - 上游节点: {upstream.get('upstream_node_name', 'Unknown')} (node_id: {upstream_node_id})")
                    
                    logger.trace(f"    📋 最终依赖列表 (node_id): {upstream_node_ids}")
                    
                    await self.context_manager.register_node_dependencies(
                        workflow_instance_id,
                        created_node['node_instance_id'],
                        created_node['node_data']['node_id'],  # 使用node_id而不是node_base_id
                        upstream_node_ids  # 上游节点的node_id列表
                    )
                    
                    logger.trace(f"  ✅ 节点依赖注册成功: {len(upstream_node_ids)} 个上游节点 (使用node_id)")
                except Exception as e:
                    logger.error(f"  ❌ 节点依赖注册失败: {e}")
                    import traceback
                    logger.error(f"    异常详情: {traceback.format_exc()}")
            
            # 3. 不再为所有处理器节点立即创建任务 - 改为延迟创建机制
            logger.trace(f"阶段3: 启用延迟任务创建机制，只为START节点创建任务")
            try:
                # 只为START节点创建任务（如果START节点是PROCESSOR类型）
                start_nodes = [n for n in created_nodes if n['node_data']['type'] == NodeType.START.value]
                if start_nodes:
                    await self._create_tasks_for_nodes(start_nodes, workflow_instance_id)
                    logger.trace(f"✅ START节点任务创建完成")
                
                # 检查所有就绪节点，为满足条件的节点创建任务
                await self._check_downstream_nodes_for_task_creation(workflow_instance_id)
                logger.trace(f"✅ 延迟任务创建机制启动完成")
            except Exception as e:
                logger.error(f"❌ 延迟任务创建机制启动失败: {e}")
            
            logger.trace(f"✅ 节点实例和依赖关系创建完成: {len(created_nodes)} 个节点")
            
            # 打印依赖关系总结
            logger.trace(f"📊 [依赖总结] 打印工作流 {workflow_instance_id} 的完整依赖关系:")
            self.context_manager.print_dependency_summary(workflow_instance_id)
            
        except Exception as e:
            logger.error(f"❌ 创建带依赖的节点实例失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            raise
    
    async def _create_tasks_for_nodes(self, created_nodes: List[Dict], workflow_instance_id: uuid.UUID):
        """为节点创建任务实例"""
        logger.trace(f"🔧 开始为 {len(created_nodes)} 个节点创建任务实例")
        
        task_creation_count = 0
        for i, created_node in enumerate(created_nodes, 1):
            logger.trace(f"📋 处理节点 {i}/{len(created_nodes)}: {created_node.get('node_data', {}).get('name', '未知节点')}")
            logger.trace(f"   节点类型: {created_node['node_type']}")
            logger.trace(f"   节点实例ID: {created_node['node_instance_id']}")
            
            if created_node['node_type'] == NodeType.PROCESSOR.value:
                node_data = created_node['node_data']
                
                logger.trace(f"   🔍 查询节点处理器...")
                # 获取节点的处理器（修复：使用node_id）
                processors = await self._get_node_processors(
                    created_node['node_data']['node_id']
                )
                
                if not processors:
                    logger.warning(f"   ⚠️  节点 {node_data['name']} 没有配置处理器，跳过任务创建")
                    continue
                
                logger.trace(f"   ✅ 找到 {len(processors)} 个处理器")
                
                for j, processor in enumerate(processors, 1):
                    logger.trace(f"   🎯 处理处理器 {j}/{len(processors)}: {processor.get('processor_name', processor.get('name', 'Unknown'))}")
                    
                    processor_type = processor.get('processor_type', processor.get('type', 'HUMAN'))
                    task_type = self._determine_task_type(processor_type)
                    
                    logger.trace(f"      处理器类型: {processor_type}")
                    logger.trace(f"      任务类型: {task_type.value}")
                    
                    # 根据任务类型和节点配置确定超时设置
                    estimated_duration = self._determine_task_duration(task_type, node_data)
                    
                    logger.trace(f"      预估持续时间: {estimated_duration}分钟")
                    
                    # 确定任务分配
                    assigned_user_id = processor.get('user_id')
                    assigned_agent_id = processor.get('agent_id')
                    
                    if assigned_user_id:
                        logger.trace(f"      👤 任务将分配给用户: {assigned_user_id}")
                    elif assigned_agent_id:
                        logger.trace(f"      🤖 任务将分配给代理: {assigned_agent_id}")
                    else:
                        logger.trace(f"      ⏳ 任务暂未分配，将保持PENDING状态")
                    
                    # 创建任务实例，但暂时不分配上下文数据
                    task_title = node_data['name']
                    
                    # 确保task_description有值
                    task_description = node_data.get('task_description') or node_data.get('description') or f"执行节点 {node_data['name']} 的任务"
                    
                    logger.trace(f"      📝 任务描述: {task_description[:50]}{'...' if len(task_description) > 50 else ''}")
                    
                    # 收集任务上下文数据
                    logger.trace(f"      🔍 收集任务上下文数据...")
                    context_data = await self.context_manager.get_task_context_data(workflow_instance_id, created_node['node_instance_id'])
                    
                    # 将上下文数据转换为文本格式
                    context_text = json.dumps(context_data, ensure_ascii=False, indent=2, default=_json_serializer) if context_data else ""
                    input_text = json.dumps(node_data.get('input_data', {}), ensure_ascii=False, indent=2, default=_json_serializer)
                    
                    task_data = TaskInstanceCreate(
                        node_instance_id=created_node['node_instance_id'],
                        workflow_instance_id=workflow_instance_id,
                        processor_id=processor['processor_id'],
                        task_type=task_type,
                        task_title=task_title,
                        task_description=task_description,
                        input_data=input_text,
                        context_data=context_text,
                        assigned_user_id=assigned_user_id,
                        assigned_agent_id=assigned_agent_id,
                        estimated_duration=estimated_duration
                    )
                    
                    logger.trace(f"      📝 正在创建任务实例...")
                    try:
                        task = await self.task_instance_repo.create_task(task_data)
                        if task:
                            task_creation_count += 1
                            logger.trace(f"      ✅ 任务实例创建成功!")
                            logger.trace(f"         任务ID: {task['task_instance_id']}")
                            logger.trace(f"         任务标题: {task['task_title']}")
                        else:
                            logger.error(f"      ❌ 任务实例创建失败: 返回空结果")
                    except Exception as e:
                        logger.error(f"      ❌ 任务实例创建异常: {e}")
                        import traceback
                        logger.error(f"      异常堆栈: {traceback.format_exc()}")
            else:
                logger.trace(f"   ⏭️  节点类型不是PROCESSOR，跳过任务创建")
        
        logger.trace(f"🎉 任务创建完成! 总共创建了 {task_creation_count} 个任务实例")
    
    async def _start_workflow_execution_with_dependencies(self, 
                                                        workflow_instance_id: uuid.UUID,
                                                        workflow_base_id: uuid.UUID):
        """启动工作流执行（只启动START节点）"""
        try:
            logger.trace(f"启动工作流执行: {workflow_instance_id}")
            logger.trace(f"调用_get_start_nodes，工作流实例ID: {workflow_instance_id}")
            
            # 首先更新工作流实例状态为运行中
            update_data = WorkflowInstanceUpdate(status=WorkflowInstanceStatus.RUNNING)
            await self.workflow_instance_repo.update_instance(workflow_instance_id, update_data)
            
            # 获取START节点
            logger.trace(f"步骤A: 查找START节点")
            start_nodes = await self._get_start_nodes(workflow_instance_id)
            logger.trace(f"✅ START节点查询结果: 找到 {len(start_nodes)} 个START节点")
            
            if not start_nodes:
                logger.warning(f"⚠️ 没有找到pending状态的START节点，可能工作流已在运行中")
                # 检查是否有已完成的START节点，如果有则说明工作流已启动
                logger.trace(f"检查工作流当前状态并尝试恢复执行")
                await self._resume_workflow_execution(workflow_instance_id)
                return
            
            # 显示找到的START节点详情
            for i, start_node in enumerate(start_nodes, 1):
                unknown_text = "未知"
                logger.trace(f"  START节点{i}: {start_node.get('node_name', unknown_text)} (ID: {start_node['node_instance_id']})")
            
            # 执行START节点
            logger.trace(f"步骤B: 开始执行 {len(start_nodes)} 个START节点")
            for i, start_node in enumerate(start_nodes, 1):
                node_name = start_node.get('node_name', '\u672a\u77e5')
                logger.trace(f"  正在执行START节点 {i}/{len(start_nodes)}: {node_name} (ID: {start_node['node_instance_id']})")
                try:
                    await self._execute_start_node_directly(workflow_instance_id, start_node)
                    logger.trace(f"  ✅ START节点执行成功: {node_name}")
                except Exception as e:
                    logger.error(f"  ❌ START节点执行失败: {node_name} - {e}")
                    raise
            
            logger.trace(f"✅ 工作流 {workflow_instance_id} 所有START节点执行完成，工作流已开始运行")
            
        except Exception as e:
            logger.error(f"❌ 启动工作流执行失败: {e}")
            import traceback
            logger.error(f"异常堆栈详情: {traceback.format_exc()}")
            raise
    
    async def _get_start_nodes(self, workflow_instance_id: uuid.UUID) -> List[Dict]:
        """获取START节点"""
        try:
            logger.trace(f"🔍 开始查询START节点: workflow_instance_id={workflow_instance_id}")
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_instance_repo = NodeInstanceRepository()
            
            query = """
            SELECT ni.*, n.type as node_type, n.name as node_name
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.workflow_instance_id = $1
            AND LOWER(n.type) = 'start'
            AND ni.status IN ('pending', 'PENDING')
            AND ni.is_deleted = FALSE
            AND n.is_deleted = FALSE
            ORDER BY ni.created_at ASC
            """
            
            # 使用数据库管理器直接执行查询
            start_nodes = await node_instance_repo.db.fetch_all(query, workflow_instance_id)
            logger.trace(f"找到 {len(start_nodes)} 个START节点实例，工作流实例ID: {workflow_instance_id}")
            
            # 总是查找所有节点以进行调试
            logger.trace("调试: 查找所有节点类型")
            debug_query = """
            SELECT ni.*, n.type as node_type, n.name as node_name
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.workflow_instance_id = $1
            AND ni.is_deleted = FALSE
            AND n.is_deleted = FALSE
            ORDER BY n.type, ni.created_at ASC
            """
            all_nodes = await node_instance_repo.db.fetch_all(debug_query, workflow_instance_id)
            logger.trace(f"工作流实例 {workflow_instance_id} 的所有节点 ({len(all_nodes)} 个):")
            for node in all_nodes:
                logger.trace(f"  - 节点: {node.get('node_name', 'Unknown')} (类型: '{node.get('node_type', 'Unknown')}', 状态: {node.get('status', 'Unknown')})")
            
            # 如果没有找到pending状态的START节点，检查是否有已完成的START节点
            if not start_nodes and all_nodes:
                logger.warning("没有找到pending状态的START节点，检查是否有已完成的START节点")
                completed_start_query = """
                SELECT ni.*, n.type as node_type, n.name as node_name
                FROM node_instance ni
                JOIN node n ON ni.node_id = n.node_id
                WHERE ni.workflow_instance_id = $1
                AND LOWER(n.type) = 'start'
                AND ni.status IN ('completed', 'COMPLETED')
                AND ni.is_deleted = FALSE
                AND n.is_deleted = FALSE
                ORDER BY ni.created_at ASC
                """
                completed_start_nodes = await node_instance_repo.db.fetch_all(completed_start_query, workflow_instance_id)
                logger.trace(f"找到 {len(completed_start_nodes)} 个已完成的START节点")
                
                if completed_start_nodes:
                    logger.trace("START节点已经执行完成，工作流已在运行中")
                    # 返回空列表，表示不需要重新启动START节点
                    return []
                
                # 尝试不同的查询方式
                alt_query = """
                SELECT ni.*, n.type as node_type, n.name as node_name
                FROM node_instance ni
                JOIN node n ON ni.node_id = n.node_id
                WHERE ni.workflow_instance_id = $1
                AND n.type IN ('start', 'START')
                AND ni.status IN ('pending', 'PENDING')
                AND ni.is_deleted = FALSE
                AND n.is_deleted = FALSE
                ORDER BY ni.created_at ASC
                """
                alt_start_nodes = await node_instance_repo.db.fetch_all(alt_query, workflow_instance_id)
                logger.trace(f"备用查询找到 {len(alt_start_nodes)} 个START节点")
                if alt_start_nodes:
                    start_nodes = alt_start_nodes
            
            return start_nodes
            
        except Exception as e:
            logger.error(f"获取START节点失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            return []
    
    async def _resume_workflow_execution(self, workflow_instance_id: uuid.UUID):
        """恢复工作流执行，检查并触发准备好的节点"""
        try:
            logger.trace(f"🔄 开始恢复工作流执行: {workflow_instance_id}")
            
            # 查找所有pending状态的节点
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_instance_repo = NodeInstanceRepository()
            
            pending_query = """
            SELECT ni.*, n.type as node_type, n.name as node_name
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.workflow_instance_id = $1
            AND ni.status IN ('pending', 'PENDING', 'waiting', 'WAITING')
            AND ni.is_deleted = FALSE
            AND n.is_deleted = FALSE
            ORDER BY ni.created_at ASC
            """
            
            pending_nodes = await node_instance_repo.db.fetch_all(pending_query, workflow_instance_id)
            logger.trace(f"找到 {len(pending_nodes)} 个待处理状态的节点 (pending/waiting)")
            
            if pending_nodes:
                for node in pending_nodes:
                    node_name = node.get('node_name', '未知')
                    node_type = node.get('node_type', '未知')
                    logger.trace(f"  - 待处理节点: {node_name} (类型: {node_type}, 状态: {node.get('status', '未知')})")
                
                # 确保已完成的START节点已通知上下文管理器
                await self._ensure_completed_start_nodes_notified(workflow_instance_id)
                
                # 检查这些节点的依赖是否已满足，如果满足则触发执行
                logger.trace(f"检查pending节点的依赖关系")
                await self._check_and_trigger_ready_nodes(workflow_instance_id, pending_nodes)
            else:
                logger.trace(f"没有找到pending状态的节点，工作流可能已完成或出现异常")
                
        except Exception as e:
            logger.error(f"恢复工作流执行失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
    
    async def _ensure_completed_start_nodes_notified(self, workflow_instance_id: uuid.UUID):
        """确保已完成的START节点已通知上下文管理器"""
        try:
            logger.trace(f"🔍 [START节点修复] 检查已完成的START节点是否已通知上下文管理器")
            
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_instance_repo = NodeInstanceRepository()
            
            # 查找已完成的START节点
            completed_start_query = """
            SELECT ni.*, n.type as node_type, n.name as node_name, n.node_id
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.workflow_instance_id = $1
            AND LOWER(n.type) = 'start'
            AND ni.status IN ('completed', 'COMPLETED')
            AND ni.is_deleted = FALSE
            AND n.is_deleted = FALSE
            ORDER BY ni.completed_at ASC
            """
            
            completed_start_nodes = await node_instance_repo.db.fetch_all(completed_start_query, workflow_instance_id)
            logger.trace(f"  - 找到 {len(completed_start_nodes)} 个已完成的START节点")
            
            # 反序列化JSON字段
            for i, node in enumerate(completed_start_nodes):
                completed_start_nodes[i] = node_instance_repo._deserialize_json_fields(dict(node))
            
            if not completed_start_nodes:
                logger.trace(f"  ❌ 没有找到已完成的START节点")
                return
            
            for start_node in completed_start_nodes:
                node_instance_id = start_node['node_instance_id']
                node_id = start_node['node_id']
                node_name = start_node.get('node_name', '未知')
                output_data = start_node.get('output_data', {})
                
                logger.trace(f"  📋 处理START节点: {node_name}")
                logger.trace(f"    - node_instance_id: {node_instance_id}")
                logger.trace(f"    - node_id: {node_id}")
                
                # 检查上下文管理器中是否已经记录了这个节点的完成状态
                dependency_info = self.context_manager.get_node_dependency_info(node_instance_id)
                if dependency_info:
                    logger.trace(f"    - 节点依赖信息存在，检查是否已在completed_nodes中")
                    workflow_context = self.context_manager.contexts.get(workflow_instance_id, None)
                    if workflow_context:
                        completed_nodes = workflow_context.execution_context.get('completed_nodes', set())
                    else:
                        completed_nodes = set()
                    
                    if node_id not in completed_nodes:
                        logger.trace(f"  🔧 [START节点修复] START节点 {node_name} 已完成但未通知上下文管理器，正在修复...")
                        
                        # 确保output_data包含task_description
                        if isinstance(output_data, dict) and 'task_description' not in output_data:
                            # 从节点定义中获取task_description
                            task_description = start_node.get('task_description', '')
                            if not task_description:
                                from ..repositories.node.node_repository import NodeRepository
                                node_repo = NodeRepository()
                                node_data = await node_repo.get_node_by_id(node_id)
                                if node_data:
                                    task_description = node_data.get('task_description', '')
                            
                            # 确保output_data是字典类型，并添加task_description
                            if not isinstance(output_data, dict):
                                output_data = {}
                            output_data['task_description'] = task_description
                            logger.trace(f"    - 补充task_description: {task_description[:50]}...")
                        
                        # 手动通知上下文管理器
                        await self.context_manager.mark_node_completed(
                            workflow_instance_id, 
                            node_id, 
                            node_instance_id, 
                            output_data
                        )
                        
                        logger.trace(f"  ✅ [START节点修复] 已通知上下文管理器START节点 {node_name} 的完成状态")
                    else:
                        logger.trace(f"  ✅ START节点 {node_name} 已在上下文管理器中标记为完成")
                else:
                    logger.warning(f"  ⚠️ START节点 {node_name} 的依赖信息不存在，可能需要重新注册")
            
            logger.trace(f"✅ [START节点修复] 已完成的START节点通知检查完成")
            
        except Exception as e:
            logger.error(f"❌ [START节点修复] 确保START节点通知失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
    
    async def _check_and_trigger_ready_nodes(self, workflow_instance_id: uuid.UUID, pending_nodes: List[Dict]):
        """检查并触发准备好的节点"""
        try:
            logger.trace(f"检查 {len(pending_nodes)} 个pending节点的依赖关系")
            
            for node in pending_nodes:
                node_instance_id = node['node_instance_id']
                node_name = node.get('node_name', '未知')
                
                # 检查节点依赖是否满足
                if await self._check_node_dependencies_satisfied(workflow_instance_id, node_instance_id):
                    logger.trace(f"✅ 节点 {node_name} 的依赖已满足，触发执行")
                    await self._execute_node_when_ready(workflow_instance_id, node_instance_id)
                else:
                    logger.trace(f"⏳ 节点 {node_name} 的依赖尚未满足，等待中")
                    
        except Exception as e:
            logger.error(f"检查和触发准备好的节点失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
    
    # _collect_task_context_data 方法已被 WorkflowContextManager.get_task_context_data 替换

    async def _check_node_dependencies_satisfied(self, workflow_instance_id: uuid.UUID, node_instance_id: uuid.UUID) -> bool:
        """检查节点的依赖是否已满足（修复版：严格检查依赖顺序）"""
        try:
            # 🔍 首先检查工作流上下文是否存在
            if workflow_instance_id not in self.context_manager.contexts:
                logger.warning(f"⚠️ [依赖检查] 工作流上下文 {workflow_instance_id} 不存在，跳过节点 {node_instance_id}")
                return False
            
            # 🔍 严格检查节点状态 - 防止重复执行
            node_state = self.context_manager.node_completion_status.get(node_instance_id)
            if node_state in ['EXECUTING', 'COMPLETED']:
                logger.trace(f"🚫 [依赖检查] 节点 {node_instance_id} 内存状态为 {node_state}，跳过触发")
                return False
            
            # 🔍 双重检查：数据库状态验证
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_instance_repo = NodeInstanceRepository()
            
            node_info = await node_instance_repo.get_instance_by_id(node_instance_id)
            if node_info and node_info.get('status') in ['running', 'completed']:
                logger.trace(f"🚫 [依赖检查-DB] 节点 {node_instance_id} 数据库状态为 {node_info.get('status')}，跳过触发")
                return False
            
            # 🔍 获取节点依赖信息（修复版：支持降级查询）
            deps = self.context_manager.get_node_dependency_info(node_instance_id)
            if not deps:
                logger.warning(f"⚠️ [依赖检查] 节点 {node_instance_id} 在上下文管理器中没有依赖信息，尝试从数据库恢复")
                
                # 🔄 降级策略：从数据库重新构建依赖信息
                try:
                    await self._rebuild_node_dependencies_from_db(workflow_instance_id, node_instance_id)
                    
                    # 重新尝试获取依赖信息
                    deps = self.context_manager.get_node_dependency_info(node_instance_id)
                    if not deps:
                        logger.error(f"❌ [依赖检查] 无法从数据库恢复节点 {node_instance_id} 的依赖信息")
                        return False
                    else:
                        logger.info(f"✅ [依赖检查] 成功从数据库恢复节点 {node_instance_id} 的依赖信息")
                except Exception as e:
                    logger.error(f"❌ [依赖检查] 从数据库恢复依赖信息失败: {e}")
                    return False
            
            node_id = deps.get('node_id')
            upstream_nodes = deps.get('upstream_nodes', [])
            
            # 🔍 如果没有上游依赖（START节点），检查是否可以执行
            if not upstream_nodes:
                # START节点，检查是否已经在上下文中标记为完成
                context = self.context_manager.contexts[workflow_instance_id]
                if node_id in context.execution_context.get('completed_nodes', set()):
                    logger.trace(f"🚫 [依赖检查] START节点 {node_instance_id} 已在上下文中完成")
                    return False
                logger.trace(f"✅ [依赖检查] START节点 {node_instance_id} 无依赖，可以执行")
                return True
            
            # 🔍 严格检查所有上游依赖的完成状态
            context = self.context_manager.contexts[workflow_instance_id]
            completed_nodes = context.execution_context.get('completed_nodes', set())
            
            # 检查每个上游节点是否都已完成
            all_upstream_completed = True
            completed_count = 0
            
            for upstream_node_id in upstream_nodes:
                # 检查上下文状态
                if upstream_node_id in completed_nodes:
                    completed_count += 1
                    logger.trace(f"  ✅ 上游节点 {upstream_node_id} 在上下文中已完成")
                else:
                    # 双重检查：验证数据库状态
                    upstream_query = """
                    SELECT ni.status, ni.node_instance_id, n.name
                    FROM node_instance ni 
                    JOIN node n ON ni.node_id = n.node_id
                    WHERE ni.node_id = $1 
                    AND ni.workflow_instance_id = $2 
                    AND ni.is_deleted = FALSE
                    ORDER BY ni.created_at DESC LIMIT 1
                    """
                    
                    upstream_result = await node_instance_repo.db.fetch_one(
                        upstream_query, upstream_node_id, workflow_instance_id
                    )
                    
                    if upstream_result and upstream_result.get('status') == 'completed':
                        completed_count += 1
                        logger.trace(f"  ✅ 上游节点 {upstream_node_id} 在数据库中已完成")
                        # 同步到上下文（修复状态不一致）
                        context['completed_nodes'].add(upstream_node_id)
                    else:
                        all_upstream_completed = False
                        status = upstream_result.get('status') if upstream_result else 'not_found'
                        name = upstream_result.get('name') if upstream_result else 'Unknown'
                        logger.trace(f"  ❌ 上游节点 {upstream_node_id} ({name}) 状态为 {status}，依赖未满足")
                        break
            
            # 🔍 最终依赖检查结果
            dependencies_satisfied = all_upstream_completed and completed_count == len(upstream_nodes)
            
            if dependencies_satisfied:
                # 再次确认节点未被执行
                if node_id in context.execution_context.get('completed_nodes', set()):
                    logger.trace(f"🚫 [依赖检查] 节点 {node_instance_id} 已在上下文中完成，跳过")
                    return False
                
                logger.trace(f"✅ [依赖检查] 节点 {node_instance_id} 所有依赖已满足 ({completed_count}/{len(upstream_nodes)})")
                return True
            else:
                logger.trace(f"⏳ [依赖检查] 节点 {node_instance_id} 依赖未满足 ({completed_count}/{len(upstream_nodes)})")
                return False
                
        except Exception as e:
            logger.error(f"❌ [依赖检查] 检查节点依赖失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return False
                
    async def _rebuild_node_dependencies_from_db(self, workflow_instance_id: uuid.UUID, node_instance_id: uuid.UUID):
        """从数据库重新构建节点依赖信息（修复方法）"""
        try:
            logger.debug(f"🔄 [依赖重建] 开始从数据库重建节点 {node_instance_id} 的依赖信息")
            
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_repo = NodeInstanceRepository()
            
            # 获取节点实例信息
            node_instance = await node_repo.get_instance_by_id(node_instance_id)
            if not node_instance:
                logger.error(f"❌ [依赖重建] 节点实例不存在: {node_instance_id}")
                return False
            
            node_id = node_instance['node_id']
            logger.debug(f"  节点ID: {node_id}")
            
            # 查询上游连接关系
            upstream_query = """
            SELECT DISTINCT 
                nc.from_node_id as upstream_node_id,
                n.name as upstream_node_name,
                n.type as upstream_node_type
            FROM node_connection nc
            JOIN node n ON nc.from_node_id = n.node_id
            JOIN node_instance ni ON ni.node_id = n.node_id
            WHERE nc.to_node_id = $1 
            AND ni.workflow_instance_id = $2
            AND ni.is_deleted = FALSE
            ORDER BY n.name
            """
            
            upstream_connections = await node_repo.db.fetch_all(
                upstream_query, node_id, workflow_instance_id
            )
            
            logger.debug(f"  查询到 {len(upstream_connections)} 个上游连接")
            
            upstream_node_ids = []
            for upstream in upstream_connections:
                upstream_node_id = upstream['upstream_node_id']
                upstream_node_ids.append(upstream_node_id)
                logger.debug(f"    上游节点: {upstream.get('upstream_node_name', 'Unknown')} (node_id: {upstream_node_id})")
            
            # 重新注册依赖关系
            await self.context_manager.register_node_dependencies(
                workflow_instance_id,
                node_instance_id,
                node_id,
                upstream_node_ids
            )
            
            logger.debug(f"✅ [依赖重建] 成功重建节点 {node_instance_id} 的依赖信息: {len(upstream_node_ids)} 个上游节点")
            return True
            
        except Exception as e:
            logger.error(f"❌ [依赖重建] 重建依赖信息失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return False
    
    async def _try_recover_node_context_state(self, workflow_instance_id: uuid.UUID, node_instance_id: uuid.UUID):
        """尝试恢复节点的上下文状态"""
        try:
            logger.debug(f"🔄 [状态恢复] 尝试恢复节点 {node_instance_id} 的上下文状态")
            
            # 检查上下文管理器是否有生命周期一致性检查方法
            if hasattr(self.context_manager, 'ensure_context_lifecycle_consistency'):
                await self.context_manager.ensure_context_lifecycle_consistency(workflow_instance_id)
                logger.debug(f"✅ [状态恢复] 完成工作流生命周期一致性检查")
            
            # 检查是否可以重新初始化上下文
            if workflow_instance_id not in self.context_manager.contexts:
                logger.info(f"🔄 [状态恢复] 重新初始化工作流上下文: {workflow_instance_id}")
                await self.context_manager.initialize_workflow_context(workflow_instance_id, restore_from_snapshot=True)
                
                # 重新注册依赖关系
                await self._rebuild_workflow_dependencies(workflow_instance_id)
            
        except Exception as e:
            logger.error(f"❌ [状态恢复] 恢复节点上下文状态失败: {e}")
    
    async def _rebuild_workflow_dependencies(self, workflow_instance_id: uuid.UUID):
        """重建工作流的依赖关系"""
        try:
            logger.debug(f"🔧 [依赖重建] 开始重建工作流 {workflow_instance_id} 的依赖关系")
            
            # 获取工作流的所有节点实例
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_repo = NodeInstanceRepository()
            
            nodes_query = """
            SELECT ni.node_instance_id, ni.node_id, n.type
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.workflow_instance_id = $1 AND ni.is_deleted = FALSE
            ORDER BY ni.created_at
            """
            
            nodes = await node_repo.db.fetch_all(nodes_query, workflow_instance_id)
            
            for node in nodes:
                node_instance_id = node['node_instance_id']
                node_id = node['node_id']
                
                # 获取上游依赖
                upstream_query = """
                SELECT nc.from_node_id
                FROM node_connection nc
                WHERE nc.to_node_id = $1
                """
                
                upstream_results = await node_repo.db.fetch_all(upstream_query, node_id)
                upstream_nodes = [result['from_node_id'] for result in upstream_results]
                
                # 重新注册依赖
                await self.context_manager.register_node_dependencies(
                    node_instance_id, node_id, workflow_instance_id, upstream_nodes
                )
                
                logger.trace(f"🔧 [依赖重建] 节点 {node_instance_id} 依赖已重建: {len(upstream_nodes)} 个上游节点")
            
            logger.debug(f"✅ [依赖重建] 工作流 {workflow_instance_id} 依赖关系重建完成")
            
        except Exception as e:
            logger.error(f"❌ [依赖重建] 重建依赖关系失败: {e}")
    
    async def _execute_start_node_directly(self, workflow_instance_id: uuid.UUID, start_node: Dict[str, Any]):
        """直接执行START节点"""
        try:
            node_instance_id = start_node['node_instance_id']
            node_name = start_node.get('node_name', '未知')
            logger.trace(f"▶️ 开始直接执行START节点: {node_name} (ID: {node_instance_id})")
            
            # 更新节点实例状态为执行中
            logger.trace(f"  步骤1: 更新节点实例状态为 RUNNING")
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            from ..models.instance import NodeInstanceUpdate, NodeInstanceStatus
            
            node_instance_repo = NodeInstanceRepository()
            
            # 标记节点开始执行
            update_data = NodeInstanceUpdate(
                status=NodeInstanceStatus.RUNNING
            )
            await node_instance_repo.update_node_instance(node_instance_id, update_data)
            logger.trace(f"  ✅ 节点状态更新为 RUNNING 成功")
            
            # START节点没有实际任务，直接完成，但要包含task_description供下游使用
            logger.trace(f"  步骤2: START节点无实际任务，直接标记为 COMPLETED")
            
            # 获取节点的task_description
            task_description = start_node.get('task_description', '')
            if not task_description:
                # 如果节点实例没有task_description，从节点定义中获取
                from ..repositories.node.node_repository import NodeRepository
                node_repo = NodeRepository()
                node_data = await node_repo.get_node_by_id(start_node['node_id'])
                if node_data:
                    task_description = node_data.get('task_description', '')
            
            completed_data = NodeInstanceUpdate(
                status=NodeInstanceStatus.COMPLETED,
                output_data={
                    'message': 'START节点自动完成',
                    'task_description': task_description,  # 添加task_description供下游节点使用
                    'completed_at': datetime.utcnow().isoformat()
                }
            )
            await node_instance_repo.update_node_instance(node_instance_id, completed_data)
            logger.trace(f"  ✅ 节点状态更新为 COMPLETED 成功")
            
            # 步骤3: 通知上下文管理器节点完成
            logger.trace(f"  步骤3: 通知上下文管理器START节点完成")
            node_instance_data = await node_instance_repo.get_instance_by_id(node_instance_id)
            if node_instance_data and self.context_manager:
                node_id = node_instance_data['node_id']
                output_data = completed_data.output_data
                
                logger.trace(f"    - 通知上下文管理器: node_id={node_id}")
                logger.trace(f"    - 传递的output_data类型: {type(output_data)}")
                logger.trace(f"    - 传递的output_data内容: {output_data}")
                await self.context_manager.mark_node_completed(
                    workflow_instance_id, node_id, node_instance_id, output_data
                )
                logger.trace(f"    ✅ 上下文管理器通知完成")
            else:
                logger.warning(f"    ⚠️ 无法通知上下文管理器: node_instance_data={node_instance_data is not None}, context_manager={self.context_manager is not None}")
            
            # 获取下游节点并启动执行（这个方法可能是重复的，上下文管理器已经处理了）
            logger.trace(f"  步骤4: 触发下游节点执行（通过_trigger_downstream_nodes）")
            await self._trigger_downstream_nodes(workflow_instance_id, start_node)
            logger.trace(f"  ✅ 下游节点触发完成")
            
            logger.trace(f"  ✅ START节点执行完成: {node_name} (ID: {node_instance_id})")
            
        except Exception as e:
            node_name = start_node.get('node_name', '未知')
            logger.error(f"❌ 执行START节点失败 {node_name}: {e}")
            import traceback
            logger.error(f"异常堆栈详情: {traceback.format_exc()}")
            raise
    
    async def _trigger_downstream_nodes(self, workflow_instance_id: uuid.UUID, completed_node: Dict[str, Any]):
        """触发下游节点执行"""
        try:
            logger.trace(f"触发下游节点执行，已完成节点: {completed_node.get('node_base_id')}")
            
            # 1. 获取工作流实例上下文
            logger.trace(f"触发下游节点执行，已完成节点: {completed_node.get('node_id')}")
            
            # 使用统一上下文管理器处理依赖关系
            
        except Exception as e:
            logger.error(f"触发下游节点失败: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def _execute_node_when_ready(self, workflow_instance_id: uuid.UUID, node_instance_id: uuid.UUID):
        """当节点准备好时执行节点"""
        try:
            logger.trace(f"🚀 [节点执行] 开始执行节点: {node_instance_id}")
            logger.trace(f"  - 工作流实例: {workflow_instance_id}")
            
            # 首先检查节点是否已经完成或正在执行，防止重复执行
            node_status = self.context_manager.node_completion_status.get(node_instance_id)
            if node_status in ['COMPLETED', 'EXECUTING']:
                logger.warning(f"🔄 [节点执行-防重复] 节点 {node_instance_id} 状态为 {node_status}，跳过重复执行")
                return
            
            # 标记节点为执行中状态
            self.context_manager.node_completion_status[node_instance_id] = 'EXECUTING'
            logger.trace(f"  - 节点状态已标记为: EXECUTING")
            
            # 首先检查工作流上下文是否仍然存在
            if workflow_instance_id not in self.context_manager.contexts:
                logger.warning(f"❌ [节点执行] 工作流上下文 {workflow_instance_id} 已被清理，节点执行取消")
                
                # 🔄 尝试恢复上下文
                try:
                    logger.info(f"🔄 [节点执行] 尝试恢复工作流上下文: {workflow_instance_id}")
                    await self._try_recover_node_context_state(workflow_instance_id, node_instance_id)
                    
                    # 再次检查上下文是否恢复
                    if workflow_instance_id not in self.context_manager.contexts:
                        logger.error(f"❌ [节点执行] 无法恢复工作流上下文，节点执行终止")
                        # 恢复状态为PENDING
                        self.context_manager.node_completion_status[node_instance_id] = 'PENDING'
                        return
                    else:
                        logger.info(f"✅ [节点执行] 工作流上下文恢复成功")
                except Exception as recovery_error:
                    logger.error(f"❌ [节点执行] 上下文恢复失败: {recovery_error}")
                    # 恢复状态为PENDING
                    self.context_manager.node_completion_status[node_instance_id] = 'PENDING'
                    return
            
            # 检查节点是否准备好执行
            is_ready = self.context_manager.is_node_ready_to_execute(node_instance_id)
            logger.trace(f"  - 节点就绪状态检查: {is_ready}")
            
            if not is_ready:
                logger.warning(f"❌ [节点执行] 节点 {node_instance_id} 尚未准备好执行")
                # 恢复状态为PENDING
                self.context_manager.node_completion_status[node_instance_id] = 'PENDING'
                return
            
            # 获取节点信息
            dep_info = self.context_manager.get_node_dependency_info(node_instance_id)
            logger.trace(f"  - 依赖信息获取: {'成功' if dep_info else '失败'}")
            
            if not dep_info:
                logger.error(f"❌ [节点执行] 无法获取节点 {node_instance_id} 的依赖信息")
                return
            
            node_id = dep_info.get('node_id')  # 使用node_id而不是node_base_id
            logger.trace(f"  - 节点ID: {node_id}")
            logger.trace(f"  - 依赖数量: {dep_info.get('dependency_count', 0)}")
            logger.trace(f"  - 已完成上游: {len(dep_info.get('completed_upstream', set()))}")
            
            # 标记节点开始执行
            logger.trace(f"📍 [节点执行] 标记节点开始执行...")
            await self.context_manager.mark_node_executing(
                workflow_instance_id, node_id, node_instance_id  # 使用node_id
            )
            
            # 获取节点的上游上下文
            logger.trace(f"🔍 [节点执行] 收集上游上下文数据...")
            upstream_context = await self.context_manager.get_node_upstream_context(
                workflow_instance_id, node_instance_id
            )
            logger.trace(f"  - 上游结果数量: {len(upstream_context.get('immediate_upstream_results', {}))}")
            
            # 更新节点的任务实例，添加上下文数据
            logger.trace(f"📝 [节点执行] 更新任务上下文数据...")
            await self._update_node_tasks_with_context(node_instance_id, upstream_context)
            
            # 执行节点的任务
            logger.trace(f"⚡ [节点执行] 开始执行节点任务...")
            await self._execute_node_tasks(workflow_instance_id, node_instance_id)
            
            logger.trace(f"✅ [节点执行] 节点 {node_instance_id} 执行流程完成")
            
        except Exception as e:
            logger.error(f"❌ [节点执行] 执行节点 {node_instance_id} 失败: {e}")
            import traceback
            logger.error(f"  异常详情: {traceback.format_exc()}")
            
            # 标记节点失败
            dep_info = self.context_manager.get_node_dependency_info(node_instance_id)
            if dep_info:
                node_id = dep_info.get('node_id', dep_info.get('node_base_id'))  # 兼容处理
                await self.context_manager.mark_node_failed(
                    workflow_instance_id, 
                    node_id, 
                    node_instance_id,
                    {'error': str(e)}
                )
    
    async def _update_node_tasks_with_context(self, node_instance_id: uuid.UUID, upstream_context: Dict[str, Any]):
        """更新节点任务的上下文数据，并同步更新节点的输入数据"""
        try:
            # 构建完整的任务上下文 - 修复数据格式转换问题
            immediate_upstream_results = upstream_context.get('immediate_upstream_results', {})
            logger.trace(f"🔄 [数据格式转换] 原始上游结果: {immediate_upstream_results}")
            
            task_context = {
                'immediate_upstream': immediate_upstream_results,  # 修复：直接使用immediate_upstream_results
                'workflow_global': upstream_context.get('workflow_global', {}),
                'node_info': {
                    'node_instance_id': str(node_instance_id),
                    'upstream_node_count': upstream_context.get('upstream_node_count', 0)
                }
            }
            
            logger.trace(f"🔄 [数据格式转换] 最终任务上下文包含 {len(immediate_upstream_results)} 个上游节点数据")
            
            # 首先更新节点实例的输入数据（用于前端显示）
            logger.trace(f"📝 [节点上下文] 更新节点 {node_instance_id} 的输入数据")
            logger.trace(f"   - 上游结果数量: {len(task_context.get('immediate_upstream', {}))}")
            logger.trace(f"   - 工作流全局数据: {len(task_context.get('workflow_global', {}).get('global_data', {}))}")
            
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            from ..models.instance import NodeInstanceUpdate
            node_instance_repo = NodeInstanceRepository()
            
            node_update = NodeInstanceUpdate(input_data=task_context)
            await node_instance_repo.update_node_instance(node_instance_id, node_update)
            logger.trace(f"   ✅ 节点输入数据已更新：包含 {len(task_context)} 个顶级字段")
            
            # 然后获取节点的所有任务并更新它们的上下文
            tasks = await self.task_instance_repo.get_tasks_by_node_instance(node_instance_id)
            
            for task in tasks:
                
                # 将上下文转换为JSON字符串（数据库input_data字段是TEXT类型）
                from ..utils.helpers import safe_json_dumps
                task_context_json = safe_json_dumps(task_context)
                
                # 更新任务的输入数据（但不改变已完成或失败任务的状态）
                current_status = task.get('status', 'PENDING')
                
                # 只有PENDING状态的任务才需要更新状态
                if current_status == 'PENDING':
                    new_status = TaskInstanceStatus.ASSIGNED if task.get('assigned_user_id') or task.get('assigned_agent_id') else TaskInstanceStatus.PENDING
                    update_data = TaskInstanceUpdate(
                        input_data=task_context_json,
                        status=new_status
                    )
                    logger.warning(f"任务 {task['task_instance_id']} 状态更新: {current_status} → {new_status.value}")
                    logger.warning(f"任务 {task['task_instance_id']} 上下文数据: {len(task_context_json)} 字符")
                else:
                    # 已完成/失败/进行中的任务只更新上下文，不改变状态
                    update_data = TaskInstanceUpdate(
                        input_data=task_context_json
                    )
                    logger.warning(f"任务 {task['task_instance_id']} 状态保持: {current_status}（仅更新上下文）")
                    logger.warning(f"任务 {task['task_instance_id']} 上下文数据: {len(task_context_json)} 字符")
                
                await self.task_instance_repo.update_task(task['task_instance_id'], update_data)
                logger.warning(f"更新任务 {task['task_instance_id']} 的上下文数据")
                
        except Exception as e:
            logger.error(f"更新节点任务上下文失败: {e}")
            raise
    
    async def _execute_node_tasks(self, workflow_instance_id: uuid.UUID, node_instance_id: uuid.UUID):
        """执行节点的任务"""
        try:
            # 获取节点的所有任务
            tasks = await self.task_instance_repo.get_tasks_by_node_instance(node_instance_id)
            
            if not tasks:
                # 获取节点信息判断是否需要创建任务
                from ..repositories.instance.node_instance_repository import NodeInstanceRepository
                node_repo = NodeInstanceRepository()
                node_instance_data = await node_repo.get_instance_by_id(node_instance_id)
                
                if not node_instance_data:
                    logger.error(f"无法获取节点实例信息: {node_instance_id}")
                    return
                
                # 获取节点详细信息
                node_query = """
                SELECT n.*, ni.workflow_instance_id
                FROM node n 
                JOIN node_instance ni ON n.node_id = ni.node_id
                WHERE ni.node_instance_id = $1
                """
                node_info = await self.task_instance_repo.db.fetch_one(node_query, node_instance_id)
                
                if not node_info:
                    logger.error(f"无法获取节点详细信息: {node_instance_id}")
                    return
                
                # 如果是PROCESSOR节点但没有任务，需要先创建任务（不区分大小写）
                if node_info['type'].upper() == 'PROCESSOR':
                    logger.trace(f"🔧 PROCESSOR节点 {node_info['name']} 没有任务，开始创建任务...")
                    
                    # 构造节点数据用于任务创建
                    created_node = {
                        'node_instance_id': node_instance_id,
                        'node_type': node_info['type'],
                        'node_data': {
                            'node_id': node_info['node_id'],
                            'name': node_info['name'],
                            'description': node_info.get('description', ''),
                            'task_description': node_info.get('task_description', ''),
                            'input_data': {}
                        }
                    }
                    
                    logger.trace(f"📋 开始为节点创建任务，节点数据: {created_node}")
                    
                    try:
                        # 为这个节点创建任务
                        await self._create_tasks_for_nodes([created_node], workflow_instance_id)
                        logger.trace(f"✅ 节点 {node_info['name']} 任务创建完成")
                    except Exception as task_creation_error:
                        logger.error(f"❌ 节点 {node_info['name']} 任务创建失败: {task_creation_error}")
                        import traceback
                        logger.error(f"任务创建错误堆栈: {traceback.format_exc()}")
                        # 继续执行，但可能无法找到任务
                    
                    # 重新获取任务
                    tasks = await self.task_instance_repo.get_tasks_by_node_instance(node_instance_id)
                    
                    if not tasks:
                        logger.error(f"❌ PROCESSOR节点 {node_info['name']} 任务创建失败，没有配置处理器")
                        await self._complete_node_without_tasks(workflow_instance_id, node_instance_id)
                        return
                else:
                    # 如果是START或END节点等非PROCESSOR节点，直接标记完成
                    logger.trace(f"⏭️ 非PROCESSOR节点 {node_info.get('name', 'Unknown')} 没有任务，直接标记完成")
                    await self._complete_node_without_tasks(workflow_instance_id, node_instance_id)
                    return
            
            # 执行所有任务
            for task in tasks:
                if task['task_type'] == TaskInstanceType.AGENT.value:
                    # Agent任务：提交给AgentTaskService处理
                    await self._execute_agent_task(task)
                elif task['task_type'] == TaskInstanceType.HUMAN.value:
                    # Human任务：调用_execute_task方法处理（包含用户通知）
                    await self._execute_task(task)
                    logger.trace(f"Human任务 {task['task_instance_id']} 已分配并通知用户")
                elif task['task_type'] == TaskInstanceType.MIXED.value:
                    # Mixed任务：先分配给用户，同时提供AI辅助
                    await self._execute_mixed_task(task)
            
            # 注册任务完成监听
            await self._register_node_completion_monitor(workflow_instance_id, node_instance_id)
            
        except Exception as e:
            logger.error(f"执行节点任务失败: {e}")
            raise
    
    async def _complete_node_without_tasks(self, workflow_instance_id: uuid.UUID, node_instance_id: uuid.UUID):
        """完成没有任务的节点（如START、END节点）"""
        try:
            from datetime import datetime as dt
            from ..models.instance import NodeInstanceStatus, NodeInstanceUpdate
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            
            # 获取node_id用于标记完成
            node_repo = NodeInstanceRepository()
            node_instance_data = await node_repo.get_instance_by_id(node_instance_id)
            if not node_instance_data:
                logger.error(f"无法找到节点实例: {node_instance_id}")
                return
            
            node_id = node_instance_data['node_id']
            
            # 标记节点完成
            output_data = {
                'completed_at': dt.utcnow().isoformat(),
                'node_type': 'system',
                'message': '系统节点自动完成'
            }
            
            await self.context_manager.mark_node_completed(
                workflow_instance_id, node_id, node_instance_id, output_data
            )
            
            # 同时更新数据库中的节点实例状态
            try:
                node_repo = NodeInstanceRepository()
                node_update = NodeInstanceUpdate(
                    status=NodeInstanceStatus.COMPLETED,
                    output_data=output_data,
                    completed_at=dt.utcnow()
                )
                await node_repo.update_node_instance(node_instance_id, node_update)
                logger.trace(f"💾 [系统节点] 节点实例 {node_instance_id} 数据库状态已更新为COMPLETED")
            except Exception as e:
                logger.error(f"❌ [系统节点] 更新节点实例数据库状态失败: {e}")
            
            logger.trace(f"✅ 系统节点 {node_id} 自动完成")
            
        except Exception as e:
            logger.error(f"完成系统节点失败: {e}")
            raise
    
    async def _execute_agent_task(self, task: Dict[str, Any]):
        """执行Agent任务"""
        try:
            task_id = task['task_instance_id']
            logger.trace(f"🚀 [EXECUTION-ENGINE] 开始执行Agent任务: {task_id}")
            logger.trace(f"   - 任务标题: {task.get('task_title', 'unknown')}")
            logger.trace(f"   - 任务类型: {task.get('task_type', 'unknown')}")
            logger.trace(f"   - 当前状态: {task.get('status', 'unknown')}")
            logger.trace(f"   - 分配Agent: {task.get('assigned_agent_id', 'none')}")
            logger.trace(f"   - 处理器ID: {task.get('processor_id', 'none')}")
            
            # 调用AgentTaskService处理任务
            logger.trace(f"🔄 [EXECUTION-ENGINE] 调用AgentTaskService处理任务")
            await agent_task_service.process_agent_task(task_id)
            
            logger.trace(f"✅ [EXECUTION-ENGINE] Agent任务执行完成: {task_id}")
            
        except Exception as e:
            logger.error(f"❌ [EXECUTION-ENGINE] 执行Agent任务 {task['task_instance_id']} 失败: {e}")
            import traceback
            logger.error(f"   - 错误堆栈: {traceback.format_exc()}")
            raise
    
    async def _execute_mixed_task(self, task: Dict[str, Any]):
        """执行Mixed任务（人机协作）"""
        try:
            # Mixed任务分配给用户，同时启动AI辅助
            task_id = task['task_instance_id']
            
            # 更新任务状态为ASSIGNED（分配给用户）
            update_data = TaskInstanceUpdate(status=TaskInstanceStatus.ASSIGNED)
            await self.task_instance_repo.update_task(task_id, update_data)
            
            # 启动AI辅助（可选）
            asyncio.create_task(self._provide_ai_assistance(task))
            
            logger.trace(f"Mixed任务 {task_id} 已分配给用户，AI辅助已启动")
            
        except Exception as e:
            logger.error(f"执行Mixed任务失败: {e}")
            raise
    
    async def _provide_ai_assistance(self, task: Dict[str, Any]):
        """为Mixed任务提供AI辅助"""
        try:
            # 这里可以实现AI辅助逻辑
            # 例如：分析任务内容，提供建议等
            logger.trace(f"为任务 {task['task_instance_id']} 提供AI辅助")
            
        except Exception as e:
            logger.error(f"提供AI辅助失败: {e}")
    
    async def _register_node_completion_monitor(self, workflow_instance_id: uuid.UUID, node_instance_id: uuid.UUID):
        """注册节点完成监听器（防重复）"""
        try:
            # 检查是否已经有活跃的监听器
            if node_instance_id in self.active_monitors:
                logger.warning(f"🔄 [监听器注册-防重复] 节点 {node_instance_id} 已有活跃监听器，跳过重复注册")
                return
            
            logger.trace(f"📋 [监听器注册] 为节点 {node_instance_id} 注册完成监听器")
            logger.trace(f"   - 工作流实例: {workflow_instance_id}")
            
            # 添加到活跃监听器集合
            self.active_monitors.add(node_instance_id)
            
            # 启动节点完成监听协程
            task = asyncio.create_task(self._monitor_node_completion(workflow_instance_id, node_instance_id))
            logger.trace(f"✅ [监听器注册] 节点 {node_instance_id} 监听协程已启动")
            
        except Exception as e:
            logger.error(f"❌ [监听器注册] 注册节点完成监听失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    async def _monitor_node_completion(self, workflow_instance_id: uuid.UUID, node_instance_id: uuid.UUID):
        """监听节点完成"""
        try:
            logger.trace(f"🔍 [节点监听] 开始监听节点完成: {node_instance_id}")
            
            while True:
                # 检查节点的所有任务是否完成
                tasks = await self.task_instance_repo.get_tasks_by_node_instance(node_instance_id)
                
                if not tasks:
                    logger.trace(f"⚠️ [节点监听] 节点 {node_instance_id} 没有任务，停止监听")
                    break
                
                completed_tasks = [t for t in tasks if t['status'] == TaskInstanceStatus.COMPLETED.value]
                failed_tasks = [t for t in tasks if t['status'] == TaskInstanceStatus.FAILED.value]
                
                logger.trace(f"📊 [节点监听] 节点 {node_instance_id} 任务状态:")
                logger.trace(f"   - 总任务数: {len(tasks)}")
                logger.trace(f"   - 已完成: {len(completed_tasks)}")
                logger.trace(f"   - 失败: {len(failed_tasks)}")
                
                # 显示每个任务的详细状态
                for i, task in enumerate(tasks):
                    task_id = task.get('task_instance_id', 'unknown')
                    task_status = task.get('status', 'unknown')
                    task_title = task.get('task_title', 'unknown')
                    logger.trace(f"   - 任务{i+1}: {task_title} (ID: {task_id}) - 状态: {task_status}")
                
                if len(completed_tasks) == len(tasks):
                    # 所有任务完成，标记节点完成
                    logger.trace(f"🎉 [节点监听] 节点 {node_instance_id} 所有任务已完成，开始标记节点完成")
                    output_data = await self._aggregate_node_output(completed_tasks)
                    
                    # 检查context manager是否可用
                    if self.context_manager is None:
                        logger.error(f"❌ [节点监听] context_manager 为 None，无法标记节点完成")
                        break
                    
                    # 获取node_id用于依赖匹配，因为依赖关系是基于node_id注册的
                    from ..repositories.instance.node_instance_repository import NodeInstanceRepository
                    node_repo = NodeInstanceRepository()
                    node_instance_data = await node_repo.get_instance_by_id(node_instance_id)
                    node_id = node_instance_data['node_id'] if node_instance_data else None
                    
                    if node_id:
                        logger.trace(f"🎯 [节点监听] 标记节点完成: node_id={node_id}")
                        await self.context_manager.mark_node_completed(
                            workflow_instance_id, node_id, node_instance_id, output_data
                        )
                    else:
                        logger.error(f"❌ [节点监听] 无法获取node_id，无法标记节点完成")
                        break
                    
                    # 同时更新数据库中的节点实例状态
                    try:
                        from datetime import datetime
                        from ..models.instance import NodeInstanceStatus, NodeInstanceUpdate
                        from ..repositories.instance.node_instance_repository import NodeInstanceRepository
                        
                        node_repo = NodeInstanceRepository()
                        node_update = NodeInstanceUpdate(
                            status=NodeInstanceStatus.COMPLETED,
                            output_data=output_data,
                            completed_at=datetime.utcnow()
                        )
                        await node_repo.update_node_instance(node_instance_id, node_update)
                        logger.trace(f"💾 [节点监听] 节点实例 {node_instance_id} 数据库状态已更新为COMPLETED")
                    except Exception as e:
                        logger.error(f"❌ [节点监听] 更新节点实例数据库状态失败: {e}")
                    
                    logger.trace(f"✅ [节点监听] 节点 {node_instance_id} 已标记为完成，停止监听")
                    # 从活跃监听器集合中移除
                    self.active_monitors.discard(node_instance_id)
                    break
                elif len(failed_tasks) > 0:
                    # 有任务失败，标记节点失败
                    logger.error(f"❌ [节点监听] 节点 {node_instance_id} 有任务失败，标记节点失败")
                    error_info = {'failed_tasks': [str(t['task_instance_id']) for t in failed_tasks]}
                    
                    # 获取node_id用于标记失败
                    from ..repositories.instance.node_instance_repository import NodeInstanceRepository
                    node_repo = NodeInstanceRepository()
                    node_instance_data = await node_repo.get_instance_by_id(node_instance_id)
                    node_id = node_instance_data['node_id'] if node_instance_data else None
                    
                    if node_id:
                        await self.context_manager.mark_node_failed(
                            workflow_instance_id, node_id, node_instance_id, error_info
                        )
                    else:
                        logger.error(f"❌ [节点监听] 无法获取node_id，无法标记节点失败")
                    # 从活跃监听器集合中移除
                    self.active_monitors.discard(node_instance_id)
                    break
                
                # 等待5秒后再次检查
                logger.trace(f"⏳ [节点监听] 节点 {node_instance_id} 仍有任务未完成，5秒后再次检查")
                await asyncio.sleep(5)
                
        except Exception as e:
            logger.error(f"监听节点完成失败: {e}")
            # 异常时也要从活跃监听器集合中移除
            self.active_monitors.discard(node_instance_id)
        finally:
            # 确保监听器被清理
            self.active_monitors.discard(node_instance_id)
            logger.trace(f"🧹 [节点监听] 节点 {node_instance_id} 监听器已清理")
    
    def _make_json_serializable(self, obj):
        """将对象转换为JSON可序列化的形式"""
        if isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        else:
            return obj

    async def _aggregate_node_output(self, completed_tasks: List[Dict]) -> Dict[str, Any]:
        """聚合节点的输出数据"""
        try:
            aggregated = {
                'task_count': len(completed_tasks),
                'completed_at': datetime.utcnow().isoformat(),
                'task_results': []
            }
            
            combined_output = {}
            
            for task_index, task in enumerate(completed_tasks):
                task_result = {
                    'task_id': str(task['task_instance_id']),  # 转换UUID为字符串
                    'task_title': task.get('task_title', ''),
                    'output_data': task.get('output_data', ''),  # 现在是文本格式
                    'result_summary': task.get('result_summary', '')
                }
                aggregated['task_results'].append(task_result)
                
                # 合并任务输出数据（现在是文本格式）
                if task.get('output_data'):
                    output_data = task['output_data']
                    # 为每个任务创建一个键值对
                    task_key = f"task_{task_index + 1}_output"
                    combined_output[task_key] = str(output_data)
            
            aggregated['combined_output'] = combined_output
            
            return self._make_json_serializable(aggregated)
            
        except Exception as e:
            logger.error(f"聚合节点输出失败: {e}")
            return {'error': str(e)}
    
    async def _on_nodes_ready_to_execute(self, workflow_instance_id: uuid.UUID, ready_node_instance_ids: List[uuid.UUID]):
        """上下文管理器回调：有节点准备执行"""
        try:
            logger.trace(f"工作流 {workflow_instance_id} 中有 {len(ready_node_instance_ids)} 个节点准备执行")
            
            # 执行准备好的节点
            for node_instance_id in ready_node_instance_ids:
                await self._execute_node_when_ready(workflow_instance_id, node_instance_id)
                
        except Exception as e:
            logger.error(f"执行准备好的节点失败: {e}")
    
    async def _log_task_assignment_event(self, task_id: uuid.UUID, assigned_user_id: Optional[uuid.UUID], task_title: str):
        """记录任务分配事件"""
        try:
            event_data = {
                'event_type': 'task_assigned',
                'task_id': str(task_id),
                'assigned_user_id': str(assigned_user_id) if assigned_user_id else None,
                'task_title': task_title,
                'timestamp': now_utc().isoformat(),
                'status': 'success'
            }
            
            # 这里可以记录到事件日志表或发送到消息队列
            logger.trace(f"📝 任务分配事件记录: {event_data}")
            
            # 记录到专门的事件日志文件
            try:
                event_log_entry = f"{event_data['timestamp']}|{event_data['event_type']}|{event_data['task_id']}|{event_data['assigned_user_id']}|{task_title[:50]}"
                with open("task_events.log", "a", encoding="utf-8") as f:
                    f.write(event_log_entry + "\n")
                logger.warning(f"   事件已记录到文件")
            except Exception as e:
                logger.warning(f"   事件文件记录失败: {e}")
            
            # TODO: 可以在这里集成消息队列系统，如Redis、RabbitMQ等
            # await self.message_queue.publish('task_assignments', event_data)
            
        except Exception as e:
            logger.error(f"记录任务分配事件失败: {e}")
    
    async def _log_workflow_execution_summary(self, workflow_instance_id: uuid.UUID):
        """记录工作流执行摘要"""
        try:
            logger.trace(f"📊 生成工作流执行摘要: {workflow_instance_id}")
            
            # 获取工作流实例信息
            instance = await self.workflow_instance_repo.get_instance_by_id(workflow_instance_id)
            if not instance:
                logger.warning(f"   工作流实例不存在: {workflow_instance_id}")
                return
            
            # 获取所有任务
            tasks = await self.task_instance_repo.get_tasks_by_workflow_instance(workflow_instance_id)
            
            # 统计信息
            total_tasks = len(tasks)
            human_tasks = len([t for t in tasks if t['task_type'] == TaskInstanceType.HUMAN.value])
            agent_tasks = len([t for t in tasks if t['task_type'] == TaskInstanceType.AGENT.value])
            assigned_tasks = len([t for t in tasks if t['status'] in ['ASSIGNED', 'IN_PROGRESS', 'COMPLETED']])
            pending_tasks = len([t for t in tasks if t['status'] == 'PENDING'])
            
            # 输出摘要
            print(f"\n📊 【工作流执行摘要】")
            print(f"工作流实例: {instance.get('workflow_instance_name', 'Unknown')}")
            print(f"实例ID: {workflow_instance_id}")
            print(f"状态: {instance.get('status', 'Unknown')}")
            print(f"总任务数: {total_tasks}")
            print(f"  - 人工任务: {human_tasks}")
            print(f"  - Agent任务: {agent_tasks}")
            print(f"  - 已分配: {assigned_tasks}")
            print(f"  - 等待中: {pending_tasks}")
            print(f"创建时间: {instance.get('created_at', 'Unknown')}")
            print("=" * 50)
            
            # 列出所有已分配的人工任务
            human_assigned_tasks = [t for t in tasks if t['task_type'] == TaskInstanceType.HUMAN.value and t.get('assigned_user_id')]
            if human_assigned_tasks:
                print(f"📋 已分配的人工任务:")
                for i, task in enumerate(human_assigned_tasks, 1):
                    print(f"  {i}. {task['task_title']}")
                    print(f"     用户: {task.get('assigned_user_id')}")
                    print(f"     状态: {task['status']}")
                print("=" * 50)
            
        except Exception as e:
            logger.error(f"生成工作流执行摘要失败: {e}")
            import traceback
            logger.error(f"异常详情: {traceback.format_exc()}")
    
    async def _notify_user_new_task(self, user_id: uuid.UUID, task_id: uuid.UUID, task_title: str):
        """通知用户有新任务分配"""
        try:
            logger.trace(f"🔔 开始发送任务通知给用户: {user_id}")
            
            # 获取用户信息用于通知
            user_info = await self.user_repo.get_by_id(user_id, id_column="user_id")
            username = user_info.get('username', 'Unknown') if user_info else 'Unknown'
            
            notification_data = {
                'user_id': str(user_id),
                'username': username,
                'task_id': str(task_id),
                'task_title': task_title,
                'notification_type': 'new_task_assigned',
                'timestamp': now_utc().isoformat(),
                'message': f'您有新的任务: {task_title}',
                'action_url': f'/tasks/{task_id}'
            }
            
            logger.trace(f"📨 通知数据准备完成:")
            logger.trace(f"   - 用户: {username} ({user_id})")
            logger.trace(f"   - 任务: {task_title}")
            logger.trace(f"   - 时间: {notification_data['timestamp']}")
            
            # 方式1: 控制台通知（用于开发调试）
            print(f"\n🔔 【用户通知】")
            print(f"用户: {username} ({user_id})")
            print(f"消息: 您有新的任务分配")
            print(f"任务: {task_title}")
            print(f"任务ID: {task_id}")
            print(f"时间: {notification_data['timestamp']}")
            print(f"操作: 请登录系统查看任务详情")
            print("=" * 50)
            
            # 方式2: 记录到数据库（用户通知历史）
            try:
                await self._store_user_notification(notification_data)
                logger.trace(f"   ✅ 通知已存储到数据库")
            except Exception as e:
                logger.warning(f"   ⚠️  存储通知失败: {e}")
            
            # 方式3: 文件日志记录（可用于其他系统读取）
            try:
                notification_log_entry = f"{now_utc().isoformat()}|TASK_ASSIGNED|{user_id}|{username}|{task_id}|{task_title}"
                with open("user_notifications.log", "a", encoding="utf-8") as f:
                    f.write(notification_log_entry + "\n")
                logger.trace(f"   ✅ 通知已记录到文件")
            except Exception as e:
                logger.warning(f"   ⚠️  文件记录失败: {e}")
            
            # TODO: 方式4: 实时推送（未来实现）
            # 可以通过以下方式之一实现：
            # 1. WebSocket 推送: await self.websocket_manager.send_to_user(user_id, notification_data)
            # 2. Server-Sent Events (SSE): await self.sse_manager.send_event(user_id, notification_data)
            # 3. 消息队列: await self.message_queue.publish(f"user.{user_id}.notifications", notification_data)
            # 4. 邮件通知: await self.email_service.send_task_notification(user_info.get('email'), notification_data)
            
            logger.trace(f"   🎉 用户通知处理完成")
            
        except Exception as e:
            logger.error(f"❌ 发送用户通知失败: {e}")
            import traceback
            logger.error(f"   异常详情: {traceback.format_exc()}")
    
    async def _store_user_notification(self, notification_data: dict):
        """存储用户通知到数据库（可选功能）"""
        try:
            # 这里可以存储到专门的通知表中
            # 如果没有通知表，可以创建一个简单的记录表
            logger.warning(f"存储通知数据: {notification_data}")
            # 暂时跳过数据库存储，避免表结构依赖
        except Exception as e:
            logger.warning(f"存储用户通知失败: {e}")
    
    # ================================================================================
    # 延迟任务创建机制 - 核心方法
    # ================================================================================
    
    async def _check_node_prerequisites(self, workflow_instance_id: uuid.UUID, 
                                      node_instance_id: uuid.UUID) -> bool:
        """检查节点的前置条件是否满足（修复版：双重验证）"""
        try:
            logger.trace(f"🔍 检查节点前置条件: {node_instance_id}")
            
            # 从数据库查询节点实例信息
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_repo = NodeInstanceRepository()
            node_instance = await node_repo.get_instance_by_id(node_instance_id)
            
            if not node_instance:
                logger.error(f"❌ 节点实例不存在: {node_instance_id}")
                return False
            
            node_id = node_instance['node_id']
            logger.trace(f"  节点ID: {node_id}")
            
            # 🔒 严格检查：防止重复执行
            current_status = node_instance.get('status')
            if current_status in ['running', 'completed', 'failed']:
                logger.trace(f"  🚫 节点已处于 {current_status} 状态，跳过检查")
                return False  # 已处理过的节点不再处理
            
            # 🔍 双重检查：上下文管理器状态
            if hasattr(self.context_manager, 'contexts') and workflow_instance_id in self.context_manager.contexts:
                context = self.context_manager.contexts[workflow_instance_id]
                if node_id in context.execution_context.get('completed_nodes', set()):
                    logger.trace(f"  🚫 节点在上下文中已完成，跳过检查")
                    return False
                if node_id in context.execution_context.get('current_executing_nodes', set()):
                    logger.trace(f"  🚫 节点在上下文中正在执行，跳过检查")
                    return False
            
            # 查询该节点的前置节点（使用更严格的查询）
            prerequisite_query = '''
            SELECT source_n.node_id as prerequisite_node_id, source_n.name as prerequisite_name,
                   source_ni.node_instance_id as prerequisite_instance_id, source_ni.status as prerequisite_status,
                   c.workflow_id
            FROM node_connection c
            JOIN node source_n ON c.from_node_id = source_n.node_id  
            JOIN node target_n ON c.to_node_id = target_n.node_id
            JOIN node_instance source_ni ON source_n.node_id = source_ni.node_id
            WHERE target_n.node_id = $1 
              AND source_ni.workflow_instance_id = $2
              AND source_ni.is_deleted = FALSE
            ORDER BY source_n.name
            '''
            
            prerequisites = await self.workflow_instance_repo.db.fetch_all(
                prerequisite_query, node_id, workflow_instance_id
            )
            
            logger.trace(f"  找到 {len(prerequisites)} 个前置节点")
            
            # 如果没有前置节点（如START节点），需要再次检查是否已处理
            if not prerequisites:
                # 对于START节点，检查是否已经被处理过
                if current_status == 'completed':
                    logger.trace(f"  🚫 START节点已完成，跳过")
                    return False
                logger.trace(f"  ✅ 无前置节点（START节点），满足条件")
                return True
            
            # 检查所有前置节点是否都已完成
            all_completed = True
            completed_count = 0
            
            for prerequisite in prerequisites:
                status = prerequisite['prerequisite_status']
                name = prerequisite['prerequisite_name']
                prereq_node_id = prerequisite['prerequisite_node_id']
                
                logger.trace(f"    前置节点 {name} (node_id: {prereq_node_id}): {status}")
                
                if status == 'completed':
                    completed_count += 1
                    
                    # 🔍 双重验证：检查上下文管理器中的状态
                    if hasattr(self.context_manager, 'contexts') and workflow_instance_id in self.context_manager.contexts:
                        context = self.context_manager.contexts[workflow_instance_id]
                        if prereq_node_id not in context.execution_context.get('completed_nodes', set()):
                            logger.warning(f"    ⚠️ 前置节点 {name} 数据库显示已完成但上下文未更新，同步状态")
                            # 同步状态到上下文
                            context.execution_context['completed_nodes'].add(prereq_node_id)
                    
                    logger.trace(f"    ✅ 前置节点 {name} 已完成")
                else:
                    all_completed = False
                    logger.trace(f"    ❌ 前置节点 {name} 未完成: {status}")
            
            # 最终结果检查
            if all_completed and completed_count == len(prerequisites):
                logger.trace(f"  ✅ 所有前置节点已完成 ({completed_count}/{len(prerequisites)})，满足任务创建条件")
                return True
            else:
                logger.trace(f"  ⏳ 前置节点未全部完成 ({completed_count}/{len(prerequisites)})，等待中")
                return False
            
        except Exception as e:
            logger.error(f"❌ 检查节点前置条件失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return False
    
    async def _create_tasks_when_ready(self, workflow_instance_id: uuid.UUID, 
                                     node_instance_id: uuid.UUID) -> bool:
        """当节点满足前置条件时创建任务"""
        try:
            logger.trace(f"🎯 尝试为节点创建任务: {node_instance_id}")
            
            # 检查前置条件
            prerequisites_met = await self._check_node_prerequisites(workflow_instance_id, node_instance_id)
            if not prerequisites_met:
                logger.trace(f"  ⏳ 前置条件未满足，暂不创建任务")
                return False
            
            # 获取节点实例信息
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_repo = NodeInstanceRepository()
            node_instance = await node_repo.get_instance_by_id(node_instance_id)
            
            if not node_instance:
                logger.error(f"❌ 节点实例不存在: {node_instance_id}")
                return False
            
            # 获取节点详细信息
            node = await self.node_repo.get_node_by_id(node_instance['node_id'])
            if not node:
                logger.error(f"❌ 节点不存在: {node_instance['node_id']}")
                return False
            
            # 只为PROCESSOR节点创建任务
            if node['type'] != NodeType.PROCESSOR.value:
                logger.trace(f"  ⏭️ 节点类型不是PROCESSOR ({node['type']})，自动完成")
                
                # 对于非PROCESSOR节点（如END节点），直接标记为完成
                if node['type'] == NodeType.END.value:
                    await self._execute_end_node(workflow_instance_id, node_instance_id)
                elif node['type'] == NodeType.START.value:
                    from ..models.instance import NodeInstanceUpdate, NodeInstanceStatus
                    update_data = NodeInstanceUpdate(status=NodeInstanceStatus.COMPLETED)
                    await node_repo.update_node_instance(node_instance_id, update_data)
                    
                    # 修复：START节点完成时也需要调用mark_node_completed存储输出数据
                    logger.trace(f"🚀 START节点完成，存储输出数据到WorkflowContextManager")
                    task_description = node.get('task_description', '开始节点已完成')
                    start_output_data = {
                        'task_result': task_description,  # 将task_description作为输出结果传递给下游
                        'task_summary': 'START节点处理完成',
                        'execution_time': 0,
                        'completion_time': datetime.utcnow().isoformat()
                    }
                    logger.trace(f"  - START节点输出数据: {start_output_data}")
                    
                    await self.context_manager.mark_node_completed(
                        workflow_instance_id=workflow_instance_id,
                        node_id=node['node_id'],
                        node_instance_id=node_instance_id,
                        output_data=start_output_data
                    )
                else:
                    logger.error(f"error node type:{node['type']}")

                # 继续检查下游节点
                await self._check_downstream_nodes_for_task_creation(workflow_instance_id)
                return True
            
            # 检查节点状态，如果已完成或正在运行则无需处理
            current_status = node_instance['status']
            if current_status in ['completed', 'running', 'failed']:
                logger.trace(f"  ✅ 节点状态为{current_status}，无需重复处理")
                return True
            
            # 检查是否已经创建过任务
            existing_tasks_query = '''
            SELECT task_instance_id FROM task_instance 
            WHERE node_instance_id = $1 AND is_deleted = FALSE
            '''
            existing_tasks = await self.task_instance_repo.db.fetch_all(existing_tasks_query, node_instance_id)
            
            if existing_tasks:
                logger.trace(f"  ✅ 任务已存在，无需重复创建")
                return True
            
            # 对于已经是pending状态的节点，避免重复设置
            if current_status == 'pending':
                logger.trace(f"  ℹ️ 节点已是pending状态，跳过状态更新直接创建任务")
                # 跳过状态更新，直接进入任务创建流程
            else:
                # 更新节点状态为准备中
                from ..models.instance import NodeInstanceUpdate, NodeInstanceStatus
                update_data = NodeInstanceUpdate(status=NodeInstanceStatus.PENDING)
                
                # 添加重试机制来处理可能的时序问题
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        result = await node_repo.update_node_instance(node_instance_id, update_data)
                        if result:
                            logger.trace(f"  ✅ 节点状态更新为pending成功")
                            break
                        elif attempt < max_retries - 1:
                            logger.warning(f"节点实例更新失败，尝试 {attempt + 1}/{max_retries}，等待后重试...")
                            await asyncio.sleep(0.1)  # 短暂等待
                        else:
                            logger.error(f"节点实例更新失败，已达到最大重试次数")
                            # 继续执行，不因为状态更新失败而中断整个流程
                    except Exception as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"节点实例更新异常，尝试 {attempt + 1}/{max_retries}: {e}")
                            await asyncio.sleep(0.1)
                        else:
                            logger.error(f"节点实例更新异常，已达到最大重试次数: {e}")
                            # 继续执行
            
            # 为该节点创建任务
            created_node = {
                'node_instance_id': node_instance_id,
                'node_id': node['node_id'],  # 使用node_id而不是node_base_id
                'node_type': node['type'],
                'node_data': node
            }
            
            await self._create_tasks_for_nodes([created_node], workflow_instance_id)
            
            logger.trace(f"  ✅ 节点任务创建完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 创建节点任务失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return False
    
    async def _check_downstream_nodes_for_task_creation(self, workflow_instance_id: uuid.UUID):
        """检查下游节点是否可以创建任务"""
        try:
            logger.trace(f"🔄 检查下游节点任务创建机会")
            
            # 查询工作流中所有等待状态的节点
            waiting_nodes_query = '''
            SELECT ni.node_instance_id, ni.node_id, n.name, n.type
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.workflow_instance_id = $1 
              AND ni.status = 'pending'
              AND ni.is_deleted = FALSE
            '''
            
            waiting_nodes = await self.workflow_instance_repo.db.fetch_all(
                waiting_nodes_query, workflow_instance_id
            )
            
            logger.trace(f"  找到 {len(waiting_nodes)} 个等待中的节点")
            
            # 为每个等待节点检查是否可以创建任务
            for node in waiting_nodes:
                node_instance_id = node['node_instance_id']
                node_name = node['name']
                
                logger.trace(f"  检查节点: {node_name} ({node_instance_id})")
                
                # 尝试创建任务
                created = await self._create_tasks_when_ready(workflow_instance_id, node_instance_id)
                if created:
                    logger.trace(f"    ✅ 节点 {node_name} 任务创建成功")
                else:
                    logger.trace(f"    ⏳ 节点 {node_name} 条件未满足")
            
        except Exception as e:
            logger.error(f"❌ 检查下游节点失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    async def _execute_end_node(self, workflow_instance_id: uuid.UUID, node_instance_id: uuid.UUID):
        """执行END节点（修复版：严格依赖检查）"""
        try:
            logger.trace(f"🏁 执行END节点: {node_instance_id}")
            
            # 🔒 严格检查：防止重复执行  
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            from ..models.instance import NodeInstanceUpdate, NodeInstanceStatus
            
            node_repo = NodeInstanceRepository()
            node_info = await node_repo.get_instance_by_id(node_instance_id)
            
            if not node_info:
                logger.error(f"❌ [END节点] 节点实例不存在: {node_instance_id}")
                return
            
            # 检查节点当前状态
            current_status = node_info.get('status')
            if current_status in ['running', 'completed']:
                logger.trace(f"🚫 [END节点] 节点已处于 {current_status} 状态，跳过执行")
                return
            
            # 🔍 双重依赖检查：上下文管理器 + 数据库
            node_id = node_info['node_id']
            
            # 1. 检查上下文管理器的准备状态
            is_ready = self.context_manager.is_node_ready_to_execute(node_instance_id)
            if not is_ready:
                logger.warning(f"❌ [END节点] 节点 {node_instance_id} 在上下文管理器中未准备就绪")
                return
            
            # 2. 检查数据库依赖状态
            dependencies_satisfied = await self._check_node_dependencies_satisfied(workflow_instance_id, node_instance_id)
            if not dependencies_satisfied:
                logger.warning(f"❌ [END节点] 节点 {node_instance_id} 依赖检查失败，无法执行")
                return
            
            logger.trace(f"✅ [END节点] 依赖检查通过，开始执行")
            
            # 更新节点状态为运行中
            logger.trace(f"🏃 [END节点] 更新状态为运行中")
            update_data = NodeInstanceUpdate(status=NodeInstanceStatus.RUNNING)
            await node_repo.update_node_instance(node_instance_id, update_data)
            
            # 标记节点开始执行
            await self.context_manager.mark_node_executing(
                workflow_instance_id=workflow_instance_id,
                node_id=node_id,
                node_instance_id=node_instance_id
            )
            
            # 收集完整的工作流上下文
            logger.trace(f"📋 [END节点] 收集工作流上下文")
            context_data = await self._collect_workflow_context(workflow_instance_id)
            
            # 更新节点状态为完成，并保存上下文数据
            logger.trace(f"✅ [END节点] 更新状态为完成")
            final_update = NodeInstanceUpdate(
                status=NodeInstanceStatus.COMPLETED,
                output_data=context_data
            )
            await node_repo.update_node_instance(node_instance_id, final_update)
            
            # 通知上下文管理器节点完成
            logger.trace(f"🎉 [END节点] 通知上下文管理器节点完成")
            await self.context_manager.mark_node_completed(
                workflow_instance_id=workflow_instance_id,
                node_id=node_id,
                node_instance_id=node_instance_id,
                output_data=context_data
            )
            
            logger.trace(f"✅ END节点执行完成")
            
            # 检查工作流是否可以完成
            await self._check_workflow_completion(workflow_instance_id)
            
        except Exception as e:
            logger.error(f"❌ 执行END节点失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    async def _collect_workflow_context(self, workflow_instance_id: uuid.UUID) -> Dict[str, Any]:
        """收集工作流的完整上下文"""
        try:
            logger.trace(f"📋 收集工作流上下文: {workflow_instance_id}")
            
            # 获取所有已完成的节点实例及其输出
            context_query = '''
            SELECT ni.node_instance_id, ni.output_data, n.name as node_name, n.type as node_type
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.workflow_instance_id = $1 
              AND ni.status = 'completed'
              AND ni.is_deleted = FALSE
            ORDER BY ni.created_at
            '''
            
            completed_nodes = await self.workflow_instance_repo.db.fetch_all(
                context_query, workflow_instance_id
            )
            
            # 获取所有已完成的任务实例及其输出  
            task_context_query = '''
            SELECT ti.task_instance_id, ti.output_data, ti.task_title, ti.result_summary,
                   n.name as node_name, n.type as node_type
            FROM task_instance ti
            JOIN node_instance ni ON ti.node_instance_id = ni.node_instance_id
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.workflow_instance_id = $1 
              AND ti.status = 'completed'
              AND ti.is_deleted = FALSE
            ORDER BY ti.completed_at
            '''
            
            completed_tasks = await self.task_instance_repo.db.fetch_all(
                task_context_query, workflow_instance_id
            )
            
            # 构建完整上下文
            context_data = {
                'workflow_instance_id': str(workflow_instance_id),
                'completed_at': now_utc().isoformat(),
                'nodes_context': {},
                'tasks_context': {},
                'execution_summary': {
                    'total_nodes': len(completed_nodes),
                    'total_tasks': len(completed_tasks)
                }
            }
            
            # 添加节点上下文
            for node in completed_nodes:
                node_id = str(node['node_instance_id'])
                context_data['nodes_context'][node_id] = {
                    'node_name': node['node_name'],
                    'node_type': node['node_type'],
                    'output_data': node['output_data'] or {}
                }
            
            # 添加任务上下文
            for task in completed_tasks:
                task_id = str(task['task_instance_id'])
                context_data['tasks_context'][task_id] = {
                    'task_title': task['task_title'],
                    'node_name': task['node_name'],
                    'node_type': task['node_type'],
                    'output_data': task['output_data'] or {},
                    'result_summary': task['result_summary']
                }
            
            logger.trace(f"✅ 上下文收集完成: {len(completed_nodes)} 个节点, {len(completed_tasks)} 个任务")
            return context_data
            
        except Exception as e:
            logger.error(f"❌ 收集工作流上下文失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return {}
    
    async def _check_workflow_completion(self, workflow_instance_id: uuid.UUID):
        """检查工作流是否可以完成"""
        try:
            logger.trace(f"🏁 检查工作流完成状态: {workflow_instance_id}")
            
            # 查询所有节点实例的状态
            nodes_status_query = '''
            SELECT ni.node_instance_id, ni.status, n.name, n.type
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.workflow_instance_id = $1 AND ni.is_deleted = FALSE
            '''
            
            all_nodes = await self.workflow_instance_repo.db.fetch_all(
                nodes_status_query, workflow_instance_id
            )
            
            logger.trace(f"  工作流总节点数: {len(all_nodes)}")
            
            # 检查所有节点是否都已完成
            completed_nodes = [n for n in all_nodes if n['status'] == 'completed']
            failed_nodes = [n for n in all_nodes if n['status'] == 'failed']
            
            logger.trace(f"  已完成节点: {len(completed_nodes)}")
            logger.trace(f"  失败节点: {len(failed_nodes)}")
            
            # 如果有失败节点，标记工作流为失败
            if failed_nodes:
                from ..models.instance import WorkflowInstanceUpdate, WorkflowInstanceStatus
                update_data = WorkflowInstanceUpdate(
                    status=WorkflowInstanceStatus.FAILED,
                    error_message=f"工作流包含 {len(failed_nodes)} 个失败节点"
                )
                await self.workflow_instance_repo.update_instance(workflow_instance_id, update_data)
                logger.trace(f"❌ 工作流标记为失败")
                return
            
            # 如果所有节点都已完成，标记工作流为完成
            if len(completed_nodes) == len(all_nodes):
                from ..models.instance import WorkflowInstanceUpdate, WorkflowInstanceStatus
                update_data = WorkflowInstanceUpdate(status=WorkflowInstanceStatus.COMPLETED)
                await self.workflow_instance_repo.update_instance(workflow_instance_id, update_data)
                logger.trace(f"✅ 工作流标记为完成")
            else:
                logger.trace(f"⏳ 工作流仍在进行中: {len(completed_nodes)}/{len(all_nodes)} 节点完成")
            
        except Exception as e:
            logger.error(f"❌ 检查工作流完成状态失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")

    # =============================================================================
    # 新架构方法 - 支持WorkflowInstanceContext
    # =============================================================================
    
    async def _create_node_instances_with_new_context(self, 
                                                    workflow_context, 
                                                    workflow_instance_id: uuid.UUID, 
                                                    workflow_base_id: uuid.UUID,
                                                    nodes: List[Dict[str, Any]]):
        """使用新上下文管理器创建节点实例"""
        try:
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            from ..models.instance import NodeInstanceCreate, NodeInstanceStatus
            
            node_instance_repo = NodeInstanceRepository()
            
            for node in nodes:
                # 1. 创建节点实例
                node_instance_data = NodeInstanceCreate(
                    workflow_instance_id=workflow_instance_id,
                    node_id=node['node_id'],
                    node_base_id=node['node_base_id'],
                    node_instance_name=f"{node['name']}_instance",
                    task_description=node.get('task_description', ''),
                    status=NodeInstanceStatus.PENDING,
                    input_data={},
                    output_data={},
                    error_message=None,
                    retry_count=0
                )
                
                node_instance = await node_instance_repo.create_node_instance(node_instance_data)
                if not node_instance:
                    logger.error(f"创建节点实例失败: {node['name']}")
                    continue
                
                node_instance_id = node_instance['node_instance_id']
                logger.trace(f"创建节点实例: {node['name']} (ID: {node_instance_id})")
                
                # 2. 获取上游依赖 - 暂时使用空列表
                upstream_node_ids = []
                
                # 3. 在新上下文中注册依赖
                await workflow_context.register_node_dependencies(
                    node_instance_id,
                    node['node_id'],  # 使用node_id而不是node_base_id
                    upstream_node_ids
                )
                
                # 4. 为处理器节点创建任务实例
                if node['type'] == NodeType.PROCESSOR.value:
                    await self._create_tasks_for_node_new_context(node, node_instance_id, workflow_instance_id)
                
            logger.trace(f"✅ 使用新上下文创建了 {len(nodes)} 个节点实例")
            
        except Exception as e:
            logger.error(f"使用新上下文创建节点实例失赅: {e}")
            raise
    
    async def _create_tasks_for_node_new_context(self, node: Dict[str, Any], 
                                               node_instance_id: uuid.UUID,
                                               workflow_instance_id: uuid.UUID):
        """为节点创建任务实例（新架构）"""
        try:
            # 获取节点的处理器（修复：使用node_id）  
            processors = await self._get_node_processors(node['node_id'])
            
            for processor in processors:
                # 根据处理器类型确定任务类型和分配
                processor_type = processor.get('processor_type', processor.get('type', 'HUMAN'))
                task_type = self._determine_task_type(processor_type)
                assigned_user_id = processor.get('user_id')
                assigned_agent_id = processor.get('agent_id')
                
                # 添加调试日志
                logger.trace(f"🔍 [任务创建] 处理器信息:")
                logger.trace(f"   - 处理器名称: {processor.get('name', 'Unknown')}")
                logger.trace(f"   - 处理器类型: '{processor_type}' -> 任务类型: {task_type.value}")
                logger.trace(f"   - 分配用户: {assigned_user_id}")
                logger.trace(f"   - 分配Agent: {assigned_agent_id}")
                
                # 创建任务实例
                task_title = node['name']
                task_description = node.get('task_description') or node.get('description') or f"执行节点 {node['name']} 的任务"
                
                task_data = TaskInstanceCreate(
                    workflow_instance_id=workflow_instance_id,
                    node_instance_id=node_instance_id,
                    processor_id=processor.get('processor_id'),
                    task_type=task_type,
                    task_title=task_title,
                    task_description=task_description,
                    assigned_user_id=assigned_user_id,
                    assigned_agent_id=assigned_agent_id,
                    estimated_duration=processor.get('estimated_duration', 30),
                    input_data="{}",  # 空的JSON字符串
                    context_data=""   # 空字符串
                )
                
                task_instance = await self.task_instance_repo.create_task(task_data)
                if task_instance:
                    task_id = task_instance['task_instance_id']
                    logger.trace(f"创建任务实例: {task_title} (ID: {task_id}, 类型: {task_type})")
                else:
                    logger.error(f"创建任务实例失败: {task_title}")
                
        except Exception as e:
            logger.error(f"为节点创建任务实例失败: {e}")
            raise
    
    async def _start_workflow_execution_with_new_context(self, 
                                                       workflow_context,
                                                       workflow_instance_id: uuid.UUID,
                                                       workflow_base_id: uuid.UUID):
        """使用新上下文启动工作流执行"""
        try:
            # 获取准备执行的节点（START节点）
            ready_nodes = await workflow_context.get_ready_nodes()
            
            logger.trace(f"找到 {len(ready_nodes)} 个准备执行的节点")
            
            for node_instance_id in ready_nodes:
                try:
                    # 执行节点
                    await self._execute_node_with_new_context(workflow_context, node_instance_id)
                    logger.trace(f"启动节点执行: {node_instance_id}")
                    
                except Exception as e:
                    logger.error(f"启动节点执行失败 {node_instance_id}: {e}")
            
        except Exception as e:
            logger.error(f"使用新上下文启动工作流执行失败: {e}")
            raise
    
    async def _execute_node_with_new_context(self, workflow_context, node_instance_id: uuid.UUID):
        """使用新上下文执行节点"""
        try:
            # 检查节点是否准备好执行
            if not workflow_context.is_node_ready_to_execute(node_instance_id):
                logger.warning(f"节点 {node_instance_id} 尚未准备好执行")
                return
            
            # 获取节点信息
            dep_info = workflow_context.get_node_dependency_info(node_instance_id)
            if not dep_info:
                logger.error(f"无法获取节点 {node_instance_id} 的依赖信息")
                return
            
            node_id = dep_info['node_id']  # 使用node_id而不是node_base_id
            
            # 标记节点开始执行
            await workflow_context.mark_node_executing(node_id, node_instance_id)
            
            # 获取节点的任务实例
            tasks = await self.task_instance_repo.get_tasks_by_node_instance(node_instance_id)
            
            if not tasks:
                # 无任务节点（如START或END节点）
                output_data = {'message': f'Node {node_id} executed without tasks'}
                triggered_nodes = await workflow_context.mark_node_completed(
                    node_id, node_instance_id, output_data
                )
                
                # 处理触发的下游节点
                for triggered_node_id in triggered_nodes:
                    await self._execute_node_with_new_context(workflow_context, triggered_node_id)
                
            else:
                # 有任务的节点，启动任务执行
                for task in tasks:
                    await self._execute_task(task)
                
                logger.trace(f"节点 {node_id} 的 {len(tasks)} 个任务已启动")
            
        except Exception as e:
            logger.error(f"使用新上下文执行节点 {node_instance_id} 失败: {e}")
            # 标记节点失败
            if 'dep_info' in locals() and dep_info:
                await workflow_context.mark_node_failed(
                    dep_info['node_id'],  # 使用node_id而不是node_base_id
                    node_instance_id,
                    {'error': str(e)}
                )
            raise
    
    async def _log_workflow_execution_summary_new(self, workflow_context, workflow_instance_id: uuid.UUID):
        """生成新架构的执行摘要"""
        try:
            status = await workflow_context.get_workflow_status()
            
            logger.trace(f"\n📈 【工作流执行摘要 - 新架构】")
            logger.trace(f"  实例 ID: {workflow_instance_id}")
            logger.trace(f"  状态: {status['status']}")
            logger.trace(f"  总节点数: {status['total_nodes']}")
            logger.trace(f"  已完成: {status['completed_nodes']}")
            logger.trace(f"  执行中: {status['executing_nodes']}")
            logger.trace(f"  待执行: {status['pending_nodes']}")
            logger.trace(f"  失败: {status['failed_nodes']}")
            logger.trace(f"  架构类型: WorkflowInstanceContext")
            
        except Exception as e:
            logger.error(f"生成新架构执行摘要失败: {e}")
    
    async def get_execution_stats(self) -> Dict[str, Any]:
        """获取执行引擎统计信息"""
        stats = {
            'is_running': self.is_running,
            'architecture': 'new_context_management',
            'features': {
                'instance_isolation': True,
                'thread_safe': True,
                'auto_cleanup': True,
                'resource_management': True
            }
        }
        
        if hasattr(self, 'resource_cleanup_manager') and self.resource_cleanup_manager:
            cleanup_stats = self.resource_cleanup_manager.get_cleanup_stats()
            stats['resource_cleanup'] = cleanup_stats
        
        return stats

    async def _trigger_downstream_nodes_new_architecture(self, workflow_instance_id: uuid.UUID, completed_node: Dict[str, Any], context):
        """使用新架构触发下游节点"""
        try:
            node_id = completed_node.get('node_id')
            if not node_id:
                logger.warning("completed_node 缺少 node_id")
                return
            
            # 查询下游节点
            workflow_base_id = context.workflow_base_id
            downstream_query = """
            SELECT DISTINCT nc.to_node_id as downstream_node_id
            FROM node_connection nc
            WHERE nc.from_node_id = $1
            ORDER BY nc.to_node_id
            """
            downstream_results = await self.workflow_instance_repo.db.fetch_all(
                downstream_query, node_id
            )
            downstream_nodes = [result['downstream_node_id'] for result in downstream_results]
            
            logger.trace(f"找到 {len(downstream_nodes)} 个下游节点需要检查")
            
            for downstream_node_id in downstream_nodes:
                await self._check_and_trigger_node_new_architecture(
                    workflow_instance_id, downstream_node_id, context
                )
            
        except Exception as e:
            logger.error(f"新架构触发下游节点失败: {e}")
            import traceback
            traceback.print_exc()

    async def _check_and_trigger_node_new_architecture(self, workflow_instance_id: uuid.UUID, node_id: uuid.UUID, context):
        """检查并触发单个节点（新架构）"""
        try:
            # 获取该节点的所有上游依赖
            upstream_query = """
            SELECT DISTINCT nc.from_node_id as upstream_node_id
            FROM node_connection nc
            WHERE nc.to_node_id = $1
            ORDER BY nc.from_node_id
            """
            upstream_results = await self.workflow_instance_repo.db.fetch_all(
                upstream_query, node_id
            )
            upstream_nodes = [result['upstream_node_id'] for result in upstream_results]
            
            # 检查所有上游节点是否都已完成
            all_upstream_completed = True
            for upstream_node_id in upstream_nodes:
                if upstream_node_id not in context.completed_nodes:
                    all_upstream_completed = False
                    break
            
            if all_upstream_completed:
                # 更新节点状态为pending并创建任务
                await self._update_node_status_to_pending(workflow_instance_id, node_id)
                logger.trace(f"节点 {node_id} 所有依赖已满足，状态更新为pending")
            else:
                logger.trace(f"节点 {node_id} 仍有未完成的上游依赖")
                
        except Exception as e:
            logger.error(f"检查并触发节点失败: {e}")

    async def _trigger_downstream_nodes_legacy(self, workflow_instance_id: uuid.UUID, completed_node: Dict[str, Any]):
        """使用旧架构触发下游节点（向下兼容）"""
        try:
            node_id = completed_node.get('node_id')
            if not node_id:
                logger.warning("completed_node 缺少 node_id")
                return
            
            # 通过上下文管理器通知节点完成
            if self.context_manager:
                self.context_manager.mark_node_completed(
                    workflow_instance_id, 
                    node_id,  # 使用node_id而不是node_base_id
                    completed_node.get('output_data', {})
                )
                logger.trace(f"通过旧架构上下文管理器标记节点 {node_id} 完成")
            
            # 查询数据库获取下游节点
            workflow_instance = await self.workflow_instance_repo.get_workflow_instance(workflow_instance_id)
            if not workflow_instance:
                logger.error(f"未找到工作流实例: {workflow_instance_id}")
                return
            
            # 查询该工作流的所有节点实例
            all_node_instances_query = """
                SELECT ni.*, n.type as node_type, n.name as node_name
                FROM node_instance ni
                JOIN node n ON ni.node_id = n.node_id
                WHERE ni.workflow_instance_id = $1
                AND ni.status = 'pending'
                AND ni.is_deleted = FALSE
            """
            
            waiting_nodes = await self.workflow_instance_repo.db.fetch_all(
                all_node_instances_query, 
                workflow_instance_id
            )
            
            logger.trace(f"找到 {len(waiting_nodes)} 个等待中的节点")
            
            # 检查每个等待的节点是否可以执行
            for node in waiting_nodes:
                await self._check_node_dependencies_and_trigger(
                    workflow_instance_id, node['node_instance_id'], node['node_id']
                )
                
        except Exception as e:
            logger.error(f"旧架构触发下游节点失败: {e}")
            import traceback
            traceback.print_exc()

    async def _check_node_dependencies_and_trigger(self, workflow_instance_id: uuid.UUID, node_instance_id: uuid.UUID, node_id: uuid.UUID):
        """检查节点依赖并触发执行"""
        try:
            # 获取工作流版本ID用于查询连接关系
            workflow_instance = await self.workflow_instance_repo.get_instance_by_id(workflow_instance_id)
            workflow_id = workflow_instance['workflow_id'] if workflow_instance else None
            
            if not workflow_id:
                logger.error(f"无法获取工作流版本ID: {workflow_instance_id}")
                return
            
            # 查询该节点的上游依赖（使用node_connection表，这是正确的依赖关系来源）
            dependencies_query = """
                SELECT nc.from_node_id as upstream_node_id, ni_upstream.status as upstream_status
                FROM node_connection nc
                LEFT JOIN node_instance ni_upstream ON (
                    nc.from_node_id = ni_upstream.node_id 
                    AND ni_upstream.workflow_instance_id = $1
                )
                WHERE nc.to_node_id = $2 AND nc.workflow_id = $3
            """
            
            dependencies = await self.workflow_instance_repo.db.fetch_all(
                dependencies_query, 
                workflow_instance_id, node_id, workflow_id
            )
            
            # 检查所有上游节点是否已完成
            all_dependencies_met = True
            for dep in dependencies:
                if dep['upstream_status'] not in ['completed', 'COMPLETED']:
                    all_dependencies_met = False
                    logger.trace(f"节点 {node_id} 的上游节点 {dep['upstream_node_id']} 状态为 {dep['upstream_status']}")
                    break
            
            if all_dependencies_met:
                # 更新节点状态为pending
                await self._update_node_status_to_pending(workflow_instance_id, node_id)
                logger.trace(f"节点 {node_id} 所有依赖已满足，状态更新为pending")
            else:
                logger.trace(f"节点 {node_id} 依赖未满足，继续等待")
                
        except Exception as e:
            logger.error(f"检查节点依赖失败: {e}")

    async def _update_node_status_to_pending(self, workflow_instance_id: uuid.UUID, node_id: uuid.UUID):
        """更新节点状态为pending并创建相应任务"""
        try:
            # 查找节点实例
            find_node_query = """
                SELECT ni.*, n.type as node_type, n.name as node_name
                FROM node_instance ni
                JOIN node n ON ni.node_id = n.node_id
                WHERE ni.workflow_instance_id = $1 AND ni.node_id = $2
            """
            
            node_instance = await self.workflow_instance_repo.db.fetch_one(
                find_node_query, workflow_instance_id, node_id
            )
            
            if not node_instance:
                logger.error(f"未找到节点实例: workflow_instance_id={workflow_instance_id}, node_id={node_id}")
                return
            
            # 更新节点状态
            update_query = """
                UPDATE node_instance 
                SET status = 'pending', updated_at = CURRENT_TIMESTAMP
                WHERE node_instance_id = $1
            """
            
            await self.workflow_instance_repo.db.execute(
                update_query, 
                node_instance['node_instance_id']
            )
            
            # 为pending的节点创建任务
            await self._create_tasks_for_pending_node(node_instance)
            
            logger.trace(f"节点 {node_id} 状态已更新为pending，任务已创建")
            
        except Exception as e:
            logger.error(f"更新节点状态为pending失败: {e}")
            import traceback
            traceback.print_exc()

    async def _create_tasks_for_pending_node(self, node_instance: Dict[str, Any]):
        """为pending状态的节点创建任务"""
        try:
            node_type = node_instance.get('node_type', '').lower()
            node_instance_id = node_instance['node_instance_id']
            node_id = node_instance.get('node_id')
            
            # 对于START, END等节点，不需要创建任务实例
            if node_type in ['start', 'end']:
                logger.trace(f"   节点类型 {node_type} 不需要任务实例，跳过")
                return
            
            # 对于processor类型节点，需要查询处理器类型来确定任务类型
            task_type = None
            if node_type == 'processor':
                # 查询节点关联的处理器信息
                processor_query = """
                    SELECT p.type as processor_type, p.user_id, p.agent_id
                    FROM node_processor np
                    LEFT JOIN processor p ON np.processor_id = p.processor_id
                    WHERE np.node_id = %s
                    LIMIT 1
                """
                processor_info = await self.task_instance_repo.db.fetch_one(processor_query, node_id)
                
                if processor_info:
                    processor_type = processor_info['processor_type'].lower() if processor_info['processor_type'] else None
                    if processor_type == 'human':
                        task_type = TaskInstanceType.HUMAN
                    elif processor_type == 'agent':
                        task_type = TaskInstanceType.AGENT
                    elif processor_type == 'mixed':
                        task_type = TaskInstanceType.MIXED
                    else:
                        logger.warning(f"未知的处理器类型: {processor_type}")
                        return
                else:
                    logger.warning(f"节点 {node_id} 没有关联的处理器，无法创建任务")
                    return
            elif node_type == 'human':
                task_type = TaskInstanceType.HUMAN
            elif node_type == 'agent':
                task_type = TaskInstanceType.AGENT
            elif node_type == 'mixed':
                task_type = TaskInstanceType.MIXED
            else:
                logger.trace(f"   节点类型 {node_type} 不需要任务实例，跳过")
                return
                
            if not task_type:
                logger.error(f"无法确定节点 {node_id} 的任务类型")
                return
            
            # 创建任务实例 - 需要获取更多必要的信息
            workflow_instance_id = node_instance['workflow_instance_id']
            
            # 获取处理器信息用于任务分配
            processor_info = None
            if task_type == TaskInstanceType.HUMAN:
                processor_query = """
                    SELECT p.processor_id, p.user_id
                    FROM node_processor np
                    LEFT JOIN processor p ON np.processor_id = p.processor_id
                    WHERE np.node_id = %s AND p.type = 'human'
                    LIMIT 1
                """
                processor_info = await self.task_instance_repo.db.fetch_one(processor_query, node_id)
            elif task_type == TaskInstanceType.AGENT:
                processor_query = """
                    SELECT p.processor_id, p.agent_id
                    FROM node_processor np
                    LEFT JOIN processor p ON np.processor_id = p.processor_id
                    WHERE np.node_id = %s AND p.type = 'agent'
                    LIMIT 1
                """
                processor_info = await self.task_instance_repo.db.fetch_one(processor_query, node_id)
            
            if not processor_info:
                logger.error(f"找不到节点 {node_id} 的处理器信息")
                return
                
            # 构造符合TaskInstanceCreate模型的数据
            task_data = TaskInstanceCreate(
                node_instance_id=node_instance_id,
                workflow_instance_id=workflow_instance_id,
                processor_id=processor_info['processor_id'],
                task_type=task_type,
                task_title=f"Task for {node_instance.get('node_instance_name', 'Unknown')}",
                task_description=node_instance.get('task_description', f"Auto-generated task for node {node_instance_id}"),
                input_data=str(node_instance.get('input_data', {})),  # 转换为文本格式
                assigned_user_id=processor_info.get('user_id') if task_type == TaskInstanceType.HUMAN else None,
                assigned_agent_id=processor_info.get('agent_id') if task_type == TaskInstanceType.AGENT else None,
                estimated_duration=30  # 默认30分钟
            )
            
            task_instance = await self.task_instance_repo.create_task(task_data)
            if task_instance:
                # task_instance is a dict, get the ID from it
                task_instance_id = task_instance.get('task_instance_id') if isinstance(task_instance, dict) else task_instance.task_instance_id
                logger.trace(f"✅ 为节点 {node_instance_id} 创建了 {task_type} 类型的任务: {task_instance_id}")
                
                if task_type == TaskInstanceType.HUMAN and processor_info.get('user_id'):
                    logger.info(f"🎯 人工任务已分配给用户 {processor_info['user_id']}: {task_data.task_title}")
            else:
                logger.error(f"❌ 任务创建失败")
            
        except Exception as e:
            logger.error(f"为pending节点创建任务失败: {e}")
            import traceback
            traceback.print_exc()

    async def _cancel_running_tasks(self, instance_id: uuid.UUID):
        """取消正在运行的异步任务"""
        try:
            # 查找所有正在运行的任务实例
            running_tasks_query = """
                SELECT ti.*, ni.workflow_instance_id
                FROM task_instance ti
                JOIN node_instance ni ON ti.node_instance_id = ni.node_instance_id
                WHERE ni.workflow_instance_id = $1
                AND ti.status IN ('running', 'RUNNING', 'assigned', 'ASSIGNED')
            """
            
            running_tasks = await self.task_instance_repo.db.fetch_all(
                running_tasks_query, 
                instance_id
            )
            
            logger.trace(f"找到 {len(running_tasks)} 个正在运行的任务需要取消")
            
            for task in running_tasks:
                try:
                    # 更新任务状态为取消
                    task_id = task['task_instance_id']
                    update_query = """
                        UPDATE task_instance 
                        SET status = 'cancelled', 
                            error_message = '工作流被取消',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE task_instance_id = $1
                    """
                    
                    await self.task_instance_repo.db.execute(update_query, task_id)
                    logger.trace(f"已取消任务: {task_id}")
                    
                except Exception as e:
                    logger.error(f"取消任务 {task.get('task_instance_id')} 失败: {e}")
            
        except Exception as e:
            logger.error(f"取消运行任务失败: {e}")

    async def _cancel_instance_context_tasks(self, context):
        """取消实例上下文中的任务"""
        try:
            # 标记所有未完成的节点为取消状态
            for node_id, node_info in context.node_dependencies.items():
                if node_id not in context.completed_nodes:
                    # 添加到完成节点集合中，防止后续执行
                    context.completed_nodes.add(node_id)
                    logger.trace(f"标记节点 {node_id} 为已取消")
            
            # 清理上下文状态
            context.current_executing_nodes.clear()
            
        except Exception as e:
            logger.error(f"取消实例上下文任务失败: {e}")

    async def _notify_services_workflow_cancelled(self, instance_id: uuid.UUID):
        """通知相关服务工作流已取消"""
        try:
            # 通知Agent任务服务（如果有相关方法）
            try:
                from .agent_task_service import agent_task_service
                # 检查是否有取消方法，如果没有则跳过
                if hasattr(agent_task_service, 'cancel_workflow_tasks'):
                    await agent_task_service.cancel_workflow_tasks(instance_id)
                else:
                    logger.trace("Agent任务服务没有cancel_workflow_tasks方法，跳过通知")
            except Exception as e:
                logger.warning(f"通知Agent任务服务失败，但继续执行: {e}")
            
            # 清理执行队列中的相关任务
            await self._remove_workflow_from_queue(instance_id)
            
            logger.trace(f"已通知相关服务工作流 {instance_id} 取消")
            
        except Exception as e:
            logger.error(f"通知服务工作流取消失败: {e}")

    async def _remove_workflow_from_queue(self, instance_id: uuid.UUID):
        """从执行队列中移除工作流相关任务"""
        try:
            # 创建新的队列来存储不需要取消的任务
            temp_queue = asyncio.Queue()
            cancelled_count = 0
            
            # 处理现有队列中的所有项目
            while not self.execution_queue.empty():
                try:
                    item = self.execution_queue.get_nowait()
                    
                    # 检查是否属于要取消的工作流
                    if item.get('workflow_instance_id') == instance_id:
                        cancelled_count += 1
                        logger.trace(f"从队列中移除任务: {item.get('task_instance_id')}")
                    else:
                        # 保留其他工作流的任务
                        await temp_queue.put(item)
                        
                except asyncio.QueueEmpty:
                    break
            
            # 将保留的任务放回原队列
            while not temp_queue.empty():
                try:
                    item = temp_queue.get_nowait()
                    await self.execution_queue.put(item)
                except asyncio.QueueEmpty:
                    break
            
            if cancelled_count > 0:
                logger.trace(f"从执行队列中移除了 {cancelled_count} 个待执行任务")
                
        except Exception as e:
            logger.error(f"从执行队列移除任务失败: {e}")

    # =============================================================================
    # 人工任务管理方法 (已整合到统一服务)
    # =============================================================================
    
    async def get_user_tasks(self, user_id: uuid.UUID, 
                           status: Optional[TaskInstanceStatus] = None,
                           limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户的任务列表"""
        try:
            logger.info(f"🔍 [任务查询] 开始查询用户任务:")
            logger.info(f"   - 用户ID: {user_id}")
            logger.info(f"   - 状态过滤: {status.value if status else '全部'}")
            logger.info(f"   - 限制数量: {limit}")
            
            tasks = await self.task_instance_repo.get_human_tasks_for_user(user_id, status, limit)
            
            logger.info(f"📊 [任务查询] 查询结果: 找到 {len(tasks)} 个任务")
            
            # 添加任务优先级和截止时间等附加信息
            # for i, task in enumerate(tasks, 1):
            #     logger.info(f"   任务{i}: {task.get('task_title')} | 状态: {task.get('status')} | ID: {task.get('task_instance_id')}")
            #     task = await self._enrich_task_info(task)
            
            if len(tasks) == 0:
                logger.warning(f"⚠️ [任务查询] 用户 {user_id} 没有找到任何任务")
            
            return tasks
            
        except Exception as e:
            logger.error(f"获取用户任务失败: {e}")
            raise
    
    async def get_task_details(self, task_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取任务详情"""
        try:
            logger.info(f"🔍 [任务详情] 开始查询任务详情:")
            logger.info(f"   - 任务ID: {task_id}")
            logger.info(f"   - 用户ID: {user_id}")
            
            # 获取任务基础信息
            task = await self.task_instance_repo.get_task_by_id(task_id)
            if not task:
                logger.warning(f"⚠️ [任务详情] 任务不存在: {task_id}")
                return None
            
            # 验证任务分配给该用户
            assigned_user_id = task.get('assigned_user_id')
            user_id_str = str(user_id)
            assigned_user_id_str = str(assigned_user_id) if assigned_user_id else None
            
            logger.info(f"   - 分配用户ID: {assigned_user_id} (类型: {type(assigned_user_id)})")
            logger.info(f"   - 请求用户ID: {user_id} (类型: {type(user_id)})")
            logger.info(f"   - 字符串比较: '{assigned_user_id_str}' vs '{user_id_str}'")
            
            if assigned_user_id_str != user_id_str:
                logger.warning(f"⚠️ [任务详情] 用户 {user_id_str} 无权限访问任务 {task_id}")
                logger.warning(f"   - 分配给用户: {assigned_user_id_str}")
                return None
            
            # 获取节点信息
            node_info = await self._get_node_info(task.get('node_instance_id'))
            if node_info:
                task['node_info'] = node_info
            
            # 获取处理器信息
            processor_info = await self._get_processor_info(task.get('processor_id'))
            if processor_info:
                task['processor_info'] = processor_info
            
            # 获取上游上下文
            upstream_context = await self._get_upstream_context(task)
            task['upstream_context'] = upstream_context
            
            # 丰富任务信息
            task = await self._enrich_task_info(task)
            
            logger.info(f"✅ [任务详情] 任务详情查询成功")
            return task
            
        except Exception as e:
            logger.error(f"获取任务详情失败: {e}")
            raise
    
    async def start_human_task(self, task_id: uuid.UUID, user_id: uuid.UUID) -> Dict[str, Any]:
        """开始人工任务"""
        try:
            logger.info(f"🚀 [任务开始] 用户开始任务:")
            logger.info(f"   - 任务ID: {task_id}")
            logger.info(f"   - 用户ID: {user_id}")
            
            # 获取任务信息
            logger.info(f"🔍 [任务开始] 正在查询任务信息...")
            task = await self.task_instance_repo.get_task_by_id(task_id)
            if not task:
                logger.error(f"❌ [任务开始] 任务不存在: {task_id}")
                return {"success": False, "message": "任务不存在"}
            
            logger.info(f"📋 [任务开始] 找到任务信息:")
            logger.info(f"   - 任务标题: {task.get('task_title')}")
            logger.info(f"   - 当前状态: {task.get('status')}")
            logger.info(f"   - 分配用户ID: {task.get('assigned_user_id')}")
            logger.info(f"   - 任务类型: {task.get('task_type')}")
            
            # 验证权限
            logger.info(f"🔐 [任务开始] 验证用户权限...")
            assigned_user_id = task.get('assigned_user_id')
            logger.info(f"   - 请求用户ID: {user_id} (类型: {type(user_id)})")
            logger.info(f"   - 分配用户ID: {assigned_user_id} (类型: {type(assigned_user_id)})")
            
            # 统一转换为字符串进行比较
            user_id_str = str(user_id)
            assigned_user_id_str = str(assigned_user_id) if assigned_user_id else None
            logger.info(f"   - 字符串比较: '{user_id_str}' vs '{assigned_user_id_str}'")
            
            if assigned_user_id_str != user_id_str:
                logger.error(f"❌ [任务开始] 权限验证失败:")
                logger.error(f"   - 请求用户ID(str): {user_id_str}")
                logger.error(f"   - 分配用户ID(str): {assigned_user_id_str}")
                return {"success": False, "message": "您无权限操作此任务"}
            logger.info(f"✅ [任务开始] 权限验证通过")
            
            # 验证状态
            logger.info(f"📊 [任务开始] 验证任务状态...")
            current_status = task.get('status')
            # 支持大小写状态匹配
            allowed_statuses = ['PENDING', 'ASSIGNED', 'pending', 'assigned']
            if current_status not in allowed_statuses:
                logger.error(f"❌ [任务开始] 状态验证失败:")
                logger.error(f"   - 当前状态: {current_status}")
                logger.error(f"   - 允许的状态: {allowed_statuses}")
                return {"success": False, "message": f"任务状态不允许开始: {current_status}"}
            logger.info(f"✅ [任务开始] 状态验证通过")
            
            # 更新任务状态
            logger.info(f"💾 [任务开始] 准备更新任务状态为 IN_PROGRESS...")
            update_data = TaskInstanceUpdate(
                status=TaskInstanceStatus.IN_PROGRESS,
                started_at=now_utc()
            )
            
            logger.info(f"📝 [任务开始] 调用数据库更新...")
            result = await self.task_instance_repo.update_task(task_id, update_data)
            logger.info(f"💾 [任务开始] 数据库更新结果: {result}")
            
            if result:
                logger.info(f"✅ [任务开始] 任务状态已更新为 IN_PROGRESS")
                
                # 验证更新结果
                logger.info(f"🔍 [任务开始] 验证更新结果...")
                updated_task = await self.task_instance_repo.get_task_by_id(task_id)
                if updated_task:
                    logger.info(f"📊 [任务开始] 更新后的任务状态: {updated_task.get('status')}")
                    logger.info(f"📊 [任务开始] 更新后的开始时间: {updated_task.get('started_at')}")
                else:
                    logger.error(f"❌ [任务开始] 无法获取更新后的任务信息")
                
                success_result = {
                    "success": True,
                    "message": "任务已开始",
                    "task_id": str(task_id),
                    "status": "IN_PROGRESS",
                    "started_at": now_utc().isoformat()
                }
                logger.info(f"🎉 [任务开始] 返回成功结果: {success_result}")
                return success_result
            else:
                logger.error(f"❌ [任务开始] 数据库更新失败")
                return {"success": False, "message": "启动任务失败"}
                
        except Exception as e:
            logger.error(f"💥 [任务开始] 异常发生: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"📄 [任务开始] 异常堆栈: {traceback.format_exc()}")
            raise
    
    async def submit_human_task_result(self, task_id: uuid.UUID, user_id: uuid.UUID,
                                     result_data: Dict[str, Any], result_summary: Optional[str] = None) -> Dict[str, Any]:
        """提交人工任务结果"""
        try:
            logger.info(f"📝 [任务提交] 用户提交任务结果:")
            logger.info(f"   - 任务ID: {task_id}")
            logger.info(f"   - 用户ID: {user_id}")
            logger.info(f"   - 结果数据: {result_data}")
            logger.info(f"   - 结果键数量: {len(result_data.keys()) if isinstance(result_data, dict) else 'N/A'}")
            
            # 获取任务信息
            logger.info(f"🔍 [任务提交] 正在查询任务信息...")
            task = await self.task_instance_repo.get_task_by_id(task_id)
            if not task:
                logger.error(f"❌ [任务提交] 任务不存在: {task_id}")
                return {"success": False, "message": "任务不存在"}
            
            logger.info(f"📋 [任务提交] 找到任务信息:")
            logger.info(f"   - 任务标题: {task.get('task_title')}")
            logger.info(f"   - 当前状态: {task.get('status')}")
            logger.info(f"   - 分配用户ID: {task.get('assigned_user_id')}")
            logger.info(f"   - 任务类型: {task.get('task_type')}")
            
            # 验证权限
            logger.info(f"🔐 [任务提交] 验证用户权限...")
            assigned_user_id = task.get('assigned_user_id')
            logger.info(f"   - 请求用户ID: {user_id} (类型: {type(user_id)})")
            logger.info(f"   - 分配用户ID: {assigned_user_id} (类型: {type(assigned_user_id)})")
            
            # 统一转换为字符串进行比较
            user_id_str = str(user_id)
            assigned_user_id_str = str(assigned_user_id) if assigned_user_id else None
            logger.info(f"   - 字符串比较: '{user_id_str}' vs '{assigned_user_id_str}'")
            
            if assigned_user_id_str != user_id_str:
                logger.error(f"❌ [任务提交] 权限验证失败:")
                logger.error(f"   - 请求用户ID(str): {user_id_str}")
                logger.error(f"   - 分配用户ID(str): {assigned_user_id_str}")
                return {"success": False, "message": "您无权限操作此任务"}
            logger.info(f"✅ [任务提交] 权限验证通过")
            
            # 验证状态
            logger.info(f"📊 [任务提交] 验证任务状态...")
            current_status = task.get('status')
            # 支持大小写状态匹配
            allowed_statuses = ['IN_PROGRESS', 'ASSIGNED', 'in_progress', 'assigned']
            if current_status not in allowed_statuses:
                logger.error(f"❌ [任务提交] 状态验证失败:")
                logger.error(f"   - 当前状态: {current_status}")
                logger.error(f"   - 允许的状态: {allowed_statuses}")
                return {"success": False, "message": f"任务状态不允许提交: {current_status}"}
            logger.info(f"✅ [任务提交] 状态验证通过")
            
            # 更新任务状态和结果
            logger.info(f"💾 [任务提交] 准备更新任务状态为 COMPLETED...")
            
            # 将字典转换为JSON字符串以符合模型要求
            import json
            output_data_str = json.dumps(result_data, ensure_ascii=False) if result_data else "{}"
            logger.info(f"   - 输出数据字符串长度: {len(output_data_str)}")
            
            update_data = TaskInstanceUpdate(
                status=TaskInstanceStatus.COMPLETED,
                output_data=output_data_str,
                result_summary=result_summary,
                completed_at=now_utc()
            )
            
            result = await self.task_instance_repo.update_task(task_id, update_data)
            if result:
                logger.info(f"✅ [任务提交] 任务状态已更新为 COMPLETED")
                
                # 获取更新后的任务
                updated_task = await self.task_instance_repo.get_task_by_id(task_id)
                
                # 统一处理任务完成 - 避免重复调用 mark_node_completed
                await self._handle_task_completion_unified(task, updated_task, result_data, "human")
                
                return {
                    "success": True,
                    "message": "任务结果已提交",
                    "task_id": str(task_id),
                    "status": "COMPLETED"
                }
            else:
                logger.error(f"❌ [任务提交] 数据库更新失败")
                return {"success": False, "message": "提交任务结果失败"}
                
        except Exception as e:
            logger.error(f"提交人工任务结果失败: {e}")
            raise
    
    async def pause_human_task(self, task_id: uuid.UUID, user_id: uuid.UUID,
                             pause_reason: Optional[str] = None) -> Dict[str, Any]:
        """暂停人工任务"""
        try:
            logger.info(f"⏸️ [任务暂停] 用户暂停任务:")
            logger.info(f"   - 任务ID: {task_id}")
            logger.info(f"   - 用户ID: {user_id}")
            logger.info(f"   - 暂停原因: {pause_reason}")
            
            # 获取任务信息
            task = await self.task_instance_repo.get_task_by_id(task_id)
            if not task:
                return {"success": False, "message": "任务不存在"}
            
            # 验证权限
            assigned_user_id = task.get('assigned_user_id')
            user_id_str = str(user_id)
            assigned_user_id_str = str(assigned_user_id) if assigned_user_id else None
            
            if assigned_user_id_str != user_id_str:
                return {"success": False, "message": "您无权限操作此任务"}
            
            # 验证状态 - 支持大小写匹配
            current_status = task.get('status')
            if current_status not in ['IN_PROGRESS', 'in_progress']:
                return {"success": False, "message": f"只有进行中的任务可以暂停，当前状态: {current_status}"}
            
            # 更新任务状态
            update_data = TaskInstanceUpdate(
                status=TaskInstanceStatus.PAUSED,
                paused_reason=pause_reason,
                paused_at=now_utc()
            )
            
            result = await self.task_instance_repo.update_task(task_id, update_data)
            if result:
                logger.info(f"✅ [任务暂停] 任务状态已更新为 PAUSED")
                return {
                    "success": True,
                    "message": "任务已暂停",
                    "task_id": str(task_id),
                    "status": "PAUSED"
                }
            else:
                return {"success": False, "message": "暂停任务失败"}
                
        except Exception as e:
            logger.error(f"暂停人工任务失败: {e}")
            raise
    
    async def cancel_human_task(self, task_id: uuid.UUID, user_id: uuid.UUID,
                              cancel_reason: Optional[str] = None) -> Dict[str, Any]:
        """取消人工任务"""
        try:
            logger.info(f"🚫 [任务取消] 用户取消任务:")
            logger.info(f"   - 任务ID: {task_id}")
            logger.info(f"   - 用户ID: {user_id}")
            logger.info(f"   - 取消原因: {cancel_reason}")
            
            # 获取任务信息
            task = await self.task_instance_repo.get_task_by_id(task_id)
            if not task:
                return {"success": False, "message": "任务不存在"}
            
            # 验证权限
            assigned_user_id = task.get('assigned_user_id')
            user_id_str = str(user_id)
            assigned_user_id_str = str(assigned_user_id) if assigned_user_id else None
            
            if assigned_user_id_str != user_id_str:
                return {"success": False, "message": "您无权限操作此任务"}
            
            # 验证状态 - 支持大小写匹配
            current_status = task.get('status')
            if current_status in ['COMPLETED', 'CANCELLED', 'FAILED', 'completed', 'cancelled', 'failed']:
                return {"success": False, "message": f"任务已结束，无法取消，当前状态: {current_status}"}
            
            # 更新任务状态
            update_data = TaskInstanceUpdate(
                status=TaskInstanceStatus.CANCELLED,
                error_message=cancel_reason or "用户取消",
                cancelled_at=now_utc()
            )
            
            result = await self.task_instance_repo.update_task(task_id, update_data)
            if result:
                logger.info(f"✅ [任务取消] 任务状态已更新为 CANCELLED")
                return {
                    "success": True,
                    "message": "任务已取消",
                    "task_id": str(task_id),
                    "status": "CANCELLED"
                }
            else:
                return {"success": False, "message": "取消任务失败"}
                
        except Exception as e:
            logger.error(f"取消人工任务失败: {e}")
            raise
    
    # 通用任务操作方法（为API层提供兼容接口）
    async def pause_task(self, task_id: uuid.UUID, user_id: uuid.UUID, reason: Optional[str] = None) -> Dict[str, Any]:
        """暂停任务（通用接口）"""
        return await self.pause_human_task(task_id, user_id, reason)
    
    async def cancel_task(self, task_id: uuid.UUID, user_id: uuid.UUID, reason: Optional[str] = None) -> Dict[str, Any]:
        """取消任务（通用接口）"""
        return await self.cancel_human_task(task_id, user_id, reason)
    
    async def request_help(self, task_id: uuid.UUID, user_id: uuid.UUID, help_message: str) -> Dict[str, Any]:
        """请求帮助"""
        try:
            logger.info(f"🆘 [请求帮助] 用户请求帮助:")
            logger.info(f"   - 任务ID: {task_id}")
            logger.info(f"   - 用户ID: {user_id}")
            logger.info(f"   - 帮助信息: {help_message}")
            
            # 获取任务信息
            task = await self.task_instance_repo.get_task_by_id(task_id)
            if not task:
                return {"success": False, "message": "任务不存在"}
            
            # 验证权限
            assigned_user_id = task.get('assigned_user_id')
            user_id_str = str(user_id)
            assigned_user_id_str = str(assigned_user_id) if assigned_user_id else None
            
            if assigned_user_id_str != user_id_str:
                return {"success": False, "message": "您无权限操作此任务"}
            
            # 记录帮助请求到任务实例的context_data中
            current_context = task.get('context_data', {})
            if 'help_requests' not in current_context:
                current_context['help_requests'] = []
            
            help_request = {
                'timestamp': now_utc().isoformat(),
                'message': help_message,
                'status': 'pending'
            }
            current_context['help_requests'].append(help_request)
            
            # 更新任务
            update_data = TaskInstanceUpdate(context_data=current_context)
            result = await self.task_instance_repo.update_task(task_id, update_data)
            
            if result:
                logger.info(f"✅ [请求帮助] 帮助请求已记录")
                return {
                    "success": True,
                    "message": "帮助请求已提交",
                    "task_id": str(task_id),
                    "help_request": help_request
                }
            else:
                return {"success": False, "message": "提交帮助请求失败"}
                
        except Exception as e:
            logger.error(f"请求帮助失败: {e}")
            raise
    
    async def reject_task(self, task_id: uuid.UUID, user_id: uuid.UUID, reason: str) -> Dict[str, Any]:
        """拒绝任务"""
        try:
            logger.info(f"🚫 [拒绝任务] 用户拒绝任务:")
            logger.info(f"   - 任务ID: {task_id}")
            logger.info(f"   - 用户ID: {user_id}")
            logger.info(f"   - 拒绝原因: {reason}")
            
            # 获取任务信息
            task = await self.task_instance_repo.get_task_by_id(task_id)
            if not task:
                return {"success": False, "message": "任务不存在"}
            
            # 验证权限
            assigned_user_id = task.get('assigned_user_id')
            user_id_str = str(user_id)
            assigned_user_id_str = str(assigned_user_id) if assigned_user_id else None
            
            if assigned_user_id_str != user_id_str:
                return {"success": False, "message": "您无权限操作此任务"}
            
            # 验证状态 - 支持大小写匹配
            current_status = task.get('status')
            if current_status not in ['PENDING', 'ASSIGNED', 'pending', 'assigned']:
                return {"success": False, "message": f"任务状态不允许拒绝: {current_status}"}
            
            # 更新任务状态为拒绝
            update_data = TaskInstanceUpdate(
                status=TaskInstanceStatus.CANCELLED,
                error_message=f"用户拒绝: {reason}",
                cancelled_at=now_utc()
            )
            
            result = await self.task_instance_repo.update_task(task_id, update_data)
            if result:
                logger.info(f"✅ [拒绝任务] 任务状态已更新为 CANCELLED")
                
                # TODO: 这里可以添加重新分配任务的逻辑
                
                return {
                    "success": True,
                    "message": "任务已拒绝",
                    "task_id": str(task_id),
                    "status": "CANCELLED"
                }
            else:
                return {"success": False, "message": "拒绝任务失败"}
                
        except Exception as e:
            logger.error(f"拒绝任务失败: {e}")
            raise
    
    async def get_task_history(self, user_id: uuid.UUID, 
                             days: int = 30, limit: int = 100) -> List[Dict[str, Any]]:
        """获取用户任务历史"""
        try:
            logger.info(f"📜 [任务历史] 查询用户任务历史:")
            logger.info(f"   - 用户ID: {user_id}")
            logger.info(f"   - 天数: {days}")
            logger.info(f"   - 限制: {limit}")
            
            tasks = await self.task_instance_repo.get_user_task_history(user_id, days, limit)
            
            # 丰富任务信息
            for task in tasks:
                task = await self._enrich_task_info(task)
            
            logger.info(f"✅ [任务历史] 找到 {len(tasks)} 条历史记录")
            return tasks
            
        except Exception as e:
            logger.error(f"获取任务历史失败: {e}")
            raise
    
    async def get_task_statistics(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """获取用户任务统计信息"""
        try:
            logger.info(f"📊 [任务统计] 查询用户任务统计:")
            logger.info(f"   - 用户ID: {user_id}")
            
            stats = await self.task_instance_repo.get_user_task_statistics(user_id)
            
            logger.info(f"✅ [任务统计] 统计信息查询成功")
            return stats
            
        except Exception as e:
            logger.error(f"获取任务统计失败: {e}")
            raise
    
    # =============================================================================
    # 辅助方法 (已整合到统一服务)
    # =============================================================================
    
    async def _get_node_info(self, node_instance_id: Optional[uuid.UUID]) -> Optional[Dict[str, Any]]:
        """获取节点信息"""
        if not node_instance_id:
            return None
            
        try:
            query = """
            SELECT ni.*, n.name as node_name, n.type as node_type, n.description
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.node_instance_id = $1
            """
            return await self.task_instance_repo.db.fetch_one(query, node_instance_id)
        except Exception as e:
            logger.error(f"获取节点信息失败: {e}")
            return None
    
    async def _get_processor_info(self, processor_id: Optional[uuid.UUID]) -> Optional[Dict[str, Any]]:
        """获取处理器信息"""
        if not processor_id:
            return None
            
        try:
            query = """
            SELECT p.*, u.username, a.agent_name
            FROM processor p
            LEFT JOIN "user" u ON p.user_id = u.user_id
            LEFT JOIN agent a ON p.agent_id = a.agent_id
            WHERE p.processor_id = $1
            """
            return await self.processor_repo.db.fetch_one(query, processor_id)
        except Exception as e:
            logger.error(f"获取处理器信息失败: {e}")
            return None
    
    async def _get_upstream_context(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """获取上游上下文"""
        try:
            workflow_instance_id = task.get('workflow_instance_id')
            node_instance_id = task.get('node_instance_id')
            
            if not workflow_instance_id or not node_instance_id:
                return {}
            
            # 使用统一上下文管理器获取上游上下文
            return await self.context_manager.get_node_upstream_context(
                workflow_instance_id, node_instance_id
            )
        except Exception as e:
            logger.error(f"获取上游上下文失败: {e}")
            return {}
    
    async def _enrich_task_info(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """丰富任务信息"""
        try:
            # 添加执行时间等计算字段
            if task.get('started_at') and not task.get('completed_at'):
                execution_time = (now_utc() - task['started_at']).total_seconds() / 60
                task['execution_time_minutes'] = round(execution_time, 2)
            
            # 添加任务优先级
            task['priority'] = self._calculate_task_priority(task)
            
            # 添加截止时间
            task['due_date'] = self._calculate_due_date(task)
            
            return task
        except Exception as e:
            logger.error(f"丰富任务信息失败: {e}")
            return task
    
    def _calculate_task_priority(self, task: Dict[str, Any]) -> str:
        """计算任务优先级"""
        try:
            # 基于任务类型和创建时间计算优先级
            created_at = task.get('created_at')
            if not created_at:
                return "normal"
            
            age_hours = (now_utc() - created_at).total_seconds() / 3600
            
            if age_hours > 24:
                return "high"
            elif age_hours > 8:
                return "medium"
            else:
                return "normal"
        except Exception:
            return "normal"
    
    def _calculate_due_date(self, task: Dict[str, Any]) -> Optional[str]:
        """计算截止时间"""
        try:
            created_at = task.get('created_at')
            estimated_duration = task.get('estimated_duration', 60)  # 默认60分钟
            
            if created_at:
                due_date = created_at + timedelta(minutes=estimated_duration)
                return due_date.isoformat()
            return None
        except Exception:
            return None
    
    async def _handle_task_completion_unified(self, task: Dict[str, Any], 
                                            updated_task: Dict[str, Any],
                                            output_data: str,
                                            task_type: str):
        """统一处理任务完成 - 避免重复调用 mark_node_completed"""
        try:
            logger.info(f"🔄 [统一任务完成] 处理{task_type}任务完成: {task['task_instance_id']}")
            
            # 获取节点信息
            node_query = """
            SELECT n.node_id 
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.node_instance_id = $1
            """
            node_info = await self.task_instance_repo.db.fetch_one(node_query, task['node_instance_id'])
            
            if not node_info:
                logger.error(f"❌ 无法找到节点信息: {task['node_instance_id']}")
                return
            
            # 构造输出数据
            completion_output = {
                "message": f"{task_type}任务完成",
                "task_type": task_type,
                "output_data": output_data,
                "completed_at": updated_task.get('completed_at').isoformat() if updated_task.get('completed_at') else None,
                "task_id": str(task['task_instance_id'])
            }
            
            # 只在这里调用一次 mark_node_completed - 避免重复
            await self.context_manager.mark_node_completed(
                workflow_instance_id=task['workflow_instance_id'],
                node_id=node_info['node_id'],
                node_instance_id=task['node_instance_id'],
                output_data=completion_output
            )
            
            logger.info(f"✅ [统一任务完成] {task_type}任务完成处理成功")
            
        except Exception as e:
            logger.error(f"💥 [统一任务完成] 处理失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")


# 全局执行引擎实例
execution_engine = ExecutionEngine()