"""
工作流实例管理器
统一管理所有工作流实例的上下文，提供实例创建、查询、销毁等功能
"""

import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from threading import Lock, RLock
from weakref import WeakValueDictionary
from loguru import logger

from .workflow_instance_context import WorkflowInstanceContext


class WorkflowInstanceManager:
    """工作流实例管理器"""
    
    def __init__(self):
        # 使用弱引用字典防止内存泄漏
        self._instances: Dict[uuid.UUID, WorkflowInstanceContext] = {}
        self._weak_instances = WeakValueDictionary()
        
        # 实例元数据
        self._instance_metadata: Dict[uuid.UUID, Dict[str, Any]] = {}
        
        # 全局锁
        self._lock = RLock()
        
        # 清理相关
        self._cleanup_interval = 300  # 5分钟清理一次
        self._max_completed_age = 3600  # 完成的工作流保留1小时
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_enabled = True
        
        # 统计信息
        self._stats = {
            'total_created': 0,
            'currently_running': 0,
            'total_completed': 0,
            'total_failed': 0,
            'total_cleaned': 0,
            'manager_start_time': datetime.utcnow()
        }
        
        logger.info("Initialized WorkflowInstanceManager")
    
    async def start_manager(self):
        """启动实例管理器"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Started workflow instance manager cleanup loop")
    
    async def stop_manager(self):
        """停止实例管理器"""
        self._cleanup_enabled = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        
        logger.info("Stopped workflow instance manager")
    
    async def create_instance(self, 
                            workflow_instance_id: uuid.UUID, 
                            workflow_base_id: uuid.UUID,
                            executor_id: uuid.UUID,
                            instance_name: str = None) -> WorkflowInstanceContext:
        """创建新的工作流实例上下文"""
        with self._lock:
            try:
                # 检查实例是否已存在
                if workflow_instance_id in self._instances:
                    logger.warning(f"Workflow instance {workflow_instance_id} already exists")
                    return self._instances[workflow_instance_id]
                
                # 创建新实例
                context = WorkflowInstanceContext(workflow_instance_id, workflow_base_id)
                
                # 存储实例
                self._instances[workflow_instance_id] = context
                self._weak_instances[workflow_instance_id] = context
                
                # 存储元数据
                self._instance_metadata[workflow_instance_id] = {
                    'workflow_base_id': workflow_base_id,
                    'executor_id': executor_id,
                    'instance_name': instance_name or f"Instance_{workflow_instance_id}",
                    'created_at': datetime.utcnow(),
                    'last_activity': datetime.utcnow(),
                    'status': 'RUNNING'
                }
                
                # 更新统计
                self._stats['total_created'] += 1
                self._stats['currently_running'] += 1
                
                logger.info(f"Created workflow instance context: {workflow_instance_id}")
                return context
                
            except Exception as e:
                logger.error(f"Failed to create workflow instance: {e}")
                raise
    
    async def get_instance(self, workflow_instance_id: uuid.UUID) -> Optional[WorkflowInstanceContext]:
        """获取工作流实例上下文"""
        with self._lock:
            context = self._instances.get(workflow_instance_id)
            if context:
                # 更新最后活动时间
                if workflow_instance_id in self._instance_metadata:
                    self._instance_metadata[workflow_instance_id]['last_activity'] = datetime.utcnow()
            return context
    
    async def remove_instance(self, workflow_instance_id: uuid.UUID, force: bool = False) -> bool:
        """移除工作流实例"""
        with self._lock:
            try:
                context = self._instances.get(workflow_instance_id)
                if not context:
                    logger.warning(f"Workflow instance {workflow_instance_id} not found for removal")
                    return False
                
                # 检查是否可以安全移除
                if not force:
                    status = await context.get_workflow_status()
                    if status['status'] not in ['COMPLETED', 'FAILED']:
                        logger.warning(f"Cannot remove running workflow instance {workflow_instance_id}")
                        return False
                
                # 清理上下文
                await context.cleanup()
                
                # 从管理器中移除
                del self._instances[workflow_instance_id]
                
                # 移除元数据
                if workflow_instance_id in self._instance_metadata:
                    metadata = self._instance_metadata[workflow_instance_id]
                    status = metadata.get('status', 'UNKNOWN')
                    
                    if status == 'COMPLETED':
                        self._stats['total_completed'] += 1
                    elif status == 'FAILED':
                        self._stats['total_failed'] += 1
                    
                    del self._instance_metadata[workflow_instance_id]
                
                # 更新统计
                self._stats['currently_running'] = max(0, self._stats['currently_running'] - 1)
                self._stats['total_cleaned'] += 1
                
                logger.info(f"Removed workflow instance: {workflow_instance_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to remove workflow instance {workflow_instance_id}: {e}")
                return False
    
    async def list_instances(self, 
                           status_filter: Optional[str] = None,
                           executor_filter: Optional[uuid.UUID] = None) -> List[Dict[str, Any]]:
        """列出工作流实例"""
        with self._lock:
            try:
                instances = []
                
                for instance_id, context in self._instances.items():
                    metadata = self._instance_metadata.get(instance_id, {})
                    status_info = await context.get_workflow_status()
                    
                    # 应用过滤器
                    if status_filter and status_info['status'] != status_filter:
                        continue
                    
                    if executor_filter and metadata.get('executor_id') != executor_filter:
                        continue
                    
                    instance_info = {
                        'workflow_instance_id': str(instance_id),
                        'workflow_base_id': str(metadata.get('workflow_base_id', '')),
                        'instance_name': metadata.get('instance_name', ''),
                        'executor_id': str(metadata.get('executor_id', '')),
                        'created_at': metadata.get('created_at'),
                        'last_activity': metadata.get('last_activity'),
                        'status': status_info['status'],
                        'total_nodes': status_info['total_nodes'],
                        'completed_nodes': status_info['completed_nodes'],
                        'failed_nodes': status_info['failed_nodes'],
                        'executing_nodes': status_info['executing_nodes']
                    }
                    instances.append(instance_info)
                
                return instances
                
            except Exception as e:
                logger.error(f"Failed to list workflow instances: {e}")
                return []
    
    async def get_instance_status(self, workflow_instance_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取工作流实例状态"""
        context = await self.get_instance(workflow_instance_id)
        if context:
            status = await context.get_workflow_status()
            metadata = self._instance_metadata.get(workflow_instance_id, {})
            
            # 合并状态和元数据
            status.update({
                'instance_name': metadata.get('instance_name', ''),
                'executor_id': str(metadata.get('executor_id', '')),
                'created_at': metadata.get('created_at'),
                'last_activity': metadata.get('last_activity')
            })
            
            return status
        
        return None
    
    async def update_instance_status(self, 
                                   workflow_instance_id: uuid.UUID, 
                                   status: str) -> bool:
        """更新工作流实例状态"""
        with self._lock:
            try:
                if workflow_instance_id in self._instance_metadata:
                    self._instance_metadata[workflow_instance_id]['status'] = status
                    self._instance_metadata[workflow_instance_id]['last_activity'] = datetime.utcnow()
                    return True
                return False
                
            except Exception as e:
                logger.error(f"Failed to update instance status: {e}")
                return False
    
    async def cleanup_completed_instances(self, max_age_seconds: int = None) -> int:
        """清理已完成的工作流实例"""
        if max_age_seconds is None:
            max_age_seconds = self._max_completed_age
        
        cutoff_time = datetime.utcnow() - timedelta(seconds=max_age_seconds)
        cleaned_count = 0
        
        with self._lock:
            try:
                instances_to_remove = []
                
                for instance_id, metadata in self._instance_metadata.items():
                    context = self._instances.get(instance_id)
                    if not context:
                        continue
                    
                    status_info = await context.get_workflow_status()
                    last_activity = metadata.get('last_activity', datetime.utcnow())
                    
                    # 清理条件：已完成且超过保留时间
                    if (status_info['status'] in ['COMPLETED', 'FAILED'] and 
                        last_activity < cutoff_time):
                        instances_to_remove.append(instance_id)
                
                # 执行清理
                for instance_id in instances_to_remove:
                    if await self.remove_instance(instance_id, force=True):
                        cleaned_count += 1
                
                if cleaned_count > 0:
                    logger.info(f"Cleaned up {cleaned_count} completed workflow instances")
                
                return cleaned_count
                
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
                return 0
    
    async def _cleanup_loop(self):
        """定期清理循环"""
        while self._cleanup_enabled:
            try:
                await asyncio.sleep(self._cleanup_interval)
                
                if self._cleanup_enabled:
                    await self.cleanup_completed_instances()
                    
                    # 清理孤儿元数据
                    await self._cleanup_orphaned_metadata()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _cleanup_orphaned_metadata(self):
        """清理孤儿元数据"""
        with self._lock:
            try:
                orphaned_keys = []
                
                for instance_id in self._instance_metadata.keys():
                    if instance_id not in self._instances:
                        orphaned_keys.append(instance_id)
                
                for key in orphaned_keys:
                    del self._instance_metadata[key]
                
                if orphaned_keys:
                    logger.debug(f"Cleaned up {len(orphaned_keys)} orphaned metadata entries")
                    
            except Exception as e:
                logger.error(f"Error cleaning orphaned metadata: {e}")
    
    async def get_manager_stats(self) -> Dict[str, Any]:
        """获取管理器统计信息"""
        with self._lock:
            current_time = datetime.utcnow()
            uptime = (current_time - self._stats['manager_start_time']).total_seconds()
            
            # 重新计算当前运行数
            running_count = 0
            for context in self._instances.values():
                status = await context.get_workflow_status()
                if status['status'] == 'RUNNING':
                    running_count += 1
            
            self._stats['currently_running'] = running_count
            
            return {
                **self._stats,
                'uptime_seconds': uptime,
                'instances_count': len(self._instances),
                'metadata_count': len(self._instance_metadata),
                'cleanup_enabled': self._cleanup_enabled,
                'cleanup_interval': self._cleanup_interval,
                'max_completed_age': self._max_completed_age
            }
    
    async def force_cleanup_all(self) -> int:
        """强制清理所有实例（用于测试或紧急情况）"""
        with self._lock:
            try:
                instance_ids = list(self._instances.keys())
                cleaned_count = 0
                
                for instance_id in instance_ids:
                    if await self.remove_instance(instance_id, force=True):
                        cleaned_count += 1
                
                logger.warning(f"Force cleaned {cleaned_count} workflow instances")
                return cleaned_count
                
            except Exception as e:
                logger.error(f"Error during force cleanup: {e}")
                return 0
    
    async def get_instance_by_name(self, instance_name: str) -> Optional[WorkflowInstanceContext]:
        """根据实例名称查找工作流实例"""
        with self._lock:
            for instance_id, metadata in self._instance_metadata.items():
                if metadata.get('instance_name') == instance_name:
                    return self._instances.get(instance_id)
            return None
    
    async def register_instance_callback(self, 
                                       workflow_instance_id: uuid.UUID, 
                                       callback) -> bool:
        """为工作流实例注册回调函数"""
        context = await self.get_instance(workflow_instance_id)
        if context:
            return context.register_completion_callback(callback)
        return False
    
    def __len__(self) -> int:
        """返回当前管理的实例数量"""
        return len(self._instances)
    
    def __contains__(self, workflow_instance_id: uuid.UUID) -> bool:
        """检查是否包含指定的工作流实例"""
        return workflow_instance_id in self._instances
    
    def __repr__(self) -> str:
        return f"WorkflowInstanceManager(instances={len(self._instances)}, running={self._stats['currently_running']})"


# 全局实例管理器（单例模式）
_instance_manager: Optional[WorkflowInstanceManager] = None
_manager_lock = Lock()


async def get_instance_manager() -> WorkflowInstanceManager:
    """获取全局工作流实例管理器（单例）"""
    global _instance_manager
    
    if _instance_manager is None:
        with _manager_lock:
            if _instance_manager is None:
                _instance_manager = WorkflowInstanceManager()
                await _instance_manager.start_manager()
    
    return _instance_manager


async def cleanup_instance_manager():
    """清理全局实例管理器"""
    global _instance_manager
    
    if _instance_manager is not None:
        await _instance_manager.stop_manager()
        await _instance_manager.force_cleanup_all()
        _instance_manager = None