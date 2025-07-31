"""
工作流输出数据验证器
Output Data Validator for Workflow Results
"""

import uuid
import json
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime
from loguru import logger
from pydantic import ValidationError

from ..models.instance import (
    WorkflowOutputSummary, ExecutionResult, ExecutionStatistics,
    QualityMetrics, DataLineage, ExecutionIssues,
    WorkflowInstanceStatus
)


class ValidationResult:
    """验证结果类"""
    
    def __init__(self):
        self.is_valid = True
        self.errors = []
        self.warnings = []
        self.suggestions = []
    
    def add_error(self, field: str, message: str):
        self.is_valid = False
        self.errors.append({"field": field, "message": message})
    
    def add_warning(self, field: str, message: str):
        self.warnings.append({"field": field, "message": message})
    
    def add_suggestion(self, field: str, message: str):
        self.suggestions.append({"field": field, "message": message})
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "validation_time": datetime.utcnow().isoformat()
        }


class OutputDataValidator:
    """工作流输出数据验证器"""
    
    def __init__(self):
        # 数据类型验证规则
        self.field_types = {
            'execution_result': {
                'result_type': str,
                'processed_count': int,
                'success_count': int,
                'error_count': int,
                'data_output': dict
            },
            'execution_stats': {
                'total_nodes': int,
                'completed_nodes': int,
                'failed_nodes': int,
                'total_tasks': int,
                'completed_tasks': int,
                'failed_tasks': int,
                'human_tasks': int,
                'agent_tasks': int,
                'mixed_tasks': int
            },
            'quality_metrics': {
                'data_completeness': float,
                'accuracy_score': float,
                'validation_errors': list,
                'quality_gates_passed': bool,
                'overall_quality_score': float
            }
        }
        
        # 数值范围验证规则
        self.value_ranges = {
            'data_completeness': (0.0, 1.0),
            'accuracy_score': (0.0, 1.0),
            'overall_quality_score': (0.0, 1.0),
            'processed_count': (0, None),
            'success_count': (0, None),
            'error_count': (0, None),
            'total_nodes': (0, None),
            'completed_nodes': (0, None),
            'failed_nodes': (0, None)
        }
        
        # 必需字段定义
        self.required_fields = {
            'execution_result': ['result_type', 'processed_count', 'success_count', 'error_count'],
            'execution_stats': ['total_nodes', 'completed_nodes', 'failed_nodes', 'total_tasks'],
            'quality_metrics': ['quality_gates_passed']
        }
    
    async def validate_workflow_output_summary(self, output_summary: Union[WorkflowOutputSummary, Dict[str, Any]]) -> ValidationResult:
        """验证工作流输出摘要"""
        result = ValidationResult()
        
        try:
            logger.info("🔍 开始验证工作流输出摘要")
            
            # 转换为字典格式进行验证
            if isinstance(output_summary, WorkflowOutputSummary):
                summary_dict = output_summary.dict()
            else:
                summary_dict = output_summary
            
            # 1. 验证基本结构
            await self._validate_basic_structure(summary_dict, result)
            
            # 2. 验证执行结果
            if 'execution_result' in summary_dict and summary_dict['execution_result']:
                await self._validate_execution_result(summary_dict['execution_result'], result)
            
            # 3. 验证执行统计
            if 'execution_stats' in summary_dict and summary_dict['execution_stats']:
                await self._validate_execution_statistics(summary_dict['execution_stats'], result)
            
            # 4. 验证质量指标
            if 'quality_metrics' in summary_dict and summary_dict['quality_metrics']:
                await self._validate_quality_metrics(summary_dict['quality_metrics'], result)
            
            # 5. 验证数据血缘
            if 'data_lineage' in summary_dict and summary_dict['data_lineage']:
                await self._validate_data_lineage(summary_dict['data_lineage'], result)
            
            # 6. 验证执行问题
            if 'issues' in summary_dict and summary_dict['issues']:
                await self._validate_execution_issues(summary_dict['issues'], result)
            
            # 7. 验证逻辑一致性
            await self._validate_logical_consistency(summary_dict, result)
            
            # 8. 生成优化建议
            await self._generate_optimization_suggestions(summary_dict, result)
            
            if result.is_valid:
                logger.info("✅ 工作流输出摘要验证通过")
            else:
                logger.warning(f"⚠️ 工作流输出摘要验证失败，发现 {len(result.errors)} 个错误")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 验证工作流输出摘要异常: {e}")
            result.add_error("validation", f"验证过程异常: {str(e)}")
            return result
    
    async def _validate_basic_structure(self, summary_dict: Dict[str, Any], result: ValidationResult):
        """验证基本结构"""
        try:
            # 检查顶级字段
            expected_fields = ['execution_result', 'execution_stats', 'quality_metrics', 'data_lineage', 'issues']
            present_fields = [field for field in expected_fields if field in summary_dict and summary_dict[field] is not None]
            
            if len(present_fields) == 0:
                result.add_error("structure", "输出摘要为空或缺少所有关键字段")
            elif len(present_fields) < 3:
                result.add_warning("structure", f"输出摘要字段不完整，仅包含: {present_fields}")
            
            # 检查生成时间
            if 'generated_at' not in summary_dict:
                result.add_warning("structure", "缺少生成时间字段")
            else:
                try:
                    datetime.fromisoformat(summary_dict['generated_at'].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    result.add_error("generated_at", "生成时间格式无效")
            
        except Exception as e:
            result.add_error("structure", f"基本结构验证异常: {str(e)}")
    
    async def _validate_execution_result(self, execution_result: Dict[str, Any], result: ValidationResult):
        """验证执行结果"""
        try:
            # 验证必需字段
            for field in self.required_fields['execution_result']:
                if field not in execution_result:
                    result.add_error(f"execution_result.{field}", f"缺少必需字段: {field}")
            
            # 验证结果类型
            if 'result_type' in execution_result:
                valid_types = ['success', 'partial_success', 'failure']
                if execution_result['result_type'] not in valid_types:
                    result.add_error("execution_result.result_type", f"无效的结果类型，应为: {valid_types}")
            
            # 验证数值字段
            numeric_fields = ['processed_count', 'success_count', 'error_count']
            for field in numeric_fields:
                if field in execution_result:
                    value = execution_result[field]
                    if not isinstance(value, int) or value < 0:
                        result.add_error(f"execution_result.{field}", f"{field} 应为非负整数")
            
            # 验证逻辑关系
            if all(field in execution_result for field in ['processed_count', 'success_count', 'error_count']):
                processed = execution_result['processed_count']
                success = execution_result['success_count']
                error = execution_result['error_count']
                
                if success + error != processed:
                    result.add_error("execution_result.logic", 
                                   f"数据不一致: success_count({success}) + error_count({error}) != processed_count({processed})")
                
                # 检查成功率
                if processed > 0:
                    success_rate = success / processed
                    if success_rate < 0.5:
                        result.add_warning("execution_result.performance", f"成功率较低: {success_rate:.2%}")
                    elif success_rate > 0.95:
                        result.add_suggestion("execution_result.performance", f"成功率优秀: {success_rate:.2%}")
            
        except Exception as e:
            result.add_error("execution_result", f"执行结果验证异常: {str(e)}")
    
    async def _validate_execution_statistics(self, execution_stats: Dict[str, Any], result: ValidationResult):
        """验证执行统计"""
        try:
            # 验证必需字段
            for field in self.required_fields['execution_stats']:
                if field not in execution_stats:
                    result.add_error(f"execution_stats.{field}", f"缺少必需字段: {field}")
            
            # 验证数值字段类型和范围
            numeric_fields = ['total_nodes', 'completed_nodes', 'failed_nodes', 'pending_nodes',
                            'total_tasks', 'completed_tasks', 'failed_tasks', 'pending_tasks',
                            'human_tasks', 'agent_tasks', 'mixed_tasks']
            
            for field in numeric_fields:
                if field in execution_stats:
                    value = execution_stats[field]
                    if not isinstance(value, int) or value < 0:
                        result.add_error(f"execution_stats.{field}", f"{field} 应为非负整数")
            
            # 验证节点统计逻辑
            if all(field in execution_stats for field in ['total_nodes', 'completed_nodes', 'failed_nodes']):
                total = execution_stats['total_nodes']
                completed = execution_stats['completed_nodes']
                failed = execution_stats['failed_nodes']
                pending = execution_stats.get('pending_nodes', 0)
                
                if completed + failed + pending != total:
                    result.add_warning("execution_stats.nodes", 
                                     f"节点统计可能不一致: completed({completed}) + failed({failed}) + pending({pending}) != total({total})")
            
            # 验证任务统计逻辑
            if all(field in execution_stats for field in ['total_tasks', 'human_tasks', 'agent_tasks', 'mixed_tasks']):
                total_tasks = execution_stats['total_tasks']
                type_sum = execution_stats['human_tasks'] + execution_stats['agent_tasks'] + execution_stats['mixed_tasks']
                
                if type_sum != total_tasks:
                    result.add_warning("execution_stats.tasks", 
                                     f"任务类型统计不一致: human + agent + mixed = {type_sum} != total_tasks({total_tasks})")
            
            # 验证执行时长
            if 'total_duration_minutes' in execution_stats:
                duration = execution_stats['total_duration_minutes']
                if isinstance(duration, (int, float)):
                    if duration > 1440:  # 超过24小时
                        result.add_warning("execution_stats.duration", f"执行时长较长: {duration} 分钟")
                    elif duration < 1:  # 少于1分钟
                        result.add_suggestion("execution_stats.duration", f"执行效率很高: {duration} 分钟")
            
        except Exception as e:
            result.add_error("execution_stats", f"执行统计验证异常: {str(e)}")
    
    async def _validate_quality_metrics(self, quality_metrics: Dict[str, Any], result: ValidationResult):
        """验证质量指标"""
        try:
            # 验证评分字段范围
            score_fields = ['data_completeness', 'accuracy_score', 'overall_quality_score']
            for field in score_fields:
                if field in quality_metrics:
                    value = quality_metrics[field]
                    if value is not None:
                        if not isinstance(value, (int, float)) or not (0.0 <= value <= 1.0):
                            result.add_error(f"quality_metrics.{field}", f"{field} 应为 0.0-1.0 之间的数值")
            
            # 验证质量门禁
            if 'quality_gates_passed' in quality_metrics:
                if not isinstance(quality_metrics['quality_gates_passed'], bool):
                    result.add_error("quality_metrics.quality_gates_passed", "质量门禁状态应为布尔值")
            
            # 验证验证错误列表
            if 'validation_errors' in quality_metrics:
                errors = quality_metrics['validation_errors']
                if not isinstance(errors, list):
                    result.add_error("quality_metrics.validation_errors", "验证错误应为列表格式")
                elif len(errors) > 0:
                    result.add_warning("quality_metrics.validation", f"发现 {len(errors)} 个验证错误")
            
            # 验证质量评分一致性
            if all(field in quality_metrics and quality_metrics[field] is not None 
                   for field in ['data_completeness', 'accuracy_score', 'overall_quality_score']):
                completeness = quality_metrics['data_completeness']
                accuracy = quality_metrics['accuracy_score']
                overall = quality_metrics['overall_quality_score']
                
                expected_overall = (completeness + accuracy) / 2
                if abs(overall - expected_overall) > 0.1:
                    result.add_warning("quality_metrics.consistency", 
                                     f"整体质量评分({overall:.2f})与预期({expected_overall:.2f})差异较大")
            
            # 质量建议
            if 'overall_quality_score' in quality_metrics and quality_metrics['overall_quality_score'] is not None:
                score = quality_metrics['overall_quality_score']
                if score < 0.6:
                    result.add_warning("quality_metrics.score", f"整体质量评分较低: {score:.2f}")
                elif score > 0.9:
                    result.add_suggestion("quality_metrics.score", f"整体质量评分优秀: {score:.2f}")
            
        except Exception as e:
            result.add_error("quality_metrics", f"质量指标验证异常: {str(e)}")
    
    async def _validate_data_lineage(self, data_lineage: Dict[str, Any], result: ValidationResult):
        """验证数据血缘"""
        try:
            # 验证输入来源
            if 'input_sources' in data_lineage:
                sources = data_lineage['input_sources']
                if not isinstance(sources, list):
                    result.add_error("data_lineage.input_sources", "输入来源应为列表格式")
                elif len(sources) == 0:
                    result.add_warning("data_lineage.input_sources", "未记录输入来源")
            
            # 验证转换步骤
            if 'transformation_steps' in data_lineage:
                steps = data_lineage['transformation_steps']
                if not isinstance(steps, list):
                    result.add_error("data_lineage.transformation_steps", "转换步骤应为列表格式")
                else:
                    for i, step in enumerate(steps):
                        if not isinstance(step, dict):
                            result.add_error(f"data_lineage.transformation_steps[{i}]", "转换步骤应为字典格式")
                            continue
                        
                        if 'node' not in step:
                            result.add_error(f"data_lineage.transformation_steps[{i}]", "转换步骤缺少节点名称")
                        
                        if 'operations' not in step or not isinstance(step['operations'], list):
                            result.add_error(f"data_lineage.transformation_steps[{i}]", "转换步骤缺少操作列表")
            
            # 验证输出目标
            if 'output_destinations' in data_lineage:
                destinations = data_lineage['output_destinations']
                if not isinstance(destinations, list):
                    result.add_error("data_lineage.output_destinations", "输出目标应为列表格式")
                elif len(destinations) == 0:
                    result.add_warning("data_lineage.output_destinations", "未记录输出目标")
            
        except Exception as e:
            result.add_error("data_lineage", f"数据血缘验证异常: {str(e)}")
    
    async def _validate_execution_issues(self, issues: Dict[str, Any], result: ValidationResult):
        """验证执行问题"""
        try:
            issue_types = ['errors', 'warnings', 'recoverable_failures']
            
            for issue_type in issue_types:
                if issue_type in issues:
                    issue_list = issues[issue_type]
                    if not isinstance(issue_list, list):
                        result.add_error(f"issues.{issue_type}", f"{issue_type} 应为列表格式")
                    else:
                        # 检查问题数量
                        if issue_type == 'errors' and len(issue_list) > 0:
                            result.add_warning(f"issues.{issue_type}", f"发现 {len(issue_list)} 个错误")
                        elif issue_type == 'warnings' and len(issue_list) > 5:
                            result.add_warning(f"issues.{issue_type}", f"警告数量较多: {len(issue_list)} 个")
                        elif issue_type == 'recoverable_failures' and len(issue_list) > 0:
                            result.add_suggestion(f"issues.{issue_type}", f"有 {len(issue_list)} 个可恢复失败已处理")
            
        except Exception as e:
            result.add_error("issues", f"执行问题验证异常: {str(e)}")
    
    async def _validate_logical_consistency(self, summary_dict: Dict[str, Any], result: ValidationResult):
        """验证逻辑一致性"""
        try:
            # 验证结果类型与统计数据的一致性
            if 'execution_result' in summary_dict and 'execution_stats' in summary_dict:
                exec_result = summary_dict['execution_result']
                exec_stats = summary_dict['execution_stats']
                
                result_type = exec_result.get('result_type')
                failed_nodes = exec_stats.get('failed_nodes', 0)
                completed_nodes = exec_stats.get('completed_nodes', 0)
                total_nodes = exec_stats.get('total_nodes', 0)
                
                # 检查结果类型与节点状态的一致性
                if result_type == 'success' and failed_nodes > 0:
                    result.add_warning("consistency", f"结果类型为success但有 {failed_nodes} 个失败节点")
                elif result_type == 'failure' and failed_nodes == 0:
                    result.add_warning("consistency", "结果类型为failure但没有失败节点")
                elif result_type == 'partial_success' and (failed_nodes == 0 or completed_nodes == 0):
                    result.add_warning("consistency", "结果类型为partial_success但节点状态不符合预期")
            
            # 验证质量指标与结果的一致性
            if 'execution_result' in summary_dict and 'quality_metrics' in summary_dict:
                result_type = summary_dict['execution_result'].get('result_type')
                quality_gates = summary_dict['quality_metrics'].get('quality_gates_passed')
                
                if result_type == 'success' and quality_gates is False:
                    result.add_warning("consistency", "执行成功但质量门禁未通过")
                elif result_type == 'failure' and quality_gates is True:
                    result.add_warning("consistency", "执行失败但质量门禁通过")
            
        except Exception as e:
            result.add_error("consistency", f"逻辑一致性验证异常: {str(e)}")
    
    async def _generate_optimization_suggestions(self, summary_dict: Dict[str, Any], result: ValidationResult):
        """生成优化建议"""
        try:
            # 基于执行统计的建议
            if 'execution_stats' in summary_dict:
                stats = summary_dict['execution_stats']
                
                # 执行时长建议
                if 'total_duration_minutes' in stats and stats['total_duration_minutes']:
                    duration = stats['total_duration_minutes']
                    total_tasks = stats.get('total_tasks', 0)
                    
                    if total_tasks > 0:
                        avg_task_time = duration / total_tasks
                        if avg_task_time > 10:
                            result.add_suggestion("optimization", f"平均任务时长较长({avg_task_time:.1f}分钟)，考虑优化任务拆分")
                
                # 任务类型分布建议
                human_tasks = stats.get('human_tasks', 0)
                agent_tasks = stats.get('agent_tasks', 0)
                total_tasks = stats.get('total_tasks', 0)
                
                if total_tasks > 0:
                    human_ratio = human_tasks / total_tasks
                    if human_ratio > 0.8:
                        result.add_suggestion("optimization", "人工任务比例较高，考虑增加自动化")
                    elif human_ratio < 0.1:
                        result.add_suggestion("optimization", "自动化程度很高，表现优秀")
            
            # 基于质量指标的建议
            if 'quality_metrics' in summary_dict:
                metrics = summary_dict['quality_metrics']
                
                data_completeness = metrics.get('data_completeness')
                if data_completeness is not None and data_completeness < 0.9:
                    result.add_suggestion("optimization", f"数据完整性({data_completeness:.2f})有提升空间")
                
                accuracy_score = metrics.get('accuracy_score')
                if accuracy_score is not None and accuracy_score < 0.85:
                    result.add_suggestion("optimization", f"准确性评分({accuracy_score:.2f})有提升空间")
            
        except Exception as e:
            logger.warning(f"生成优化建议异常: {e}")
    
    async def validate_workflow_instance_output(self, workflow_instance: Dict[str, Any]) -> ValidationResult:
        """验证工作流实例的输出数据"""
        result = ValidationResult()
        
        try:
            logger.info(f"🔍 开始验证工作流实例输出: {workflow_instance.get('instance_id')}")
            
            # 1. 验证基础输出数据
            if 'output_data' in workflow_instance and workflow_instance['output_data']:
                await self._validate_basic_output_data(workflow_instance['output_data'], result)
            
            # 2. 验证结构化输出字段
            structured_fields = ['execution_summary', 'quality_metrics', 'data_lineage', 'output_summary']
            for field in structured_fields:
                if field in workflow_instance and workflow_instance[field]:
                    await self._validate_structured_field(field, workflow_instance[field], result)
            
            # 3. 验证状态一致性
            await self._validate_instance_status_consistency(workflow_instance, result)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 验证工作流实例输出异常: {e}")
            result.add_error("validation", f"验证过程异常: {str(e)}")
            return result
    
    async def _validate_basic_output_data(self, output_data: Dict[str, Any], result: ValidationResult):
        """验证基础输出数据"""
        try:
            # 检查基础字段
            if 'message' not in output_data:
                result.add_warning("output_data", "缺少消息字段")
            
            if 'completion_time' in output_data:
                try:
                    datetime.fromisoformat(output_data['completion_time'].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    result.add_error("output_data.completion_time", "完成时间格式无效")
            
            if 'result_type' in output_data:
                valid_types = ['success', 'partial_success', 'failure']
                if output_data['result_type'] not in valid_types:
                    result.add_error("output_data.result_type", f"无效的结果类型，应为: {valid_types}")
            
        except Exception as e:
            result.add_error("output_data", f"基础输出数据验证异常: {str(e)}")
    
    async def _validate_structured_field(self, field_name: str, field_data: Dict[str, Any], result: ValidationResult):
        """验证结构化字段"""
        try:
            if field_name == 'execution_summary':
                if 'execution_result' in field_data:
                    await self._validate_execution_result(field_data['execution_result'], result)
                if 'execution_stats' in field_data:
                    await self._validate_execution_statistics(field_data['execution_stats'], result)
            
            elif field_name == 'quality_metrics':
                await self._validate_quality_metrics(field_data, result)
            
            elif field_name == 'data_lineage':
                await self._validate_data_lineage(field_data, result)
            
            elif field_name == 'output_summary':
                await self.validate_workflow_output_summary(field_data)
            
        except Exception as e:
            result.add_error(field_name, f"结构化字段验证异常: {str(e)}")
    
    async def _validate_instance_status_consistency(self, workflow_instance: Dict[str, Any], result: ValidationResult):
        """验证实例状态一致性"""
        try:
            status = workflow_instance.get('status')
            
            # 检查完成状态的一致性
            if status == WorkflowInstanceStatus.COMPLETED.value:
                if not workflow_instance.get('completed_at'):
                    result.add_error("status", "状态为已完成但缺少完成时间")
                
                if not workflow_instance.get('output_data'):
                    result.add_warning("status", "状态为已完成但缺少输出数据")
            
            elif status == WorkflowInstanceStatus.FAILED.value:
                if not workflow_instance.get('error_message'):
                    result.add_warning("status", "状态为失败但缺少错误信息")
            
            elif status == WorkflowInstanceStatus.RUNNING.value:
                if workflow_instance.get('completed_at'):
                    result.add_error("status", "状态为运行中但存在完成时间")
            
        except Exception as e:
            result.add_error("status", f"状态一致性验证异常: {str(e)}")
    
    async def get_validation_summary(self, validation_results: List[ValidationResult]) -> Dict[str, Any]:
        """获取验证摘要"""
        try:
            total_validations = len(validation_results)
            valid_count = sum(1 for r in validation_results if r.is_valid)
            invalid_count = total_validations - valid_count
            
            total_errors = sum(len(r.errors) for r in validation_results)
            total_warnings = sum(len(r.warnings) for r in validation_results)
            total_suggestions = sum(len(r.suggestions) for r in validation_results)
            
            return {
                'total_validations': total_validations,
                'valid_count': valid_count,
                'invalid_count': invalid_count,
                'success_rate': valid_count / total_validations if total_validations > 0 else 0,
                'total_errors': total_errors,
                'total_warnings': total_warnings,
                'total_suggestions': total_suggestions,
                'validation_time': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ 生成验证摘要异常: {e}")
            return {
                'error': str(e),
                'validation_time': datetime.utcnow().isoformat()
            }