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
from time import sleep
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
        logger.info(f"🔗 [EXECUTION-ENGINE] 注册Agent任务完成回调监听器")
        logger.info(f"   - 执行服务实例: {self}")
        logger.info(f"   - 注册前回调数量: {len(agent_task_service.completion_callbacks)}")
        
        agent_task_service.register_completion_callback(self)
        
        logger.info(f"   - 注册后回调数量: {len(agent_task_service.completion_callbacks)}")
        logger.info(f"   - 回调列表: {[str(cb) for cb in agent_task_service.completion_callbacks]}")
        logger.info("✅ 已注册Agent任务回调监听器")
        
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
        """执行工作流 - 解耦重构版本（修复锁超时问题）"""
        
        # 🔍 [调试] 参数类型检查
        logger.info(f"🔍 [UUID调试] execute_workflow入口参数检查:")
        logger.info(f"🔍 [UUID调试] request.workflow_base_id类型: {type(request.workflow_base_id)}, 值: {request.workflow_base_id}")
        logger.info(f"🔍 [UUID调试] executor_id类型: {type(executor_id)}, 值: {executor_id}")
        
        # 🔧 修复锁超时：缩小事务范围，只包含数据创建
        workflow_data = None
        async with self.workflow_instance_repo.db.transaction() as conn:
            try:
                logger.trace(f"🔄 [编排器] 开始工作流编排: {request.workflow_base_id}")
                
                # 1. 幂等性检查
                existing = await self._check_workflow_idempotency(
                    conn, request, executor_id
                )
                if existing:
                    return existing
                
                # 2. 数据层：创建工作流数据（纯数据操作 - 快速完成）
                workflow_data = await self._create_workflow_data(
                    conn, request, executor_id
                )
                
                logger.trace(f"✅ [编排器] 数据层创建完成，事务即将提交")
                
                # 事务在此处自动提交，释放锁
                
            except Exception as e:
                logger.error(f"❌ [编排器] 数据创建失败: {e}")
                import traceback
                logger.error(f"   - 错误堆栈: {traceback.format_exc()}")
                raise
        
        # 3. 上下文层：注册执行上下文（事务外 - 避免长时间持锁）
        try:
            await self._register_execution_context(workflow_data)
            logger.trace(f"✅ [编排器] 工作流编排完成")
            return workflow_data
        except Exception as e:
            logger.error(f"❌ [编排器] 上下文注册失败: {e}")
            # 数据已创建成功，返回基本信息
            workflow_data['message'] += f" (注意: 上下文注册失败，可能影响自动执行: {str(e)})"
            return workflow_data
    
    async def _check_workflow_idempotency(self, conn, request: WorkflowExecuteRequest, 
                                        executor_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """幂等性检查 - 纯查询逻辑"""
        logger.trace(f"🔍 [幂等检查] 检查重复执行")
        
        existing_check_query = """
            SELECT workflow_instance_id, status, workflow_instance_name, created_at
            FROM `workflow_instance` 
            WHERE workflow_base_id = %s 
            AND executor_id = %s 
            AND workflow_instance_name = %s
            AND status IN ('RUNNING', 'PENDING')
            AND is_deleted = FALSE
            ORDER BY created_at DESC
            LIMIT 1
        """
        
        existing = await conn.fetchrow(
            existing_check_query, 
            request.workflow_base_id, 
            executor_id, 
            request.workflow_instance_name
        )
        
        if existing:
            logger.info(f"🔄 [幂等检查] 发现已存在的运行中实例: {existing['workflow_instance_id']}")
            return {
                'instance_id': existing['workflow_instance_id'],
                'status': 'already_running',
                'message': f'工作流实例 "{request.workflow_instance_name}" 已在运行中',
                'existing_instance': {
                    'id': existing['workflow_instance_id'],
                    'name': existing['workflow_instance_name'],
                    'status': existing['status'],
                    'created_at': existing['created_at']
                }
            }
        
        return None
    
    async def _create_workflow_data(self, conn, request: WorkflowExecuteRequest, 
                                  executor_id: uuid.UUID) -> Dict[str, Any]:
        """数据层：纯数据创建操作"""
        from ..models.instance import NodeInstanceStatus
        from ..models.node import NodeType
        import uuid, json
        from ..utils.helpers import now_utc
        
        logger.trace(f"🏗️ [数据层] 开始创建工作流数据")
        
        # 1. 验证工作流
        workflow = await self.workflow_repo.get_workflow_by_base_id(request.workflow_base_id)
        if not workflow:
            raise ValueError("工作流不存在")
        workflow_id = workflow['workflow_id']
        
        # 2. 创建工作流实例
        instance_id = uuid.uuid4()
        create_instance_query = """
            INSERT INTO `workflow_instance` 
            (workflow_instance_id, workflow_id, workflow_base_id, executor_id, workflow_instance_name, 
             input_data, context_data, status, created_at, is_deleted)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        await conn.execute(
            create_instance_query,
            instance_id, workflow_id, request.workflow_base_id, executor_id, 
            request.workflow_instance_name,
            json.dumps(request.input_data or {}), json.dumps(request.context_data or {}),
            'RUNNING', now_utc(), False
        )
        
        # 3. 批量创建节点实例和对应的任务实例
        nodes = await self._get_workflow_nodes_by_version_id(workflow_id)
        if not nodes:
            raise ValueError(f"工作流 {workflow_id} 没有节点")
        
        node_instances = []
        start_nodes_count = 0
        created_tasks_count = 0
        
        # 🔧 Linus式修复: 导入附件服务
        from ..services.file_association_service import FileAssociationService
        file_service = FileAssociationService()
        
        for node in nodes:
            node_instance_id = uuid.uuid4()
            
            # 创建节点实例
            create_node_query = """
                INSERT INTO `node_instance`
                (node_instance_id, workflow_instance_id, node_id, node_base_id, 
                 node_instance_name, task_description, status, input_data, output_data,
                 error_message, retry_count, created_at, is_deleted)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            await conn.execute(
                create_node_query,
                node_instance_id, instance_id, node['node_id'], node['node_base_id'],
                f"{node['name']}_instance", node.get('task_description', ''),
                NodeInstanceStatus.PENDING.value, json.dumps({}), json.dumps({}),
                None, 0, now_utc(), False
            )
            
            # 🔧 Critical Fix: 创建节点实例后立即继承附件
            try:
                await file_service.inherit_node_files_to_instance(
                    node_id=uuid.UUID(node['node_id']), 
                    node_instance_id=node_instance_id
                )
            except Exception as e:
                logger.warning(f"⚠️ 节点实例 {node_instance_id} 附件继承失败: {e}")
            
            node_instances.append({
                'node_instance_id': node_instance_id,
                'node_id': node['node_id'],
                'node_name': node['name'],
                'node_type': node['type']
            })
            
            if node['type'] == NodeType.START.value:
                start_nodes_count += 1
            
            # 🔧 修复Critical Bug: 不要在此处创建任务实例！
            # 任务实例应该只在节点准备执行时才创建，而不是在工作流创建时全部创建
            # 这样可以确保只有满足依赖关系的节点才会有分配的任务
            
            # 注释掉原来的任务创建逻辑，改为节点执行时再创建
            # TODO: 在节点触发时动态创建任务实例
        
        logger.trace(f"✅ [数据层] 创建完成: 实例={instance_id}, 节点={len(node_instances)}, 任务={created_tasks_count}")
        
        return {
            'workflow_instance_id': instance_id,
            'workflow_id': workflow_id,
            'workflow_name': workflow.get('name', 'Unknown'),
            'workflow_instance_name': request.workflow_instance_name,
            'status': 'RUNNING',
            'executor_id': executor_id,
            'nodes_count': len(nodes),
            'tasks_count': created_tasks_count,
            'start_nodes_count': start_nodes_count,
            'created_at': now_utc().isoformat(),
            'node_instances': node_instances,
            'message': f'工作流实例 "{request.workflow_instance_name}" 创建成功，包含 {len(nodes)} 个节点，{created_tasks_count} 个任务'
        }
    
    async def _register_execution_context(self, workflow_data: Dict[str, Any]):
        """上下文层：纯执行逻辑注册"""
        instance_id = workflow_data['workflow_instance_id']
        
        try:
            logger.trace(f"🔗 [上下文层] 开始注册执行上下文: {instance_id}")
            
            # 1. 初始化上下文管理器
            await self.context_manager.initialize_workflow_context(instance_id)
            
            # 2. 获取上下文实例
            from ..services.workflow_execution_context import get_context_manager
            context_manager = get_context_manager()
            workflow_context = await context_manager.get_or_create_context(instance_id)
            
            # 3. 使用已有数据注册节点依赖（无需查询数据库）
            registered_count = 0
            start_nodes_triggered = 0
            
            for node_instance in workflow_data['node_instances']:
                node_instance_id = node_instance['node_instance_id']
                node_id = node_instance['node_id']
                node_type = node_instance['node_type']
                
                # 获取上游节点（基于node_id查询） - 🔧 修复参数顺序
                upstream_node_instances = await self._get_upstream_node_instances(
                    node_id, instance_id
                )
                
                # 注册到上下文
                await workflow_context.register_node_dependencies(
                    node_instance_id=node_instance_id,
                    node_id=node_id,
                    upstream_nodes=upstream_node_instances
                )
                
                registered_count += 1
                if node_type == 'START':
                    start_nodes_triggered += 1
                
                logger.trace(f"✅ [上下文层] 注册节点: {node_instance['node_name']}")
            
            logger.trace(f"📊 [上下文层] 注册完成: {registered_count} 个节点")
            
            # 4. 触发准备好的节点
            triggered_nodes = await workflow_context.scan_and_trigger_ready_nodes()
            
            expected_start_nodes = workflow_data['start_nodes_count']
            if triggered_nodes:
                logger.trace(f"🚀 [上下文层] 成功触发 {len(triggered_nodes)} 个节点")
                logger.trace(f"   - 预期START节点: {expected_start_nodes}")
                logger.trace(f"   - 触发的节点: {triggered_nodes}")
                
                # 🔧 修复Critical Bug: 将触发的节点实际提交执行
                for node_instance_id in triggered_nodes:
                    try:
                        await self._execute_node_with_new_context(workflow_context, node_instance_id)
                        logger.trace(f"✅ [执行提交] 启动节点执行: {node_instance_id}")
                    except Exception as e:
                        logger.error(f"❌ [执行提交] 启动节点执行失败 {node_instance_id}: {e}")
                        
            else:
                logger.warning(f"⚠️ [上下文层] 未触发任何节点")
                logger.warning(f"   - 预期START节点: {expected_start_nodes}")  
                logger.warning(f"   - 注册的节点: {registered_count}")
                
                # 调试信息
                logger.trace(f"🔍 [调试] 上下文状态:")
                logger.trace(f"   - 节点依赖数量: {len(workflow_context.node_dependencies)}")
                for node_id, deps in workflow_context.node_dependencies.items():
                    ready = deps.get('ready_to_execute', False)
                    upstream = deps.get('upstream_nodes', [])
                    logger.trace(f"   - 节点 {node_id}: ready={ready}, upstream={len(upstream)}")
                
        except Exception as e:
            logger.error(f"❌ [上下文层] 注册失败: {e}")
            import traceback
            logger.error(f"   - 详细堆栈: {traceback.format_exc()}")
            # 不抛出异常，数据已创建成功
    
    async def _get_workflow_nodes_by_version_id(self, workflow_id: uuid.UUID) -> List[Dict[str, Any]]:
        """通过工作流版本ID获取所有节点（修复版本 - 使用当前版本逻辑）"""
        logger.debug(f"🔍 [节点查询] 正在查询工作流版本 {workflow_id} 的节点...")
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
            
            # 查询当前版本的所有节点（避免笛卡尔积问题）
            query = """
                SELECT n.*
                FROM "node" n
                WHERE n.workflow_base_id = $1
                AND n.is_current_version = TRUE
                AND n.is_deleted = FALSE
                ORDER BY n.created_at ASC
            """
            results = await self.node_repo.db.fetch_all(query, workflow_base_id)
            logger.trace(f"✅ 通过base_id {workflow_base_id} 获取当前版本节点 {len(results)} 个")

            # 为每个节点单独查询处理器信息（避免重复节点记录）
            nodes_with_processors = []
            for node_result in results:
                node_dict = dict(node_result)

                # 查询该节点的处理器
                processor_query = """
                    SELECT processor_id FROM node_processor
                    WHERE node_id = $1 AND is_deleted = FALSE
                """
                processors = await self.node_repo.db.fetch_all(processor_query, node_dict['node_id'])

                # 如果有处理器，取第一个（保持兼容性）
                if processors:
                    node_dict['processor_id'] = processors[0]['processor_id']
                else:
                    node_dict['processor_id'] = None

                nodes_with_processors.append(node_dict)

            results = nodes_with_processors
            
            # 如果没有找到当前版本节点，尝试直接用workflow_id查询
            if not results:
                logger.warning(f"通过base_id未找到节点，尝试直接查询workflow_id: {workflow_id}")
                fallback_query = """
                    SELECT n.*
                    FROM "node" n
                    WHERE n.workflow_id = $1
                    AND n.is_deleted = FALSE
                    ORDER BY n.created_at ASC
                """
                fallback_results = await self.node_repo.db.fetch_all(fallback_query, workflow_id)
                logger.trace(f"✅ 通过workflow_id {workflow_id} fallback查询获取到 {len(fallback_results)} 个节点")

                # 为fallback结果也单独查询处理器信息
                nodes_with_processors = []
                for node_result in fallback_results:
                    node_dict = dict(node_result)

                    # 查询该节点的处理器
                    processor_query = """
                        SELECT processor_id FROM node_processor
                        WHERE node_id = $1 AND is_deleted = FALSE
                    """
                    processors = await self.node_repo.db.fetch_all(processor_query, node_dict['node_id'])

                    # 如果有处理器，取第一个（保持兼容性）
                    if processors:
                        node_dict['processor_id'] = processors[0]['processor_id']
                    else:
                        node_dict['processor_id'] = None

                    nodes_with_processors.append(node_dict)

                results = nodes_with_processors
            
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
    async def _get_node_processors(self, node_id: uuid.UUID):
        """获取节点的处理器列表（修复版本：使用具体node_id）"""
        try:
            logger.debug(f"🔍 [处理器查询] 正在查询节点 {node_id} 的处理器绑定...")
            
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
            
            logger.debug(f"🔍 [处理器查询] 节点 {node_id} 查询结果:")
            logger.debug(f"   - 找到处理器数量: {len(results)}")
            
            if not results:
                # 进一步诊断：检查node_processor表中是否有该节点的记录
                diagnostic_query = "SELECT COUNT(*) as count FROM node_processor WHERE node_id = $1"
                diagnostic_result = await self.processor_repo.db.fetch_one(diagnostic_query, node_id)
                total_records = diagnostic_result['count'] if diagnostic_result else 0
                
                logger.warning(f"🚨 [处理器查询] 节点 {node_id} 未找到处理器:")
                logger.warning(f"   - node_processor表中该节点记录数: {total_records}")
                logger.warning(f"   - 可能原因: 1)节点未绑定处理器 2)node_id不匹配 3)处理器被删除")
                
                # 检查节点是否存在
                node_check_query = "SELECT node_id, name, node_base_id FROM node WHERE node_id = $1"
                node_check = await self.processor_repo.db.fetch_one(node_check_query, node_id)
                if node_check:
                    logger.warning(f"   - 节点存在: {node_check['name']} (base_id: {node_check['node_base_id']})")
                else:
                    logger.warning(f"   - 节点不存在于node表中!")
            else:
                for i, result in enumerate(results):
                    logger.debug(f"   - 处理器{i+1}: {result.get('processor_name')} (类型: {result.get('processor_type')})")
            
            return results
        except Exception as e:
            logger.error(f"获取节点处理器列表失败: {e}")
            return []
    
    async def _get_next_nodes(self, node_id: uuid.UUID):
        """获取节点的下游节点（支持条件边）"""
        try:
            # 修改查询以获取连接信息，包括条件配置
            query = """
                SELECT
                    nc.to_node_id,
                    nc.connection_type,
                    nc.condition_config,
                    tn.node_base_id as to_node_base_id,
                    tn.name as to_node_name,
                    tn.type as to_node_type
                FROM node_connection nc
                JOIN node tn ON tn.node_id = nc.to_node_id
                WHERE nc.from_node_id = $1
                  AND tn.is_deleted = FALSE
                ORDER BY nc.created_at ASC
            """
            results = await self.node_repo.db.fetch_all(query, node_id)

            connections = []
            for result in results:
                connection = {
                    'to_node_id': result['to_node_id'],
                    'to_node_base_id': result['to_node_base_id'],
                    'to_node_name': result['to_node_name'],
                    'to_node_type': result['to_node_type'],
                    'connection_type': result['connection_type'] or 'normal',
                    'condition_config': {}
                }

                # 解析条件配置
                if result['condition_config']:
                    try:
                        if isinstance(result['condition_config'], str):
                            import json
                            connection['condition_config'] = json.loads(result['condition_config'])
                        else:
                            connection['condition_config'] = result['condition_config']
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"解析条件配置失败: {e}")
                        connection['condition_config'] = {}

                connections.append(connection)

            logger.debug(f"获取节点 {node_id} 的下游连接: {len(connections)} 个")
            return connections

        except Exception as e:
            logger.error(f"获取节点下游连接失败: {e}")
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
                            
                await asyncio.sleep(15)  # 每15秒检查一次 - 优化为更频繁
                
            except Exception as e:
                logger.error(f"监控运行实例失败: {e}")
                await asyncio.sleep(10)

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
    
    async def _create_tasks_for_nodes(self, created_nodes: List[Dict], workflow_instance_id: uuid.UUID):
        """为节点创建任务实例 - 统一使用新架构"""
        logger.info(f"🔧 [统一架构] 开始为 {len(created_nodes)} 个节点创建任务实例")
        
        task_creation_count = 0
        for i, created_node in enumerate(created_nodes, 1):
            logger.info(f"📋 [统一架构] 处理节点 {i}/{len(created_nodes)}: {created_node.get('node_data', {}).get('name', '未知节点')}")
            logger.info(f"   节点类型: {created_node['node_type']}")
            logger.info(f"   节点实例ID: {created_node['node_instance_id']}")
            
            if created_node['node_type'] == NodeType.PROCESSOR.value:
                node_data = created_node['node_data']
                
                # 直接调用新架构的任务创建方法
                node_data_for_creation = {
                    'node_id': node_data['node_id'],
                    'name': node_data['name'],
                    'task_description': node_data.get('task_description') or node_data.get('description'),
                    'type': created_node['node_type'],
                    'input_data': node_data.get('input_data', {})
                }
                
                try:
                    await self._create_tasks_for_node_new_context(
                        node_data_for_creation,
                        created_node['node_instance_id'],
                        workflow_instance_id
                    )
                    
                    task_creation_count += 1
                    logger.info(f"✅ [统一架构] 节点任务创建完成!")
                    
                except Exception as e:
                    logger.error(f"❌ [统一架构] 任务实例创建异常: {e}")
                    import traceback
                    logger.error(f"异常堆栈: {traceback.format_exc()}")
                    # 继续处理其他节点
            else:
                logger.info(f"ℹ️ [统一架构] 跳过非PROCESSOR节点: {created_node['node_type']}")
                
        logger.info(f"🎉 [统一架构] 所有节点任务创建完成，共创建 {task_creation_count} 个任务")
    
    
    
    async def _resume_workflow_execution(self, workflow_instance_id: uuid.UUID):
        """恢复工作流执行，检查并触发准备好的节点"""
        try:
            logger.trace(f"🔄 开始恢复工作流执行: {workflow_instance_id}")
            
            # 🔒 首先检查工作流状态，避免处理已取消/失败的工作流
            workflow_status_query = """
            SELECT status FROM workflow_instance 
            WHERE workflow_instance_id = $1 AND is_deleted = FALSE
            """
            workflow_status_result = await self.workflow_instance_repo.db.fetch_one(
                workflow_status_query, workflow_instance_id
            )
            
            if not workflow_status_result:
                logger.warning(f"⚠️ [恢复执行] 工作流 {workflow_instance_id} 不存在，停止恢复")
                return
                
            workflow_status = workflow_status_result['status']
            if workflow_status.lower() in ['cancelled', 'failed', 'completed']:
                logger.trace(f"🚫 [恢复执行] 工作流 {workflow_instance_id} 状态为 {workflow_status}，跳过恢复")
                return
            
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
                triggered_count = await self._check_and_trigger_ready_nodes(workflow_instance_id, pending_nodes)
                logger.trace(f"触发了 {triggered_count} 个准备就绪的节点")
            else:
                logger.trace(f"没有找到pending状态的节点，工作流可能已完成或出现异常")
                
        except Exception as e:
            logger.error(f"恢复工作流执行失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
    
    
    async def _check_and_trigger_ready_nodes(self, workflow_instance_id: uuid.UUID, pending_nodes: List[Dict]) -> int:
        """检查并触发准备好的节点，返回触发的节点数量"""
        triggered_count = 0
        try:
            logger.trace(f"检查 {len(pending_nodes)} 个pending节点的依赖关系")
            
            for node in pending_nodes:
                node_instance_id = node['node_instance_id']
                node_name = node.get('node_name', '未知')
                
                # 检查节点依赖是否满足
                if await self._check_node_dependencies_satisfied(workflow_instance_id, node_instance_id):
                    logger.trace(f"✅ 节点 {node_name} 的依赖已满足，触发执行")
                    # 获取工作流上下文并执行节点
                    from .workflow_execution_context import get_context_manager
                    context_manager = get_context_manager()
                    workflow_context = await context_manager.get_context(workflow_instance_id)
                    if workflow_context:
                        await self._execute_node_with_unified_context(workflow_context, workflow_instance_id, node_instance_id)
                    triggered_count += 1
                else:
                    logger.trace(f"⏳ 节点 {node_name} 的依赖尚未满足，等待中")
            
            return triggered_count
                    
        except Exception as e:
            logger.error(f"检查和触发准备好的节点失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            return triggered_count
    
    # _collect_task_context_data 方法已被 WorkflowContextManager.get_task_context_data 替换

    async def _check_node_dependencies_satisfied(self, workflow_instance_id: uuid.UUID, node_instance_id: uuid.UUID) -> bool:
        """检查节点的依赖是否已满足（增强版：支持自动恢复）"""
        try:
            # 🔍 使用新的 get_context 方法，自动支持恢复
            context = await self.context_manager.get_context(workflow_instance_id)
            if not context:
                logger.warning(f"⚠️ [依赖检查] 无法获取或恢复工作流上下文: {workflow_instance_id}")
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
                if node_instance_id in context.execution_context.get('completed_nodes', set()):
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
                if node_instance_id in context.execution_context.get('completed_nodes', set()):
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
            
            upstream_node_instance_ids = []
            for upstream in upstream_connections:
                upstream_node_id = upstream['upstream_node_id']
                
                # 查找对应的node_instance_id
                instance_query = """
                SELECT node_instance_id 
                FROM node_instance 
                WHERE node_id = $1 AND workflow_instance_id = $2 AND is_deleted = FALSE
                """
                upstream_instance_result = await node_repo.db.fetch_one(
                    instance_query, upstream_node_id, workflow_instance_id
                )
                
                if upstream_instance_result:
                    upstream_node_instance_id = upstream_instance_result['node_instance_id']
                    upstream_node_instance_ids.append(upstream_node_instance_id)
                    logger.debug(f"    上游节点: {upstream.get('upstream_node_name', 'Unknown')} (node_id: {upstream_node_id} -> instance_id: {upstream_node_instance_id})")
                else:
                    logger.warning(f"    ⚠️ 未找到上游节点 {upstream_node_id} 对应的实例")
            
            # 重新注册依赖关系
            await self.context_manager.register_node_dependencies(
                workflow_instance_id,
                node_instance_id,
                node_id,
                upstream_node_instance_ids
            )
            
            logger.debug(f"✅ [依赖重建] 成功重建节点 {node_instance_id} 的依赖信息: {len(upstream_node_instance_ids)} 个上游节点实例")
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
                upstream_node_ids = [result['from_node_id'] for result in upstream_results]
                
                # 转换为node_instance_id
                upstream_node_instance_ids = []
                for upstream_node_id in upstream_node_ids:
                    instance_query = """
                    SELECT node_instance_id 
                    FROM node_instance 
                    WHERE node_id = $1 AND workflow_instance_id = $2 AND is_deleted = FALSE
                    """
                    upstream_instance_result = await node_repo.db.fetch_one(
                        instance_query, upstream_node_id, workflow_instance_id
                    )
                    
                    if upstream_instance_result:
                        upstream_node_instance_ids.append(upstream_instance_result['node_instance_id'])
                    else:
                        logger.warning(f"    ⚠️ 未找到上游节点 {upstream_node_id} 对应的实例")
                
                # 重新注册依赖 - 修复参数顺序
                await self.context_manager.register_node_dependencies(
                    workflow_instance_id, node_instance_id, node_id, upstream_node_instance_ids
                )
                
                logger.trace(f"🔧 [依赖重建] 节点 {node_instance_id} 依赖已重建: {len(upstream_node_instance_ids)} 个上游节点实例")
            
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
            
            # 获取下游节点并启动执行（WorkflowExecutionContext已经处理了下游触发，避免重复触发）
            logger.trace(f"  步骤4: 跳过额外的下游节点触发（WorkflowExecutionContext已自动处理）")
            # await self._trigger_downstream_nodes(workflow_instance_id, start_node)  # 注释掉避免重复触发
            logger.trace(f"  ✅ 依赖WorkflowExecutionContext自动触发机制")
            
            
            logger.trace(f"  ✅ START节点执行完成: {node_name} (ID: {node_instance_id})")
            
        except Exception as e:
            node_name = start_node.get('node_name', '未知')
            logger.error(f"❌ 执行START节点失败 {node_name}: {e}")
            import traceback
            logger.error(f"异常堆栈详情: {traceback.format_exc()}")
            raise
    
            # 移除废弃的_trigger_downstream_nodes方法 - 功能已由工作流上下文管理器替代
    
    # 旧架构方法已移除：_execute_node_when_ready
    
    
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
            task_title = task.get('task_title', 'unknown')
            task_type = task.get('task_type', 'unknown')
            current_status = task.get('status', 'unknown')
            assigned_agent_id = task.get('assigned_agent_id', 'none')
            processor_id = task.get('processor_id', 'none')
            node_instance_id = task.get('node_instance_id', 'none')
            workflow_instance_id = task.get('workflow_instance_id', 'none')
            
            logger.info(f"🚀 [EXECUTION-ENGINE] === 开始执行Agent任务 ===")
            logger.info(f"   📋 任务ID: {task_id}")
            logger.info(f"   🏷️  任务标题: {task_title}")
            logger.info(f"   📝 任务类型: {task_type}")
            logger.info(f"   📊 当前状态: {current_status}")
            logger.info(f"   🤖 分配Agent: {assigned_agent_id}")
            logger.info(f"   ⚙️  处理器ID: {processor_id}")
            logger.info(f"   🔗 节点实例ID: {node_instance_id}")
            logger.info(f"   🌊 工作流实例ID: {workflow_instance_id}")
            
            # 检查任务是否真的需要执行
            if current_status in ['completed', 'failed', 'cancelled']:
                logger.warning(f"⚠️ [EXECUTION-ENGINE] 任务 {task_id} 状态为 {current_status}，跳过执行")
                return
            
            # 记录执行前的时间戳
            start_time = datetime.now()
            logger.info(f"⏰ [EXECUTION-ENGINE] 任务开始执行时间: {start_time.isoformat()}")
            
            # 检查Agent服务是否正在运行
            logger.info(f"🔍 [EXECUTION-ENGINE] 检查Agent服务状态...")
            logger.info(f"   - Agent服务运行状态: {agent_task_service.is_running}")
            logger.info(f"   - Agent服务处理队列大小: {agent_task_service.processing_queue.qsize()}")
            logger.info(f"   - Agent服务回调数量: {len(agent_task_service.completion_callbacks)}")
            
            # 调用AgentTaskService处理任务
            logger.info(f"🔄 [EXECUTION-ENGINE] 调用AgentTaskService.process_agent_task()")
            logger.info(f"   - 传递任务ID: {task_id}")
            logger.info(f"   - 预期流程: assigned → in_progress → completed")
            
            try:
                # 在调用前再次检查任务状态
                current_task = await self.task_instance_repo.get_task_by_id(task_id)
                if current_task:
                    logger.info(f"📊 [EXECUTION-ENGINE] 调用前任务状态验证:")
                    logger.info(f"   - 数据库中状态: {current_task.get('status', 'unknown')}")
                    logger.info(f"   - 是否已分配Agent: {'是' if current_task.get('assigned_agent_id') else '否'}")
                    logger.info(f"   - Agent ID匹配: {'是' if str(current_task.get('assigned_agent_id', '')) == str(assigned_agent_id) else '否'}")
                
                # 实际调用Agent处理
                result = await agent_task_service.process_agent_task(task_id)
                
                # 记录执行后的时间和结果
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                logger.info(f"✅ [EXECUTION-ENGINE] AgentTaskService调用完成!")
                logger.info(f"   ⏱️  执行耗时: {duration:.2f}秒")
                logger.info(f"   🎯 返回结果类型: {type(result)}")
                
                if isinstance(result, dict):
                    result_status = result.get('status', 'unknown')
                    result_message = result.get('message', 'no message')
                    logger.info(f"   📊 结果状态: {result_status}")
                    logger.info(f"   💬 结果消息: {result_message}")
                    
                    # 如果有具体的结果内容，也记录下来
                    if 'result' in result:
                        result_content = str(result['result'])
                        content_preview = result_content[:200] + '...' if len(result_content) > 200 else result_content
                        logger.info(f"   📄 结果内容预览: {content_preview}")
                else:
                    logger.info(f"   📄 结果内容: {result}")
                
                # 验证任务是否真的完成了
                updated_task = await self.task_instance_repo.get_task_by_id(task_id)
                if updated_task:
                    final_status = updated_task.get('status', 'unknown')
                    has_output = bool(updated_task.get('output_data', '').strip())
                    
                    logger.info(f"🔍 [EXECUTION-ENGINE] 执行后任务状态验证:")
                    logger.info(f"   - 最终状态: {final_status}")
                    logger.info(f"   - 有输出数据: {'是' if has_output else '否'}")
                    logger.info(f"   - 完成时间: {updated_task.get('completed_at', '未设置')}")
                    logger.info(f"   - 实际执行时长: {updated_task.get('actual_duration', '未设置')}分钟")
                    
                    if final_status == 'completed':
                        logger.info(f"🎉 [EXECUTION-ENGINE] Agent任务真实执行成功!")
                        if has_output:
                            output_preview = str(updated_task.get('output_data', ''))[:150]
                            logger.info(f"   📋 输出数据: {output_preview}...")
                    else:
                        logger.warning(f"⚠️ [EXECUTION-ENGINE] Agent任务状态异常: {final_status}")
                        if updated_task.get('error_message'):
                            logger.warning(f"   ❌ 错误信息: {updated_task['error_message']}")
                else:
                    logger.error(f"❌ [EXECUTION-ENGINE] 无法验证任务执行结果，任务可能已被删除")
                
            except Exception as process_error:
                logger.error(f"❌ [EXECUTION-ENGINE] AgentTaskService处理失败!")
                logger.error(f"   🚫 错误类型: {type(process_error).__name__}")
                logger.error(f"   💬 错误消息: {str(process_error)}")
                import traceback
                logger.error(f"   📚 完整堆栈:")
                for line in traceback.format_exc().split('\n'):
                    if line.strip():
                        logger.error(f"      {line}")
                raise
            
            logger.info(f"✅ [EXECUTION-ENGINE] === Agent任务执行流程完成 ===")
            logger.info(f"   🏁 任务ID: {task_id}")
            logger.info(f"   ⏱️  总耗时: {(datetime.now() - start_time).total_seconds():.2f}秒")
            
        except Exception as e:
            logger.error(f"❌ [EXECUTION-ENGINE] === Agent任务执行失败 ===")
            logger.error(f"   🚫 任务ID: {task.get('task_instance_id', 'unknown')}")
            logger.error(f"   📝 任务标题: {task.get('task_title', 'unknown')}")
            logger.error(f"   💥 失败原因: {str(e)}")
            logger.error(f"   📊 原始任务数据: {task}")
            import traceback
            logger.error(f"   📚 完整错误堆栈:")
            for line in traceback.format_exc().split('\n'):
                if line.strip():
                    logger.error(f"      {line}")
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
        """上下文管理器回调：有节点准备执行（新架构版本）"""
        try:
            logger.info(f"🔔 [统一架构-回调] 工作流 {workflow_instance_id} 中有 {len(ready_node_instance_ids)} 个节点准备执行")
            
            # 获取工作流上下文
            from .workflow_execution_context import get_context_manager
            context_manager = get_context_manager()
            workflow_context = await context_manager.get_context(workflow_instance_id)
            
            if not workflow_context:
                logger.error(f"❌ [统一架构-回调] 未找到工作流上下文: {workflow_instance_id}")
                return
            
            # 使用新架构执行准备好的节点
            for node_instance_id in ready_node_instance_ids:
                try:
                    logger.info(f"⚡ [统一架构-回调] 开始执行节点: {node_instance_id}")
                    await self._execute_node_with_unified_context(workflow_context, workflow_instance_id, node_instance_id)
                except Exception as e:
                    logger.error(f"❌ [统一架构-回调] 执行节点 {node_instance_id} 失败: {e}")
                    import traceback
                    logger.error(f"错误堆栈: {traceback.format_exc()}")
                
        except Exception as e:
            logger.error(f"❌ [统一架构-回调] 执行准备好的节点失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    async def _execute_node_with_unified_context(self, workflow_context, workflow_instance_id: uuid.UUID, node_instance_id: uuid.UUID):
        """使用统一上下文执行节点"""
        try:
            # 获取节点信息
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            from ..repositories.node.node_repository import NodeRepository
            
            node_instance_repo = NodeInstanceRepository()
            node_repo = NodeRepository()
            
            node_instance_info = await node_instance_repo.get_instance_by_id(node_instance_id)
            if not node_instance_info:
                logger.error(f"❌ [统一架构-执行] 无法获取节点实例信息: {node_instance_id}")
                return
                
            node_info = await node_repo.get_node_by_id(node_instance_info['node_id'])
            if not node_info:
                logger.error(f"❌ [统一架构-执行] 无法获取节点信息: {node_instance_info['node_id']}")
                return
            
            logger.info(f"📋 [统一架构-执行] 执行节点: {node_info.get('name')} (类型: {node_info.get('type')})")
            
            # 根据节点类型处理
            if node_info.get('type') == NodeType.PROCESSOR.value:
                # PROCESSOR节点：创建任务并执行
                logger.info(f"🔨 [统一架构-执行] PROCESSOR节点 {node_info.get('name')} - 创建并分配任务")
                
                # 检查是否已有任务实例
                from ..repositories.instance.task_instance_repository import TaskInstanceRepository
                task_repo = TaskInstanceRepository()
                existing_tasks = await task_repo.get_tasks_by_node_instance(node_instance_id)
                
                if not existing_tasks:
                    # 创建任务实例
                    await self._create_tasks_for_node_new_context(node_info, node_instance_id, workflow_instance_id)
                    logger.info(f"✅ [统一架构-执行] PROCESSOR节点 {node_info.get('name')} 任务创建完成")
                    
                    # 重新获取刚创建的任务
                    existing_tasks = await task_repo.get_tasks_by_node_instance(node_instance_id)
                else:
                    logger.info(f"ℹ️ [统一架构-执行] PROCESSOR节点 {node_info.get('name')} 已有 {len(existing_tasks)} 个任务实例")
                
                # ✨ 关键修复：执行任务！
                logger.info(f"🚀 [统一架构-执行] 开始执行PROCESSOR节点 {node_info.get('name')} 的任务")
                logger.info(f"   - 待执行任务数量: {len(existing_tasks)}")
                
                for i, task in enumerate(existing_tasks, 1):
                    task_title = task.get('task_title', 'unknown')
                    task_type = task.get('task_type', 'unknown') 
                    task_status = task.get('status', 'unknown')
                    logger.info(f"   - 任务{i}: {task_title} (类型: {task_type}, 状态: {task_status})")
                
                # 调用任务执行方法
                await self._execute_node_tasks(workflow_instance_id, node_instance_id)
                logger.info(f"✅ [统一架构-执行] PROCESSOR节点 {node_info.get('name')} 任务执行调用完成")
            
            elif node_info.get('type') == NodeType.END.value:
                # 🔧 修复：END节点应该收集所有上游节点的输出结果
                logger.info(f"🏁 [统一架构-执行] END节点 {node_info.get('name')} - 收集上游结果")
                
                # 收集上游节点的输出数据
                upstream_outputs = {}
                try:
                    # 获取完整的工作流上下文数据
                    context_data = await self.context_manager.get_task_context_data(workflow_instance_id, node_instance_id)
                    # 🔧 修复：使用正确的键名 'immediate_upstream_results' 而不是 'upstream_outputs'
                    upstream_outputs = context_data.get('immediate_upstream_results', {})
                    logger.info(f"   📊 收集到 {len(upstream_outputs)} 个上游节点的输出")
                    
                    # 调试输出
                    logger.info(f"   🔍 上游输出详情: {list(upstream_outputs.keys())}")
                    for node_name, node_data in upstream_outputs.items():
                        output_preview = str(node_data.get('output_data', ''))[:100]
                        logger.info(f"     - {node_name}: {output_preview}...")
                        
                except Exception as e:
                    logger.warning(f"   ⚠️ 收集上游输出失败: {e}")
                    import traceback
                    logger.error(f"   详细错误: {traceback.format_exc()}")
                
                # 构建包含上游结果的完整输出
                end_output = {
                    'workflow_completed': True,
                    'completion_time': datetime.utcnow().isoformat(),
                    'end_node': node_info.get('name'),
                    'upstream_results': upstream_outputs,  # 🔧 关键修复：包含上游结果
                    'full_context': self._format_workflow_final_output(upstream_outputs)  # 🔧 格式化的完整结果
                }
                
                logger.info(f"   📋 最终输出包含完整上下文，长度: {len(str(end_output.get('full_context', '')))}")
                
                await workflow_context.mark_node_completed(
                    node_info.get('node_id'),
                    node_instance_id, 
                    end_output
                )
                
                logger.info(f"✅ [统一架构-执行] END节点 {node_info.get('name')} 已标记为完成（包含上游结果）")
            
            else:
                logger.warning(f"⚠️ [统一架构-执行] 未知节点类型: {node_info.get('type')}")
                
        except Exception as e:
            logger.error(f"❌ [统一架构-执行] 执行节点失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    def _format_workflow_final_output(self, upstream_outputs: Dict[str, Any]) -> str:
        """格式化工作流的最终输出为可读文本"""
        if not upstream_outputs:
            return "工作流执行完成，但未找到上游节点输出。"
        
        output_lines = ["=== 工作流执行结果汇总 ===\n"]
        
        for node_name, node_data in upstream_outputs.items():
            output_lines.append(f"【节点：{node_name}】")
            
            # 提取节点输出数据
            if isinstance(node_data, dict):
                # 处理结构化的输出数据
                if 'output_data' in node_data:
                    output_data = node_data['output_data']
                    if isinstance(output_data, str) and output_data.strip():
                        output_lines.append(f"输出结果：{output_data}")
                    elif isinstance(output_data, dict):
                        # 格式化字典输出
                        formatted_output = self._format_dict_as_text(output_data)
                        output_lines.append(f"输出结果：{formatted_output}")
                    else:
                        output_lines.append("输出结果：[无有效输出数据]")
                
                # 添加执行统计
                if 'status' in node_data:
                    output_lines.append(f"执行状态：{node_data['status']}")
                if 'completed_at' in node_data:
                    output_lines.append(f"完成时间：{node_data['completed_at']}")
            else:
                # 处理简单的输出数据
                output_lines.append(f"输出结果：{str(node_data)}")
            
            output_lines.append("")  # 空行分隔
        
        output_lines.append("✅ 工作流执行完成，所有节点处理结果已汇总。")
        
        return "\n".join(output_lines)
    
    def _format_dict_as_text(self, data: dict) -> str:
        """将字典数据格式化为可读文本"""
        if not data:
            return "[空数据]"
        
        lines = []
        for key, value in data.items():
            if isinstance(value, (str, int, float, bool)):
                lines.append(f"  • {key}: {value}")
            elif isinstance(value, dict):
                lines.append(f"  • {key}: {json.dumps(value, ensure_ascii=False, indent=2)}")
            elif isinstance(value, list):
                lines.append(f"  • {key}: [{len(value)}项]")
            else:
                lines.append(f"  • {key}: {str(value)}")
        
        return "\n".join(lines) if lines else "[无数据]"
    
    async def _log_task_assignment_event(self, task_id: uuid.UUID, assigned_user_id: Optional[uuid.UUID], task_title: str):
        """记录任务分配事件"""
        try:
            from datetime import datetime
            event_data = {
                'event_type': 'task_assigned',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'task_id': str(task_id),
                'assigned_user_id': str(assigned_user_id) if assigned_user_id else None
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
            
            
        except Exception as e:
            logger.error(f"记录任务分配事件失败: {e}")
    
    async def _log_workflow_execution_summary(self, workflow_instance_id: uuid.UUID):
        """记录工作流执行摘要"""
        try:
            logger.info(f"📊 [执行摘要] 开始生成工作流执行摘要: {workflow_instance_id}")
            
            # 获取工作流实例信息
            instance = await self.workflow_instance_repo.get_instance_by_id(workflow_instance_id)
            if not instance:
                logger.warning(f"   [执行摘要] 工作流实例不存在: {workflow_instance_id}")
                return
            
            # 获取所有任务
            tasks = await self.task_instance_repo.get_tasks_by_workflow_instance(workflow_instance_id)
            logger.info(f"📋 [执行摘要] 查询到总任务数: {len(tasks) if tasks else 0}")
            
            if tasks:
                logger.info(f"📋 [执行摘要] 任务详细信息:")
                for i, task in enumerate(tasks, 1):
                    logger.info(f"   任务{i}: {task.get('task_title')} (状态: {task.get('status')}, 类型: {task.get('task_type')}, 分配用户: {task.get('assigned_user_id')})")
            else:
                logger.warning(f"⚠️ [执行摘要] 未找到任何任务实例")
            
            # 统计信息
            total_tasks = len(tasks) if tasks else 0
            human_tasks = len([t for t in tasks if t['task_type'] == TaskInstanceType.HUMAN.value]) if tasks else 0
            agent_tasks = len([t for t in tasks if t['task_type'] == TaskInstanceType.AGENT.value]) if tasks else 0
            assigned_tasks = len([t for t in tasks if t['status'] in ['ASSIGNED', 'IN_PROGRESS', 'COMPLETED']]) if tasks else 0
            pending_tasks = len([t for t in tasks if t['status'] == 'PENDING']) if tasks else 0
            
            logger.info(f"📊 [执行摘要] 任务统计:")
            logger.info(f"   - 总任务数: {total_tasks}")
            logger.info(f"   - 人工任务: {human_tasks}")
            logger.info(f"   - Agent任务: {agent_tasks}")
            logger.info(f"   - 已分配: {assigned_tasks} (状态为 ASSIGNED/IN_PROGRESS/COMPLETED)")
            logger.info(f"   - 等待中: {pending_tasks} (状态为 PENDING)")
            
            # 详细分析状态分布
            if tasks:
                status_distribution = {}
                for task in tasks:
                    status = task.get('status')
                    status_distribution[status] = status_distribution.get(status, 0) + 1
                logger.info(f"📊 [执行摘要] 状态分布: {status_distribution}")
            
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
            else:
                print(f"📋 暂无已分配的人工任务")
                if tasks:
                    print(f"📋 所有任务详情:")
                    for i, task in enumerate(tasks, 1):
                        print(f"  {i}. 标题: {task['task_title']}")
                        print(f"     状态: {task['status']}")
                        print(f"     类型: {task['task_type']}")
                        print(f"     分配用户: {task.get('assigned_user_id', 'None')}")
                        print(f"     任务ID: {task.get('task_instance_id')}")
                        print("     ---")
                else:
                    print(f"📋 ⚠️ 工作流中没有找到任何任务实例！")
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
            
            # 🔧 修复：检查并恢复上下文管理器状态
            if workflow_instance_id not in self.context_manager.contexts:
                logger.warning(f"⚠️ [上下文恢复] 工作流实例 {workflow_instance_id} 不在上下文管理器中，尝试恢复...")
                
                # 重新创建上下文
                context = await self.context_manager.get_or_create_context(workflow_instance_id)
                
                # 从数据库恢复已完成节点状态
                await self._recover_context_state_from_database(workflow_instance_id, context)
                
                logger.info(f"✅ [上下文恢复] 工作流实例 {workflow_instance_id} 上下文恢复成功")
            
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
                if node_instance_id in context.execution_context.get('completed_nodes', set()):
                    logger.trace(f"  🚫 节点在上下文中已完成，跳过检查")
                    return False
                if node_instance_id in context.execution_context.get('current_executing_nodes', set()):
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
    
    async def _recover_context_state_from_database(self, workflow_instance_id: uuid.UUID, context):
        """从数据库恢复上下文状态（修复丢失的上下文管理器状态）"""
        try:
            logger.debug(f"🔄 [上下文恢复] 开始从数据库恢复工作流 {workflow_instance_id} 的状态...")
            
            # 查询所有已完成的节点
            completed_nodes_query = '''
            SELECT ni.node_id, ni.node_instance_id, ni.output_data, n.name
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id  
            WHERE ni.workflow_instance_id = $1 
              AND ni.status = 'completed'
              AND ni.is_deleted = FALSE
            '''
            
            completed_nodes = await self.workflow_instance_repo.db.fetch_all(
                completed_nodes_query, workflow_instance_id
            )
            
            logger.debug(f"  🔍 发现 {len(completed_nodes)} 个已完成的节点")
            
            # 恢复已完成节点状态到上下文
            for node in completed_nodes:
                node_id = node['node_id']
                node_instance_id = node['node_instance_id']
                output_data = node['output_data'] or {}
                node_name = node['name']
                
                # 添加到已完成节点集合 - 修复：使用node_instance_id
                context.execution_context['completed_nodes'].add(node_instance_id)
                
                # 恢复节点输出数据 - 修复：使用node_instance_id作为key
                context.execution_context['node_outputs'][node_instance_id] = output_data
                
                logger.debug(f"    ✅ 恢复节点 {node_name} ({node_instance_id}) 的完成状态")
            
            # 查询正在执行的节点
            executing_nodes_query = '''
            SELECT ni.node_id, ni.node_instance_id, n.name
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.workflow_instance_id = $1 
              AND ni.status = 'running'
              AND ni.is_deleted = FALSE
            '''
            
            executing_nodes = await self.workflow_instance_repo.db.fetch_all(
                executing_nodes_query, workflow_instance_id
            )
            
            logger.debug(f"  🔍 发现 {len(executing_nodes)} 个执行中的节点")
            
            # 恢复执行中节点状态
            for node in executing_nodes:
                node_id = node['node_id']
                node_instance_id = node['node_instance_id']
                node_name = node['name']
                
                # 修复：使用node_instance_id
                context.execution_context['current_executing_nodes'].add(node_instance_id)
                logger.debug(f"    🏃 恢复节点 {node_name} ({node_instance_id}) 的执行状态")
            
            # 重新构建节点依赖信息
            await self._rebuild_all_node_dependencies(workflow_instance_id)
            
            logger.info(f"✅ [上下文恢复] 工作流 {workflow_instance_id} 状态恢复完成")
            logger.info(f"    - 已完成节点: {len(completed_nodes)} 个")
            logger.info(f"    - 执行中节点: {len(executing_nodes)} 个")
            
        except Exception as e:
            logger.error(f"❌ [上下文恢复] 恢复工作流状态失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    async def _rebuild_all_node_dependencies(self, workflow_instance_id: uuid.UUID):
        """重建所有节点的依赖关系"""
        try:
            logger.debug(f"🔄 重建工作流 {workflow_instance_id} 的所有节点依赖关系...")
            
            # 查询所有节点实例
            nodes_query = '''
            SELECT ni.node_instance_id, ni.node_id, n.name
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.workflow_instance_id = $1 AND ni.is_deleted = FALSE
            '''
            
            nodes = await self.workflow_instance_repo.db.fetch_all(nodes_query, workflow_instance_id)
            
            for node in nodes:
                node_instance_id = node['node_instance_id']
                node_id = node['node_id']
                
                # 查询该节点的上游依赖
                upstream_query = '''
                SELECT DISTINCT nc.from_node_id
                FROM node_connection nc
                WHERE nc.to_node_id = $1
                '''
                
                upstream_results = await self.workflow_instance_repo.db.fetch_all(upstream_query, node_id)
                upstream_node_ids = [result['from_node_id'] for result in upstream_results]
                
                # 转换为node_instance_id
                upstream_node_instance_ids = []
                for upstream_node_id in upstream_node_ids:
                    instance_query = """
                    SELECT node_instance_id 
                    FROM node_instance 
                    WHERE node_id = $1 AND workflow_instance_id = $2 AND is_deleted = FALSE
                    """
                    upstream_instance_result = await self.workflow_instance_repo.db.fetch_one(
                        instance_query, upstream_node_id, workflow_instance_id
                    )
                    
                    if upstream_instance_result:
                        upstream_node_instance_ids.append(upstream_instance_result['node_instance_id'])
                    else:
                        logger.warning(f"    ⚠️ 未找到上游节点 {upstream_node_id} 对应的实例")
                
                # 注册依赖关系到上下文管理器
                await self.context_manager.register_node_dependencies(
                    workflow_instance_id, node_instance_id, node_id, upstream_node_instance_ids
                )
                
                logger.debug(f"    ✅ 重建节点 {node['name']} 依赖: {len(upstream_node_instance_ids)} 个上游节点实例")
            
            logger.debug(f"✅ 所有节点依赖关系重建完成")
            
        except Exception as e:
            logger.error(f"❌ 重建节点依赖关系失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
    
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
                
                # 对于非PROCESSOR节点的处理策略
                if node['type'] == NodeType.END.value:
                    # 🔧 修复END节点过早执行问题：不在这里直接执行，让依赖驱动的触发机制处理
                    logger.trace(f"  🏁 END节点 {node_instance_id} 等待依赖驱动的触发机制处理")
                    return False  # 不创建任务，等待正确的触发时机
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

                # 🔧 修复：只有START节点才需要立即检查下游，END节点通过依赖机制触发
                if node['type'] == NodeType.START.value:
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
        """检查下游节点是否可以创建任务 - 增强并发处理版本"""
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                logger.trace(f"🔄 检查下游节点任务创建机会 (尝试 {attempt + 1}/{max_retries})")
                
                # 🔧 强制刷新工作流上下文状态（防止状态延迟）
                await self._refresh_workflow_context_state(workflow_instance_id)
                
                # 查询工作流中所有等待状态的节点
                waiting_nodes_query = '''
                SELECT ni.node_instance_id, ni.node_id, n.name, n.type
                FROM node_instance ni
                JOIN node n ON ni.node_id = n.node_id
                WHERE ni.workflow_instance_id = %s 
                  AND ni.status = 'pending'
                  AND ni.is_deleted = FALSE
                '''
                
                waiting_nodes = await self.workflow_instance_repo.db.fetch_all(
                    waiting_nodes_query, workflow_instance_id
                )
                
                logger.trace(f"  找到 {len(waiting_nodes)} 个等待中的节点")
                
                created_any_task = False
                
                # 为每个等待节点检查是否可以创建任务
                for node in waiting_nodes:
                    node_instance_id = node['node_instance_id']
                    node_name = node['name']
                    
                    logger.trace(f"  检查节点: {node_name} ({node_instance_id})")
                    
                    # 🔧 检查节点是否已经有任务（防止重复创建）
                    existing_tasks = await self.task_instance_repo.db.fetch_all(
                        "SELECT task_instance_id FROM task_instance WHERE node_instance_id = %s AND is_deleted = FALSE",
                        node_instance_id
                    )
                    
                    if existing_tasks:
                        logger.trace(f"    节点 {node_name} 已有 {len(existing_tasks)} 个任务，跳过")
                        continue
                    
                    # 尝试创建任务
                    try:
                        created = await self._create_tasks_when_ready(workflow_instance_id, node_instance_id)
                        if created:
                            logger.info(f"  ✅ 为节点 {node_name} 创建了任务")
                            created_any_task = True
                        else:
                            logger.trace(f"  ⏳ 节点 {node_name} 依赖未满足或不符合创建条件")
                    except Exception as e:
                        logger.warning(f"  ❌ 为节点 {node_name} 创建任务失败: {e}")
                        continue
                
                # 如果成功创建了任务或没有等待节点，则退出重试
                if created_any_task or len(waiting_nodes) == 0:
                    if created_any_task:
                        logger.info(f"✅ 下游节点检查完成，创建了新任务")
                    return
                
                # 如果没有创建任何任务且还有等待节点，可能需要重试
                if attempt < max_retries - 1:
                    logger.debug(f"  ⏱️ 没有创建任务，{retry_delay}秒后重试...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5  # 指数退避
                
            except Exception as e:
                logger.error(f"检查下游节点失败 (尝试 {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5
                else:
                    import traceback
                    logger.error(f"下游节点检查最终失败: {traceback.format_exc()}")
        
        logger.trace(f"🏁 下游节点检查完成")
    
    async def _refresh_workflow_context_state(self, workflow_instance_id: uuid.UUID):
        """刷新工作流上下文状态（防止状态延迟问题）"""
        try:
            from .workflow_execution_context import get_context_manager
            context_manager = get_context_manager()
            workflow_context = await context_manager.get_context(workflow_instance_id)
            
            if not workflow_context:
                logger.debug(f"   📋 工作流上下文不存在，跳过刷新")
                return
            
            # 🔧 从数据库重新同步节点状态
            nodes_query = """
            SELECT ni.node_instance_id, ni.status, n.node_id
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.workflow_instance_id = %s
            AND ni.is_deleted = FALSE
            """
            
            nodes = await self.workflow_instance_repo.db.fetch_all(nodes_query, workflow_instance_id)
            
            updated_count = 0
            for node in nodes:
                node_instance_id = node['node_instance_id']
                db_status = node['status']
                
                # 将数据库状态转换为上下文状态
                context_status = {
                    'pending': 'PENDING',
                    'running': 'EXECUTING', 
                    'completed': 'COMPLETED',
                    'failed': 'FAILED'
                }.get(db_status, 'UNKNOWN')
                
                current_status = workflow_context.node_states.get(node_instance_id)
                
                if current_status != context_status:
                    workflow_context.node_states[node_instance_id] = context_status
                    updated_count += 1
                    
                    # 更新完成节点集合
                    if context_status == 'COMPLETED':
                        workflow_context.execution_context['completed_nodes'].add(node_instance_id)
                    elif context_status in ['PENDING', 'EXECUTING']:
                        workflow_context.execution_context['completed_nodes'].discard(node_instance_id)
            
            if updated_count > 0:
                logger.debug(f"   🔄 刷新了 {updated_count} 个节点的上下文状态")
            
        except Exception as e:
            logger.warning(f"刷新工作流上下文状态失败: {e}")
    
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
            
            # 收集直接上游节点的输出结果（简化版）
            logger.trace(f"📋 [END节点] 收集直接上游节点结果")
            context_data = await self._collect_immediate_upstream_results(workflow_instance_id, node_instance_id)
            
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
    
    async def _collect_immediate_upstream_results(self, workflow_instance_id: uuid.UUID, node_instance_id: uuid.UUID) -> Dict[str, Any]:
        """收集结束节点的直接上游节点结果（简化版）"""
        try:
            logger.trace(f"📋 收集直接上游节点结果: {node_instance_id}")
            
            # 使用上下文管理器获取直接上游结果
            context_data = await self.context_manager.get_task_context_data(workflow_instance_id, node_instance_id)
            immediate_upstream = context_data.get('immediate_upstream_results', {})
            
            # 简单整理上游结果
            end_node_output = {
                'workflow_completed': True,
                'completion_time': datetime.utcnow().isoformat(),
                'upstream_results': immediate_upstream,  # 直接使用上游结果
                'upstream_count': len(immediate_upstream),
                'summary': f"工作流完成，整合了{len(immediate_upstream)}个上游节点的结果",
                'workflow_instance_id': str(workflow_instance_id)
            }
            
            logger.trace(f"✅ 收集到 {len(immediate_upstream)} 个直接上游节点的结果")
            for node_name, result in immediate_upstream.items():
                logger.trace(f"  - {node_name}: {len(str(result.get('output_data', '')))} 字符输出")
            
            return end_node_output
            
        except Exception as e:
            logger.error(f"❌ 收集直接上游结果失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return {
                'workflow_completed': True,
                'completion_time': datetime.utcnow().isoformat(),
                'error': f"收集上游结果失败: {str(e)}",
                'workflow_instance_id': str(workflow_instance_id)
            }
    
    async def _check_workflow_completion(self, workflow_instance_id: uuid.UUID):
        """检查工作流是否可以完成，并触发准备就绪的节点"""
        try:
            logger.info(f"🔍 检查工作流完成状态和触发准备就绪节点: {workflow_instance_id}")
            
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
            
            logger.info(f"  📊 工作流总节点数: {len(all_nodes)}")
            
            # 检查各种状态的节点
            completed_nodes = [n for n in all_nodes if n['status'] == 'completed']
            failed_nodes = [n for n in all_nodes if n['status'] == 'failed']
            pending_nodes = [n for n in all_nodes if n['status'] == 'pending']
            running_nodes = [n for n in all_nodes if n['status'] == 'running']
            
            logger.info(f"  📊 节点状态分布: 完成 {len(completed_nodes)}, 失败 {len(failed_nodes)}, 等待 {len(pending_nodes)}, 运行中 {len(running_nodes)}")
            
            # 🔧 关键修复：检查并触发准备就绪的节点
            if pending_nodes:
                logger.info(f"🔄 检查 {len(pending_nodes)} 个等待节点是否准备就绪:")
                for node in pending_nodes:
                    logger.info(f"  - {node['name']} ({node['node_instance_id']}) 状态: {node['status']}")
                
                # 触发准备就绪的节点
                triggered_count = await self._check_and_trigger_ready_nodes(workflow_instance_id, pending_nodes)
                if triggered_count > 0:
                    logger.info(f"✅ 成功触发了 {triggered_count} 个准备就绪的节点")
                else:
                    logger.info(f"ℹ️ 没有节点准备就绪，等待更多依赖完成")
            
            # 如果有失败节点，标记工作流为失败
            if failed_nodes:
                from ..models.instance import WorkflowInstanceUpdate, WorkflowInstanceStatus
                update_data = WorkflowInstanceUpdate(
                    status=WorkflowInstanceStatus.FAILED,
                    error_message=f"工作流包含 {len(failed_nodes)} 个失败节点"
                )
                await self.workflow_instance_repo.update_instance(workflow_instance_id, update_data)
                logger.info(f"❌ 工作流标记为失败")
                return
            
            # 🆕 使用基于路径状态的工作流完成检查
            workflow_context = await self.context_manager.get_context(workflow_instance_id)
            if workflow_context:
                # 检查工作流是否完成（基于路径状态）
                is_completed = await workflow_context.is_workflow_completed()

                if is_completed:
                    from ..models.instance import WorkflowInstanceUpdate, WorkflowInstanceStatus
                    update_data = WorkflowInstanceUpdate(status=WorkflowInstanceStatus.COMPLETED)
                    await self.workflow_instance_repo.update_instance(workflow_instance_id, update_data)
                    logger.info(f"✅ 基于路径状态检测，工作流标记为完成")
                else:
                    # 提供详细的路径状态信息
                    active_paths = len(workflow_context.execution_context.get('active_paths', set()))
                    completed_paths = len(workflow_context.execution_context.get('completed_paths', set()))
                    failed_paths = len(workflow_context.execution_context.get('failed_paths', set()))

                    logger.info(f"⏳ 工作流仍在进行中: 活跃路径={active_paths}, 完成路径={completed_paths}, 失败路径={failed_paths}")
                    logger.info(f"   传统统计: {len(completed_nodes)}/{len(all_nodes)} 节点完成, {len(pending_nodes)} 节点等待, {len(running_nodes)} 节点运行中")
            else:
                # 向后兼容：如果没有上下文，使用原有逻辑
                logger.warning("⚠️ 工作流上下文不存在，使用传统完成检查逻辑")

                # 如果所有节点都已完成，标记工作流为完成
                if len(completed_nodes) == len(all_nodes) and len(all_nodes) > 0:
                    from ..models.instance import WorkflowInstanceUpdate, WorkflowInstanceStatus
                    update_data = WorkflowInstanceUpdate(status=WorkflowInstanceStatus.COMPLETED)
                    await self.workflow_instance_repo.update_instance(workflow_instance_id, update_data)
                    logger.info(f"✅ 传统逻辑：工作流标记为完成")
                else:
                    logger.info(f"⏳ 传统逻辑：工作流仍在进行中: {len(completed_nodes)}/{len(all_nodes)} 节点完成, {len(pending_nodes)} 节点等待, {len(running_nodes)} 节点运行中")
            
        except Exception as e:
            logger.error(f"❌ 检查工作流完成状态失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")

    # =============================================================================
    # 新架构方法 - 支持WorkflowInstanceContext
    # =============================================================================
    
    async def _get_upstream_node_instances(self, node_id: uuid.UUID, workflow_instance_id: uuid.UUID) -> List[uuid.UUID]:
        """获取节点的上游节点实例ID列表（修复版：确保使用正确的工作流实例）"""
        try:
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_repo = NodeInstanceRepository()
            
            # 查询上游连接关系
            upstream_query = """
            SELECT DISTINCT 
                nc.from_node_id as upstream_node_id,
                n.name as upstream_node_name
            FROM node_connection nc
            JOIN node n ON nc.from_node_id = n.node_id
            WHERE nc.to_node_id = $1
            ORDER BY n.name
            """
            
            logger.info(f"🔍 [上游查询] 查询节点 {node_id} 的上游依赖")
            upstream_connections = await node_repo.db.fetch_all(upstream_query, node_id)
            logger.info(f"🔍 [上游查询] 查询到 {len(upstream_connections)} 个上游连接")
            
            # 输出所有上游连接的详细信息
            for conn in upstream_connections:
                logger.info(f"🔍 [上游查询] 发现连接: {conn.get('upstream_node_name', 'Unknown')} ({conn['upstream_node_id']}) -> 当前节点({node_id})")
            
            upstream_node_instance_ids = []
            for upstream in upstream_connections:
                upstream_node_id = upstream['upstream_node_id']
                logger.info(f"🔍 [上游查询] 处理上游节点 {upstream.get('upstream_node_name', 'Unknown')} (node_id: {upstream_node_id})")
                
                # 🔧 关键修复：确保查询的是当前工作流实例的节点实例，而不是其他实例的
                instance_query = """
                SELECT node_instance_id 
                FROM node_instance 
                WHERE node_id = $1 AND workflow_instance_id = $2 AND is_deleted = FALSE
                ORDER BY created_at DESC
                LIMIT 1
                """
                upstream_instance_result = await node_repo.db.fetch_one(
                    instance_query, upstream_node_id, workflow_instance_id
                )
                
                if upstream_instance_result:
                    upstream_node_instance_id = upstream_instance_result['node_instance_id']
                    upstream_node_instance_ids.append(upstream_node_instance_id)
                    logger.info(f"  ✅ 找到上游实例: {upstream.get('upstream_node_name', 'Unknown')} -> {upstream_node_instance_id}")
                    logger.info(f"    (确认属于工作流实例: {workflow_instance_id})")
                else:
                    logger.warning(f"  ⚠️ 未找到上游节点 {upstream_node_id} 在工作流实例 {workflow_instance_id} 中的对应实例")
            
            logger.info(f"✅ [上游查询] 获取到 {len(upstream_node_instance_ids)} 个上游节点实例ID: {upstream_node_instance_ids}")
            return upstream_node_instance_ids
            
        except Exception as e:
            logger.error(f"获取上游节点实例失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return []

    async def _create_node_instances_with_new_context(self, 
                                                    workflow_context:WorkflowExecutionContext, 
                                                    workflow_instance_id: uuid.UUID, 
                                                    workflow_base_id: uuid.UUID,
                                                    nodes: List[Dict[str, Any]],
                                                    execute_request):
        """使用新上下文管理器创建节点实例（修复版：真正的分阶段处理，避免时序问题）"""
        try:
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            from ..models.instance import NodeInstanceCreate, NodeInstanceStatus
            
            node_instance_repo = NodeInstanceRepository()
            
            logger.info(f"🏗️ [节点创建] 开始为工作流 {workflow_instance_id} 创建 {len(nodes)} 个节点实例")
            
            task_creation_summary = {
                'start_nodes': 0,
                'processor_nodes': 0, 
                'end_nodes': 0,
                'start_completed': 0,
                'tasks_deferred': 0
            }
            
            # 存储创建的节点信息
            created_nodes_info = []
            start_nodes_to_complete = []
            
            # ====== 第一阶段：仅创建所有节点实例 ======
            logger.info(f"📋 [第一阶段] 创建所有节点实例")
            instance_id_set = set()  # 用于跟踪已创建的节点实例ID
            
            for i, node in enumerate(nodes, 1):
                logger.info(f"📋 [节点创建 {i}/{len(nodes)}] 处理节点: {node['name']} (类型: {node['type']})")
                logger.info(f"   - node_id: {node['node_id']}")
                logger.info(f"   - node_base_id: {node['node_base_id']}")
                # await asyncio.sleep(1) 
                
                # 创建节点实例
                task_description = node.get('task_description') or ''  # 确保不传入None
                node_instance_data = NodeInstanceCreate(
                    workflow_instance_id=workflow_instance_id,
                    node_id=node['node_id'],
                    node_base_id=node['node_base_id'],
                    node_instance_name=f"{node['name']}_instance",
                    task_description=task_description,
                    status=NodeInstanceStatus.PENDING,
                    input_data={},
                    output_data={},
                    error_message=None,
                    retry_count=0
                )
                
                node_instance = await node_instance_repo.create_node_instance(node_instance_data)
                if not node_instance:
                    logger.error(f"❌ [节点创建] 创建节点实例失败: {node['name']}")
                    continue
                
                node_instance_id = node_instance['node_instance_id']
                if node_instance_id in instance_id_set:
                    raise ValueError(f"创建节点实例失败: 节点 {node['name']} 已存在于实例 {workflow_instance_id}")
                instance_id_set.add(node_instance_id)
                logger.info(f"✅ [节点创建] 节点实例创建成功: {node['name']} (实例ID: {node_instance_id})")
                # logger.debug(f"🔍 [变量检查] 节点 {node['name']} 变量状态:")
                # logger.debug(f"   - node字典内存地址: {id(node)}")
                # logger.debug(f"   - node_instance_id: {node_instance_id}")
                # logger.debug(f"   - node_instance字典内存地址: {id(node_instance)}")
                
                # 收集节点信息用于第二阶段处理
                # 使用深拷贝确保node字典的独立性，防止变量引用问题
                node_info = {
                    'node': {
                        'node_id': node['node_id'],
                        'node_base_id': node['node_base_id'], 
                        'name': node['name'],
                        'type': node['type'],
                        'task_description': node.get('task_description')
                    },  # 创建新的字典对象而不是引用原对象
                    'node_instance_id': node_instance_id  # 明确使用当前循环中的node_instance_id
                }
                created_nodes_info.append(node_info)
                
                # 记录节点类型统计
                if node['type'] == NodeType.START.value:
                    task_creation_summary['start_nodes'] += 1
                    start_nodes_to_complete.append(node_info)
                elif node['type'] == NodeType.PROCESSOR.value:
                    task_creation_summary['processor_nodes'] += 1
                    task_creation_summary['tasks_deferred'] += 1
                elif node['type'] == NodeType.END.value:
                    task_creation_summary['end_nodes'] += 1
            
            logger.info(f"✅ [第一阶段] 所有 {len(created_nodes_info)} 个节点实例创建完成")
            
            # ====== 第二阶段：查询依赖关系并注册 ======
            logger.info(f"📋 [第二阶段] 查询依赖关系并注册到上下文")
            
            for i, node_info in enumerate(created_nodes_info, 1):
                node = node_info['node']
                node_instance_id = node_info['node_instance_id']
                
                logger.info(f"🔗 [依赖分析 {i}/{len(created_nodes_info)}] 分析节点 {node['name']} 的上游依赖...")
                logger.debug(f"🔍 [第二阶段变量检查] 节点 {node['name']} 变量状态:")
                logger.debug(f"   - node_info内存地址: {id(node_info)}")
                logger.debug(f"   - node字典内存地址: {id(node)}")
                logger.debug(f"   - 从node_info获取的node_instance_id: {node_instance_id}")
                
                try:
                    # 现在所有节点实例都已创建，可以安全查询上游依赖
                    upstream_node_instance_ids = await self._get_upstream_node_instances(
                        node['node_id'], workflow_instance_id
                    )
                    logger.info(f"🔗 [依赖分析] 节点 {node['name']} 有 {len(upstream_node_instance_ids)} 个上游依赖: {upstream_node_instance_ids}")
                except Exception as e:
                    logger.error(f"❌ [依赖分析] 查询节点 {node['name']} 上游依赖失败: {e}")
                    import traceback
                    logger.error(f"错误堆栈: {traceback.format_exc()}")
                    upstream_node_instance_ids = []
                
                # 在新上下文中注册依赖
                logger.info(f"📝 [依赖注册] 准备注册节点 {node['name']} 的依赖关系")
                logger.info(f"   - 当前节点实例ID: {node_instance_id}")
                logger.info(f"   - 当前节点ID: {node['node_id']}")
                logger.info(f"   - 上游实例ID列表: {upstream_node_instance_ids}")
                
                await workflow_context.register_node_dependencies(
                    node_instance_id,
                    node['node_id'],  # 使用node_id而不是node_base_id
                    upstream_node_instance_ids  # 使用node_instance_id列表
                )
                logger.info(f"📝 [依赖注册] 节点 {node['name']} 依赖关系注册完成: {len(upstream_node_instance_ids)} 个上游依赖")
                
                # 更新节点信息
                node_info['upstream_count'] = len(upstream_node_instance_ids)
                
            logger.info(f"✅ [第二阶段] 所有 {len(created_nodes_info)} 个节点的依赖关系注册完成")
            
            # ====== 第三阶段：标记START节点完成，触发工作流执行 ======
            logger.info(f"📋 [第三阶段] 标记START节点完成并触发执行")
            logger.info(f"   - 已创建 {len(created_nodes_info)} 个节点实例")
            logger.info(f"   - 已注册 {len(created_nodes_info)} 个节点的依赖关系")
            logger.info(f"   - 找到 {len(start_nodes_to_complete)} 个START节点待完成")
            
            for start_node_info in start_nodes_to_complete:
                node = start_node_info['node']
                node_instance_id = start_node_info['node_instance_id']
                
                logger.info(f"🚀 [START节点] {node['name']} - 标记为完成，传递初始上下文")
                
                # START节点传递初始上下文，包含任务描述和上下文数据
                initial_context = {
                    'workflow_start': True,
                    'start_time': datetime.utcnow().isoformat(),
                    'start_node': node['name'],
                    'workflow_instance_id': str(workflow_instance_id),
                    'task_description': node.get('task_description', ''),  # 添加任务描述
                    'context_data': execute_request.context_data if hasattr(execute_request, 'context_data') and execute_request.context_data else {}  # 添加上下文数据
                }
                
                # 统一使用workflow_context而不是self.context_manager
                await workflow_context.mark_node_completed(
                    node['node_id'], 
                    node_instance_id, 
                    initial_context
                )
                
                task_creation_summary['start_completed'] += 1
                logger.info(f"✅ [START节点] {node['name']} 已标记为完成，传递初始上下文")
                
            # ====== 总结报告 ======
            logger.info(f"🎯 [节点创建总结] 工作流 {workflow_instance_id}:")
            logger.info(f"   📊 节点分布: START={task_creation_summary['start_nodes']}, PROCESSOR={task_creation_summary['processor_nodes']}, END={task_creation_summary['end_nodes']}")
            logger.info(f"   ⚡ 节点处理: START完成={task_creation_summary['start_completed']}, 任务延迟创建={task_creation_summary['tasks_deferred']}")
            logger.info(f"   🔗 依赖关系: 所有 {len(created_nodes_info)} 个节点的依赖关系已注册完成")
            logger.trace(f"✅ 使用新上下文创建了 {len(nodes)} 个节点实例")
            
        except Exception as e:
            logger.error(f"使用新上下文创建节点实例失败: {e}")
            raise
    
    async def _create_tasks_for_node_new_context(self, node: Dict[str, Any], 
                                               node_instance_id: uuid.UUID,
                                               workflow_instance_id: uuid.UUID):
        """为节点创建任务实例（新架构）"""
        try:
            logger.info(f"🔍 [新架构-任务创建] 开始为节点创建任务:")
            logger.info(f"   - 节点名称: {node.get('name', 'Unknown')}")
            logger.info(f"   - 节点类型: {node.get('type', 'Unknown')}")
            logger.info(f"   - 节点ID: {node.get('node_id')}")
            logger.info(f"   - 节点实例ID: {node_instance_id}")
            
            # 获取节点的处理器（修复：使用node_id）  
            processors = await self._get_node_processors(node['node_id'])
            
            logger.info(f"🔍 [新架构-任务创建] 处理器查询结果: {len(processors)} 个处理器")
            
            if not processors:
                logger.warning(f"⚠️ [新架构-任务创建] 节点 {node.get('name')} 没有绑定处理器，跳过任务创建")
                return
            
            created_task_count = 0
            for i, processor in enumerate(processors, 1):
                logger.info(f"🔍 [新架构-任务创建] 处理处理器 {i}/{len(processors)}:")
                logger.info(f"   - 处理器名称: {processor.get('processor_name', 'Unknown')}")
                logger.info(f"   - 处理器ID: {processor.get('processor_id')}")
                
                # 根据处理器类型确定任务类型和分配
                processor_type = processor.get('processor_type', processor.get('type', 'HUMAN'))
                task_type = self._determine_task_type(processor_type)
                assigned_user_id = processor.get('user_id')
                assigned_agent_id = processor.get('agent_id')
                
                logger.info(f"   - 处理器类型: {processor_type} -> 任务类型: {task_type.value}")
                logger.info(f"   - 分配用户ID: {assigned_user_id}")
                logger.info(f"   - 分配AgentID: {assigned_agent_id}")
                
                # 🔧 修复：获取真实的上下文和输入数据
                logger.info(f"🔍 [新架构-任务创建] 获取节点上下文数据...")
                logger.info(f"   - 工作流实例ID: {workflow_instance_id}")
                logger.info(f"   - 节点实例ID: {node_instance_id}")
                
                context_data = await self.context_manager.get_task_context_data(workflow_instance_id, node_instance_id)
                logger.info(f"   - 上下文数据键: {list(context_data.keys()) if context_data else '空'}")
                
                if context_data:
                    # 详细记录上下文内容
                    upstream_results = context_data.get('immediate_upstream_results', {})
                    logger.info(f"   - 上游节点结果数量: {len(upstream_results)}")
                    for upstream_name, upstream_data in upstream_results.items():
                        output_data = upstream_data.get('output_data', '')
                        logger.info(f"     * {upstream_name}: {len(str(output_data))} 字符输出")
                        if output_data:
                            logger.info(f"       预览: {str(output_data)[:100]}...")
                    
                    global_data = context_data.get('workflow_global', {}).get('global_data', {})
                    logger.info(f"   - 全局数据: {len(global_data)} 个键")
                
                # 将上下文数据转换为文本格式（与旧方法保持一致）
                context_text = json.dumps(context_data, ensure_ascii=False, indent=2, default=_json_serializer) if context_data else ""
                input_text = json.dumps(node.get('input_data', {}), ensure_ascii=False, indent=2, default=_json_serializer)
                
                logger.info(f"   - 上下文文本长度: {len(context_text)} 字符")
                logger.info(f"   - 输入数据文本长度: {len(input_text)} 字符")
                if context_text:
                    logger.info(f"   - 上下文预览: {context_text}...")

                
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
                    input_data=input_text,  
                    context_data=context_text, 
                    status=TaskInstanceStatus.PENDING,
                    priority='MEDIUM'
                )
                
                logger.info(f"🔍 [新架构-任务创建] 准备创建任务实例...")
                logger.info(f"   - 任务标题: {task_title}")
                logger.info(f"   - 任务描述: {task_description[:100]}...")
                
                try:
                    # 修复：使用正确的方法名称
                    task_instance = await self.task_instance_repo.create_task(task_data)
                    if task_instance:
                        created_task_count += 1
                        task_id = task_instance.get('task_instance_id')
                        logger.info(f"✅ [新架构-任务创建] 任务创建成功:")
                        logger.info(f"   - 任务实例ID: {task_id}")
                        logger.info(f"   - 任务状态: {task_instance.get('status')}")
                    else:
                        logger.error(f"❌ [新架构-任务创建] 任务创建失败: create_task_instance返回空结果")
                except Exception as task_creation_error:
                    logger.error(f"❌ [新架构-任务创建] 任务创建异常: {task_creation_error}")
                    import traceback
                    logger.error(f"异常堆栈: {traceback.format_exc()}")
                
            logger.info(f"🎉 [新架构-任务创建] 节点 {node.get('name')} 任务创建完成，共创建 {created_task_count} 个任务")
                
        except Exception as e:
            logger.error(f"❌ [新架构-任务创建] 为节点创建任务实例失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
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
            # 🔧 修复：通过context manager获取节点信息，而不是直接从context
            from ..services.workflow_execution_context import get_context_manager
            context_manager = get_context_manager()
            
            # 检查节点是否准备好执行
            if not context_manager.is_node_ready_to_execute(node_instance_id):
                logger.warning(f"节点 {node_instance_id} 尚未准备好执行")
                return
            
            # 获取节点信息
            dep_info = context_manager.get_node_dependency_info(node_instance_id)
            if not dep_info:
                logger.error(f"无法获取节点 {node_instance_id} 的依赖信息")
                return
            
            node_id = dep_info['node_id']
            workflow_instance_id = dep_info['workflow_instance_id']
            
            # 标记节点开始执行
            await context_manager.mark_node_executing(workflow_instance_id, node_id, node_instance_id)
            
            # 🔧 动态创建任务实例：只有在节点准备执行时才创建任务
            tasks = await self.task_instance_repo.get_tasks_by_node_instance(node_instance_id)
            
            if not tasks:
                # 检查节点类型 - START/END节点不需要任务，直接自动完成
                node_instance_data = await self._get_node_instance_data(node_instance_id)
                if node_instance_data:
                    node_type = node_instance_data.get('node_type', 'PROCESSOR')
                    node_name = node_instance_data.get('node_name', 'Unknown')
                    node_id = node_instance_data.get('node_id', 'Unknown')
                    
                    # 🔧 添加详细的节点类型调试信息
                    logger.info(f"🔍 [节点类型检查] 节点实例: {node_instance_id}")
                    logger.info(f"    - 节点ID: {node_id}")
                    logger.info(f"    - 节点名称: {node_name}")
                    logger.info(f"    - 节点类型: {node_type}")
                    logger.info(f"    - 原始数据: {node_instance_data}")
                    
                    if node_type.upper() in ['START', 'END']:
                        logger.info(f"🚀 [{node_type}节点] 无需创建任务，直接自动执行: {node_instance_id}")
                        # START/END节点直接标记为完成，使用当前上下文
                        await self._auto_complete_system_node_with_context(workflow_context, node_instance_id, node_type.upper())
                        return
                    else:
                        # 🔧 只为PROCESSOR等需要任务的节点创建任务
                        logger.info(f"🔨 [动态任务创建] 为{node_type}节点创建任务: {node_instance_id}")
                        task_created = await self._create_task_for_node(node_instance_id, workflow_instance_id)
                        if task_created:
                            # 重新查询任务
                            tasks = await self.task_instance_repo.get_tasks_by_node_instance(node_instance_id)
                            logger.info(f"✅ [动态任务创建] 成功创建并分配任务")
                        else:
                            logger.error(f"❌ [动态任务创建] 任务创建失败")
                            return
            
            # 现在所有到这里的节点都应该有任务了（START/END已提前返回）
            if not tasks:
                logger.error(f"❌ PROCESSOR节点没有任务且创建失败: {node_instance_id}")
                return
            
            # 有任务的节点，启动任务执行
            for task in tasks:
                await self._execute_task(task)
            
            logger.trace(f"节点 {node_id} 的 {len(tasks)} 个任务已启动")
            
        except Exception as e:
            logger.error(f"使用新上下文执行节点 {node_instance_id} 失败: {e}")
            # 标记节点失败
            if 'dep_info' in locals() and dep_info:
                # 🔧 修复：使用context manager标记节点失败
                await context_manager.mark_node_failed(
                    workflow_instance_id,
                    dep_info['node_id'],
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
                           limit: Optional[int] = None) -> List[Dict[str, Any]]:
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
            
            # 验证任务分配给该用户 - 使用字符串比较避免UUID类型问题
            task_assigned_user_id = task.get('assigned_user_id')
            task_assigned_user_id_str = str(task_assigned_user_id) if task_assigned_user_id else None
            user_id_str = str(user_id) if user_id else None
            
            if task_assigned_user_id_str != user_id_str:
                logger.warning(f"⚠️ [任务详情] 用户 {user_id} 无权限访问任务 {task_id}")
                logger.warning(f"   - 任务分配用户ID: {task_assigned_user_id_str}")
                logger.warning(f"   - 请求用户ID: {user_id_str}")
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
            
            # 🔍 添加调试日志
            logger.info(f"🔍 [任务详情调试] 上游上下文数据:")
            logger.info(f"   - 上游上下文键: {list(upstream_context.keys()) if upstream_context else '无数据'}")

            # 🆕 提取所有上游任务提交的附件到任务顶级字段
            task_attachments = []
            if upstream_context:
                immediate_results = upstream_context.get('immediate_upstream_results', {})
                logger.info(f"   - immediate_upstream_results键: {list(immediate_results.keys())}")
                for node_name, node_data in immediate_results.items():
                    logger.info(f"   - 节点 {node_name} 的output_data: {node_data.get('output_data', {})}")
                    # 提取上游任务附件
                    upstream_task_attachments = node_data.get('task_attachments', [])
                    if upstream_task_attachments:
                        task_attachments.extend(upstream_task_attachments)
                        logger.info(f"   - 节点 {node_name} 贡献 {len(upstream_task_attachments)} 个任务附件")

            # 将合并的附件添加到任务数据中
            task['task_attachments'] = task_attachments
            logger.info(f"📎 [附件合并] 共收集到 {len(task_attachments)} 个上游任务附件")

            # 丰富任务信息
            task = await self._enrich_task_info(task)
            
            # 🔍 最终任务数据结构调试
            logger.info(f"🔍 [任务详情调试] 最终任务数据结构:")
            logger.info(f"   - 任务基础字段: {list(task.keys())}")
            logger.info(f"   - upstream_context是否存在: {'upstream_context' in task}")
            logger.info(f"   - context_data是否存在: {'context_data' in task}")
            
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
                                     result_data: Dict[str, Any], result_summary: Optional[str] = None,
                                     selected_next_nodes: Optional[List[uuid.UUID]] = None) -> Dict[str, Any]:
        """提交人工任务结果"""
        try:
            # logger.info(f"📝 [任务提交] 用户提交任务结果:")
            # logger.info(f"   - 任务ID: {task_id}")
            # logger.info(f"   - 用户ID: {user_id}")
            # logger.info(f"   - 结果数据: {result_data}")
            # logger.info(f"   - 结果键数量: {len(result_data.keys()) if isinstance(result_data, dict) else 'N/A'}")
            
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
            # logger.info(f"🔐 [任务提交] 验证用户权限...")
            assigned_user_id = task.get('assigned_user_id')
            # logger.info(f"   - 请求用户ID: {user_id} (类型: {type(user_id)})")
            # logger.info(f"   - 分配用户ID: {assigned_user_id} (类型: {type(assigned_user_id)})")
            
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

                # 🆕 处理用户条件边选择
                if selected_next_nodes:
                    logger.info(f"🔀 [条件边] 处理用户选择的下游节点: {selected_next_nodes}")
                    # 将用户选择保存到上下文中
                    workflow_instance_id = updated_task.get('workflow_instance_id')
                    node_instance_id = updated_task.get('node_instance_id')

                    if workflow_instance_id and node_instance_id:
                        try:
                            context = await self.context_manager.get_context(workflow_instance_id)
                            if context:
                                # 获取主路径ID
                                main_path_id = f"main_{workflow_instance_id}"
                                if main_path_id in context.execution_context['execution_paths']:
                                    path = context.execution_context['execution_paths'][main_path_id]
                                    path.user_selections[node_instance_id] = selected_next_nodes
                                    logger.info(f"✅ [条件边] 用户选择已保存到执行路径")
                                else:
                                    logger.warning(f"⚠️ [条件边] 主执行路径不存在: {main_path_id}")
                            else:
                                logger.warning(f"⚠️ [条件边] 工作流上下文不存在: {workflow_instance_id}")
                        except Exception as e:
                            logger.error(f"❌ [条件边] 保存用户选择失败: {e}")

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

                # 🔧 Linus式修复：向上传播取消状态到节点和工作流
                await self._propagate_task_cancellation(task_id, task, cancel_reason)

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
            SELECT ni.*, n.name as node_name, n.type as node_type, n.task_description as description
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.node_instance_id = %s
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
        """统一处理任务完成 - 修复并发竞态条件"""
        # 🔧 关键修复：使用分布式锁防止并发竞态条件
        lock_key = f"task_completion_{task['workflow_instance_id']}"
        
        try:
            logger.info(f"🔄 [统一任务完成-并发修复] 处理{task_type}任务完成: {task['task_instance_id']}")
            logger.info(f"   获取工作流级别锁: {lock_key}")
            
            # 🔧 使用异步锁确保同一工作流的任务完成处理是串行的
            if not hasattr(self, '_completion_locks'):
                self._completion_locks = {}
            
            if lock_key not in self._completion_locks:
                self._completion_locks[lock_key] = asyncio.Lock()
            
            async with self._completion_locks[lock_key]:
                logger.debug(f"   🔒 已获取工作流锁，开始原子操作")
                
                # 获取节点信息  
                node_query = """
                SELECT n.node_id 
                FROM node_instance ni
                JOIN node n ON ni.node_id = n.node_id
                WHERE ni.node_instance_id = %s
                """
                node_info = await self.task_instance_repo.db.fetch_one(node_query, task['node_instance_id'])
                
                if not node_info:
                    logger.error(f"❌ 无法找到节点信息: {task['node_instance_id']}")
                    return
                
                # 🔧 状态一致性检查：确保任务和节点状态同步
                fresh_task = await self.task_instance_repo.get_task_by_id(task['task_instance_id'])
                if fresh_task and fresh_task.get('status') != 'completed':
                    logger.warning(f"⚠️  任务状态不一致，重新检查: {fresh_task.get('status')}")
                    return
                
                # 🔧 检查节点是否已经被标记为完成（防止重复处理）
                from .workflow_execution_context import get_context_manager
                context_manager = get_context_manager()
                workflow_context = await context_manager.get_context(task['workflow_instance_id'])
                
                if workflow_context:
                    node_status = workflow_context.get_node_state(task['node_instance_id'])
                    if node_status == 'COMPLETED':
                        logger.warning(f"⚠️  节点 {task['node_instance_id']} 已经完成，跳过重复处理")
                        return
                
                # 构造输出数据
                completion_output = {
                    "message": f"{task_type}任务完成",
                    "task_type": task_type,
                    "output_data": output_data,
                    "completed_at": updated_task.get('completed_at').isoformat() if updated_task.get('completed_at') else None,
                    "task_id": str(task['task_instance_id'])
                }
                
                # 🔧 原子操作：标记节点完成并触发下游检查
                logger.debug(f"   🎯 开始节点完成标记和下游触发")
                await self.context_manager.mark_node_completed(
                    workflow_instance_id=task['workflow_instance_id'],
                    node_id=node_info['node_id'],
                    node_instance_id=task['node_instance_id'],
                    output_data=completion_output
                )
                
                # 🔧 额外的下游检查确保：强制检查是否有遗漏的下游节点
                logger.debug(f"   🔍 执行额外的下游节点检查")
                await self._check_downstream_nodes_for_task_creation(task['workflow_instance_id'])
                
                logger.info(f"✅ [统一任务完成-并发修复] {task_type}任务完成处理成功")
                
        except Exception as e:
            logger.error(f"💥 [统一任务完成] 处理失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    async def _get_node_instance_data(self, node_instance_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取节点实例数据（包含节点类型）"""
        try:
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_repo = NodeInstanceRepository()
            # 🔧 使用带详细信息的查询方法获取node_type
            return await node_repo.get_instance_with_details(node_instance_id)
        except Exception as e:
            logger.error(f"获取节点实例数据失败: {e}")
            return None
    
    async def _get_processor_info_for_node(self, node_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取节点的处理器信息"""
        try:
            from ..repositories.node.node_repository import NodeRepository
            node_repo = NodeRepository()
            
            # 查询节点及其关联的处理器信息
            query = """
                SELECT 
                    n.*,
                    np.processor_id,
                    p.type as processor_type,
                    p.name as processor_name,
                    COALESCE(u.username, a.agent_name) as processor_display_name
                FROM node n
                LEFT JOIN node_processor np ON n.node_id = np.node_id
                LEFT JOIN processor p ON np.processor_id = p.processor_id
                LEFT JOIN user u ON p.user_id = u.user_id AND p.type = 'human'
                LEFT JOIN agent a ON p.agent_id = a.agent_id AND p.type = 'agent'
                WHERE n.node_id = $1 AND n.is_deleted = FALSE
            """
            
            result = await node_repo.db.fetch_one(query, node_id)
            if result:
                return {
                    'processor_id': result.get('processor_id'),
                    'processor_type': result.get('processor_type', 'HUMAN'),
                    'processor_name': result.get('processor_name'),
                    'processor_display_name': result.get('processor_display_name'),
                    'node_name': result.get('name')
                }
            else:
                # 如果没有显式处理器，默认返回HUMAN类型
                logger.warning(f"节点 {node_id} 没有分配处理器，使用默认HUMAN类型")
                return {
                    'processor_id': None,
                    'processor_type': 'HUMAN',
                    'processor_name': None,
                    'processor_display_name': None,
                    'node_name': 'Unknown'
                }
                
        except Exception as e:
            logger.error(f"获取节点处理器信息失败: {e}")
            return None
    
    async def _auto_complete_system_node_with_context(self, workflow_context, node_instance_id: uuid.UUID, node_type: str):
        """使用指定上下文自动完成系统节点（START/END节点）"""
        try:
            # 获取节点实例信息
            node_instance_data = await self._get_node_instance_data(node_instance_id)
            if not node_instance_data:
                logger.error(f"无法获取节点实例信息: {node_instance_id}")
                return
            
            workflow_instance_id = node_instance_data['workflow_instance_id']
            node_id = node_instance_data['node_id']
            
            # 生成系统节点的输出数据
            from datetime import datetime
            output_data = {
                'message': f'{node_type} node completed automatically',
                'node_type': node_type,
                'completion_time': str(datetime.now()),
                'auto_completed': True
            }
            
            # 🔧 特殊处理START节点：添加任务描述和上下文信息
            if node_type.upper() == 'START':
                # 获取节点的任务描述
                node_data = await self.node_repo.get_node_by_id(node_id)
                if node_data:
                    task_description = node_data.get('task_description', '')
                    output_data.update({
                        'message': 'START节点自动完成',
                        'task_description': task_description,
                        'completed_at': datetime.utcnow().isoformat()
                    })
                
                # 添加工作流上下文信息
                try:
                    global_data = workflow_context.execution_context.get('global_data', {})
                    workflow_context_data = global_data.get('workflow_context_data', {})
                    
                    if workflow_context_data:
                        output_data['workflow_context'] = {
                            'subdivision_context': workflow_context_data.get('subdivision_context'),
                            'subdivision_id': workflow_context_data.get('subdivision_id'),
                            'execution_type': workflow_context_data.get('execution_type'),
                            'source': 'task_subdivision_workflow'
                        }
                        logger.info(f"📋 START节点添加上下文信息: {workflow_context_data}")
                except Exception as ctx_error:
                    logger.error(f"⚠️ START节点添加上下文信息失败: {ctx_error}")
            
            # 使用当前上下文标记节点完成
            await workflow_context.mark_node_completed(node_id, node_instance_id, output_data)
            
            logger.info(f"✅ [{node_type}节点] 自动完成: {node_instance_id}")
            
        except Exception as e:
            logger.error(f"自动完成系统节点失败: {e}")
            raise

    async def _auto_complete_system_node(self, node_instance_id: uuid.UUID, node_type: str):
        """🔧 自动完成系统节点（START/END节点）"""
        try:
            # 获取节点实例信息
            node_instance_data = await self._get_node_instance_data(node_instance_id)
            if not node_instance_data:
                logger.error(f"无法获取节点实例信息: {node_instance_id}")
                return
            
            workflow_instance_id = node_instance_data['workflow_instance_id']
            node_id = node_instance_data['node_id']
            
            # 生成系统节点的输出数据
            from datetime import datetime
            output_data = {
                'message': f'{node_type} node completed automatically',
                'node_type': node_type,
                'completion_time': str(datetime.now()),
                'auto_completed': True
            }
            
            from ..services.workflow_execution_context import get_context_manager
            context_manager = get_context_manager()
            
            # 直接标记节点完成
            await context_manager.mark_node_completed(
                workflow_instance_id, node_id, node_instance_id, output_data
            )
            
            logger.info(f"✅ [{node_type}节点] 自动完成: {node_instance_id}")
            
        except Exception as e:
            logger.error(f"自动完成系统节点失败: {e}")
            raise
    
    async def _create_task_for_node(self, node_instance_id: uuid.UUID, workflow_instance_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """为节点动态创建任务实例"""
        try:
            # 获取节点实例信息
            node_instance_data = await self._get_node_instance_data(node_instance_id)
            if not node_instance_data:
                logger.error(f"无法获取节点实例信息: {node_instance_id}")
                return None
            
            node_id = node_instance_data['node_id']
            
            # 获取节点定义信息（包含处理器信息）
            from ..repositories.node.node_repository import NodeRepository
            node_repo = NodeRepository()
            node_data = await node_repo.get_node_by_id(node_id)
            if not node_data:
                logger.error(f"无法获取节点定义信息: {node_id}")
                return None
            
            # 获取处理器信息
            processor_info = await self._get_processor_info_for_node(node_id)
            if not processor_info:
                logger.error(f"节点 {node_id} 没有分配处理器，无法创建任务")
                return None
            
            # 获取工作流实例信息（用于分配用户）
            workflow_instance = await self.workflow_instance_repo.get_instance_by_id(workflow_instance_id)
            executor_id = workflow_instance.get('executor_id') if workflow_instance else None
            
            from ..models.instance import TaskInstanceStatus, TaskInstanceType
            import uuid
            from ..utils.helpers import now_utc
            
            # 确定任务类型和分配对象 - 🔧 修复 None 值处理
            processor_type_raw = processor_info.get('processor_type')
            processor_type = (processor_type_raw or 'HUMAN').upper()
            
            logger.debug(f"[动态任务] 处理器类型: {processor_type_raw} -> {processor_type}")
            
            if processor_type == 'HUMAN':
                task_type = TaskInstanceType.HUMAN
                assigned_user_id = executor_id  # 分配给工作流执行者
                assigned_agent_id = None
            elif processor_type == 'AGENT':
                task_type = TaskInstanceType.AGENT
                assigned_user_id = None
                assigned_agent_id = processor_info.get('processor_id')
            else:
                task_type = TaskInstanceType.HUMAN
                assigned_user_id = executor_id
                assigned_agent_id = None
            
            # 🔧 使用TaskInstanceCreate模型而不是dict
            from ..models.instance import TaskInstanceCreate
            
            task_data = TaskInstanceCreate(
                node_instance_id=node_instance_id,
                workflow_instance_id=workflow_instance_id,
                processor_id=processor_info['processor_id'],
                task_title=f"{node_data['name']} - 动态任务",
                task_description=node_data.get('task_description') or f"{node_data['name']}节点的执行任务",
                task_type=task_type,
                assigned_user_id=assigned_user_id,
                assigned_agent_id=assigned_agent_id
            )
            
            logger.debug(f"[动态任务] 创建TaskInstanceCreate对象: {task_data.task_title}")
            
            # 创建任务实例
            result = await self.task_instance_repo.create_task(task_data)
            if result:
                logger.info(f"✅ [动态任务] 成功创建任务: {task_data.task_title}")
                
                # 🔧 Critical Fix: 创建任务后立即传递节点实例附件
                try:
                    from ..services.file_association_service import FileAssociationService, AttachmentType
                    file_service = FileAssociationService()
                    
                    task_instance_id = result.get('task_instance_id')
                    if task_instance_id:
                        # 获取节点实例的所有附件
                        node_files = await file_service.get_node_instance_files(node_instance_id)
                        
                        # 将每个附件关联到任务实例
                        for file_info in node_files:
                            file_id = file_info['file_id']
                            attachment_type_str = file_info.get('attachment_type', 'input')
                            
                            # 转换字符串为AttachmentType枚举
                            try:
                                attachment_type = AttachmentType(attachment_type_str.upper())
                            except ValueError:
                                attachment_type = AttachmentType.INPUT
                            
                            await file_service.associate_task_instance_file(
                                task_instance_id=uuid.UUID(task_instance_id),
                                file_id=uuid.UUID(file_id),
                                uploaded_by=uuid.UUID(assigned_user_id) if assigned_user_id else uuid.UUID('00000000-0000-0000-0000-000000000000'),
                                attachment_type=attachment_type
                            )
                        
                        logger.info(f"📎 [附件传递] 任务 {task_instance_id} 继承了 {len(node_files)} 个节点附件")
                    
                except Exception as e:
                    logger.warning(f"⚠️ 任务附件传递失败: {e}")
                
                if task_type == TaskInstanceType.HUMAN:
                    logger.info(f"🎯 [动态任务] 人工任务已分配给用户: {assigned_user_id}")
                return result
            else:
                logger.error(f"❌ [动态任务] 任务创建失败")
                return None
                
        except Exception as e:
            logger.error(f"为节点创建任务失败: {e}")
            return None

    async def _propagate_task_cancellation(self, task_id: uuid.UUID, task_data: Dict[str, Any], cancel_reason: Optional[str] = None):
        """
        简洁的状态向上传播：任务取消 -> 节点取消 -> 工作流检查
        Linus式设计：没有特殊情况，就是简单的状态更新链
        """
        try:
            logger.info(f"🔄 [状态传播] 开始传播任务取消状态: {task_id}")

            # 1. 获取节点实例ID
            node_instance_id = task_data.get('node_instance_id')
            workflow_instance_id = task_data.get('workflow_instance_id')

            if not node_instance_id or not workflow_instance_id:
                logger.warning(f"⚠️ [状态传播] 缺少必要信息，跳过传播")
                logger.warning(f"   - node_instance_id: {node_instance_id}")
                logger.warning(f"   - workflow_instance_id: {workflow_instance_id}")
                return

            # 2. 标记节点实例为取消状态
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            from ..models.instance import NodeInstanceUpdate, NodeInstanceStatus

            node_repo = NodeInstanceRepository()
            node_update = NodeInstanceUpdate(
                status=NodeInstanceStatus.CANCELLED,
                error_message=cancel_reason or "任务被取消",
                completed_at=now_utc()
            )

            node_result = await node_repo.update_node_instance(node_instance_id, node_update)
            if node_result:
                logger.info(f"✅ [状态传播] 节点实例已标记为取消: {node_instance_id}")

                # 3. 通知执行上下文管理器
                try:
                    await self.context_manager.mark_node_failed(
                        workflow_instance_id,
                        task_data.get('node_id'),  # 需要node_id，不是node_instance_id
                        node_instance_id,
                        {"message": cancel_reason or "任务被取消", "type": "user_cancelled"}
                    )
                    logger.info(f"✅ [状态传播] 上下文管理器已更新节点状态")
                except Exception as ctx_error:
                    logger.warning(f"⚠️ [状态传播] 更新上下文失败: {ctx_error}")

                # 4. 检查是否需要取消整个工作流
                await self._check_and_update_workflow_status(workflow_instance_id)

            else:
                logger.error(f"❌ [状态传播] 更新节点状态失败: {node_instance_id}")

        except Exception as e:
            logger.error(f"❌ [状态传播] 传播任务取消状态失败: {e}")
            import traceback
            logger.error(f"   - 堆栈: {traceback.format_exc()}")

    async def _check_and_update_workflow_status(self, workflow_instance_id: uuid.UUID):
        """
        🔧 Linus式修复：简化工作流状态检查逻辑

        消除特殊情况：只有一个简单的规则
        - 没有运行中节点 = 工作流结束
        - 根据完成/失败/取消节点决定最终状态
        """
        try:
            logger.info(f"🔍 [工作流状态检查] 检查工作流: {workflow_instance_id}")

            # 获取所有节点实例状态
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_repo = NodeInstanceRepository()

            nodes = await node_repo.get_instances_by_workflow_instance(workflow_instance_id)
            if not nodes:
                logger.warning(f"⚠️ 未找到节点实例，跳过状态检查")
                return

            # 统计节点状态 - 简单分类
            total_nodes = len(nodes)
            completed_nodes = 0
            failed_nodes = 0
            cancelled_nodes = 0
            running_nodes = 0

            for node in nodes:
                status = node.get('status', '').lower()
                if status == 'completed':
                    completed_nodes += 1
                elif status == 'failed':
                    failed_nodes += 1
                elif status == 'cancelled':
                    cancelled_nodes += 1
                elif status in ['running', 'pending', 'waiting']:
                    running_nodes += 1

            logger.info(f"📊 节点状态: 总={total_nodes}, 完成={completed_nodes}, 失败={failed_nodes}, 取消={cancelled_nodes}, 运行中={running_nodes}")

            # 🔧 Linus原则：简单的判断逻辑，无特殊情况
            if running_nodes == 0:
                # 没有运行中的节点，工作流结束
                from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
                from ..models.instance import WorkflowInstanceUpdate, WorkflowInstanceStatus

                workflow_repo = WorkflowInstanceRepository()

                # 决定最终状态：优先级 取消 > 失败 > 完成
                if cancelled_nodes > 0:
                    final_status = WorkflowInstanceStatus.CANCELLED
                    status_name = "已取消"
                elif failed_nodes > 0:
                    final_status = WorkflowInstanceStatus.FAILED
                    status_name = "已失败"
                else:
                    final_status = WorkflowInstanceStatus.COMPLETED
                    status_name = "已完成"

                from ..utils.helpers import now_utc
                workflow_update = WorkflowInstanceUpdate(
                    status=final_status,
                    completed_at=now_utc()
                )

                result = await workflow_repo.update_instance(workflow_instance_id, workflow_update)
                if result:
                    logger.info(f"✅ 工作流状态已更新: {status_name}")
                else:
                    logger.error(f"❌ 更新工作流状态失败")
            else:
                logger.info(f"ℹ️ 工作流仍在运行中 ({running_nodes} 个节点)")

        except Exception as e:
            logger.error(f"❌ 检查工作流状态失败: {e}")
            import traceback
            logger.error(f"   堆栈: {traceback.format_exc()}")


# 全局执行引擎实例
execution_engine = ExecutionEngine()