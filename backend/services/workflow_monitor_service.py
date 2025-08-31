"""
工作流监控服务
Workflow Monitor Service
"""

import uuid
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from loguru import logger

from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
from ..repositories.instance.node_instance_repository import NodeInstanceRepository
from ..repositories.instance.task_instance_repository import TaskInstanceRepository
from .workflow_execution_context import get_context_manager
from .execution_service import execution_engine


class WorkflowMonitorService:
    """工作流监控服务 - 定期扫描和修复停滞的工作流实例"""
    
    def __init__(self):
        self.workflow_repo = WorkflowInstanceRepository()
        self.node_repo = NodeInstanceRepository()
        self.task_repo = TaskInstanceRepository()
        self.context_manager = get_context_manager()
        
        # 监控配置
        self.scan_interval = 300  # 5分钟扫描一次
        self.stale_threshold_hours = 2  # 超过2小时未更新视为停滞
        self.max_recovery_attempts = 3  # 最大恢复尝试次数
        
        # 运行状态
        self.is_running = False
        self.monitor_task = None
        self.recovery_stats = {
            'total_scanned': 0,
            'stale_workflows_found': 0,
            'recovery_attempts': 0,
            'successful_recoveries': 0,
            'failed_recoveries': 0,
            'last_scan_time': None
        }
        
    async def start_monitoring(self):
        """启动监控服务"""
        if self.is_running:
            logger.warning("工作流监控服务已在运行中")
            return
            
        logger.info("🔍 启动工作流停滞监控服务")
        logger.info(f"   - 扫描间隔: {self.scan_interval}秒")
        logger.info(f"   - 停滞阈值: {self.stale_threshold_hours}小时")
        logger.info(f"   - 最大重试: {self.max_recovery_attempts}次")
        
        self.is_running = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        
    async def stop_monitoring(self):
        """停止监控服务"""
        if not self.is_running:
            return
            
        logger.info("🛑 停止工作流监控服务")
        self.is_running = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
                
    async def _monitoring_loop(self):
        """监控循环"""
        logger.info("🔄 工作流监控循环已启动")
        
        while self.is_running:
            try:
                await self._scan_and_recover_stale_workflows()
                await asyncio.sleep(self.scan_interval)
            except asyncio.CancelledError:
                logger.info("监控循环被取消")
                break
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                await asyncio.sleep(self.scan_interval)  # 出错后仍继续监控
                
    async def _scan_and_recover_stale_workflows(self):
        """扫描并恢复停滞的工作流"""
        try:
            logger.debug("🔍 开始扫描停滞的工作流实例...")
            
            # 查找停滞的工作流实例
            stale_workflows = await self._find_stale_workflows()
            
            self.recovery_stats['total_scanned'] += len(stale_workflows) if stale_workflows else 0
            self.recovery_stats['stale_workflows_found'] = len(stale_workflows) if stale_workflows else 0
            self.recovery_stats['last_scan_time'] = datetime.utcnow().isoformat()
            
            if not stale_workflows:
                logger.debug("✅ 未发现停滞的工作流实例")
                return
                
            logger.info(f"🚨 发现 {len(stale_workflows)} 个停滞的工作流实例，开始恢复...")
            
            for workflow in stale_workflows:
                try:
                    await self._attempt_workflow_recovery(workflow)
                except Exception as e:
                    logger.error(f"恢复工作流 {workflow['workflow_instance_id']} 失败: {e}")
                    self.recovery_stats['failed_recoveries'] += 1
                    
        except Exception as e:
            logger.error(f"扫描停滞工作流异常: {e}")
            
    async def _find_stale_workflows(self) -> List[Dict[str, Any]]:
        """查找停滞的工作流实例"""
        try:
            # 计算停滞阈值时间
            stale_threshold = datetime.utcnow() - timedelta(hours=self.stale_threshold_hours)
            
            # 查询潜在停滞的工作流实例
            query = """
            SELECT 
                wi.workflow_instance_id,
                wi.workflow_instance_name,
                wi.status as workflow_status,
                wi.updated_at,
                wi.created_at,
                w.name as workflow_name,
                u.username as executor_name,
                -- 统计节点实例信息
                COUNT(ni.node_instance_id) as total_nodes,
                COUNT(CASE WHEN ni.status = 'completed' THEN 1 END) as completed_nodes,
                COUNT(CASE WHEN ni.status = 'pending' THEN 1 END) as pending_nodes,
                COUNT(CASE WHEN ni.status = 'running' THEN 1 END) as running_nodes,
                COUNT(CASE WHEN ni.status = 'failed' THEN 1 END) as failed_nodes,
                -- 最后更新时间
                MAX(ni.updated_at) as last_node_update,
                MAX(ti.updated_at) as last_task_update
            FROM workflow_instance wi
            LEFT JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id AND w.is_current_version = 1
            LEFT JOIN user u ON wi.executor_id = u.user_id
            LEFT JOIN node_instance ni ON wi.workflow_instance_id = ni.workflow_instance_id AND ni.is_deleted = 0
            LEFT JOIN task_instance ti ON ni.node_instance_id = ti.node_instance_id AND ti.is_deleted = 0
            WHERE wi.is_deleted = 0
            AND wi.status IN ('running', 'pending')  -- 只检查运行中或待处理的工作流
            AND wi.updated_at < %s  -- 超过阈值时间未更新
            GROUP BY wi.workflow_instance_id, wi.workflow_instance_name, wi.status, wi.updated_at, wi.created_at, w.name, u.username
            HAVING pending_nodes > 0  -- 存在待处理节点
            AND completed_nodes > 0   -- 但有已完成节点（说明执行过程中停滞）
            ORDER BY wi.updated_at ASC
            LIMIT 50  -- 限制批量处理数量
            """
            
            results = await self.workflow_repo.db.fetch_all(query, stale_threshold)
            
            # 进一步筛选真正停滞的工作流
            stale_workflows = []
            for result in results:
                # 检查是否真的停滞（有完成的节点，但有等待中的节点且长时间无更新）
                if await self._is_workflow_truly_stale(result):
                    stale_workflows.append(dict(result))
                    
            return stale_workflows
            
        except Exception as e:
            logger.error(f"查找停滞工作流失败: {e}")
            return []
            
    async def _is_workflow_truly_stale(self, workflow_data: Dict) -> bool:
        """判断工作流是否真的停滞"""
        try:
            workflow_id = workflow_data['workflow_instance_id']
            
            # 检查是否有正在运行的任务
            running_tasks_query = """
            SELECT COUNT(*) as running_task_count
            FROM task_instance ti
            JOIN node_instance ni ON ti.node_instance_id = ni.node_instance_id
            WHERE ni.workflow_instance_id = %s
            AND ti.status IN ('in_progress', 'assigned')
            AND ti.is_deleted = 0
            """
            
            running_task_result = await self.task_repo.db.fetch_one(running_tasks_query, workflow_id)
            if running_task_result and running_task_result['running_task_count'] > 0:
                # 有正在运行的任务，不算停滞
                return False
                
            # 检查是否有满足条件但未执行的节点
            ready_nodes_query = """
            WITH node_dependencies AS (
                SELECT 
                    ni.node_instance_id,
                    ni.status as node_status,
                    COUNT(upstream_ni.node_instance_id) as upstream_count,
                    COUNT(CASE WHEN upstream_ni.status = 'completed' THEN 1 END) as completed_upstream_count
                FROM node_instance ni
                LEFT JOIN node_connection nc ON ni.node_id = nc.to_node_id
                LEFT JOIN node_instance upstream_ni ON nc.from_node_id = upstream_ni.node_id 
                    AND upstream_ni.workflow_instance_id = ni.workflow_instance_id
                    AND upstream_ni.is_deleted = 0
                WHERE ni.workflow_instance_id = %s 
                AND ni.is_deleted = 0
                GROUP BY ni.node_instance_id, ni.status
            )
            SELECT COUNT(*) as ready_pending_nodes
            FROM node_dependencies 
            WHERE node_status = 'pending'
            AND (upstream_count = 0 OR upstream_count = completed_upstream_count)
            """
            
            ready_result = await self.node_repo.db.fetch_one(ready_nodes_query, workflow_id)
            ready_nodes_count = ready_result['ready_pending_nodes'] if ready_result else 0
            
            # 如果有准备好但未执行的节点，则判定为停滞
            return ready_nodes_count > 0
            
        except Exception as e:
            logger.error(f"判断工作流停滞状态失败: {e}")
            return False
            
    async def _attempt_workflow_recovery(self, workflow_data: Dict):
        """尝试恢复停滞的工作流"""
        workflow_id = uuid.UUID(workflow_data['workflow_instance_id'])
        workflow_name = workflow_data.get('workflow_instance_name', '未知')
        
        logger.info(f"🔧 开始恢复停滞工作流: {workflow_name} ({workflow_id})")
        logger.info(f"   - 停滞时间: {workflow_data.get('updated_at')}")
        logger.info(f"   - 节点状态: {workflow_data.get('completed_nodes', 0)}/{workflow_data.get('total_nodes', 0)} 完成")
        
        self.recovery_stats['recovery_attempts'] += 1
        
        try:
            # 1. 检查并恢复上下文
            context_existed = self.context_manager.contexts.get(workflow_id) is not None
            if not context_existed:
                logger.info(f"   - 上下文缺失，从数据库恢复...")
                recovered_context = await self.context_manager.get_context(workflow_id)
                if not recovered_context:
                    raise Exception("无法从数据库恢复上下文")
                logger.info(f"   - 上下文恢复成功")
            else:
                recovered_context = self.context_manager.contexts[workflow_id]
                logger.info(f"   - 上下文已存在，直接使用")
            
            # 2. 检查待触发的节点
            ready_nodes = await recovered_context.get_ready_nodes()
            logger.info(f"   - 发现 {len(ready_nodes)} 个待触发节点")
            
            if not ready_nodes:
                logger.warning(f"   - 没有发现待触发节点，可能依赖关系重建失败")
                # 尝试强制重新获取上下文（这会触发依赖关系重建）
                await self.context_manager.remove_context(workflow_id)
                recovered_context = await self.context_manager.get_context(workflow_id)
                if recovered_context:
                    ready_nodes = await recovered_context.get_ready_nodes()
                    logger.info(f"   - 重建上下文后发现 {len(ready_nodes)} 个待触发节点")
                else:
                    logger.error(f"   - 重新获取上下文失败")
            
            # 3. 触发准备好的节点
            triggered_count = 0
            for node_instance_id in ready_nodes:
                try:
                    logger.info(f"   - 触发节点: {node_instance_id}")
                    await execution_engine._on_nodes_ready_to_execute(workflow_id, [node_instance_id])
                    triggered_count += 1
                except Exception as node_error:
                    logger.error(f"   - 触发节点失败 {node_instance_id}: {node_error}")
            
            if triggered_count > 0:
                self.recovery_stats['successful_recoveries'] += 1
                logger.info(f"✅ 工作流恢复成功: {workflow_name}")
                logger.info(f"   - 触发了 {triggered_count} 个节点")
            else:
                logger.warning(f"⚠️ 工作流恢复部分成功: {workflow_name}")
                logger.warning(f"   - 上下文已恢复，但没有触发任何节点")
                
        except Exception as e:
            logger.error(f"❌ 工作流恢复失败: {workflow_name}")
            logger.error(f"   - 错误: {e}")
            self.recovery_stats['failed_recoveries'] += 1
            raise
            
    async def get_monitor_stats(self) -> Dict[str, Any]:
        """获取监控统计信息"""
        return {
            'is_running': self.is_running,
            'scan_interval_seconds': self.scan_interval,
            'stale_threshold_hours': self.stale_threshold_hours,
            'max_recovery_attempts': self.max_recovery_attempts,
            'recovery_stats': self.recovery_stats.copy()
        }
        
    async def manual_scan_and_recover(self) -> Dict[str, Any]:
        """手动触发扫描和恢复"""
        logger.info("🔧 手动触发停滞工作流扫描和恢复")
        
        before_stats = self.recovery_stats.copy()
        await self._scan_and_recover_stale_workflows()
        after_stats = self.recovery_stats.copy()
        
        # 计算本次扫描的结果
        scan_results = {
            'workflows_scanned': after_stats['total_scanned'] - before_stats['total_scanned'],
            'stale_found': after_stats['stale_workflows_found'],
            'recovery_attempts': after_stats['recovery_attempts'] - before_stats['recovery_attempts'],
            'successful_recoveries': after_stats['successful_recoveries'] - before_stats['successful_recoveries'],
            'failed_recoveries': after_stats['failed_recoveries'] - before_stats['failed_recoveries'],
            'scan_time': after_stats['last_scan_time']
        }
        
        return scan_results


# 全局监控服务实例
_workflow_monitor = None

def get_workflow_monitor() -> WorkflowMonitorService:
    """获取工作流监控服务实例"""
    global _workflow_monitor
    if _workflow_monitor is None:
        _workflow_monitor = WorkflowMonitorService()
    return _workflow_monitor