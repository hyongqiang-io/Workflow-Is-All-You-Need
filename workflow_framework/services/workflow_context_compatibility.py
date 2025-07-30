"""
工作流上下文管理兼容性接口
提供与现有 ExecutionEngine 的无缝集成和平滑迁移路径
"""

import uuid
import asyncio
from typing import Dict, List, Any, Set, Optional, Callable
from datetime import datetime
import logging

# 导入新架构组件
from .workflow_instance_context import WorkflowInstanceContext, WorkflowExecutionStatus, NodeExecutionStatus
from .workflow_instance_manager import WorkflowInstanceManager, get_instance_manager
from .node_dependency_tracker import NodeDependencyTracker, DependencyRule, DependencyType
from .resource_cleanup_manager import ResourceCleanupManager, get_cleanup_manager, ResourceType

logger = logging.getLogger(__name__)


class WorkflowContextCompatibilityAdapter:
    """工作流上下文兼容性适配器
    
    提供与现有 WorkflowContextManager 接口兼容的适配层
    内部使用新的架构组件，但保持对外接口不变
    """
    
    def __init__(self):
        # 使用新架构组件
        self.instance_manager = get_instance_manager()
        self.dependency_tracker = NodeDependencyTracker()
        self.cleanup_manager = get_cleanup_manager()
        
        # 兼容性映射
        self._workflow_contexts: Dict[uuid.UUID, uuid.UUID] = {}  # workflow_instance_id -> internal_id
        self._node_mappings: Dict[uuid.UUID, uuid.UUID] = {}     # old_node_instance_id -> new_node_instance_id
        
        # 回调函数注册（兼容旧接口）
        self._completion_callbacks: List[Callable] = []
        
        # 注册资源清理
        self.cleanup_manager.register_resource(
            self,
            ResourceType.CUSTOM,
            metadata={'component': 'compatibility_adapter'}
        )
        
        logger.info("WorkflowContextCompatibilityAdapter initialized")
    
    async def initialize_workflow_context(self, workflow_instance_id: uuid.UUID) -> None:
        """初始化工作流上下文（兼容接口）"""
        try:
            # 为兼容性，我们假设 workflow_base_id 与 workflow_instance_id 相同
            # 在实际使用中，应该传入正确的 workflow_base_id
            workflow_base_id = workflow_instance_id  # 临时处理
            
            # 创建新的工作流实例上下文
            context = self.instance_manager.create_instance(
                workflow_instance_id=workflow_instance_id,
                workflow_base_id=workflow_base_id,
                auto_start=False
            )
            
            # 建立映射关系
            self._workflow_contexts[workflow_instance_id] = workflow_instance_id
            
            # 注册完成回调适配
            context.register_completion_callback(self._adapt_completion_callback)
            
            logger.info(f"Initialized compatible workflow context for {workflow_instance_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize workflow context {workflow_instance_id}: {e}")
            raise
    
    async def register_node_dependencies(self, 
                                       node_instance_id: uuid.UUID,
                                       node_base_id: uuid.UUID,
                                       workflow_instance_id: uuid.UUID, 
                                       upstream_nodes: List[uuid.UUID]) -> None:
        """注册节点的一阶依赖关系（兼容接口）"""
        try:
            # 获取工作流实例上下文
            context = self.instance_manager.get_instance(workflow_instance_id)
            if not context:
                raise ValueError(f"Workflow context not found: {workflow_instance_id}")
            
            # 转换依赖规则格式
            dependency_rules = [
                DependencyRule(upstream_node_id=upstream_id, dependency_type=DependencyType.SEQUENCE)
                for upstream_id in upstream_nodes
            ]
            
            # 在上下文中注册节点
            context.register_node(
                node_instance_id=node_instance_id,
                node_base_id=node_base_id,
                upstream_nodes=set(upstream_nodes)
            )
            
            # 在依赖跟踪器中注册
            self.dependency_tracker.register_node_dependencies(
                node_instance_id=node_instance_id,
                node_base_id=node_base_id,
                workflow_instance_id=workflow_instance_id,
                dependency_rules=dependency_rules
            )
            
            # 建立节点映射
            self._node_mappings[node_instance_id] = node_instance_id
            
            logger.debug(f"Registered compatible node dependencies for {node_base_id}")
            
        except Exception as e:
            logger.error(f"Failed to register node dependencies: {e}")
            raise
    
    async def mark_node_completed(self, 
                                workflow_instance_id: uuid.UUID,
                                node_base_id: uuid.UUID, 
                                node_instance_id: uuid.UUID,
                                output_data: Dict[str, Any]) -> None:
        """标记节点完成并更新上下文（兼容接口）"""
        try:
            # 获取工作流实例上下文
            context = self.instance_manager.get_instance(workflow_instance_id)
            if not context:
                logger.error(f"Workflow context not found: {workflow_instance_id}")
                return
            
            # 标记节点完成
            context.mark_node_completed(node_instance_id, output_data)
            
            # 更新依赖跟踪器
            newly_ready_nodes = self.dependency_tracker.mark_node_completed(
                node_instance_id, node_base_id, workflow_instance_id
            )
            
            logger.info(f"Compatible node completion: {node_base_id}, {len(newly_ready_nodes)} nodes ready")
            
        except Exception as e:
            logger.error(f"Failed to mark node completed: {e}")
            raise
    
    async def mark_node_failed(self,
                             workflow_instance_id: uuid.UUID,
                             node_base_id: uuid.UUID,
                             node_instance_id: uuid.UUID,
                             error_info: Dict[str, Any]) -> None:
        """标记节点失败（兼容接口）"""
        try:
            # 获取工作流实例上下文
            context = self.instance_manager.get_instance(workflow_instance_id)
            if not context:
                logger.error(f"Workflow context not found: {workflow_instance_id}")
                return
            
            # 标记节点失败
            context.mark_node_failed(node_instance_id, error_info)
            
            # 更新依赖跟踪器
            affected_nodes = self.dependency_tracker.mark_node_failed(
                node_instance_id, node_base_id, workflow_instance_id
            )
            
            logger.error(f"Compatible node failure: {node_base_id}, {len(affected_nodes)} nodes affected")
            
        except Exception as e:
            logger.error(f"Failed to mark node failed: {e}")
            raise
    
    async def mark_node_executing(self,
                                workflow_instance_id: uuid.UUID,
                                node_base_id: uuid.UUID,
                                node_instance_id: uuid.UUID) -> None:
        """标记节点开始执行（兼容接口）"""
        try:
            # 获取工作流实例上下文
            context = self.instance_manager.get_instance(workflow_instance_id)
            if not context:
                logger.error(f"Workflow context not found: {workflow_instance_id}")
                return
            
            # 标记节点执行
            success = context.mark_node_executing(node_instance_id)
            if success:
                logger.info(f"Compatible node execution started: {node_base_id}")
            
        except Exception as e:
            logger.error(f"Failed to mark node executing: {e}")
            raise
    
    async def get_ready_nodes(self, workflow_instance_id: uuid.UUID) -> List[uuid.UUID]:
        """获取准备执行的节点实例ID列表（兼容接口）"""
        try:
            # 从上下文获取就绪节点
            context = self.instance_manager.get_instance(workflow_instance_id)
            if not context:
                return []
            
            ready_nodes = context.get_ready_nodes()
            
            # 也从依赖跟踪器获取，确保一致性
            tracker_ready_nodes = self.dependency_tracker.get_ready_nodes(workflow_instance_id)
            
            # 取交集确保一致性
            consistent_ready = list(set(ready_nodes) & set(tracker_ready_nodes))
            
            return consistent_ready
            
        except Exception as e:
            logger.error(f"Failed to get ready nodes: {e}")
            return []
    
    async def get_node_upstream_context(self, 
                                      workflow_instance_id: uuid.UUID,
                                      node_instance_id: uuid.UUID) -> Dict[str, Any]:
        """获取节点的一阶上游上下文数据（兼容接口）"""
        try:
            # 从上下文获取上游数据
            context = self.instance_manager.get_instance(workflow_instance_id)
            if not context:
                return {'error': 'Workflow context not found'}
            
            upstream_context = context.get_node_upstream_context(node_instance_id)
            
            # 增强依赖状态信息
            dependency_status = self.dependency_tracker.get_node_dependency_status(node_instance_id)
            if dependency_status:
                upstream_context['dependency_status'] = dependency_status
            
            return upstream_context
            
        except Exception as e:
            logger.error(f"Failed to get node upstream context: {e}")
            return {'error': str(e)}
    
    async def get_workflow_status(self, workflow_instance_id: uuid.UUID) -> Dict[str, Any]:
        """获取工作流整体状态（兼容接口）"""
        try:
            # 从上下文获取状态
            context = self.instance_manager.get_instance(workflow_instance_id)
            if not context:
                return {'status': 'NOT_FOUND'}
            
            status = context.get_workflow_status()
            
            # 增强依赖图信息
            dependency_graph = self.dependency_tracker.get_workflow_dependency_graph(workflow_instance_id)
            status['dependency_graph'] = dependency_graph
            
            # 添加管理器统计信息
            manager_stats = self.instance_manager.get_manager_stats()
            status['manager_stats'] = manager_stats
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get workflow status: {e}")
            return {'status': 'ERROR', 'error': str(e)}
    
    def register_completion_callback(self, callback: Callable) -> None:
        """注册节点完成回调函数（兼容接口）"""
        self._completion_callbacks.append(callback)
    
    async def cleanup_workflow_context(self, workflow_instance_id: uuid.UUID) -> None:
        """清理工作流上下文（兼容接口）"""
        try:
            # 清理依赖跟踪器
            self.dependency_tracker.cleanup_workflow(workflow_instance_id)
            
            # 清理实例管理器
            self.instance_manager.remove_instance(workflow_instance_id, force=True)
            
            # 清理映射关系
            if workflow_instance_id in self._workflow_contexts:
                del self._workflow_contexts[workflow_instance_id]
            
            # 清理节点映射
            to_remove = [k for k, v in self._node_mappings.items() 
                        if k.hex.startswith(str(workflow_instance_id)[:8])]  # 简单的关联清理
            for key in to_remove:
                del self._node_mappings[key]
            
            logger.info(f"Cleaned up compatible workflow context: {workflow_instance_id}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup workflow context: {e}")
            raise
    
    def get_node_dependency_info(self, node_instance_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取节点的依赖信息（兼容接口）"""
        try:
            # 从依赖跟踪器获取信息
            dependency_status = self.dependency_tracker.get_node_dependency_status(node_instance_id)
            
            if dependency_status:
                # 转换为兼容格式
                return {
                    'node_base_id': uuid.UUID(dependency_status['node_base_id']),
                    'workflow_instance_id': uuid.UUID(dependency_status['workflow_instance_id']),
                    'ready_to_execute': dependency_status['is_ready'],
                    'completion_rate': dependency_status['completion_rate'],
                    'required_dependencies': dependency_status['required_dependencies'],
                    'satisfied_dependencies': dependency_status['satisfied_dependencies']
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get node dependency info: {e}")
            return None
    
    def is_node_ready_to_execute(self, node_instance_id: uuid.UUID) -> bool:
        """检查节点是否准备好执行（兼容接口）"""
        try:
            dependency_status = self.dependency_tracker.get_node_dependency_status(node_instance_id)
            return dependency_status and dependency_status['is_ready']
            
        except Exception as e:
            logger.error(f"Failed to check node readiness: {e}")
            return False
    
    def _adapt_completion_callback(self, 
                                 workflow_instance_id: uuid.UUID,
                                 completed_node_id: uuid.UUID,
                                 newly_ready_nodes: List[uuid.UUID]) -> None:
        """适配完成回调到旧格式"""
        try:
            # 调用所有注册的兼容回调
            for callback in self._completion_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback(workflow_instance_id, newly_ready_nodes))
                    else:
                        callback(workflow_instance_id, newly_ready_nodes)
                except Exception as e:
                    logger.error(f"Error in compatibility callback: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to adapt completion callback: {e}")
    
    def get_compatibility_stats(self) -> Dict[str, Any]:
        """获取兼容性适配器统计信息"""
        return {
            'active_workflows': len(self._workflow_contexts),
            'node_mappings': len(self._node_mappings),
            'registered_callbacks': len(self._completion_callbacks),
            'instance_manager_stats': self.instance_manager.get_manager_stats(),
            'dependency_tracker_stats': self.dependency_tracker.get_tracker_stats(),
            'cleanup_manager_stats': self.cleanup_manager.get_resource_stats()
        }
    
    def shutdown(self) -> None:
        """关闭兼容性适配器"""
        logger.info("Shutting down WorkflowContextCompatibilityAdapter")
        
        try:
            # 清理所有工作流
            for workflow_id in list(self._workflow_contexts.keys()):
                asyncio.create_task(self.cleanup_workflow_context(workflow_id))
            
            # 关闭依赖跟踪器
            self.dependency_tracker.shutdown()
            
            # 清理数据结构
            self._workflow_contexts.clear()
            self._node_mappings.clear()
            self._completion_callbacks.clear()
            
        except Exception as e:
            logger.error(f"Error during compatibility adapter shutdown: {e}")
        
        logger.info("WorkflowContextCompatibilityAdapter shutdown completed")


# 创建全局兼容性适配器实例
_compatibility_adapter: Optional[WorkflowContextCompatibilityAdapter] = None


def get_compatible_context_manager() -> WorkflowContextCompatibilityAdapter:
    """获取兼容性上下文管理器
    
    这个函数可以用来替换现有代码中的 WorkflowContextManager 实例化
    """
    global _compatibility_adapter
    
    if _compatibility_adapter is None:
        _compatibility_adapter = WorkflowContextCompatibilityAdapter()
    
    return _compatibility_adapter


def shutdown_compatible_context_manager() -> None:
    """关闭兼容性上下文管理器"""
    global _compatibility_adapter
    
    if _compatibility_adapter is not None:
        _compatibility_adapter.shutdown()
        _compatibility_adapter = None