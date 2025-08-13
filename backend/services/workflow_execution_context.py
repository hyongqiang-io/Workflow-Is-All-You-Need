"""
工作流执行上下文管理器
统一管理单个工作流实例的执行上下文、状态和依赖关系
一个工作流实例对应一个上下文管理器实例
"""

import uuid
from datetime import datetime
from typing import Dict, List, Any, Set, Optional
import asyncio
import json
from loguru import logger

# 延迟导入避免循环依赖
from ..models.instance import WorkflowInstanceStatus, WorkflowInstanceUpdate


def _serialize_for_json(obj):
    """将对象序列化为JSON兼容格式"""
    if isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            serialized_key = str(key) if isinstance(key, uuid.UUID) else key
            serialized_value = _serialize_for_json(value)
            result[serialized_key] = serialized_value
        return result
    elif isinstance(obj, (list, tuple, set)):
        return [_serialize_for_json(item) for item in obj]
    else:
        return obj


class WorkflowExecutionContext:
    """工作流执行上下文管理器
    
    统一管理一个工作流实例的：
    - 执行上下文数据
    - 节点状态管理 
    - 依赖关系管理
    - 数据流管理
    """
    
    def __init__(self, workflow_instance_id: uuid.UUID):
        self.workflow_instance_id = workflow_instance_id
        
        # 执行上下文数据
        self.execution_context = {
            'global_data': {},
            'node_outputs': {},  # node_id -> output_data
            'execution_path': [],  # 已执行的节点路径
            'execution_start_time': datetime.utcnow().isoformat(),
            'current_executing_nodes': set(),
            'completed_nodes': set(),
            'failed_nodes': set(),
            'auto_save_counter': 0,
            'last_snapshot_time': datetime.utcnow().isoformat(),
            'persistence_enabled': True
        }
        
        # 节点依赖关系管理 - 使用node_instance_id作为key
        self.node_dependencies: Dict[uuid.UUID, Dict[str, Any]] = {}
        
        # 节点状态管理
        self.node_states: Dict[uuid.UUID, str] = {}  # node_instance_id -> state
        
        # 待触发的节点队列
        self.pending_triggers: Set[uuid.UUID] = set()
        
        # 异步锁管理
        self._context_lock = asyncio.Lock()
        
        # 回调函数注册
        self.completion_callbacks: List[callable] = []
        
        logger.debug(f"🏠 初始化工作流执行上下文: {workflow_instance_id}")
    
    async def initialize_context(self, restore_from_snapshot: bool = False):
        """初始化工作流上下文"""
        async with self._context_lock:
            if restore_from_snapshot:
                # TODO: 实现快照恢复
                pass
            
            # 获取开始节点信息
            start_node_info = await self._get_start_node_task_descriptions()
            self.execution_context['global_data']['start_node_descriptions'] = start_node_info
            
            logger.info(f"✅ 工作流上下文初始化完成: {self.workflow_instance_id}")
    
    async def register_node_dependencies(self, 
                                       node_instance_id: uuid.UUID,
                                       node_id: uuid.UUID,
                                       upstream_nodes: List[uuid.UUID]):
        """注册节点的依赖关系"""
        async with self._context_lock:
            self.node_dependencies[node_instance_id] = {
                'node_id': node_id,
                'workflow_instance_id': self.workflow_instance_id,
                'upstream_nodes': upstream_nodes,
                'completed_upstream': set(),
                'ready_to_execute': len(upstream_nodes) == 0,
                'dependency_count': len(upstream_nodes)
            }
            
            # 初始化节点状态
            self.node_states[node_instance_id] = 'PENDING'
            
            logger.debug(f"📋 注册节点依赖: {node_instance_id} -> {len(upstream_nodes)} 个上游节点")
    
    async def mark_node_executing(self, node_id: uuid.UUID, node_instance_id: uuid.UUID):
        """标记节点开始执行"""
        async with self._context_lock:
            self.node_states[node_instance_id] = 'EXECUTING'
            self.execution_context['current_executing_nodes'].add(node_id)
            
            logger.trace(f"⚡ 标记节点执行: {node_id}")
    
    async def mark_node_completed(self, node_id: uuid.UUID, node_instance_id: uuid.UUID, output_data: Dict[str, Any]):
        """标记节点完成"""
        async with self._context_lock:
            # 防重复处理 - 检查内存状态
            if node_id in self.execution_context['completed_nodes']:
                logger.warning(f"🔄 节点 {node_id} 已经在内存中标记为完成，跳过重复处理")
                return
            
            # 防重复处理 - 检查数据库状态
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_repo = NodeInstanceRepository()
            try:
                existing_node = await node_repo.get_instance_by_id(node_instance_id)
                if existing_node and existing_node.get('status') == 'completed':
                    logger.warning(f"🔄 节点实例 {node_instance_id} 在数据库中已经完成，同步内存状态")
                    # 同步内存状态
                    self.node_states[node_instance_id] = 'COMPLETED'
                    self.execution_context['completed_nodes'].add(node_id)
                    self.execution_context['node_outputs'][node_id] = output_data
                    self.execution_context['current_executing_nodes'].discard(node_id)
                    return
            except Exception as e:
                logger.warning(f"⚠️ 检查节点数据库状态时出错: {e}")
            
            # 更新状态
            self.node_states[node_instance_id] = 'COMPLETED'
            self.execution_context['completed_nodes'].add(node_id)
            self.execution_context['node_outputs'][node_id] = output_data
            self.execution_context['execution_path'].append(str(node_id))
            
            # 从执行中移除
            self.execution_context['current_executing_nodes'].discard(node_id)
            
            logger.info(f"🎉 节点完成: {node_id}")
            
            # 更新数据库状态
            await self._update_database_node_state(node_instance_id, 'COMPLETED', output_data)
        
        # 检查并触发下游节点（在锁外执行避免死锁）
        triggered_nodes = await self._check_and_trigger_downstream_nodes(node_id)
        
        # 通知回调
        if triggered_nodes:
            await self._notify_completion_callbacks(triggered_nodes)
        
        # 检查工作流完成
        await self._check_workflow_completion()
    
    async def mark_node_failed(self, node_id: uuid.UUID, node_instance_id: uuid.UUID, error_info: Dict[str, Any]):
        """标记节点失败"""
        async with self._context_lock:
            self.node_states[node_instance_id] = 'FAILED'
            self.execution_context['failed_nodes'].add(node_id)
            self.execution_context['current_executing_nodes'].discard(node_id)
            
            logger.error(f"❌ 节点失败: {node_id} - {error_info}")
            
            # 更新数据库状态
            await self._update_database_node_state(node_instance_id, 'FAILED', None, error_info)
    
    def is_node_ready_to_execute(self, node_instance_id: uuid.UUID) -> bool:
        """检查节点是否准备好执行"""
        deps = self.node_dependencies.get(node_instance_id)
        if not deps:
            return False
        
        return deps.get('ready_to_execute', False)
    
    def get_node_state(self, node_instance_id: uuid.UUID) -> str:
        """获取节点状态"""
        return self.node_states.get(node_instance_id, 'UNKNOWN')
    
    async def get_node_execution_context(self, node_instance_id: uuid.UUID) -> Dict[str, Any]:
        """获取节点的执行上下文数据"""
        async with self._context_lock:
            # 获取全局上下文数据
            context_data = {
                'workflow': {
                    'workflow_instance_id': str(self.workflow_instance_id),
                    'execution_start_time': self.execution_context.get('execution_start_time'),
                    'execution_path': self.execution_context.get('execution_path', [])
                },
                'global_data': self.execution_context.get('global_data', {}),
                'upstream_outputs': [],
                'current_node': {}
            }
            
            # 获取节点依赖信息
            deps = self.node_dependencies.get(node_instance_id)
            if deps:
                upstream_nodes = deps.get('upstream_nodes', [])
                
                # 收集上游节点的输出数据
                for upstream_node_id in upstream_nodes:
                    if upstream_node_id in self.execution_context['node_outputs']:
                        output_data = self.execution_context['node_outputs'][upstream_node_id]
                        node_name = await self._get_node_name_by_id(upstream_node_id)
                        
                        context_data['upstream_outputs'].append({
                            'node_id': str(upstream_node_id),
                            'node_name': node_name or f'节点_{str(upstream_node_id)[:8]}',
                            'output_data': output_data,
                            'status': 'completed'
                        })
                
                # 当前节点信息
                current_node_name = await self._get_node_name_by_id(deps.get('node_id'))
                context_data['current_node'] = {
                    'node_instance_id': str(node_instance_id),
                    'node_id': str(deps.get('node_id')),
                    'node_name': current_node_name,
                    'status': self.get_node_state(node_instance_id)
                }
            
            return context_data
    
    async def _check_and_trigger_downstream_nodes(self, completed_node_id: uuid.UUID) -> List[uuid.UUID]:
        """检查并触发下游节点"""
        triggered_nodes = []
        
        for node_instance_id, deps in self.node_dependencies.items():
            if completed_node_id in deps['upstream_nodes']:
                # 标记上游节点完成
                deps['completed_upstream'].add(completed_node_id)
                
                # 检查是否所有上游都完成
                if len(deps['completed_upstream']) == len(deps['upstream_nodes']):
                    deps['ready_to_execute'] = True
                    self.pending_triggers.add(node_instance_id)
                    triggered_nodes.append(node_instance_id)
                    
                    logger.debug(f"🚀 触发下游节点: {node_instance_id}")
        
        return triggered_nodes
    
    async def get_ready_nodes(self) -> List[uuid.UUID]:
        """获取准备执行的节点"""
        ready_nodes = list(self.pending_triggers)
        self.pending_triggers.clear()
        return ready_nodes
    
    async def build_node_context(self, node_instance_id: uuid.UUID) -> Dict[str, Any]:
        """构建节点执行上下文"""
        deps = self.node_dependencies.get(node_instance_id, {})
        upstream_nodes = deps.get('upstream_nodes', [])
        
        # 收集上游输出
        upstream_context = {}
        for upstream_node_id in upstream_nodes:
            if upstream_node_id in self.execution_context['node_outputs']:
                node_name = await self._get_node_name_by_id(upstream_node_id)
                upstream_context[node_name or str(upstream_node_id)] = {
                    'node_id': str(upstream_node_id),
                    'output_data': self.execution_context['node_outputs'][upstream_node_id],
                    'status': 'completed'
                }
        
        return {
            'node_instance_id': str(node_instance_id),
            'upstream_outputs': upstream_context,
            'workflow_context': {
                'workflow_instance_id': str(self.workflow_instance_id),
                'execution_start_time': self.execution_context['execution_start_time'],
                'execution_path': self.execution_context['execution_path'],
                'global_data': self.execution_context['global_data']
            },
            'context_built_at': datetime.utcnow().isoformat()
        }
    
    async def get_workflow_status(self) -> Dict[str, Any]:
        """获取工作流状态"""
        total_nodes = len(self.node_dependencies)
        completed_nodes = len(self.execution_context['completed_nodes'])
        failed_nodes = len(self.execution_context['failed_nodes'])
        executing_nodes = len(self.execution_context['current_executing_nodes'])
        
        if failed_nodes > 0:
            status = 'FAILED'
        elif completed_nodes == total_nodes and total_nodes > 0:
            status = 'COMPLETED'
        elif executing_nodes > 0 or (total_nodes - completed_nodes - failed_nodes) > 0:
            status = 'RUNNING'
        else:
            status = 'UNKNOWN'
        
        return {
            'status': status,
            'total_nodes': total_nodes,
            'completed_nodes': completed_nodes,
            'failed_nodes': failed_nodes,
            'executing_nodes': executing_nodes,
            'execution_path': self.execution_context['execution_path']
        }
    
    def register_completion_callback(self, callback: callable):
        """注册完成回调"""
        self.completion_callbacks.append(callback)
    
    async def _notify_completion_callbacks(self, triggered_nodes: List[uuid.UUID]):
        """通知回调函数"""
        for callback in self.completion_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self.workflow_instance_id, triggered_nodes)
                else:
                    callback(self.workflow_instance_id, triggered_nodes)
            except Exception as e:
                logger.error(f"回调函数执行失败: {e}")
    
    async def _check_workflow_completion(self):
        """检查工作流是否完成"""
        status_info = await self.get_workflow_status()
        if status_info['status'] in ['COMPLETED', 'FAILED']:
            logger.info(f"🏁 工作流 {self.workflow_instance_id} 执行完成: {status_info['status']}")
            # TODO: 更新数据库中的工作流状态
    
    async def _update_database_node_state(self, node_instance_id: uuid.UUID, 
                                        state: str, output_data: Optional[Dict[str, Any]] = None,
                                        error_info: Optional[Dict[str, Any]] = None):
        """更新数据库中的节点状态"""
        try:
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            from ..models.instance import NodeInstanceUpdate, NodeInstanceStatus
            
            node_repo = NodeInstanceRepository()
            
            # 先检查节点实例是否存在
            existing_node = await node_repo.get_instance_by_id(node_instance_id)
            if not existing_node:
                logger.warning(f"⚠️ 节点实例不存在，跳过状态更新: {node_instance_id}")
                return
            
            status_mapping = {
                'COMPLETED': NodeInstanceStatus.COMPLETED,
                'FAILED': NodeInstanceStatus.FAILED,
                'EXECUTING': NodeInstanceStatus.RUNNING,
                'PENDING': NodeInstanceStatus.PENDING
            }
            
            db_status = status_mapping.get(state, NodeInstanceStatus.PENDING)
            
            # 准备输出数据 - 需要转换为JSON字符串
            import json
            output_data_str = None
            if output_data:
                output_data_str = json.dumps(output_data, ensure_ascii=False)
            
            update_data = NodeInstanceUpdate(
                status=db_status,
                output_data=output_data_str,
                error_message=error_info.get('message') if error_info else None
            )
            
            result = await node_repo.update_node_instance(node_instance_id, update_data)
            if result:
                logger.debug(f"✅ 数据库状态更新成功: {node_instance_id} -> {state}")
            else:
                logger.warning(f"⚠️ 数据库状态更新返回空结果: {node_instance_id} -> {state}")
            
        except Exception as e:
            logger.error(f"❌ 数据库状态更新失败: {node_instance_id} -> {state}: {e}")
            # 不抛出异常，让流程继续
    
    async def _get_start_node_task_descriptions(self) -> Dict[str, Any]:
        """获取开始节点任务描述"""
        try:
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            
            node_instance_repo = NodeInstanceRepository()
            
            query = """
                SELECT ni.node_instance_id, ni.node_id, n.name as node_name,
                       n.task_description, ni.task_description as instance_task_description
                FROM node_instance ni
                JOIN node n ON ni.node_id = n.node_id
                WHERE ni.workflow_instance_id = $1
                AND LOWER(n.type) = 'start'
                AND ni.is_deleted = FALSE
                AND n.is_deleted = FALSE
                ORDER BY ni.created_at ASC
            """
            
            start_nodes = await node_instance_repo.db.fetch_all(query, self.workflow_instance_id)
            
            start_node_info = {}
            for node in start_nodes:
                node_id = str(node['node_id'])
                task_description = (
                    node.get('instance_task_description') or 
                    node.get('task_description') or 
                    f"开始节点 {node.get('node_name', '未命名')} 的任务"
                )
                
                start_node_info[node_id] = {
                    'node_instance_id': str(node['node_instance_id']),
                    'node_name': node.get('node_name', '未命名'),
                    'task_description': task_description
                }
            
            return start_node_info
            
        except Exception as e:
            logger.error(f"获取开始节点任务描述失败: {e}")
            return {}
    
    async def _get_node_name_by_id(self, node_id: uuid.UUID) -> str:
        """根据node_id获取节点名称"""
        try:
            from ..repositories.node.node_repository import NodeRepository
            node_repo = NodeRepository()
            
            query = "SELECT name FROM node WHERE node_id = $1"
            result = await node_repo.db.fetch_one(query, node_id)
            return result['name'] if result else None
        except Exception as e:
            logger.error(f"获取节点名称失败: {e}")
            return None
    
    def cleanup(self):
        """清理上下文资源"""
        logger.info(f"🧹 清理工作流上下文: {self.workflow_instance_id}")
        self.execution_context.clear()
        self.node_dependencies.clear()
        self.node_states.clear()
        self.pending_triggers.clear()
        self.completion_callbacks.clear()


