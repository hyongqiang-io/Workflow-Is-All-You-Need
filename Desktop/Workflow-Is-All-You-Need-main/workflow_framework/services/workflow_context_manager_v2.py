"""
工作流上下文管理器 V2
新架构的统一入口点，整合所有组件并提供增强功能
"""

import uuid
import asyncio
import threading
from typing import Dict, List, Any, Set, Optional, Callable, Union
from datetime import datetime, timedelta
from enum import Enum
import logging

# 导入新架构组件
from .workflow_instance_context import (
    WorkflowInstanceContext, 
    WorkflowExecutionStatus, 
    NodeExecutionStatus
)
from .workflow_instance_manager import (
    WorkflowInstanceManager, 
    get_instance_manager,
    shutdown_instance_manager
)
from .node_dependency_tracker import (
    NodeDependencyTracker, 
    DependencyRule, 
    DependencyType
)
from .resource_cleanup_manager import (
    ResourceCleanupManager, 
    get_cleanup_manager,
    shutdown_cleanup_manager,
    ResourceType
)
from .workflow_context_compatibility import (
    WorkflowContextCompatibilityAdapter,
    get_compatible_context_manager
)

logger = logging.getLogger(__name__)


class ManagerMode(Enum):
    """管理器模式枚举"""
    ENHANCED = "ENHANCED"        # 增强模式，使用所有新功能
    COMPATIBLE = "COMPATIBLE"    # 兼容模式，保持与旧接口兼容
    HYBRID = "HYBRID"           # 混合模式，同时支持新旧接口


