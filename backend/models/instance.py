"""
工作流实例模型
Workflow Instance Models
"""

from __future__ import annotations
import uuid
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
from .base import BaseEntity, CreateRequest, UpdateRequest


class WorkflowInstanceStatus(str, Enum):
    """工作流实例状态枚举"""
    PENDING = "pending"       # 等待启动
    RUNNING = "running"       # 运行中
    PAUSED = "paused"         # 暂停
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败
    CANCELLED = "cancelled"   # 已取消


class NodeInstanceStatus(str, Enum):
    """节点实例状态枚举"""
    PENDING = "pending"       # 等待执行/等待前置条件
    WAITING = "waiting"       # 等待前置条件满足
    RUNNING = "running"       # 执行中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败
    CANCELLED = "cancelled"   # 已取消


class TaskInstanceStatus(str, Enum):
    """任务实例状态枚举"""
    PENDING = "pending"           # 等待分配
    ASSIGNED = "assigned"         # 已分配
    WAITING = "waiting"           # 等待前置条件
    IN_PROGRESS = "in_progress"   # 进行中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    CANCELLED = "cancelled"       # 已取消


class TaskInstanceType(str, Enum):
    """任务实例类型枚举"""
    HUMAN = "human"         # 人工任务
    AGENT = "agent"         # AI代理任务
    MIXED = "mixed"         # 混合任务


# ==================== 工作流实例模型 ====================

class WorkflowInstanceBase(BaseModel):
    """工作流实例基础模型"""
    instance_name: str = Field(..., min_length=1, max_length=255, description="实例名称")
    input_data: Optional[Dict[str, Any]] = Field(None, description="输入数据")
    context_data: Optional[Dict[str, Any]] = Field(None, description="上下文数据")


class WorkflowInstance(WorkflowInstanceBase, BaseEntity):
    """工作流实例完整模型"""
    instance_id: uuid.UUID = Field(..., description="实例ID")
    workflow_base_id: uuid.UUID = Field(..., description="工作流基础ID")
    workflow_id: uuid.UUID = Field(..., description="工作流版本ID")
    executor_id: uuid.UUID = Field(..., description="执行者ID")
    status: WorkflowInstanceStatus = Field(WorkflowInstanceStatus.PENDING, description="执行状态")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    output_data: Optional[Dict[str, Any]] = Field(None, description="原始输出数据")
    error_message: Optional[str] = Field(None, description="错误信息")
    current_node_id: Optional[uuid.UUID] = Field(None, description="当前执行节点ID")
    # 新增结构化输出字段
    execution_summary: Optional[Dict[str, Any]] = Field(None, description="执行摘要数据")
    quality_metrics: Optional[Dict[str, Any]] = Field(None, description="质量评估指标")
    data_lineage: Optional[Dict[str, Any]] = Field(None, description="数据血缘信息")
    output_summary: Optional[WorkflowOutputSummary] = Field(None, description="结构化输出摘要")


class WorkflowInstanceCreate(WorkflowInstanceBase, CreateRequest):
    """工作流实例创建模型"""
    workflow_base_id: uuid.UUID = Field(..., description="工作流基础ID")
    executor_id: uuid.UUID = Field(..., description="执行者ID")


class WorkflowInstanceUpdate(UpdateRequest):
    """工作流实例更新模型"""
    instance_name: Optional[str] = Field(None, min_length=1, max_length=255, description="实例名称")
    status: Optional[WorkflowInstanceStatus] = Field(None, description="执行状态")
    input_data: Optional[Dict[str, Any]] = Field(None, description="输入数据")
    context_data: Optional[Dict[str, Any]] = Field(None, description="上下文数据")
    output_data: Optional[Dict[str, Any]] = Field(None, description="原始输出数据")
    error_message: Optional[str] = Field(None, description="错误信息")
    current_node_id: Optional[uuid.UUID] = Field(None, description="当前执行节点ID")
    # 新增结构化输出字段更新支持
    execution_summary: Optional[Dict[str, Any]] = Field(None, description="执行摘要数据")
    quality_metrics: Optional[Dict[str, Any]] = Field(None, description="质量评估指标")
    data_lineage: Optional[Dict[str, Any]] = Field(None, description="数据血缘信息")
    output_summary: Optional[WorkflowOutputSummary] = Field(None, description="结构化输出摘要")


class WorkflowInstanceResponse(WorkflowInstanceBase):
    """工作流实例响应模型"""
    instance_id: uuid.UUID
    workflow_base_id: uuid.UUID
    workflow_id: uuid.UUID
    workflow_name: Optional[str] = None
    executor_id: uuid.UUID
    executor_name: Optional[str] = None
    status: WorkflowInstanceStatus
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    current_node_id: Optional[uuid.UUID] = None
    current_node_name: Optional[str] = None
    # 新增结构化输出字段响应支持
    execution_summary: Optional[Dict[str, Any]] = None
    quality_metrics: Optional[Dict[str, Any]] = None
    data_lineage: Optional[Dict[str, Any]] = None
    output_summary: Optional[WorkflowOutputSummary] = None


