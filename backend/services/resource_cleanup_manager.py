"""
资源清理管理器
负责管理系统资源的自动清理，包括工作流实例、缓存、临时文件等
"""

import uuid
import asyncio
import gc
import os
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Set
from threading import Lock, RLock
from pathlib import Path
from loguru import logger


class ResourceCleanupManager:
    """系统资源清理管理器"""
    
    def __init__(self):
        # 清理策略配置
        self.cleanup_policies = {
            'workflow_instances': {
                'max_completed_age': 3600,  # 1小时
                'max_failed_age': 7200,     # 2小时
                'max_running_age': 86400,   # 24小时（异常保护）
                'cleanup_interval': 300,    # 5分钟检查一次
                'enabled': True
            },
            'cache': {
                'max_age': 1800,           # 30分钟
                'max_size_mb': 100,        # 100MB
                'cleanup_interval': 600,   # 10分钟检查一次
                'enabled': True
            },
            'temp_files': {
                'max_age': 3600,           # 1小时
                'cleanup_interval': 1800,  # 30分钟检查一次
                'enabled': True
            },
            'memory': {
                'gc_interval': 60,         # 1分钟垃圾回收一次
                'force_gc_threshold': 0.8, # 内存使用率超过80%强制GC
                'enabled': True
            }
        }
        
        # 清理任务
        self._cleanup_tasks: Dict[str, asyncio.Task] = {}
        self._cleanup_enabled = True
        
        # 注册的清理器
        self._registered_cleaners: Dict[str, Callable] = {}
        
        # 临时文件跟踪
        self._temp_files: Set[str] = set()
        self._temp_dirs: Set[str] = set()
        
        # 线程安全锁
        self._lock = RLock()
        self._temp_files_lock = Lock()
        
        # 统计信息
        self._stats = {
            'total_cleanups': 0,
            'workflow_cleanups': 0,
            'cache_cleanups': 0,
            'temp_file_cleanups': 0,
            'memory_cleanups': 0,
            'cleanup_errors': 0,
            'bytes_freed': 0,
            'last_cleanup': None,
            'manager_start_time': datetime.utcnow()
        }
        
        logger.info("Initialized ResourceCleanupManager")
    
    async def start_manager(self):
        """启动资源清理管理器"""
        if not self._cleanup_enabled:
            return
        
        with self._lock:
            # 启动各类清理任务
            if self.cleanup_policies['workflow_instances']['enabled']:
                self._cleanup_tasks['workflow_instances'] = asyncio.create_task(
                    self._workflow_cleanup_loop()
                )
            
            if self.cleanup_policies['cache']['enabled']:
                self._cleanup_tasks['cache'] = asyncio.create_task(
                    self._cache_cleanup_loop()
                )
            
            if self.cleanup_policies['temp_files']['enabled']:
                self._cleanup_tasks['temp_files'] = asyncio.create_task(
                    self._temp_files_cleanup_loop()
                )
            
            if self.cleanup_policies['memory']['enabled']:
                self._cleanup_tasks['memory'] = asyncio.create_task(
                    self._memory_cleanup_loop()
                )
        
        logger.info(f"Started {len(self._cleanup_tasks)} cleanup tasks")
    
    async def stop_manager(self):
        """停止资源清理管理器"""
        self._cleanup_enabled = False
        
        with self._lock:
            # 取消所有清理任务
            for task_name, task in self._cleanup_tasks.items():
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    logger.debug(f"Stopped cleanup task: {task_name}")
            
            self._cleanup_tasks.clear()
        
        # 执行最后一次清理
        await self.force_cleanup_all()
        
        logger.info("Stopped ResourceCleanupManager")
    
    def register_cleaner(self, name: str, cleaner_func: Callable, 
                        cleanup_interval: int = 300) -> bool:
        """注册自定义清理器"""
        with self._lock:
            try:
                if name in self._registered_cleaners:
                    logger.warning(f"Cleaner {name} already registered")
                    return False
                
                self._registered_cleaners[name] = {
                    'func': cleaner_func,
                    'interval': cleanup_interval,
                    'last_run': None,
                    'total_runs': 0,
                    'total_errors': 0
                }
                
                logger.info(f"Registered custom cleaner: {name}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to register cleaner {name}: {e}")
                return False
    
    def unregister_cleaner(self, name: str) -> bool:
        """注销清理器"""
        with self._lock:
            if name in self._registered_cleaners:
                del self._registered_cleaners[name]
                logger.info(f"Unregistered cleaner: {name}")
                return True
            return False
    
    def track_temp_file(self, file_path: str):
        """跟踪临时文件"""
        with self._temp_files_lock:
            self._temp_files.add(os.path.abspath(file_path))
            logger.debug(f"Tracking temp file: {file_path}")
    
    def track_temp_dir(self, dir_path: str):
        """跟踪临时目录"""
        with self._temp_files_lock:
            self._temp_dirs.add(os.path.abspath(dir_path))
            logger.debug(f"Tracking temp dir: {dir_path}")
    
    def untrack_temp_file(self, file_path: str):
        """停止跟踪临时文件"""
        with self._temp_files_lock:
            abs_path = os.path.abspath(file_path)
            self._temp_files.discard(abs_path)
    
    def untrack_temp_dir(self, dir_path: str):
        """停止跟踪临时目录"""
        with self._temp_files_lock:
            abs_path = os.path.abspath(dir_path)
            self._temp_dirs.discard(abs_path)
    
    async def _workflow_cleanup_loop(self):
        """工作流实例清理循环"""
        policy = self.cleanup_policies['workflow_instances']
        
        while self._cleanup_enabled:
            try:
                await asyncio.sleep(policy['cleanup_interval'])
                
                if self._cleanup_enabled:
                    await self._cleanup_workflow_instances()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in workflow cleanup loop: {e}")
                self._stats['cleanup_errors'] += 1
    
    async def _cache_cleanup_loop(self):
        """缓存清理循环"""
        policy = self.cleanup_policies['cache']
        
        while self._cleanup_enabled:
            try:
                await asyncio.sleep(policy['cleanup_interval'])
                
                if self._cleanup_enabled:
                    await self._cleanup_caches()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup loop: {e}")
                self._stats['cleanup_errors'] += 1
    
    async def _temp_files_cleanup_loop(self):
        """临时文件清理循环"""
        policy = self.cleanup_policies['temp_files']
        
        while self._cleanup_enabled:
            try:
                await asyncio.sleep(policy['cleanup_interval'])
                
                if self._cleanup_enabled:
                    await self._cleanup_temp_files()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in temp files cleanup loop: {e}")
                self._stats['cleanup_errors'] += 1
    
    async def _memory_cleanup_loop(self):
        """内存清理循环"""
        policy = self.cleanup_policies['memory']
        
        while self._cleanup_enabled:
            try:
                await asyncio.sleep(policy['gc_interval'])
                
                if self._cleanup_enabled:
                    await self._cleanup_memory()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in memory cleanup loop: {e}")
                self._stats['cleanup_errors'] += 1
    
    async def _cleanup_workflow_instances(self):
        """清理工作流实例"""
        try:
            # 这里需要与WorkflowInstanceManager集成
            from .workflow_instance_manager import get_instance_manager
            
            manager = await get_instance_manager()
            policy = self.cleanup_policies['workflow_instances']
            
            # 清理已完成的实例
            completed_cleaned = await manager.cleanup_completed_instances(
                policy['max_completed_age']
            )
            
            # 清理失败的实例（保留更长时间用于调试）
            failed_cleaned = await manager.cleanup_completed_instances(
                policy['max_failed_age']
            )
            
            total_cleaned = completed_cleaned + failed_cleaned
            
            if total_cleaned > 0:
                self._stats['workflow_cleanups'] += total_cleaned
                self._stats['total_cleanups'] += total_cleaned
                logger.info(f"Cleaned up {total_cleaned} workflow instances")
            
        except Exception as e:
            logger.error(f"Error cleaning workflow instances: {e}")
            self._stats['cleanup_errors'] += 1
    
    async def _cleanup_caches(self):
        """清理各种缓存"""
        try:
            cleaned_count = 0
            freed_bytes = 0
            
            # 清理依赖跟踪器缓存
            try:
                from .node_dependency_tracker import NodeDependencyTracker
                # 这里需要访问全局的依赖跟踪器实例
                # 暂时跳过具体实现
                logger.debug("Cache cleanup: dependency tracker")
                
            except Exception as e:
                logger.debug(f"Dependency tracker cache cleanup skipped: {e}")
            
            # 执行垃圾回收
            collected = gc.collect()
            if collected > 0:
                logger.debug(f"Garbage collected {collected} objects")
                cleaned_count += collected
            
            if cleaned_count > 0:
                self._stats['cache_cleanups'] += cleaned_count
                self._stats['total_cleanups'] += cleaned_count
                self._stats['bytes_freed'] += freed_bytes
            
        except Exception as e:
            logger.error(f"Error cleaning caches: {e}")
            self._stats['cleanup_errors'] += 1
    
    async def _cleanup_temp_files(self):
        """清理临时文件"""
        try:
            cleaned_count = 0
            freed_bytes = 0
            policy = self.cleanup_policies['temp_files']
            cutoff_time = datetime.utcnow() - timedelta(seconds=policy['max_age'])
            
            with self._temp_files_lock:
                # 清理跟踪的临时文件
                files_to_remove = []
                for file_path in self._temp_files.copy():
                    try:
                        if os.path.exists(file_path):
                            stat = os.stat(file_path)
                            if datetime.fromtimestamp(stat.st_mtime) < cutoff_time:
                                file_size = stat.st_size
                                os.remove(file_path)
                                freed_bytes += file_size
                                cleaned_count += 1
                                files_to_remove.append(file_path)
                                logger.debug(f"Removed temp file: {file_path}")
                        else:
                            files_to_remove.append(file_path)
                    except Exception as e:
                        logger.debug(f"Error removing temp file {file_path}: {e}")
                
                # 从跟踪列表中移除
                for file_path in files_to_remove:
                    self._temp_files.discard(file_path)
                
                # 清理跟踪的临时目录
                dirs_to_remove = []
                for dir_path in self._temp_dirs.copy():
                    try:
                        if os.path.exists(dir_path) and os.path.isdir(dir_path):
                            # 检查目录是否为空或者只包含旧文件
                            if self._is_dir_cleanable(dir_path, cutoff_time):
                                import shutil
                                dir_size = self._get_dir_size(dir_path)
                                shutil.rmtree(dir_path)
                                freed_bytes += dir_size
                                cleaned_count += 1
                                dirs_to_remove.append(dir_path)
                                logger.debug(f"Removed temp dir: {dir_path}")
                        else:
                            dirs_to_remove.append(dir_path)
                    except Exception as e:
                        logger.debug(f"Error removing temp dir {dir_path}: {e}")
                
                # 从跟踪列表中移除
                for dir_path in dirs_to_remove:
                    self._temp_dirs.discard(dir_path)
            
            # 清理系统临时目录中的旧文件
            await self._cleanup_system_temp_files(cutoff_time)
            
            if cleaned_count > 0:
                self._stats['temp_file_cleanups'] += cleaned_count
                self._stats['total_cleanups'] += cleaned_count
                self._stats['bytes_freed'] += freed_bytes
                logger.info(f"Cleaned up {cleaned_count} temp files, freed {freed_bytes} bytes")
            
        except Exception as e:
            logger.error(f"Error cleaning temp files: {e}")
            self._stats['cleanup_errors'] += 1
    
    async def _cleanup_memory(self):
        """内存清理"""
        try:
            # 执行垃圾回收
            collected = gc.collect()
            
            if collected > 0:
                self._stats['memory_cleanups'] += 1
                self._stats['total_cleanups'] += 1
                logger.debug(f"Memory cleanup: collected {collected} objects")
            
            # 检查内存使用情况
            try:
                import psutil
                process = psutil.Process()
                memory_percent = process.memory_percent()
                
                if memory_percent > self.cleanup_policies['memory']['force_gc_threshold'] * 100:
                    # 强制垃圾回收
                    for i in range(3):  # 多次GC确保清理彻底
                        collected += gc.collect()
                    
                    logger.warning(f"High memory usage ({memory_percent:.1f}%), "
                                 f"forced GC collected {collected} objects")
                    
            except ImportError:
                logger.debug("psutil not available, skipping memory monitoring")
            
        except Exception as e:
            logger.error(f"Error in memory cleanup: {e}")
            self._stats['cleanup_errors'] += 1
    
    def _is_dir_cleanable(self, dir_path: str, cutoff_time: datetime) -> bool:
        """检查目录是否可以清理"""
        try:
            if not os.path.exists(dir_path):
                return True
            
            # 检查目录中的所有文件
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    stat = os.stat(file_path)
                    if datetime.fromtimestamp(stat.st_mtime) >= cutoff_time:
                        return False  # 有新文件，不能清理
            
            return True
            
        except Exception:
            return False
    
    def _get_dir_size(self, dir_path: str) -> int:
        """获取目录大小"""
        try:
            total_size = 0
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        total_size += os.path.getsize(file_path)
                    except (OSError, IOError):
                        pass
            return total_size
        except Exception:
            return 0
    
    async def _cleanup_system_temp_files(self, cutoff_time: datetime):
        """清理系统临时目录中的旧文件"""
        try:
            temp_dir = tempfile.gettempdir()
            workflow_temp_pattern = "workflow_"
            
            for item in os.listdir(temp_dir):
                if item.startswith(workflow_temp_pattern):
                    item_path = os.path.join(temp_dir, item)
                    try:
                        stat = os.stat(item_path)
                        if datetime.fromtimestamp(stat.st_mtime) < cutoff_time:
                            if os.path.isfile(item_path):
                                os.remove(item_path)
                            elif os.path.isdir(item_path):
                                import shutil
                                shutil.rmtree(item_path)
                            logger.debug(f"Cleaned system temp: {item_path}")
                    except Exception as e:
                        logger.debug(f"Error cleaning system temp {item_path}: {e}")
                        
        except Exception as e:
            logger.debug(f"Error cleaning system temp files: {e}")
    
    async def run_custom_cleaners(self):
        """运行自定义清理器"""
        with self._lock:
            current_time = datetime.utcnow()
            
            for name, cleaner_info in self._registered_cleaners.items():
                try:
                    last_run = cleaner_info.get('last_run')
                    interval = cleaner_info['interval']
                    
                    # 检查是否需要运行
                    if (last_run is None or 
                        (current_time - last_run).total_seconds() >= interval):
                        
                        # 执行清理器
                        cleaner_func = cleaner_info['func']
                        
                        if asyncio.iscoroutinefunction(cleaner_func):
                            await cleaner_func()
                        else:
                            cleaner_func()
                        
                        # 更新运行信息
                        cleaner_info['last_run'] = current_time
                        cleaner_info['total_runs'] += 1
                        
                        logger.debug(f"Ran custom cleaner: {name}")
                        
                except Exception as e:
                    logger.error(f"Error running custom cleaner {name}: {e}")
                    cleaner_info['total_errors'] += 1
                    self._stats['cleanup_errors'] += 1
    
    async def force_cleanup_all(self):
        """强制执行所有清理操作"""
        try:
            logger.info("Starting force cleanup of all resources")
            
            # 清理工作流实例
            await self._cleanup_workflow_instances()
            
            # 清理缓存
            await self._cleanup_caches()
            
            # 清理临时文件
            await self._cleanup_temp_files()
            
            # 内存清理
            await self._cleanup_memory()
            
            # 运行自定义清理器
            await self.run_custom_cleaners()
            
            self._stats['last_cleanup'] = datetime.utcnow()
            logger.info("Force cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during force cleanup: {e}")
            self._stats['cleanup_errors'] += 1
    
    def update_cleanup_policy(self, resource_type: str, policy_updates: Dict[str, Any]):
        """更新清理策略"""
        with self._lock:
            if resource_type in self.cleanup_policies:
                self.cleanup_policies[resource_type].update(policy_updates)
                logger.info(f"Updated cleanup policy for {resource_type}: {policy_updates}")
            else:
                logger.warning(f"Unknown resource type: {resource_type}")
    
    def get_cleanup_stats(self) -> Dict[str, Any]:
        """获取清理统计信息"""
        with self._lock:
            current_time = datetime.utcnow()
            uptime = (current_time - self._stats['manager_start_time']).total_seconds()
            
            return {
                **self._stats,
                'uptime_seconds': uptime,
                'cleanup_policies': self.cleanup_policies.copy(),
                'active_cleanup_tasks': len(self._cleanup_tasks),
                'registered_cleaners': len(self._registered_cleaners),
                'tracked_temp_files': len(self._temp_files),
                'tracked_temp_dirs': len(self._temp_dirs),
                'cleanup_enabled': self._cleanup_enabled
            }
    
    def __repr__(self) -> str:
        return (f"ResourceCleanupManager(tasks={len(self._cleanup_tasks)}, "
                f"cleaners={len(self._registered_cleaners)}, "
                f"temp_files={len(self._temp_files)})")