class WorkflowContextManagerV2:
    """工作流上下文管理器 V2
    
    这是新架构的统一入口点，整合了：
    - WorkflowInstanceManager: 实例生命周期管理
    - NodeDependencyTracker: 线程安全依赖跟踪
    - ResourceCleanupManager: 自动资源清理
    - CompatibilityAdapter: 向后兼容支持
    
    提供高性能、可扩展、线程安全的工作流上下文管理
    """
    
    def __init__(self, 
                 mode: ManagerMode = ManagerMode.ENHANCED,
                 max_concurrent_workflows: int = 100,
                 enable_monitoring: bool = True,
                 enable_metrics: bool = True):
        
        self.mode = mode
        self.enable_monitoring = enable_monitoring
        self.enable_metrics = enable_metrics
        
        # 线程安全锁
        self._lock = threading.RLock()
        
        # 核心组件初始化
        self.instance_manager = get_instance_manager()
        self.dependency_tracker = NodeDependencyTracker()
        self.cleanup_manager = get_cleanup_manager()
        
        # 兼容性适配器（根据模式决定是否启用）
        self.compatibility_adapter = None
        if mode in [ManagerMode.COMPATIBLE, ManagerMode.HYBRID]:
            self.compatibility_adapter = get_compatible_context_manager()
        
        # 监控和指标组件
        if enable_monitoring:
            self._setup_monitoring()
        
        if enable_metrics:
            self._setup_metrics()
        
        # 回调函数注册
        self._workflow_created_callbacks: List[Callable] = []
        self._workflow_completed_callbacks: List[Callable] = []
        self._workflow_failed_callbacks: List[Callable] = []
        self._node_completed_callbacks: List[Callable] = []
        
        # 注册组件间的回调
        self._setup_component_callbacks()
        
        # 全局配置
        self._config = {
            'max_concurrent_workflows': max_concurrent_workflows,
            'auto_cleanup_enabled': True,
            'dependency_validation_enabled': True,
            'performance_monitoring_enabled': enable_monitoring,
            'metrics_collection_enabled': enable_metrics
        }
        
        # 统计信息
        self._global_stats = {
            'manager_start_time': datetime.utcnow(),
            'total_workflows_created': 0,
            'total_workflows_completed': 0,
            'total_workflows_failed': 0,
            'total_nodes_executed': 0,
            'average_workflow_duration': 0.0
        }
        
        # 性能指标
        self._performance_metrics = {
            'workflow_creation_time_ms': [],
            'node_completion_time_ms': [],
            'dependency_resolution_time_ms': [],
            'memory_usage_mb': []
        }
        
        logger.info(f"WorkflowContextManagerV2 initialized in {mode.value} mode")
    
    async def create_workflow_instance(self,
                                     workflow_instance_id: uuid.UUID,
                                     workflow_base_id: uuid.UUID,
                                     config: Optional[Dict[str, Any]] = None,
                                     auto_start: bool = True) -> WorkflowInstanceContext:
        """创建新的工作流实例（增强接口）"""
        start_time = datetime.utcnow()
        
        try:
            with self._lock:
                # 检查是否已存在
                existing_instance = self.instance_manager.get_instance(workflow_instance_id)
                if existing_instance:
                    logger.warning(f"Workflow instance {workflow_instance_id} already exists")
                    return existing_instance
                
                # 创建实例
                context = self.instance_manager.create_instance(
                    workflow_instance_id=workflow_instance_id,
                    workflow_base_id=workflow_base_id,
                    auto_start=auto_start
                )
                
                # 应用配置
                if config:
                    for key, value in config.items():
                        context.set_global_data(key, value)
                
                # 注册清理资源
                self.cleanup_manager.register_resource(
                    context,
                    ResourceType.WORKFLOW_CONTEXT,
                    metadata={
                        'workflow_instance_id': str(workflow_instance_id),
                        'workflow_base_id': str(workflow_base_id)
                    }
                )
                
                # 更新统计
                self._global_stats['total_workflows_created'] += 1
                
                # 记录性能指标
                creation_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                self._performance_metrics['workflow_creation_time_ms'].append(creation_time_ms)
                
                # 通知回调
                await self._notify_workflow_created_callbacks(context)
                
                logger.info(f"Created enhanced workflow instance {workflow_instance_id}")
                return context
                
        except Exception as e:
            logger.error(f"Failed to create workflow instance {workflow_instance_id}: {e}")
            raise
    
    async def register_node_with_dependencies(self,
                                            workflow_instance_id: uuid.UUID,
                                            node_instance_id: uuid.UUID,
                                            node_base_id: uuid.UUID,
                                            dependencies: List[Dict[str, Any]],
                                            node_config: Optional[Dict[str, Any]] = None) -> bool:
        """注册节点及其增强依赖关系"""
        try:
            # 获取工作流实例
            context = self.instance_manager.get_instance(workflow_instance_id)
            if not context:
                raise ValueError(f"Workflow instance {workflow_instance_id} not found")
            
            # 解析依赖规则
            dependency_rules = []
            upstream_node_ids = set()
            
            for dep in dependencies:
                upstream_id = dep.get('upstream_node_id')
                if upstream_id:
                    upstream_node_ids.add(upstream_id)
                    
                    rule = DependencyRule(
                        upstream_node_id=upstream_id,
                        dependency_type=DependencyType(dep.get('type', 'SEQUENCE')),
                        condition=dep.get('condition'),
                        timeout_seconds=dep.get('timeout_seconds'),
                        retry_count=dep.get('retry_count', 0)
                    )
                    dependency_rules.append(rule)
            
            # 在上下文中注册节点
            context.register_node(
                node_instance_id=node_instance_id,
                node_base_id=node_base_id,
                upstream_nodes=upstream_node_ids
            )
            
            # 在依赖跟踪器中注册
            self.dependency_tracker.register_node_dependencies(
                node_instance_id=node_instance_id,
                node_base_id=node_base_id,
                workflow_instance_id=workflow_instance_id,
                dependency_rules=dependency_rules
            )
            
            # 应用节点配置
            if node_config:
                for key, value in node_config.items():
                    context.set_global_data(f"node_{node_base_id}_{key}", value)
            
            logger.debug(f"Registered enhanced node {node_base_id} with {len(dependency_rules)} dependencies")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register node dependencies: {e}")
            return False
    
    async def execute_node(self,
                          workflow_instance_id: uuid.UUID,
                          node_instance_id: uuid.UUID,
                          execution_func: Callable,
                          input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行节点（增强接口）"""
        start_time = datetime.utcnow()
        
        try:
            # 获取上下文
            context = self.instance_manager.get_instance(workflow_instance_id)
            if not context:
                raise ValueError(f"Workflow instance {workflow_instance_id} not found")
            
            # 获取节点信息
            node_info = context.get_node_info(node_instance_id)
            if not node_info:
                raise ValueError(f"Node {node_instance_id} not found")
            
            # 标记开始执行
            success = context.mark_node_executing(node_instance_id)
            if not success:
                raise RuntimeError(f"Failed to start node execution: {node_instance_id}")
            
            try:
                # 获取上游上下文
                upstream_context = context.get_node_upstream_context(node_instance_id)
                
                # 准备执行参数
                execution_args = {
                    'node_instance_id': node_instance_id,
                    'input_data': input_data or {},
                    'upstream_context': upstream_context,
                    'workflow_context': context
                }
                
                # 执行节点逻辑
                if asyncio.iscoroutinefunction(execution_func):
                    result = await execution_func(**execution_args)
                else:
                    result = execution_func(**execution_args)
                
                # 标记完成
                context.mark_node_completed(node_instance_id, result)
                
                # 更新统计
                self._global_stats['total_nodes_executed'] += 1
                
                # 记录性能指标
                execution_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                self._performance_metrics['node_completion_time_ms'].append(execution_time_ms)
                
                logger.info(f"Successfully executed node {node_info.node_base_id}")
                return result
                
            except Exception as e:
                # 标记失败
                error_info = {'error': str(e), 'timestamp': datetime.utcnow().isoformat()}
                context.mark_node_failed(node_instance_id, error_info)
                raise
            
        except Exception as e:
            logger.error(f"Failed to execute node {node_instance_id}: {e}")
            raise
    
    async def get_workflow_status(self, workflow_instance_id: uuid.UUID) -> Dict[str, Any]:
        """获取增强的工作流状态信息"""
        try:
            # 获取基本状态
            context = self.instance_manager.get_instance(workflow_instance_id)
            if not context:
                return {'status': 'NOT_FOUND', 'error': 'Workflow instance not found'}
            
            base_status = context.get_workflow_status()
            
            # 增强依赖图信息
            dependency_graph = self.dependency_tracker.get_workflow_dependency_graph(workflow_instance_id)
            
            # 验证依赖关系
            validation_result = self.dependency_tracker.validate_dependencies(workflow_instance_id)
            
            # 组合完整状态
            enhanced_status = {
                **base_status,
                'dependency_graph': dependency_graph,
                'dependency_validation': validation_result,
                'performance_metrics': self._get_workflow_performance_metrics(workflow_instance_id),
                'resource_usage': self._get_workflow_resource_usage(workflow_instance_id)
            }
            
            return enhanced_status
            
        except Exception as e:
            logger.error(f"Failed to get workflow status: {e}")
            return {'status': 'ERROR', 'error': str(e)}
    
    def get_ready_nodes(self, workflow_instance_id: uuid.UUID) -> List[uuid.UUID]:
        """获取准备执行的节点"""
        try:
            # 从上下文获取就绪节点
            context = self.instance_manager.get_instance(workflow_instance_id)
            if not context:
                return []
            
            context_ready = context.get_ready_nodes()
            
            # 从依赖跟踪器获取就绪节点
            tracker_ready = self.dependency_tracker.get_ready_nodes(workflow_instance_id)
            
            # 取交集确保一致性
            ready_nodes = list(set(context_ready) & set(tracker_ready))
            
            return ready_nodes
            
        except Exception as e:
            logger.error(f"Failed to get ready nodes: {e}")
            return []
    
    async def pause_workflow(self, workflow_instance_id: uuid.UUID) -> bool:
        """暂停工作流执行"""
        try:
            context = self.instance_manager.get_instance(workflow_instance_id)
            if context:
                context.pause_workflow()
                logger.info(f"Paused workflow {workflow_instance_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to pause workflow: {e}")
            return False
    
    async def resume_workflow(self, workflow_instance_id: uuid.UUID) -> bool:
        """恢复工作流执行"""
        try:
            context = self.instance_manager.get_instance(workflow_instance_id)
            if context:
                context.resume_workflow()
                logger.info(f"Resumed workflow {workflow_instance_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to resume workflow: {e}")
            return False
    
    async def cancel_workflow(self, workflow_instance_id: uuid.UUID) -> bool:
        """取消工作流执行"""
        try:
            context = self.instance_manager.get_instance(workflow_instance_id)
            if context:
                context.cancel_workflow()
                await self._cleanup_workflow(workflow_instance_id)
                logger.info(f"Cancelled workflow {workflow_instance_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to cancel workflow: {e}")
            return False
    
    async def cleanup_workflow(self, workflow_instance_id: uuid.UUID) -> bool:
        """清理工作流资源"""
        try:
            await self._cleanup_workflow(workflow_instance_id)
            logger.info(f"Cleaned up workflow {workflow_instance_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup workflow: {e}")
            return False
    
    def register_workflow_created_callback(self, callback: Callable) -> None:
        """注册工作流创建回调"""
        with self._lock:
            self._workflow_created_callbacks.append(callback)
    
    def register_workflow_completed_callback(self, callback: Callable) -> None:
        """注册工作流完成回调"""
        with self._lock:
            self._workflow_completed_callbacks.append(callback)
    
    def register_workflow_failed_callback(self, callback: Callable) -> None:
        """注册工作流失败回调"""
        with self._lock:
            self._workflow_failed_callbacks.append(callback)
    
    def register_node_completed_callback(self, callback: Callable) -> None:
        """注册节点完成回调"""
        with self._lock:
            self._node_completed_callbacks.append(callback)
    
    def get_global_statistics(self) -> Dict[str, Any]:
        """获取全局统计信息"""
        with self._lock:
            return {
                'global_stats': self._global_stats.copy(),
                'performance_metrics': self._calculate_performance_summary(),
                'instance_manager_stats': self.instance_manager.get_manager_stats(),
                'dependency_tracker_stats': self.dependency_tracker.get_tracker_stats(),
                'cleanup_manager_stats': self.cleanup_manager.get_resource_stats(),
                'configuration': self._config.copy()
            }
    
    def get_compatibility_interface(self) -> Optional[WorkflowContextCompatibilityAdapter]:
        """获取兼容性接口（如果启用）"""
        return self.compatibility_adapter
    
    async def optimize_performance(self) -> Dict[str, Any]:
        """执行性能优化"""
        logger.info("Starting performance optimization")
        
        optimization_results = {}
        
        try:
            # 内存优化
            memory_result = self.cleanup_manager.optimize_memory()
            optimization_results['memory_optimization'] = memory_result
            
            # 强制清理过期资源
            cleanup_count = self.cleanup_manager.force_cleanup()
            optimization_results['resource_cleanup'] = {'cleaned_resources': cleanup_count}
            
            # 依赖图缓存清理
            # TODO: 可以添加更多优化策略
            
            logger.info(f"Performance optimization completed: {optimization_results}")
            return optimization_results
            
        except Exception as e:
            logger.error(f"Performance optimization failed: {e}")
            return {'error': str(e)}
    
    async def shutdown(self, force: bool = False) -> None:
        """关闭管理器"""
        logger.info("Shutting down WorkflowContextManagerV2")
        
        try:
            # 停止所有运行中的工作流
            running_instances = self.instance_manager.get_running_instances()
            for instance in running_instances:
                if force:
                    instance.cancel_workflow()
                else:
                    instance.pause_workflow()
            
            # 等待正在执行的任务完成（如果不是强制关闭）
            if not force:
                await asyncio.sleep(5)  # 给任务时间完成
            
            # 关闭各个组件
            self.dependency_tracker.shutdown()
            
            if self.compatibility_adapter:
                self.compatibility_adapter.shutdown()
            
            # 关闭全局组件
            shutdown_instance_manager()
            shutdown_cleanup_manager()
            
            logger.info("WorkflowContextManagerV2 shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during manager shutdown: {e}")
            raise
    
    def _setup_monitoring(self) -> None:
        """设置监控组件"""
        # TODO: 实现详细的监控逻辑
        logger.debug("Monitoring setup completed")
    
    def _setup_metrics(self) -> None:
        """设置指标收集"""
        # TODO: 实现详细的指标收集逻辑
        logger.debug("Metrics setup completed")
    
    def _setup_component_callbacks(self) -> None:
        """设置组件间回调"""
        # 注册实例管理器的回调
        self.instance_manager.register_instance_completed_callback(
            self._on_workflow_completed
        )
        self.instance_manager.register_instance_failed_callback(
            self._on_workflow_failed
        )
    
    async def _cleanup_workflow(self, workflow_instance_id: uuid.UUID) -> None:
        """内部清理工作流"""
        # 清理依赖跟踪器
        self.dependency_tracker.cleanup_workflow(workflow_instance_id)
        
        # 清理实例管理器
        self.instance_manager.remove_instance(workflow_instance_id, force=True)
        
        # 如果有兼容性适配器，也清理它
        if self.compatibility_adapter:
            await self.compatibility_adapter.cleanup_workflow_context(workflow_instance_id)
    
    def _on_workflow_completed(self, workflow_instance_id: uuid.UUID) -> None:
        """处理工作流完成事件"""
        self._global_stats['total_workflows_completed'] += 1
        
        # 通知回调
        for callback in self._workflow_completed_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(workflow_instance_id))
                else:
                    callback(workflow_instance_id)
            except Exception as e:
                logger.error(f"Error in workflow completed callback: {e}")
    
    def _on_workflow_failed(self, workflow_instance_id: uuid.UUID) -> None:
        """处理工作流失败事件"""
        self._global_stats['total_workflows_failed'] += 1
        
        # 通知回调
        for callback in self._workflow_failed_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(workflow_instance_id))
                else:
                    callback(workflow_instance_id)
            except Exception as e:
                logger.error(f"Error in workflow failed callback: {e}")
    
    async def _notify_workflow_created_callbacks(self, context: WorkflowInstanceContext) -> None:
        """通知工作流创建回调"""
        for callback in self._workflow_created_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(context)
                else:
                    callback(context)
            except Exception as e:
                logger.error(f"Error in workflow created callback: {e}")
    
    def _get_workflow_performance_metrics(self, workflow_instance_id: uuid.UUID) -> Dict[str, Any]:
        """获取工作流性能指标"""
        # TODO: 实现详细的性能指标计算
        return {
            'node_execution_times': [],
            'dependency_resolution_times': [],
            'memory_usage_history': []
        }
    
    def _get_workflow_resource_usage(self, workflow_instance_id: uuid.UUID) -> Dict[str, Any]:
        """获取工作流资源使用情况"""
        # TODO: 实现详细的资源使用统计
        return {
            'memory_usage_mb': 0.0,
            'cpu_usage_percent': 0.0,
            'active_threads': 0
        }
    
    def _calculate_performance_summary(self) -> Dict[str, Any]:
        """计算性能摘要"""
        summary = {}
        
        for metric_name, values in self._performance_metrics.items():
            if values:
                summary[metric_name] = {
                    'average': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                    'count': len(values)
                }
            else:
                summary[metric_name] = {
                    'average': 0.0,
                    'min': 0.0,
                    'max': 0.0,
                    'count': 0
                }
        
        return summary


# 全局单例实例
_context_manager_v2: Optional[WorkflowContextManagerV2] = None
_manager_lock = threading.Lock()


def get_context_manager_v2(mode: ManagerMode = ManagerMode.ENHANCED) -> WorkflowContextManagerV2:
    """获取工作流上下文管理器 V2 单例"""
    global _context_manager_v2
    
    if _context_manager_v2 is None:
        with _manager_lock:
            if _context_manager_v2 is None:
                _context_manager_v2 = WorkflowContextManagerV2(mode=mode)
    
    return _context_manager_v2


async def shutdown_context_manager_v2(force: bool = False) -> None:
    """关闭全局上下文管理器 V2"""
    global _context_manager_v2
    
    with _manager_lock:
        if _context_manager_v2 is not None:
            await _context_manager_v2.shutdown(force=force)
            _context_manager_v2 = None