# ==================== 节点实例模型 ====================

class NodeInstanceBase(BaseModel):
    """节点实例基础模型"""
    input_data: Optional[Dict[str, Any]] = Field(None, description="输入数据")
    output_data: Optional[Dict[str, Any]] = Field(None, description="输出数据")


class NodeInstance(NodeInstanceBase, BaseEntity):
    """节点实例完整模型"""
    node_instance_id: uuid.UUID = Field(..., description="节点实例ID")
    workflow_instance_id: uuid.UUID = Field(..., description="工作流实例ID")
    node_id: uuid.UUID = Field(..., description="节点ID")
    node_base_id: uuid.UUID = Field(..., description="节点基础ID")
    status: NodeInstanceStatus = Field(NodeInstanceStatus.PENDING, description="执行状态")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    error_message: Optional[str] = Field(None, description="错误信息")
    retry_count: int = Field(0, description="重试次数")


class NodeInstanceCreate(NodeInstanceBase, CreateRequest):
    """节点实例创建模型"""
    workflow_instance_id: uuid.UUID = Field(..., description="工作流实例ID")
    node_id: uuid.UUID = Field(..., description="节点ID")
    node_base_id: uuid.UUID = Field(..., description="节点基础ID")
    node_instance_name: str = Field(..., description="节点实例名称")
    task_description: str = Field("", description="任务描述")
    status: NodeInstanceStatus = Field(NodeInstanceStatus.PENDING, description="执行状态")
    error_message: Optional[str] = Field(None, description="错误信息")
    retry_count: int = Field(0, description="重试次数")


class NodeInstanceUpdate(UpdateRequest):
    """节点实例更新模型"""
    status: Optional[NodeInstanceStatus] = Field(None, description="执行状态")
    input_data: Optional[Dict[str, Any]] = Field(None, description="输入数据")
    output_data: Optional[Dict[str, Any]] = Field(None, description="输出数据")
    error_message: Optional[str] = Field(None, description="错误信息")
    retry_count: Optional[int] = Field(None, description="重试次数")


class NodeInstanceResponse(NodeInstanceBase):
    """节点实例响应模型"""
    node_instance_id: uuid.UUID
    workflow_instance_id: uuid.UUID
    node_id: uuid.UUID
    node_base_id: uuid.UUID
    node_name: Optional[str] = None
    node_type: Optional[str] = None
    status: NodeInstanceStatus
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0


# ==================== 任务实例模型 ====================

class TaskInstanceBase(BaseModel):
    """任务实例基础模型"""
    task_title: str = Field(..., min_length=1, max_length=255, description="任务标题")
    task_description: str = Field(default="", description="任务描述")
    input_data: Optional[str] = Field(None, description="输入数据（文本格式）")
    context_data: Optional[str] = Field(None, description="上下文数据（文本格式）")


