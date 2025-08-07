"""
工作流输出数据处理器
Output Data Processor for Workflow Results
"""

import uuid
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from ..models.instance import (
    WorkflowOutputSummary, ExecutionResult, ExecutionStatistics,
    QualityMetrics, DataLineage, DataLineageStep, ExecutionIssues,
    WorkflowInstanceStatus, NodeInstanceStatus, TaskInstanceStatus
)
from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
from ..repositories.instance.node_instance_repository import NodeInstanceRepository
from ..repositories.instance.task_instance_repository import TaskInstanceRepository
from ..utils.helpers import now_utc


class OutputDataProcessor:
    """工作流输出数据处理器"""
    
    def __init__(self):
        self.workflow_repo = WorkflowInstanceRepository()
        self.node_repo = NodeInstanceRepository()
        self.task_repo = TaskInstanceRepository()
    
    async def generate_workflow_output_summary(self, workflow_instance_id: uuid.UUID) -> Optional[WorkflowOutputSummary]:
        """生成工作流输出摘要"""
        try:
            logger.info(f"🔄 开始生成工作流输出摘要: {workflow_instance_id}")
            
            # 获取工作流实例信息
            workflow_instance = await self.workflow_repo.get_instance_by_id(workflow_instance_id)
            if not workflow_instance:
                logger.error(f"❌ 工作流实例不存在: {workflow_instance_id}")
                return None
            
            # 获取节点实例列表
            node_instances = await self.node_repo.get_instances_by_workflow(workflow_instance_id)
            
            # 获取任务实例列表
            task_instances = await self.task_repo.get_instances_by_workflow(workflow_instance_id)
            
            logger.info(f"📊 统计信息: 节点数={len(node_instances)}, 任务数={len(task_instances)}")
            
            # 生成各个组件
            execution_result = await self._generate_execution_result(workflow_instance, node_instances, task_instances)
            execution_stats = await self._generate_execution_statistics(workflow_instance_id, workflow_instance, node_instances, task_instances)
            quality_metrics = await self._generate_quality_metrics(workflow_instance, node_instances, task_instances)
            data_lineage = await self._generate_data_lineage(workflow_instance, node_instances)
            issues = await self._generate_execution_issues(workflow_instance, node_instances, task_instances)
            
            # 构建输出摘要
            output_summary = WorkflowOutputSummary(
                execution_result=execution_result,
                execution_stats=execution_stats,
                quality_metrics=quality_metrics,
                data_lineage=data_lineage,
                issues=issues,
                generated_at=datetime.utcnow()
            )
            
            logger.info(f"✅ 工作流输出摘要生成完成: {workflow_instance_id}")
            return output_summary
            
        except Exception as e:
            logger.error(f"❌ 生成工作流输出摘要失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return None
    
    async def _generate_execution_result(self, workflow_instance: Dict[str, Any], 
                                       node_instances: List[Dict[str, Any]], 
                                       task_instances: List[Dict[str, Any]]) -> ExecutionResult:
        """生成执行结果"""
        try:
            # 分析工作流状态
            status = workflow_instance.get('status')
            if status == WorkflowInstanceStatus.COMPLETED.value:
                result_type = "success"
            elif status == WorkflowInstanceStatus.FAILED.value:
                result_type = "failure"
            elif status in [WorkflowInstanceStatus.CANCELLED.value]:
                result_type = "failure"
            else:
                # 部分完成的情况
                completed_nodes = len([n for n in node_instances if n.get('status') == NodeInstanceStatus.COMPLETED.value])
                total_nodes = len(node_instances)
                if completed_nodes > 0 and completed_nodes < total_nodes:
                    result_type = "partial_success"
                else:
                    result_type = "failure"
            
            # 统计处理数量
            processed_count = len([t for t in task_instances if t.get('status') in [
                TaskInstanceStatus.COMPLETED.value, TaskInstanceStatus.FAILED.value
            ]])
            success_count = len([t for t in task_instances if t.get('status') == TaskInstanceStatus.COMPLETED.value])
            error_count = len([t for t in task_instances if t.get('status') == TaskInstanceStatus.FAILED.value])
            
            # 聚合业务输出数据
            data_output = {}
            if workflow_instance.get('output_data'):
                data_output = workflow_instance['output_data']
            
            # 如果工作流没有输出数据，尝试聚合节点输出
            if not data_output:
                node_outputs = {}
                for node in node_instances:
                    if node.get('output_data'):
                        node_name = node.get('node_instance_name', f"node_{node.get('node_instance_id')}")
                        node_output_data = node['output_data']
                        
                        # 优化：提取主要输出数据
                        if isinstance(node_output_data, dict):
                            # 如果有primary_output，优先使用
                            if 'primary_output' in node_output_data:
                                node_outputs[node_name] = node_output_data['primary_output']
                            # 如果有tasks_output且只有一个任务，直接提升
                            elif 'tasks_output' in node_output_data and len(node_output_data.get('tasks_output', {})) == 1:
                                task_outputs = list(node_output_data['tasks_output'].values())
                                node_outputs[node_name] = task_outputs[0] if task_outputs else node_output_data
                            else:
                                node_outputs[node_name] = node_output_data
                        else:
                            node_outputs[node_name] = node_output_data
                            
                if node_outputs:
                    data_output = {"aggregated_node_outputs": node_outputs}
                    # 如果只有一个节点输出，直接提升到顶层
                    if len(node_outputs) == 1:
                        single_output = list(node_outputs.values())[0]
                        if isinstance(single_output, dict):
                            data_output.update(single_output)
                            data_output["primary_node_output"] = single_output
            
            return ExecutionResult(
                result_type=result_type,
                processed_count=processed_count,
                success_count=success_count,
                error_count=error_count,
                data_output=data_output
            )
            
        except Exception as e:
            logger.error(f"❌ 生成执行结果失败: {e}")
            return ExecutionResult(
                result_type="failure",
                processed_count=0,
                success_count=0,
                error_count=1,
                data_output={"error": str(e)}
            )
    
    async def _generate_execution_statistics(self, workflow_instance_id: uuid.UUID,
                                           workflow_instance: Dict[str, Any],
                                           node_instances: List[Dict[str, Any]], 
                                           task_instances: List[Dict[str, Any]]) -> ExecutionStatistics:
        """生成执行统计信息"""
        try:
            # 节点统计
            total_nodes = len(node_instances)
            completed_nodes = len([n for n in node_instances if n.get('status') == NodeInstanceStatus.COMPLETED.value])
            failed_nodes = len([n for n in node_instances if n.get('status') == NodeInstanceStatus.FAILED.value])
            pending_nodes = len([n for n in node_instances if n.get('status') in [
                NodeInstanceStatus.PENDING.value, NodeInstanceStatus.WAITING.value
            ]])
            
            # 任务统计
            total_tasks = len(task_instances)
            completed_tasks = len([t for t in task_instances if t.get('status') == TaskInstanceStatus.COMPLETED.value])
            failed_tasks = len([t for t in task_instances if t.get('status') == TaskInstanceStatus.FAILED.value])
            pending_tasks = len([t for t in task_instances if t.get('status') in [
                TaskInstanceStatus.PENDING.value, TaskInstanceStatus.ASSIGNED.value, TaskInstanceStatus.WAITING.value
            ]])
            
            # 任务类型统计
            human_tasks = len([t for t in task_instances if t.get('task_type') == 'human'])
            agent_tasks = len([t for t in task_instances if t.get('task_type') == 'agent'])
            mixed_tasks = len([t for t in task_instances if t.get('task_type') == 'mixed'])
            
            # 计算平均任务时长
            completed_task_durations = []
            for task in task_instances:
                if task.get('actual_duration'):
                    completed_task_durations.append(task['actual_duration'])
            
            average_task_duration = None
            if completed_task_durations:
                average_task_duration = sum(completed_task_durations) / len(completed_task_durations)
            
            # 计算总执行时间
            total_execution_time = None
            total_duration_minutes = None
            if workflow_instance.get('started_at') and workflow_instance.get('completed_at'):
                start_time = datetime.fromisoformat(workflow_instance['started_at'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(workflow_instance['completed_at'].replace('Z', '+00:00'))
                total_execution_time = int((end_time - start_time).total_seconds())
                total_duration_minutes = int(total_execution_time / 60)
            
            # 计算平均节点执行时长
            average_node_duration = None
            if total_duration_minutes and completed_nodes > 0:
                average_node_duration = total_duration_minutes / completed_nodes
            
            return ExecutionStatistics(
                workflow_instance_id=workflow_instance_id,
                total_nodes=total_nodes,
                completed_nodes=completed_nodes,
                failed_nodes=failed_nodes,
                pending_nodes=pending_nodes,
                total_tasks=total_tasks,
                completed_tasks=completed_tasks,
                failed_tasks=failed_tasks,
                pending_tasks=pending_tasks,
                human_tasks=human_tasks,
                agent_tasks=agent_tasks,
                mixed_tasks=mixed_tasks,
                average_task_duration=average_task_duration,
                total_execution_time=total_execution_time,
                total_duration_minutes=total_duration_minutes,
                average_node_duration=average_node_duration
            )
            
        except Exception as e:
            logger.error(f"❌ 生成执行统计失败: {e}")
            return ExecutionStatistics(
                workflow_instance_id=workflow_instance_id,
                total_nodes=0, completed_nodes=0, failed_nodes=0, pending_nodes=0,
                total_tasks=0, completed_tasks=0, failed_tasks=0, pending_tasks=0,
                human_tasks=0, agent_tasks=0, mixed_tasks=0
            )
    
    async def _generate_quality_metrics(self, workflow_instance: Dict[str, Any],
                                      node_instances: List[Dict[str, Any]], 
                                      task_instances: List[Dict[str, Any]]) -> QualityMetrics:
        """生成质量评估指标"""
        try:
            validation_errors = []
            
            # 数据完整性评估
            total_outputs = 0
            valid_outputs = 0
            
            for node in node_instances:
                total_outputs += 1
                if node.get('output_data') and node.get('status') == NodeInstanceStatus.COMPLETED.value:
                    valid_outputs += 1
                elif node.get('status') == NodeInstanceStatus.FAILED.value:
                    validation_errors.append(f"节点 {node.get('node_instance_name', 'unknown')} 执行失败")
            
            data_completeness = valid_outputs / total_outputs if total_outputs > 0 else 0.0
            
            # 准确性评分（基于成功率）
            total_tasks = len(task_instances)
            successful_tasks = len([t for t in task_instances if t.get('status') == TaskInstanceStatus.COMPLETED.value])
            accuracy_score = successful_tasks / total_tasks if total_tasks > 0 else 0.0
            
            # 质量门禁检查
            quality_gates_passed = (
                data_completeness >= 0.8 and  # 数据完整性至少80%
                accuracy_score >= 0.8 and     # 准确性至少80%
                len(validation_errors) == 0   # 无验证错误
            )
            
            # 整体质量评分
            overall_quality_score = (data_completeness + accuracy_score) / 2
            
            return QualityMetrics(
                data_completeness=data_completeness,
                accuracy_score=accuracy_score,
                validation_errors=validation_errors,
                quality_gates_passed=quality_gates_passed,
                overall_quality_score=overall_quality_score
            )
            
        except Exception as e:
            logger.error(f"❌ 生成质量评估指标失败: {e}")
            return QualityMetrics(
                data_completeness=0.0,
                accuracy_score=0.0,
                validation_errors=[f"质量评估失败: {str(e)}"],
                quality_gates_passed=False,
                overall_quality_score=0.0
            )
    
    async def _generate_data_lineage(self, workflow_instance: Dict[str, Any],
                                   node_instances: List[Dict[str, Any]]) -> DataLineage:
        """生成数据血缘追溯信息"""
        try:
            # 输入来源分析
            input_sources = []
            if workflow_instance.get('input_data'):
                input_data = workflow_instance['input_data']
                if isinstance(input_data, dict):
                    for key in input_data.keys():
                        if 'file' in key.lower() or 'upload' in key.lower():
                            input_sources.append("file_upload")
                        elif 'api' in key.lower():
                            input_sources.append("api_input")
                        else:
                            input_sources.append("manual_input")
            
            if not input_sources:
                input_sources = ["workflow_input"]
            
            # 转换步骤分析
            transformation_steps = []
            for node in sorted(node_instances, key=lambda x: x.get('created_at', '')):
                if node.get('status') == NodeInstanceStatus.COMPLETED.value:
                    operations = []
                    
                    # 基于节点名称和输出数据推断操作
                    node_name = node.get('node_instance_name', 'unknown_node')
                    output_data = node.get('output_data', {})
                    
                    # 分析节点名称
                    if 'clean' in node_name.lower():
                        operations.append("data_cleaning")
                    if 'validate' in node_name.lower():
                        operations.append("data_validation")
                    if 'transform' in node_name.lower():
                        operations.append("data_transformation")
                    if 'analysis' in node_name.lower() or 'analyze' in node_name.lower():
                        operations.append("data_analysis")
                    if 'process' in node_name.lower():
                        operations.append("data_processing")
                    
                    # 分析输出数据结构以推断更多操作
                    if isinstance(output_data, dict):
                        if 'tasks_output' in output_data:
                            operations.append("task_aggregation")
                        if 'primary_output' in output_data:
                            operations.append("output_processing")
                        if 'all_tasks_completed' in output_data:
                            operations.append("completion_verification")
                    
                    if not operations:
                        operations = ["node_execution"]
                    
                    # 添加数据量信息
                    data_size_info = ""
                    if isinstance(output_data, dict):
                        task_count = output_data.get('task_count', 0)
                        if task_count > 0:
                            data_size_info = f" ({task_count} tasks processed)"
                    
                    transformation_steps.append(DataLineageStep(
                        node=node_name + data_size_info,
                        operations=operations,
                        timestamp=node.get('completed_at')
                    ))
            
            # 输出目标分析
            output_destinations = []
            if workflow_instance.get('output_data'):
                output_data = workflow_instance['output_data']
                if isinstance(output_data, dict):
                    for key in output_data.keys():
                        if 'database' in key.lower() or 'db' in key.lower():
                            output_destinations.append("database")
                        elif 'file' in key.lower() or 'report' in key.lower():
                            output_destinations.append("report_file")
                        elif 'api' in key.lower():
                            output_destinations.append("api_response")
                        else:
                            output_destinations.append("workflow_output")
            
            if not output_destinations:
                output_destinations = ["workflow_result"]
            
            return DataLineage(
                input_sources=list(set(input_sources)),  # 去重
                transformation_steps=transformation_steps,
                output_destinations=list(set(output_destinations))  # 去重
            )
            
        except Exception as e:
            logger.error(f"❌ 生成数据血缘信息失败: {e}")
            return DataLineage(
                input_sources=["unknown"],
                transformation_steps=[],
                output_destinations=["unknown"]
            )
    
    async def _generate_execution_issues(self, workflow_instance: Dict[str, Any],
                                       node_instances: List[Dict[str, Any]], 
                                       task_instances: List[Dict[str, Any]]) -> ExecutionIssues:
        """生成执行问题和警告信息"""
        try:
            errors = []
            warnings = []
            recoverable_failures = []
            
            # 工作流级别错误
            if workflow_instance.get('error_message'):
                errors.append(f"工作流错误: {workflow_instance['error_message']}")
            
            # 节点级别问题
            for node in node_instances:
                if node.get('status') == NodeInstanceStatus.FAILED.value:
                    node_name = node.get('node_instance_name', 'unknown_node')
                    if node.get('error_message'):
                        errors.append(f"节点 {node_name} 失败: {node.get('error_message')}")
                    else:
                        errors.append(f"节点 {node_name} 执行失败")
                
                # 重试次数检查
                retry_count = node.get('retry_count', 0)
                if retry_count > 0:
                    node_name = node.get('node_instance_name', 'unknown_node')
                    if retry_count >= 3:
                        warnings.append(f"节点 {node_name} 重试次数过多 ({retry_count} 次)")
                    else:
                        recoverable_failures.append(f"节点 {node_name} 经过 {retry_count} 次重试后成功")
            
            # 任务级别问题
            failed_tasks = [t for t in task_instances if t.get('status') == TaskInstanceStatus.FAILED.value]
            for task in failed_tasks:
                task_title = task.get('task_title', 'unknown_task')
                if task.get('error_message'):
                    errors.append(f"任务 {task_title} 失败: {task.get('error_message')}")
                else:
                    errors.append(f"任务 {task_title} 执行失败")
            
            # 性能警告
            long_running_tasks = [t for t in task_instances if t.get('actual_duration') and t['actual_duration'] > 60]
            for task in long_running_tasks:
                task_title = task.get('task_title', 'unknown_task')
                duration = task['actual_duration']
                warnings.append(f"任务 {task_title} 执行时间过长 ({duration} 分钟)")
            
            # 数据量警告
            total_tasks = len(task_instances)
            if total_tasks > 100:
                warnings.append(f"任务数量较多 ({total_tasks} 个)，可能影响性能")
            
            return ExecutionIssues(
                errors=errors,
                warnings=warnings,
                recoverable_failures=recoverable_failures
            )
            
        except Exception as e:
            logger.error(f"❌ 生成执行问题信息失败: {e}")
            return ExecutionIssues(
                errors=[f"问题分析失败: {str(e)}"],
                warnings=[],
                recoverable_failures=[]
            )
    
    async def update_workflow_output_summary(self, workflow_instance_id: uuid.UUID) -> bool:
        """更新工作流输出摘要到数据库"""
        try:
            logger.info(f"💾 开始更新工作流输出摘要到数据库: {workflow_instance_id}")
            
            # 生成输出摘要
            output_summary = await self.generate_workflow_output_summary(workflow_instance_id)
            if not output_summary:
                logger.error(f"❌ 生成输出摘要失败: {workflow_instance_id}")
                return False
            
            # 转换为字典格式存储
            summary_dict = output_summary.dict()
            
            # 分离各个组件到不同字段
            execution_summary = {
                "execution_result": summary_dict.get("execution_result"),
                "execution_stats": summary_dict.get("execution_stats")
            }
            
            quality_metrics = summary_dict.get("quality_metrics")
            data_lineage = summary_dict.get("data_lineage")
            
            # 更新数据库
            from ..models.instance import WorkflowInstanceUpdate
            update_data = WorkflowInstanceUpdate(
                execution_summary=execution_summary,
                quality_metrics=quality_metrics,
                data_lineage=data_lineage,
                output_summary=output_summary
            )
            
            result = await self.workflow_repo.update_instance(workflow_instance_id, update_data)
            if result:
                logger.info(f"✅ 工作流输出摘要更新成功: {workflow_instance_id}")
                return True
            else:
                logger.error(f"❌ 工作流输出摘要更新失败: {workflow_instance_id}")
                return False
            
        except Exception as e:
            logger.error(f"❌ 更新工作流输出摘要异常: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return False