# 工作流执行上下文管理器工厂
class WorkflowExecutionContextManager:
    """工作流执行上下文管理器工厂
    
    管理多个工作流实例的上下文管理器
    一个工作流实例对应一个WorkflowExecutionContext
    """
    
    def __init__(self):
        self.contexts: Dict[uuid.UUID, WorkflowExecutionContext] = {}
        self._contexts_lock = asyncio.Lock()
    
    async def get_or_create_context(self, workflow_instance_id: uuid.UUID) -> WorkflowExecutionContext:
        """获取或创建工作流执行上下文"""
        async with self._contexts_lock:
            if workflow_instance_id not in self.contexts:
                self.contexts[workflow_instance_id] = WorkflowExecutionContext(workflow_instance_id)
                logger.info(f"🆕 创建新的工作流执行上下文: {workflow_instance_id}")
            
            return self.contexts[workflow_instance_id]
    
    async def get_context(self, workflow_instance_id: uuid.UUID) -> Optional[WorkflowExecutionContext]:
        """获取工作流执行上下文"""
        return self.contexts.get(workflow_instance_id)
    
    async def remove_context(self, workflow_instance_id: uuid.UUID):
        """移除工作流执行上下文"""
        async with self._contexts_lock:
            if workflow_instance_id in self.contexts:
                context = self.contexts[workflow_instance_id]
                context.cleanup()
                del self.contexts[workflow_instance_id]
                logger.info(f"🗑️ 移除工作流执行上下文: {workflow_instance_id}")
    
    def get_all_contexts(self) -> List[WorkflowExecutionContext]:
        """获取所有上下文"""
        return list(self.contexts.values())
    
    def register_completion_callback(self, callback):
        """注册完成回调函数到所有现有和未来的上下文"""
        # 将回调添加到所有现有上下文
        for context in self.contexts.values():
            if callback not in context.completion_callbacks:
                context.completion_callbacks.append(callback)
        
        # 保存回调函数，以便为新创建的上下文自动注册
        if not hasattr(self, '_global_callbacks'):
            self._global_callbacks = []
        if callback not in self._global_callbacks:
            self._global_callbacks.append(callback)
            logger.debug(f"📝 注册全局完成回调函数: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}")
    
    async def get_or_create_context(self, workflow_instance_id: uuid.UUID) -> WorkflowExecutionContext:
        """获取或创建工作流执行上下文（改进版本，自动注册全局回调）"""
        async with self._contexts_lock:
            if workflow_instance_id not in self.contexts:
                context = WorkflowExecutionContext(workflow_instance_id)
                
                # 为新上下文注册所有全局回调
                if hasattr(self, '_global_callbacks'):
                    for callback in self._global_callbacks:
                        if callback not in context.completion_callbacks:
                            context.completion_callbacks.append(callback)
                
                self.contexts[workflow_instance_id] = context
                logger.info(f"🆕 创建新的工作流执行上下文: {workflow_instance_id}")
            
            return self.contexts[workflow_instance_id]
    
    async def initialize_workflow_context(self, workflow_instance_id: uuid.UUID):
        """初始化工作流上下文"""
        context = await self.get_or_create_context(workflow_instance_id)
        await context.initialize_context()
    
    async def get_task_context_data(self, workflow_instance_id: uuid.UUID, node_instance_id: uuid.UUID) -> Dict[str, Any]:
        """获取任务的上下文数据"""
        context = await self.get_context(workflow_instance_id)
        if context:
            return await context.get_node_execution_context(node_instance_id)
        return {}
    
    async def mark_node_completed(self, workflow_instance_id: uuid.UUID, node_id: uuid.UUID, 
                                node_instance_id: uuid.UUID, output_data: Dict[str, Any]):
        """标记节点完成"""
        context = await self.get_context(workflow_instance_id)
        if context:
            await context.mark_node_completed(node_id, node_instance_id, output_data)
    
    async def mark_node_failed(self, workflow_instance_id: uuid.UUID, node_id: uuid.UUID, 
                             node_instance_id: uuid.UUID, error_info: Dict[str, Any]):
        """标记节点失败"""
        context = await self.get_context(workflow_instance_id)
        if context:
            await context.mark_node_failed(node_id, node_instance_id, error_info)
    
    @property
    def node_completion_status(self) -> Dict[uuid.UUID, str]:
        """获取所有节点的完成状态（兼容性属性）"""
        if not hasattr(self, '_node_completion_status'):
            self._node_completion_status = {}
        return self._node_completion_status
    
    async def register_node_dependencies(self, workflow_instance_id: uuid.UUID, 
                                       node_instance_id: uuid.UUID, node_id: uuid.UUID, 
                                       upstream_nodes: List[uuid.UUID]):
        """注册节点依赖关系"""
        context = await self.get_or_create_context(workflow_instance_id)
        await context.register_node_dependencies(node_instance_id, node_id, upstream_nodes)
    
    def print_dependency_summary(self, workflow_instance_id: uuid.UUID):
        """打印依赖关系摘要"""
        context = self.contexts.get(workflow_instance_id)
        if context:
            logger.info(f"📊 工作流 {workflow_instance_id} 依赖关系摘要:")
            logger.info(f"   - 节点总数: {len(context.node_dependencies)}")
            logger.info(f"   - 已完成节点: {len(context.execution_context.get('completed_nodes', set()))}")
            logger.info(f"   - 执行中节点: {len(context.execution_context.get('current_executing_nodes', set()))}")
            logger.info(f"   - 失败节点: {len(context.execution_context.get('failed_nodes', set()))}")
        else:
            logger.warning(f"⚠️ 未找到工作流 {workflow_instance_id} 的上下文信息")
    
    def get_node_dependency_info(self, node_instance_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取节点依赖信息"""
        for workflow_context in self.contexts.values():
            if node_instance_id in workflow_context.node_dependencies:
                return workflow_context.node_dependencies[node_instance_id]
        return None
    
    def is_node_ready_to_execute(self, node_instance_id: uuid.UUID) -> bool:
        """检查节点是否准备好执行"""
        for workflow_context in self.contexts.values():
            if node_instance_id in workflow_context.node_dependencies:
                return workflow_context.is_node_ready_to_execute(node_instance_id)
        return False
    
    async def mark_node_executing(self, workflow_instance_id: uuid.UUID, node_id: uuid.UUID, 
                                 node_instance_id: uuid.UUID):
        """标记节点开始执行"""
        context = await self.get_context(workflow_instance_id)
        if context:
            await context.mark_node_executing(node_id, node_instance_id)
    
    async def cleanup_workflow_context(self, workflow_instance_id: uuid.UUID):
        """清理工作流上下文"""
        await self.remove_context(workflow_instance_id)
    
    async def get_node_upstream_context(self, workflow_instance_id: uuid.UUID, 
                                       node_instance_id: uuid.UUID) -> Dict[str, Any]:
        """获取节点上游上下文数据"""
        context = await self.get_context(workflow_instance_id)
        if context:
            return await context.get_node_execution_context(node_instance_id)
        return {}
    
    async def ensure_context_lifecycle_consistency(self, workflow_instance_id: uuid.UUID):
        """确保上下文生命周期一致性"""
        # 确保工作流上下文存在
        await self.get_or_create_context(workflow_instance_id)


# 全局上下文管理器实例
_global_context_manager: Optional[WorkflowExecutionContextManager] = None

def get_context_manager() -> WorkflowExecutionContextManager:
    """获取全局上下文管理器"""
    global _global_context_manager
    if _global_context_manager is None:
        _global_context_manager = WorkflowExecutionContextManager()
        logger.debug("🌍 初始化全局工作流执行上下文管理器")
    return _global_context_manager