class TaskInstance(TaskInstanceBase, BaseEntity):
    """任务实例完整模型"""
    task_instance_id: uuid.UUID = Field(..., description="任务实例ID")
    node_instance_id: uuid.UUID = Field(..., description="节点实例ID")
    workflow_instance_id: uuid.UUID = Field(..., description="工作流实例ID")
    processor_id: uuid.UUID = Field(..., description="处理器ID")
    task_type: TaskInstanceType = Field(..., description="任务类型")
    status: TaskInstanceStatus = Field(TaskInstanceStatus.PENDING, description="执行状态")
    assigned_user_id: Optional[uuid.UUID] = Field(None, description="分配的用户ID")
    assigned_agent_id: Optional[uuid.UUID] = Field(None, description="分配的Agent ID")
    assigned_at: Optional[datetime] = Field(None, description="分配时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    output_data: Optional[str] = Field(None, description="输出数据（文本格式）")
    result_summary: Optional[str] = Field(None, description="结果摘要")
    error_message: Optional[str] = Field(None, description="错误信息")
    estimated_duration: Optional[int] = Field(None, description="预估时长(分钟)")
    actual_duration: Optional[int] = Field(None, description="实际时长(分钟)")


class TaskInstanceCreate(TaskInstanceBase, CreateRequest):
    """任务实例创建模型"""
    node_instance_id: uuid.UUID = Field(..., description="节点实例ID")
    workflow_instance_id: uuid.UUID = Field(..., description="工作流实例ID")
    processor_id: uuid.UUID = Field(..., description="处理器ID")
    task_type: TaskInstanceType = Field(..., description="任务类型")
    assigned_user_id: Optional[uuid.UUID] = Field(None, description="分配的用户ID")
    assigned_agent_id: Optional[uuid.UUID] = Field(None, description="分配的Agent ID")
    estimated_duration: Optional[int] = Field(None, description="预估时长(分钟)")


class TaskInstanceUpdate(UpdateRequest):
    """任务实例更新模型"""
    status: Optional[TaskInstanceStatus] = Field(None, description="执行状态")
    input_data: Optional[str] = Field(None, description="输入数据（文本格式）")
    output_data: Optional[str] = Field(None, description="输出数据（文本格式）")
    result_summary: Optional[str] = Field(None, description="结果摘要")
    error_message: Optional[str] = Field(None, description="错误信息")
    actual_duration: Optional[int] = Field(None, description="实际时长(分钟)")


class TaskInstanceResponse(TaskInstanceBase):
    """任务实例响应模型"""
    task_instance_id: uuid.UUID
    node_instance_id: uuid.UUID
    workflow_instance_id: uuid.UUID
    processor_id: uuid.UUID
    processor_name: Optional[str] = None
    task_type: TaskInstanceType
    status: TaskInstanceStatus
    assigned_user_id: Optional[uuid.UUID] = None
    assigned_user_name: Optional[str] = None
    assigned_agent_id: Optional[uuid.UUID] = None
    assigned_agent_name: Optional[str] = None
    assigned_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    output_data: Optional[str] = None
    result_summary: Optional[str] = None
    error_message: Optional[str] = None
    estimated_duration: Optional[int] = None
    actual_duration: Optional[int] = None


# ==================== 工作流执行控制模型 ====================

class WorkflowExecuteRequest(BaseModel):
    """工作流执行请求模型"""
    workflow_base_id: uuid.UUID = Field(..., description="工作流基础ID")
    instance_name: str = Field(..., min_length=1, max_length=255, description="实例名称")
    input_data: Optional[Dict[str, Any]] = Field(None, description="输入数据")
    context_data: Optional[Dict[str, Any]] = Field(None, description="上下文数据")


class WorkflowControlRequest(BaseModel):
    """工作流控制请求模型"""
    action: str = Field(..., description="控制动作: pause, resume, cancel")
    reason: Optional[str] = Field(None, description="操作原因")


# ==================== 工作流输出数据模型 ====================

class ExecutionResult(BaseModel):
    """执行结果模型"""
    result_type: str = Field(..., description="结果类型: success, partial_success, failure")
    processed_count: int = Field(0, description="处理数量")
    success_count: int = Field(0, description="成功数量")
    error_count: int = Field(0, description="错误数量")
    data_output: Optional[Dict[str, Any]] = Field(None, description="具体业务结果数据")


class ExecutionStatistics(BaseModel):
    """执行统计模型"""
    workflow_instance_id: uuid.UUID
    total_nodes: int
    completed_nodes: int
    failed_nodes: int
    pending_nodes: int
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    pending_tasks: int
    human_tasks: int
    agent_tasks: int
    mixed_tasks: int
    average_task_duration: Optional[float] = None
    total_execution_time: Optional[int] = None
    estimated_completion_time: Optional[str] = None
    # 新增字段
    total_duration_minutes: Optional[int] = Field(None, description="总执行时长(分钟)")
    average_node_duration: Optional[float] = Field(None, description="平均节点执行时长")


class QualityMetrics(BaseModel):
    """质量评估指标模型"""
    data_completeness: Optional[float] = Field(None, ge=0, le=1, description="数据完整性(0-1)")
    accuracy_score: Optional[float] = Field(None, ge=0, le=1, description="准确性评分(0-1)")
    validation_errors: List[str] = Field(default_factory=list, description="验证错误列表")
    quality_gates_passed: bool = Field(True, description="质量门禁是否通过")
    overall_quality_score: Optional[float] = Field(None, ge=0, le=1, description="整体质量评分")


class DataLineageStep(BaseModel):
    """数据血缘步骤模型"""
    node: str = Field(..., description="节点名称")
    operations: List[str] = Field(default_factory=list, description="执行的操作列表")
    timestamp: Optional[str] = Field(None, description="执行时间戳")


class DataLineage(BaseModel):
    """数据血缘追溯模型"""
    input_sources: List[str] = Field(default_factory=list, description="输入来源列表")
    transformation_steps: List[DataLineageStep] = Field(default_factory=list, description="转换步骤列表")
    output_destinations: List[str] = Field(default_factory=list, description="输出目标列表")


class ExecutionIssues(BaseModel):
    """执行问题和警告模型"""
    errors: List[str] = Field(default_factory=list, description="错误信息列表")
    warnings: List[str] = Field(default_factory=list, description="警告信息列表")
    recoverable_failures: List[str] = Field(default_factory=list, description="可恢复失败列表")


class WorkflowOutputSummary(BaseModel):
    """工作流输出摘要模型"""
    execution_result: Optional[ExecutionResult] = Field(None, description="执行结果")
    execution_stats: Optional[ExecutionStatistics] = Field(None, description="执行统计")
    quality_metrics: Optional[QualityMetrics] = Field(None, description="质量评估指标")
    data_lineage: Optional[DataLineage] = Field(None, description="数据血缘追溯")
    issues: Optional[ExecutionIssues] = Field(None, description="执行问题和警告")
    generated_at: Optional[datetime] = Field(None, description="生成时间")


# ==================== 执行统计模型 ====================