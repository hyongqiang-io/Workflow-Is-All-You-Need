"""
工作流实例上下文管理器
为单个工作流实例提供独立的执行上下文和状态管理
"""

import uuid
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Set, Optional, Callable
from threading import Lock, RLock
from loguru import logger


class WorkflowInstanceContext:
    """单个工作流实例的上下文管理器"""
    
    def __init__(self, workflow_instance_id: uuid.UUID, workflow_base_id: uuid.UUID):
        self.workflow_instance_id = workflow_instance_id
        self.workflow_base_id = workflow_base_id
        
        # 执行状态数据
        self.global_data: Dict[str, Any] = {}
        self.node_outputs: Dict[uuid.UUID, Any] = {}  # node_base_id -> output_data
        self.execution_path: List[uuid.UUID] = []  # 已执行的节点路径
        self.execution_start_time = datetime.utcnow()
        self.execution_end_time: Optional[datetime] = None
        
        # 节点状态集合
        self.current_executing_nodes: Set[uuid.UUID] = set()
        self.completed_nodes: Set[uuid.UUID] = set()
        self.failed_nodes: Set[uuid.UUID] = set()
        self.pending_nodes: Set[uuid.UUID] = set()
        
        # 节点依赖关系管理
        self.node_dependencies: Dict[uuid.UUID, Dict[str, Any]] = {}  # node_instance_id -> dependency_info
        self.node_completion_status: Dict[uuid.UUID, str] = {}  # node_instance_id -> status
        
        # 待触发的节点队列
        self.pending_triggers: Set[uuid.UUID] = set()
        
        # 线程安全锁
        self._lock = RLock()  # 可重入锁，支持同一线程多次获取
        self._state_lock = Lock()  # 状态更新专用锁
        
        # 回调函数（实例级别）
        self.completion_callbacks: List[Callable] = []
        
        # 统计信息
        self.stats = {
            'nodes_created': 0,
            'nodes_executed': 0,
            'nodes_completed': 0,
            'nodes_failed': 0,
            'total_execution_time': 0,
            'created_at': datetime.utcnow()
        }
        
        logger.info(f"Initialized workflow instance context: {workflow_instance_id}")
    
    async def register_node_dependencies(self, 
                                       node_instance_id: uuid.UUID,
                                       node_base_id: uuid.UUID,
                                       upstream_nodes: List[uuid.UUID]) -> bool:
        """注册节点的依赖关系（线程安全）"""
        with self._lock:
            try:
                self.node_dependencies[node_instance_id] = {
                    'node_base_id': node_base_id,
                    'upstream_nodes': upstream_nodes,
                    'completed_upstream': set(),
                    'ready_to_execute': len(upstream_nodes) == 0,  # START节点无依赖
                    'dependency_count': len(upstream_nodes),
                    'registered_at': datetime.utcnow()
                }
                
                # 初始化节点状态
                self.node_completion_status[node_instance_id] = 'PENDING'
                self.pending_nodes.add(node_base_id)
                
                # 更新统计
                self.stats['nodes_created'] += 1
                
                logger.debug(f"Registered dependencies for node {node_instance_id}: {len(upstream_nodes)} upstream nodes")
                return True
                
            except Exception as e:
                logger.error(f"Failed to register node dependencies: {e}")
                return False
    
    async def mark_node_executing(self, 
                                node_base_id: uuid.UUID, 
                                node_instance_id: uuid.UUID) -> bool:
        """标记节点开始执行（线程安全）"""
        with self._state_lock:
            try:
                # 状态转换：PENDING -> EXECUTING
                if node_base_id in self.pending_nodes:
                    self.pending_nodes.remove(node_base_id)
                
                self.current_executing_nodes.add(node_base_id)
                self.node_completion_status[node_instance_id] = 'EXECUTING'
                
                # 更新统计
                self.stats['nodes_executed'] += 1
                
                logger.info(f"Node {node_base_id} started executing in workflow {self.workflow_instance_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to mark node as executing: {e}")
                return False
    
    async def mark_node_completed(self, 
                                node_base_id: uuid.UUID, 
                                node_instance_id: uuid.UUID,
                                output_data: Dict[str, Any]) -> List[uuid.UUID]:
        """标记节点完成并返回触发的下游节点（线程安全）"""
        with self._lock:
            try:
                # 状态转换：EXECUTING -> COMPLETED
                if node_base_id in self.current_executing_nodes:
                    self.current_executing_nodes.remove(node_base_id)
                
                self.completed_nodes.add(node_base_id)
                self.node_outputs[node_base_id] = output_data
                self.execution_path.append(node_base_id)
                self.node_completion_status[node_instance_id] = 'COMPLETED'
                
                # 更新统计
                self.stats['nodes_completed'] += 1
                
                logger.info(f"Node {node_base_id} completed in workflow {self.workflow_instance_id}")
                
                # 检查并触发下游节点
                triggered_nodes = await self._check_and_trigger_downstream_nodes(node_base_id)
                
                # 检查工作流是否完成
                await self._check_workflow_completion()
                
                return triggered_nodes
                
            except Exception as e:
                logger.error(f"Failed to mark node as completed: {e}")
                return []
    
    async def mark_node_failed(self,
                             node_base_id: uuid.UUID,
                             node_instance_id: uuid.UUID,
                             error_info: Dict[str, Any]) -> bool:
        """标记节点失败（线程安全）"""
        with self._state_lock:
            try:
                # 状态转换：EXECUTING -> FAILED
                if node_base_id in self.current_executing_nodes:
                    self.current_executing_nodes.remove(node_base_id)
                
                self.failed_nodes.add(node_base_id)
                self.node_completion_status[node_instance_id] = 'FAILED'
                
                # 更新统计
                self.stats['nodes_failed'] += 1
                
                logger.error(f"Node {node_base_id} failed in workflow {self.workflow_instance_id}: {error_info}")
                
                # 检查工作流是否应该终止
                await self._check_workflow_failure()
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to mark node as failed: {e}")
                return False
    
    async def _check_and_trigger_downstream_nodes(self, completed_node_id: uuid.UUID) -> List[uuid.UUID]:
        """检查并触发下游节点（内部方法，已在锁内调用）"""
        triggered_nodes = []
        
        # 遍历所有节点依赖，找到以当前节点为上游的节点
        for node_instance_id, deps in self.node_dependencies.items():
            if completed_node_id in deps['upstream_nodes']:
                # 标记该上游节点已完成
                deps['completed_upstream'].add(completed_node_id)
                
                # 检查是否所有上游节点都已完成
                if len(deps['completed_upstream']) == len(deps['upstream_nodes']):
                    deps['ready_to_execute'] = True
                    
                    # 添加到待触发队列
                    self.pending_triggers.add(node_instance_id)
                    triggered_nodes.append(node_instance_id)
                    
                    logger.info(f"Node {deps['node_base_id']} ready to execute - all upstream completed")
        
        # 通知回调函数
        if triggered_nodes:
            await self._notify_completion_callbacks(triggered_nodes)
        
        return triggered_nodes
    
    async def _check_workflow_completion(self) -> bool:
        """检查工作流是否完成（内部方法）"""
        total_nodes = len(self.node_dependencies)
        completed_count = len(self.completed_nodes)
        failed_count = len(self.failed_nodes)
        
        if completed_count + failed_count == total_nodes:
            self.execution_end_time = datetime.utcnow()
            self.stats['total_execution_time'] = (
                self.execution_end_time - self.execution_start_time
            ).total_seconds()
            
            if failed_count == 0:
                logger.info(f"Workflow {self.workflow_instance_id} completed successfully")
            else:
                logger.warning(f"Workflow {self.workflow_instance_id} completed with {failed_count} failed nodes")
            
            return True
        
        return False
    
    async def _check_workflow_failure(self) -> bool:
        """检查工作流是否应该因为关键节点失败而终止（内部方法）"""
        # 这里可以实现更复杂的失败策略
        # 目前简单处理：如果有任何节点失败，记录但不终止整个工作流
        return False
    
    async def get_ready_nodes(self) -> List[uuid.UUID]:
        """获取准备执行的节点实例ID列表（线程安全）"""
        with self._lock:
            ready_nodes = list(self.pending_triggers)
            self.pending_triggers.clear()
            return ready_nodes
    
    async def get_node_upstream_context(self, node_instance_id: uuid.UUID) -> Dict[str, Any]:
        """获取节点的上游上下文数据（线程安全）"""
        with self._lock:
            if node_instance_id not in self.node_dependencies:
                return {
                    'immediate_upstream_results': {},
                    'upstream_node_count': 0,
                    'workflow_global': self._get_global_context()
                }
            
            deps = self.node_dependencies[node_instance_id]
            upstream_nodes = deps['upstream_nodes']
            
            # 收集上游节点的输出数据
            upstream_results = {}
            for upstream_node_id in upstream_nodes:
                if upstream_node_id in self.node_outputs:
                    upstream_results[str(upstream_node_id)] = self.node_outputs[upstream_node_id]
            
            return {
                'immediate_upstream_results': upstream_results,
                'upstream_node_count': len(upstream_nodes),
                'workflow_global': self._get_global_context()
            }
    
    def _get_global_context(self) -> Dict[str, Any]:
        """获取工作流全局上下文（内部方法）"""
        return {
            'execution_path': self.execution_path.copy(),
            'global_data': self.global_data.copy(),
            'execution_start_time': self.execution_start_time,
            'execution_end_time': self.execution_end_time,
            'stats': self.stats.copy()
        }
    
    async def get_workflow_status(self) -> Dict[str, Any]:
        """获取工作流整体状态（线程安全）"""
        with self._lock:
            total_nodes = len(self.node_dependencies)
            completed_nodes = len(self.completed_nodes)
            failed_nodes = len(self.failed_nodes)
            executing_nodes = len(self.current_executing_nodes)
            pending_nodes = len(self.pending_nodes)
            
            # 判断工作流整体状态
            if failed_nodes > 0 and (completed_nodes + failed_nodes == total_nodes):
                overall_status = 'FAILED'
            elif completed_nodes == total_nodes and failed_nodes == 0:
                overall_status = 'COMPLETED'
            elif executing_nodes > 0 or pending_nodes > 0:
                overall_status = 'RUNNING'
            else:
                overall_status = 'UNKNOWN'
            
            return {
                'workflow_instance_id': str(self.workflow_instance_id),
                'workflow_base_id': str(self.workflow_base_id),
                'status': overall_status,
                'total_nodes': total_nodes,
                'completed_nodes': completed_nodes,
                'failed_nodes': failed_nodes,
                'executing_nodes': executing_nodes,
                'pending_nodes': pending_nodes,
                'execution_path': self.execution_path.copy(),
                'execution_start_time': self.execution_start_time,
                'execution_end_time': self.execution_end_time,
                'stats': self.stats.copy()
            }
    
    def register_completion_callback(self, callback: Callable) -> bool:
        """注册节点完成回调函数（线程安全）"""
        with self._lock:
            try:
                if callback not in self.completion_callbacks:
                    self.completion_callbacks.append(callback)
                    return True
                return False
            except Exception as e:
                logger.error(f"Failed to register completion callback: {e}")
                return False
    
    async def _notify_completion_callbacks(self, triggered_nodes: List[uuid.UUID]):
        """通知回调函数有新节点准备执行（内部方法）"""
        for callback in self.completion_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self.workflow_instance_id, triggered_nodes)
                else:
                    callback(self.workflow_instance_id, triggered_nodes)
            except Exception as e:
                logger.error(f"Error in completion callback: {e}")
    
    def get_node_dependency_info(self, node_instance_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取节点的依赖信息（线程安全）"""
        with self._lock:
            return self.node_dependencies.get(node_instance_id)
    
    def is_node_ready_to_execute(self, node_instance_id: uuid.UUID) -> bool:
        """检查节点是否准备好执行（线程安全）"""
        with self._lock:
            deps = self.node_dependencies.get(node_instance_id)
            return deps is not None and deps.get('ready_to_execute', False)
    
    async def cleanup(self):
        """清理上下文资源"""
        with self._lock:
            try:
                # 清理回调函数
                self.completion_callbacks.clear()
                
                # 清理数据结构
                self.node_outputs.clear()
                self.node_dependencies.clear()
                self.node_completion_status.clear()
                self.pending_triggers.clear()
                
                # 清理状态集合
                self.current_executing_nodes.clear()
                self.completed_nodes.clear()
                self.failed_nodes.clear()
                self.pending_nodes.clear()
                
                # 清理全局数据
                self.global_data.clear()
                self.execution_path.clear()
                
                logger.info(f"Cleaned up workflow instance context: {self.workflow_instance_id}")
                
            except Exception as e:
                logger.error(f"Error during context cleanup: {e}")
    
    def __str__(self) -> str:
        return f"WorkflowInstanceContext(id={self.workflow_instance_id}, status={self.get_workflow_status()})"
    
    def __repr__(self) -> str:
        return self.__str__()