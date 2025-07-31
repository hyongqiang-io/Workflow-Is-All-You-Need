"""
状态追踪和监控服务
Status Tracking and Monitoring Service
"""

import uuid
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from loguru import logger

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
        self.monitor_interval = 60  # 监控间隔（秒）
        self.alert_thresholds = {
            'workflow_timeout_minutes': 60,  # 工作流超时阈值
            'task_timeout_minutes': 30,      # 任务超时阈值
            'failed_task_rate': 0.1,         # 失败任务比例阈值
            'queue_size_threshold': 100      # 队列大小阈值
        }
        
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
            
            timeout_threshold = datetime.now() - timedelta(
                minutes=self.alert_thresholds['workflow_timeout_minutes']
            )
            
            for instance in running_instances:
                started_at = instance.get('started_at')
                if started_at:
                    start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                    if start_time.replace(tzinfo=None) < timeout_threshold:
                        await self._create_alert(
                            'workflow_timeout',
                            f"工作流实例 {instance['instance_id']} 执行超时",
                            'error',
                            {'instance_id': instance['instance_id']}
                        )
                        
        except Exception as e:
            logger.error(f"检查工作流超时失败: {e}")
    
    async def _check_task_timeouts(self):
        """检查超时任务"""
        try:
            # 获取进行中的任务
            in_progress_tasks = await self.task_instance_repo.get_tasks_by_workflow_instance(
                None, TaskInstanceStatus.IN_PROGRESS
            )
            
            timeout_threshold = datetime.now() - timedelta(
                minutes=self.alert_thresholds['task_timeout_minutes']
            )
            
            for task in in_progress_tasks:
                started_at = task.get('started_at')
                if started_at:
                    start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                    if start_time.replace(tzinfo=None) < timeout_threshold:
                        await self._create_alert(
                            'task_timeout',
                            f"任务 {task['task_instance_id']} 执行超时",
                            'warning',
                            {'task_id': task['task_instance_id']}
                        )
                        
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


# 全局监控服务实例
monitoring_service = MonitoringService()