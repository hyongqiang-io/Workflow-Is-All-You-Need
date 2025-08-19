"""
状态追踪和监控服务
Status Tracking and Monitoring Service
"""

import uuid
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from loguru import logger
import sys
from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
from ..repositories.instance.task_instance_repository import TaskInstanceRepository
from ..models.instance import (
    WorkflowInstanceStatus, TaskInstanceStatus, TaskInstanceType
)
from ..utils.helpers import now_utc


class MonitoringService:
    """监控服务"""
    
    def __init__(self):
        self.workflow_instance_repo = WorkflowInstanceRepository()
        self.task_instance_repo = TaskInstanceRepository()
        
        # 监控配置
        self.is_monitoring = False
        self.monitor_interval = 15  # 监控间隔（秒）- 优化为更频繁
        self.alert_thresholds = {
            'workflow_timeout_minutes': 60,  # 工作流超时阈值
            'task_timeout_minutes': 30,      # 任务超时阈值
            'failed_task_rate': 0.1,         # 失败任务比例阈值
            'queue_size_threshold': 100      # 队列大小阈值
        }
        
        # 工作流完成回调注册表
        self.workflow_completion_callbacks = {}  # {workflow_instance_id: [callback_functions]}
        
        # 监控数据
        self.metrics = {
            'workflows': {
                'total': 0,
                'running': 0,
                'completed': 0,
                'failed': 0,
                'cancelled': 0
            },
            'tasks': {
                'total': 0,
                'pending': 0,
                'in_progress': 0,
                'completed': 0,
                'failed': 0,
                'cancelled': 0
            },
            'performance': {
                'avg_workflow_duration': 0,
                'avg_task_duration': 0,
                'success_rate': 0
            }
        }
        
        # 告警历史
        self.alerts = []
    
    async def start_monitoring(self):
        """启动监控服务"""
        if self.is_monitoring:
            logger.warning("监控服务已在运行中")
            return
        
        self.is_monitoring = True
        logger.info("启动工作流监控服务")
        
        # 启动监控协程
        asyncio.create_task(self._monitoring_loop())
        asyncio.create_task(self._collect_metrics())
        asyncio.create_task(self._check_timeouts())
        asyncio.create_task(self._performance_analysis())
        asyncio.create_task(self._real_time_status_sync())  # 新增实时状态同步
    
    async def stop_monitoring(self):
        """停止监控服务"""
        self.is_monitoring = False
        logger.info("停止工作流监控服务")
    
    async def _monitoring_loop(self):
        """主监控循环"""
        while self.is_monitoring:
            try:
                # 收集基础指标
                await self._update_basic_metrics()
                
                # 检查异常情况
                await self._check_anomalies()
                
                # 检查工作流完成状态并触发回调
                await self._check_workflow_completion_and_trigger_callbacks()
                
                # 等待下一个监控周期
                await asyncio.sleep(self.monitor_interval)
                
            except Exception as e:
                logger.error(f"监控循环出错: {e}")
                await asyncio.sleep(10)
    
    async def _update_basic_metrics(self):
        """更新基础指标"""
        try:
            # 获取工作流统计
            workflow_stats = await self._get_workflow_statistics()
            task_stats = await self._get_task_statistics()
            
            # 更新指标
            self.metrics['workflows'] = workflow_stats
            self.metrics['tasks'] = task_stats
            
            # 计算成功率
            total_workflows = workflow_stats['total']
            completed_workflows = workflow_stats['completed']
            
            if total_workflows > 0:
                self.metrics['performance']['success_rate'] = (
                    completed_workflows / total_workflows
                ) * 100
            
            logger.debug(f"更新基础指标: 工作流总数={total_workflows}, 任务总数={task_stats['total']}")
            
        except Exception as e:
            logger.error(f"更新基础指标失败: {e}")
    
    async def _get_workflow_statistics(self) -> Dict[str, int]:
        """获取工作流统计"""
        try:
            # 获取所有运行中的实例
            running_instances = await self.workflow_instance_repo.get_running_instances(1000)
            
            # 统计各状态的工作流数量（这里简化处理）
            stats = {
                'total': 0,
                'running': len(running_instances),
                'completed': 0,
                'failed': 0,
                'cancelled': 0,
                'paused': 0
            }
            
            # 实际应该查询数据库获取完整统计
            # 这里使用简化逻辑
            stats['total'] = stats['running'] + 100  # 模拟数据
            stats['completed'] = 80
            stats['failed'] = 15
            stats['cancelled'] = 5
            
            return stats
            
        except Exception as e:
            logger.error(f"获取工作流统计失败: {e}")
            return {'total': 0, 'running': 0, 'completed': 0, 'failed': 0, 'cancelled': 0}
    
    async def _get_task_statistics(self) -> Dict[str, int]:
        """获取任务统计"""
        try:
            # 获取任务统计（全局）
            task_stats = await self.task_instance_repo.get_task_statistics()
            
            stats = {
                'total': task_stats.get('total_tasks', 0),
                'pending': task_stats.get('pending_tasks', 0),
                'in_progress': task_stats.get('in_progress_tasks', 0),
                'completed': task_stats.get('completed_tasks', 0),
                'failed': task_stats.get('failed_tasks', 0),
                'cancelled': 0  # 需要添加到统计查询中
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取任务统计失败: {e}")
            return {'total': 0, 'pending': 0, 'in_progress': 0, 'completed': 0, 'failed': 0, 'cancelled': 0}
    
    async def _check_anomalies(self):
        """检查异常情况"""
        try:
            # 检查失败率
            await self._check_failure_rate()
            
            # 检查队列堆积
            await self._check_queue_buildup()
            
            # 检查系统资源
            await self._check_system_resources()
            
        except Exception as e:
            logger.error(f"检查异常情况失败: {e}")
    
    async def _check_failure_rate(self):
        """检查失败率"""
        try:
            failed_tasks = self.metrics['tasks']['failed']
            total_tasks = self.metrics['tasks']['total']
            
            if total_tasks > 0:
                failure_rate = failed_tasks / total_tasks
                
                if failure_rate > self.alert_thresholds['failed_task_rate']:
                    await self._create_alert(
                        'high_failure_rate',
                        f"任务失败率过高: {failure_rate:.2%}",
                        'warning'
                    )
                    
        except Exception as e:
            logger.error(f"检查失败率失败: {e}")
    
    async def _check_queue_buildup(self):
        """检查队列堆积"""
        try:
            pending_tasks = self.metrics['tasks']['pending']
            
            if pending_tasks > self.alert_thresholds['queue_size_threshold']:
                await self._create_alert(
                    'queue_buildup',
                    f"待处理任务队列堆积: {pending_tasks} 个任务",
                    'warning'
                )
                
        except Exception as e:
            logger.error(f"检查队列堆积失败: {e}")
    
    async def _check_system_resources(self):
        """检查系统资源"""
        try:
            # 这里可以添加系统资源检查
            # 如内存使用率、CPU使用率、数据库连接数等
            pass
            
        except Exception as e:
            logger.error(f"检查系统资源失败: {e}")
    
    async def _collect_metrics(self):
        """收集详细指标"""
        while self.is_monitoring:
            try:
                # 每5分钟收集一次详细指标
                await asyncio.sleep(300)
                
                # 收集性能指标
                await self._collect_performance_metrics()
                
                # 收集业务指标
                await self._collect_business_metrics()
                
            except Exception as e:
                logger.error(f"收集指标失败: {e}")
                await asyncio.sleep(60)
    
    async def _collect_performance_metrics(self):
        """收集性能指标"""
        try:
            # 获取平均执行时间
            task_stats = await self.task_instance_repo.get_task_statistics()
            
            avg_duration = task_stats.get('average_duration')
            if avg_duration:
                self.metrics['performance']['avg_task_duration'] = float(avg_duration)
            
            logger.debug(f"收集性能指标: 平均任务执行时间={avg_duration}分钟")
            
        except Exception as e:
            logger.error(f"收集性能指标失败: {e}")
    
    async def _collect_business_metrics(self):
        """收集业务指标"""
        try:
            # 这里可以添加业务相关的指标收集
            # 如用户活跃度、工作流类型分布等
            pass
            
        except Exception as e:
            logger.error(f"收集业务指标失败: {e}")
    
    async def _check_timeouts(self):
        """检查超时任务和工作流"""
        while self.is_monitoring:
            try:
                # 每10分钟检查一次超时
                await asyncio.sleep(600)
                
                # 检查超时工作流
                await self._check_workflow_timeouts()
                
                # 检查超时任务
                await self._check_task_timeouts()
                
            except Exception as e:
                logger.error(f"检查超时失败: {e}")
                await asyncio.sleep(60)
    
    async def _check_workflow_timeouts(self):
        """检查超时工作流"""
        try:
            # 获取运行中的工作流实例
            running_instances = await self.workflow_instance_repo.get_running_instances(100)
            
            # 确保超时阈值是数值类型
            timeout_minutes = self.alert_thresholds['workflow_timeout_minutes']
            if isinstance(timeout_minutes, str):
                try:
                    timeout_minutes = int(timeout_minutes)
                except ValueError:
                    logger.warning(f"无法转换workflow_timeout_minutes为整数: {timeout_minutes}，使用默认值60")
                    timeout_minutes = 60
            
            timeout_threshold = datetime.now() - timedelta(minutes=timeout_minutes)
            
            for instance in running_instances:
                started_at = instance.get('started_at')
                if started_at:
                    try:
                        if isinstance(started_at, str):
                            start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                        else:
                            # 假设是datetime对象
                            start_time = started_at
                        
                        if start_time.replace(tzinfo=None) < timeout_threshold:
                            await self._create_alert(
                                'workflow_timeout',
                                f"工作流实例 {instance['instance_id']} 执行超时",
                                'error',
                                {'instance_id': instance['instance_id']}
                            )
                    except (ValueError, TypeError) as e:
                        logger.warning(f"解析工作流开始时间失败: {started_at}, 错误: {e}")
                        
        except Exception as e:
            logger.error(f"检查工作流超时失败: {e}")
    
    async def _check_task_timeouts(self):
        """检查超时任务"""
        try:
            # 获取进行中的任务
            in_progress_tasks = await self.task_instance_repo.get_tasks_by_workflow_instance(
                None, TaskInstanceStatus.IN_PROGRESS
            )
            
            # 确保超时阈值是数值类型
            task_timeout_minutes = self.alert_thresholds['task_timeout_minutes']
            if isinstance(task_timeout_minutes, str):
                try:
                    task_timeout_minutes = int(task_timeout_minutes)
                except ValueError:
                    logger.warning(f"无法转换task_timeout_minutes为整数: {task_timeout_minutes}，使用默认值30")
                    task_timeout_minutes = 30
            
            timeout_threshold = datetime.now() - timedelta(minutes=task_timeout_minutes)
            
            for task in in_progress_tasks:
                started_at = task.get('started_at')
                if started_at:
                    try:
                        if isinstance(started_at, str):
                            start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                        else:
                            # 假设是datetime对象
                            start_time = started_at
                        
                        if start_time.replace(tzinfo=None) < timeout_threshold:
                            await self._create_alert(
                                'task_timeout',
                                f"任务 {task['task_instance_id']} 执行超时",
                                'warning',
                                {'task_id': task['task_instance_id']}
                            )
                    except (ValueError, TypeError) as e:
                        logger.warning(f"解析任务开始时间失败: {started_at}, 错误: {e}")
                        
        except Exception as e:
            logger.error(f"检查任务超时失败: {e}")
    
    async def _performance_analysis(self):
        """性能分析"""
        while self.is_monitoring:
            try:
                # 每小时进行一次性能分析
                await asyncio.sleep(3600)
                
                # 分析执行趋势
                await self._analyze_execution_trends()
                
                # 分析瓶颈
                await self._analyze_bottlenecks()
                
            except Exception as e:
                logger.error(f"性能分析失败: {e}")
                await asyncio.sleep(300)
    
    async def _analyze_execution_trends(self):
        """分析执行趋势"""
        try:
            # 这里可以分析执行时间趋势、成功率趋势等
            logger.info("执行趋势分析完成")
            
        except Exception as e:
            logger.error(f"分析执行趋势失败: {e}")
    
    async def _analyze_bottlenecks(self):
        """分析瓶颈"""
        try:
            # 分析可能的瓶颈点
            # 如某些节点类型执行时间过长、某些Agent响应慢等
            logger.info("瓶颈分析完成")
            
        except Exception as e:
            logger.error(f"分析瓶颈失败: {e}")
    
    async def _real_time_status_sync(self):
        """实时状态同步 - 每5秒主动检查运行中工作流的状态变化"""
        while self.is_monitoring:
            try:
                # 获取所有运行中的工作流
                running_workflows = await self.workflow_instance_repo.db.fetch_all("""
                    SELECT workflow_instance_id, workflow_instance_name, status, updated_at
                    FROM workflow_instance 
                    WHERE status IN ('RUNNING', 'PENDING')
                    AND is_deleted = FALSE
                    AND status NOT IN ('cancelled', 'CANCELLED', 'failed', 'FAILED')
                    ORDER BY updated_at DESC
                """)
                
                if running_workflows:
                    logger.trace(f"🔄 [实时同步] 检查 {len(running_workflows)} 个运行中的工作流状态")
                    
                    for workflow in running_workflows:
                        workflow_id = workflow['workflow_instance_id']
                        
                        # 检查节点实例状态是否有变化
                        nodes_status = await self.workflow_instance_repo.db.fetch_all("""
                            SELECT node_instance_id, status, updated_at
                            FROM node_instance 
                            WHERE workflow_instance_id = $1 
                            AND is_deleted = FALSE
                            ORDER BY updated_at DESC
                        """, workflow_id)
                        
                        completed_nodes = sum(1 for n in nodes_status if n['status'] == 'completed')
                        total_nodes = len(nodes_status)
                        
                        # 如果所有节点都完成了，但工作流状态还是RUNNING，立即更新
                        if total_nodes > 0 and completed_nodes == total_nodes and workflow['status'] == 'RUNNING':
                            logger.info(f"🎯 [实时同步] 发现完成的工作流需要状态更新: {workflow['workflow_instance_name']}")
                            
                            # 触发状态更新（通过执行引擎）
                            try:
                                from .execution_service import execution_engine
                                # 🔧 修复：调用执行引擎的方法，而不是context_manager的方法
                                await execution_engine._check_workflow_completion(workflow_id)
                            except Exception as sync_error:
                                logger.error(f"实时同步触发状态更新失败: {sync_error}")
                
                # 每5秒检查一次，保持高实时性
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"实时状态同步失败: {e}")
                await asyncio.sleep(10)  # 错误时等待10秒再重试
    
    async def _create_alert(self, alert_type: str, message: str, 
                          severity: str, context: Optional[Dict[str, Any]] = None):
        """创建告警"""
        try:
            alert = {
                'id': str(uuid.uuid4()),
                'type': alert_type,
                'message': message,
                'severity': severity,
                'context': context or {},
                'created_at': now_utc(),
                'acknowledged': False
            }
            
            self.alerts.append(alert)
            
            # 限制告警历史数量
            if len(self.alerts) > 1000:
                self.alerts = self.alerts[-500:]
            
            logger.warning(f"创建告警: [{severity}] {message}")
            
            # 这里可以添加告警通知逻辑
            # 如发送邮件、发送到监控系统等
            
        except Exception as e:
            logger.error(f"创建告警失败: {e}")
    
    async def get_current_metrics(self) -> Dict[str, Any]:
        """获取当前指标"""
        try:
            await self._update_basic_metrics()
            
            return {
                'metrics': self.metrics,
                'alerts': {
                    'total': len(self.alerts),
                    'unacknowledged': len([a for a in self.alerts if not a['acknowledged']]),
                    'recent': self.alerts[-10:] if self.alerts else []
                },
                'system_status': {
                    'monitoring_active': self.is_monitoring,
                    'last_check': now_utc()
                }
            }
            
        except Exception as e:
            logger.error(f"获取当前指标失败: {e}")
            raise
    
    async def get_workflow_health(self, instance_id: uuid.UUID) -> Dict[str, Any]:
        """获取工作流健康状态"""
        try:
            # 获取工作流实例信息
            instance = await self.workflow_instance_repo.get_instance_by_id(instance_id)
            if not instance:
                raise ValueError("工作流实例不存在")
            
            # 获取执行统计
            stats = await self.workflow_instance_repo.get_execution_statistics(instance_id)
            
            # 计算健康分数
            health_score = await self._calculate_health_score(instance, stats)
            
            # 识别问题
            issues = await self._identify_issues(instance, stats)
            
            return {
                'instance_id': instance_id,
                'health_score': health_score,
                'status': instance['status'],
                'statistics': stats,
                'issues': issues,
                'recommendations': await self._generate_recommendations(issues)
            }
            
        except Exception as e:
            logger.error(f"获取工作流健康状态失败: {e}")
            raise
    
    async def _calculate_health_score(self, instance: Dict[str, Any], 
                                    stats: Optional[Dict[str, Any]]) -> float:
        """计算健康分数"""
        try:
            score = 100.0
            
            # 根据状态扣分
            status = instance['status']
            if status == WorkflowInstanceStatus.FAILED.value:
                score -= 50
            elif status == WorkflowInstanceStatus.PAUSED.value:
                score -= 20
            
            # 根据任务失败率扣分
            if stats:
                total_tasks = stats.get('total_tasks', 0)
                failed_tasks = stats.get('failed_tasks', 0)
                
                if total_tasks > 0:
                    failure_rate = failed_tasks / total_tasks
                    score -= failure_rate * 30
            
            # 根据执行时间扣分
            if instance.get('started_at') and not instance.get('completed_at'):
                started_at = datetime.fromisoformat(instance['started_at'].replace('Z', '+00:00'))
                running_time = datetime.now().replace(tzinfo=started_at.tzinfo) - started_at
                running_hours = running_time.total_seconds() / 3600
                
                if running_hours > 2:  # 运行超过2小时
                    score -= min(running_hours * 5, 30)
            
            return max(score, 0.0)
            
        except Exception as e:
            logger.error(f"计算健康分数失败: {e}")
            return 50.0
    
    async def _identify_issues(self, instance: Dict[str, Any], 
                             stats: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """识别问题"""
        issues = []
        
        try:
            # 检查状态问题
            if instance['status'] == WorkflowInstanceStatus.FAILED.value:
                issues.append({
                    'type': 'workflow_failed',
                    'severity': 'error',
                    'message': '工作流执行失败',
                    'details': instance.get('error_message', '')
                })
            
            # 检查任务问题
            if stats:
                failed_tasks = stats.get('failed_tasks', 0)
                if failed_tasks > 0:
                    issues.append({
                        'type': 'failed_tasks',
                        'severity': 'warning',
                        'message': f'存在 {failed_tasks} 个失败任务',
                        'details': f'失败任务数量: {failed_tasks}'
                    })
                
                pending_tasks = stats.get('pending_tasks', 0)
                if pending_tasks > 10:
                    issues.append({
                        'type': 'task_backlog',
                        'severity': 'warning',
                        'message': f'待处理任务积压: {pending_tasks} 个',
                        'details': f'待处理任务数量: {pending_tasks}'
                    })
            
            return issues
            
        except Exception as e:
            logger.error(f"识别问题失败: {e}")
            return issues
    
    async def _generate_recommendations(self, issues: List[Dict[str, Any]]) -> List[str]:
        """生成建议"""
        recommendations = []
        
        try:
            for issue in issues:
                issue_type = issue['type']
                
                if issue_type == 'workflow_failed':
                    recommendations.append("检查工作流定义和输入数据")
                    recommendations.append("查看错误日志确定失败原因")
                elif issue_type == 'failed_tasks':
                    recommendations.append("检查失败任务的错误信息")
                    recommendations.append("考虑重试失败的任务")
                elif issue_type == 'task_backlog':
                    recommendations.append("检查Agent服务是否正常运行")
                    recommendations.append("考虑增加处理器并发数量")
            
            if not recommendations:
                recommendations.append("工作流运行正常，无需特别处理")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"生成建议失败: {e}")
            return ["请联系系统管理员"]
    
    async def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警"""
        try:
            for alert in self.alerts:
                if alert['id'] == alert_id:
                    alert['acknowledged'] = True
                    alert['acknowledged_at'] = now_utc()
                    logger.info(f"告警已确认: {alert_id}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"确认告警失败: {e}")
            return False
    
    async def get_performance_report(self, days: int = 7) -> Dict[str, Any]:
        """获取性能报告"""
        try:
            # 这里应该从历史数据生成性能报告
            # 简化实现，返回当前指标
            
            report = {
                'period': f'最近 {days} 天',
                'summary': {
                    'total_workflows': self.metrics['workflows']['total'],
                    'success_rate': self.metrics['performance']['success_rate'],
                    'avg_task_duration': self.metrics['performance']['avg_task_duration']
                },
                'trends': {
                    'workflow_count': [10, 15, 12, 18, 20, 16, 14],  # 模拟数据
                    'success_rate': [95, 94, 96, 93, 97, 95, 96],      # 模拟数据
                    'avg_duration': [25, 23, 27, 22, 24, 26, 23]       # 模拟数据
                },
                'generated_at': now_utc()
            }
            
            return report
            
        except Exception as e:
            logger.error(f"获取性能报告失败: {e}")
            raise
    
    async def register_workflow_completion_callback(self, workflow_instance_id: uuid.UUID, 
                                                   callback_func) -> bool:
        """注册工作流完成回调"""
        try:
            logger.info(f"🔔 注册工作流完成回调: {workflow_instance_id}")
            
            if workflow_instance_id not in self.workflow_completion_callbacks:
                self.workflow_completion_callbacks[workflow_instance_id] = []
            
            self.workflow_completion_callbacks[workflow_instance_id].append(callback_func)
            
            logger.info(f"✅ 工作流完成回调注册成功: {workflow_instance_id}")
            logger.info(f"   - 该工作流现有回调数量: {len(self.workflow_completion_callbacks[workflow_instance_id])}")
            
            return True
            
        except Exception as e:
            logger.error(f"注册工作流完成回调失败: {e}")
            return False
    
    async def _check_workflow_completion_and_trigger_callbacks(self):
        """检查工作流完成状态并触发回调"""
        try:
            if not self.workflow_completion_callbacks:
                return
            
            # 检查注册了回调的工作流状态
            for workflow_instance_id, callbacks in list(self.workflow_completion_callbacks.items()):
                try:
                    # 查询工作流状态
                    workflow_instance = await self.workflow_instance_repo.get_workflow_instance_by_id(workflow_instance_id)
                    
                    if not workflow_instance:
                        # 工作流不存在，清理回调
                        logger.warning(f"工作流实例不存在，清理回调: {workflow_instance_id}")
                        del self.workflow_completion_callbacks[workflow_instance_id]
                        continue
                    
                    status = workflow_instance.get('status')
                    
                    # 检查是否已完成（成功、失败或取消）
                    if status in ['completed', 'failed', 'cancelled', 'timeout']:
                        logger.info(f"🎯 检测到工作流完成: {workflow_instance_id}, 状态: {status}")
                        
                        # 收集执行结果
                        results = await self._collect_workflow_results(workflow_instance_id)
                        
                        # 触发所有回调
                        for callback in callbacks:
                            try:
                                await callback(workflow_instance_id, status, results)
                                logger.info(f"✅ 工作流完成回调执行成功: {workflow_instance_id}")
                            except Exception as callback_e:
                                logger.error(f"工作流完成回调执行失败: {callback_e}")
                        
                        # 清理已完成的工作流回调
                        del self.workflow_completion_callbacks[workflow_instance_id]
                        logger.info(f"🧹 已清理工作流回调: {workflow_instance_id}")
                
                except Exception as check_e:
                    logger.error(f"检查工作流完成状态失败: {workflow_instance_id}, 错误: {check_e}")
                    
        except Exception as e:
            logger.error(f"检查工作流完成状态和触发回调失败: {e}")
    
    async def _collect_workflow_results(self, workflow_instance_id: uuid.UUID) -> Dict[str, Any]:
        """收集工作流执行结果"""
        try:
            logger.info(f"🔍 收集工作流执行结果: {workflow_instance_id}")
            
            # 获取工作流实例信息
            workflow_instance = await self.workflow_instance_repo.get_workflow_instance_by_id(workflow_instance_id)
            
            # 获取该工作流的所有任务
            tasks = await self.task_instance_repo.get_tasks_by_workflow_instance(workflow_instance_id)
            
            # 统计任务完成情况
            total_tasks = len(tasks)
            completed_tasks = len([t for t in tasks if t.get('status') == 'completed'])
            failed_tasks = len([t for t in tasks if t.get('status') == 'failed'])
            
            logger.info(f"📊 任务统计: 总计 {total_tasks}, 完成 {completed_tasks}, 失败 {failed_tasks}")
            
            # 收集任务结果
            task_results = []
            
            for task in tasks:
                task_result = {
                    'task_id': task.get('task_instance_id'),
                    'title': task.get('task_title'),
                    'status': task.get('status'),
                    'output': task.get('output_data', ''),
                    'result_summary': task.get('result_summary', '')
                }
                task_results.append(task_result)
            
            # 🔧 新增：查找结束节点的输出数据，获取完整的工作流上下文
            end_node_output = None
            end_nodes_query = """
            SELECT ni.output_data, n.name as node_name, ni.node_instance_id
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.workflow_instance_id = %s 
            AND n.type = 'end'
            AND ni.status = 'completed'
            ORDER BY ni.updated_at DESC
            LIMIT 1
            """
            
            try:
                end_node = await self.workflow_instance_repo.db.fetch_one(end_nodes_query, workflow_instance_id)
                if end_node and end_node['output_data']:
                    end_node_output = end_node['output_data']
                    logger.info(f"✅ 找到结束节点输出: {end_node['node_name']}, 数据长度: {len(str(end_node_output))} 字符")
                else:
                    logger.warning(f"⚠️ 未找到结束节点输出数据")
            except Exception as end_node_e:
                logger.error(f"❌ 查询结束节点失败: {end_node_e}")
            
            # 🔧 确定最终输出：优先使用结束节点输出，否则使用任务输出拼接
            final_output = ""
            if end_node_output:
                # 如果结束节点有输出，使用结束节点的完整上下文
                if isinstance(end_node_output, dict):
                    # 如果是字典，尝试获取完整上下文或格式化输出
                    if 'full_context' in end_node_output:
                        final_output = str(end_node_output['full_context'])
                    elif 'context_data' in end_node_output:
                        final_output = str(end_node_output['context_data'])
                    else:
                        # 格式化字典输出
                        final_output = self._format_dict_output(end_node_output)
                else:
                    # 如果是字符串，直接使用
                    final_output = str(end_node_output)
                
                logger.info(f"📋 使用结束节点输出作为最终结果，长度: {len(final_output)} 字符")
            else:
                # 回退到原来的逻辑：收集所有完成任务的输出
                final_outputs = []
                for task in tasks:
                    if task.get('status') == 'completed' and task.get('output_data'):
                        final_outputs.append(str(task.get('output_data')))
                
                final_output = '\n\n=== 任务输出分隔 ===\n\n'.join(final_outputs) if final_outputs else ''
                logger.info(f"📋 使用任务输出拼接作为最终结果，长度: {len(final_output)} 字符")
            
            # 构建结果对象
            results = {
                'workflow_instance_id': str(workflow_instance_id),
                'status': workflow_instance.get('status'),
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'failed_tasks': failed_tasks,
                'task_results': task_results,
                'final_output': final_output,
                'has_end_node_output': end_node_output is not None,
                'execution_duration': self._calculate_execution_duration(workflow_instance),
                'started_at': workflow_instance.get('created_at'),
                'completed_at': workflow_instance.get('updated_at')
            }
            
            logger.info(f"✅ 工作流结果收集完成，最终输出长度: {len(final_output)} 字符")
            return results
            
        except Exception as e:
            logger.error(f"收集工作流执行结果失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return {}
    
    def _format_dict_output(self, data: dict) -> str:
        """格式化字典输出为可读文本"""
        try:
            if not data:
                return "无输出数据"
            
            # 尝试格式化为可读文本
            output_parts = []
            
            for key, value in data.items():
                if key.startswith('_'):  # 跳过私有字段
                    continue
                
                if isinstance(value, dict):
                    output_parts.append(f"**{key}:**")
                    for sub_key, sub_value in value.items():
                        output_parts.append(f"  • {sub_key}: {str(sub_value)}")
                elif isinstance(value, list):
                    output_parts.append(f"**{key}:** ({len(value)} 项)")
                    for i, item in enumerate(value[:5]):  # 只显示前5项
                        output_parts.append(f"  {i+1}. {str(item)}")
                    if len(value) > 5:
                        output_parts.append(f"  ... 还有 {len(value) - 5} 项")
                else:
                    output_parts.append(f"**{key}:** {str(value)}")
            
            return "\n".join(output_parts)
            
        except Exception as e:
            logger.error(f"格式化字典输出失败: {e}")
            return str(data)
    
    def _calculate_execution_duration(self, workflow_instance: Dict[str, Any]) -> str:
        """计算执行时长"""
        try:
            started_at = workflow_instance.get('created_at')
            completed_at = workflow_instance.get('updated_at')
            
            if started_at and completed_at:
                if isinstance(started_at, str):
                    started_at = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                if isinstance(completed_at, str):
                    completed_at = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                
                duration = completed_at - started_at
                
                hours = duration.seconds // 3600
                minutes = (duration.seconds % 3600) // 60
                seconds = duration.seconds % 60
                
                if hours > 0:
                    return f"{hours}小时{minutes}分钟{seconds}秒"
                elif minutes > 0:
                    return f"{minutes}分钟{seconds}秒"
                else:
                    return f"{seconds}秒"
            
            return "未知"
            
        except Exception as e:
            logger.error(f"计算执行时长失败: {e}")
            return "未知"


# 全局监控服务实例
monitoring_service = MonitoringService()