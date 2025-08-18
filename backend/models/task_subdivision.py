"""
任务细分模型 - 简化版
Task Subdivision Models - Simplified
"""

import uuid
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
from .base import BaseEntity, CreateRequest, UpdateRequest


class SubWorkflowStatus(str, Enum):
    """子工作流状态枚举"""
    DRAFT = "draft"               # 草稿状态
    RUNNING = "running"           # 运行中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    CANCELLED = "cancelled"       # 已取消


class TaskSubdivisionStatus(str, Enum):
    """任务细分状态枚举"""
    CREATED = "created"           # 已创建
    EXECUTING = "executing"       # 执行中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败


# ==================== 任务细分模型 ====================

class TaskSubdivisionBase(BaseModel):
    """任务细分基础模型"""
    subdivision_name: str = Field(..., min_length=1, max_length=255, description="细分工作流名称")
    subdivision_description: str = Field(default="", description="细分说明")


class TaskSubdivision(TaskSubdivisionBase, BaseEntity):
    """任务细分完整模型"""
    subdivision_id: uuid.UUID = Field(..., description="细分ID")
    original_task_id: uuid.UUID = Field(..., description="原始任务ID")
    subdivider_id: uuid.UUID = Field(..., description="细分者ID（任务执行者）")
    sub_workflow_base_id: uuid.UUID = Field(..., description="子工作流基础ID")
    sub_workflow_instance_id: Optional[uuid.UUID] = Field(None, description="子工作流实例ID")
    status: TaskSubdivisionStatus = Field(TaskSubdivisionStatus.CREATED, description="细分状态")
    
    # 上下文传递
    parent_task_description: str = Field(..., description="父任务描述")
    context_passed: str = Field(default="", description="传递给子工作流的上下文")
    
    # 时间戳
    subdivision_created_at: datetime = Field(default_factory=datetime.utcnow, description="细分创建时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")


class TaskSubdivisionCreate(TaskSubdivisionBase, CreateRequest):
    """任务细分创建模型"""
    original_task_id: uuid.UUID = Field(..., description="原始任务ID")
    subdivider_id: uuid.UUID = Field(..., description="细分者ID")
    sub_workflow_base_id: Optional[uuid.UUID] = Field(None, description="已创建的子工作流基础ID")
    sub_workflow_data: Dict[str, Any] = Field(..., description="子工作流定义数据")
    context_to_pass: str = Field(default="", description="需要传递的上下文")


class TaskSubdivisionUpdate(UpdateRequest):
    """任务细分更新模型"""
    subdivision_name: Optional[str] = Field(None, description="细分工作流名称")
    subdivision_description: Optional[str] = Field(None, description="细分说明")
    status: Optional[TaskSubdivisionStatus] = Field(None, description="细分状态")


class TaskSubdivisionResponse(TaskSubdivisionBase):
    """任务细分响应模型"""
    subdivision_id: uuid.UUID
    original_task_id: uuid.UUID
    original_task_title: Optional[str] = None
    subdivider_id: uuid.UUID
    subdivider_name: Optional[str] = None
    sub_workflow_base_id: uuid.UUID
    sub_workflow_instance_id: Optional[uuid.UUID] = None
    status: TaskSubdivisionStatus
    
    # 上下文信息
    parent_task_description: str
    context_passed: str
    
    # 时间信息
    subdivision_created_at: str
    completed_at: Optional[str] = None
    
    # 子工作流基本信息
    sub_workflow_name: Optional[str] = None
    total_sub_nodes: Optional[int] = None
    completed_sub_nodes: Optional[int] = None


# ==================== 工作流采纳模型 ====================

class WorkflowAdoptionBase(BaseModel):
    """工作流采纳基础模型"""
    adoption_name: str = Field(..., description="采纳后的节点名称")
    target_node_id: uuid.UUID = Field(..., description="要替换的目标节点ID")


class WorkflowAdoption(WorkflowAdoptionBase, BaseEntity):
    """工作流采纳完整模型"""
    adoption_id: uuid.UUID = Field(..., description="采纳ID")
    subdivision_id: uuid.UUID = Field(..., description="被采纳的细分ID")
    original_workflow_base_id: uuid.UUID = Field(..., description="原始工作流基础ID")
    adopter_id: uuid.UUID = Field(..., description="采纳者ID（原始工作流创建者）")
    
    # 采纳结果
    new_nodes_added: List[uuid.UUID] = Field(default_factory=list, description="新增的节点ID列表")
    adopted_at: datetime = Field(default_factory=datetime.utcnow, description="采纳时间")


class WorkflowAdoptionCreate(WorkflowAdoptionBase, CreateRequest):
    """工作流采纳创建模型"""
    subdivision_id: uuid.UUID = Field(..., description="要采纳的细分ID")
    original_workflow_base_id: uuid.UUID = Field(..., description="原始工作流基础ID")
    adopter_id: uuid.UUID = Field(..., description="采纳者ID")


class WorkflowAdoptionResponse(WorkflowAdoptionBase):
    """工作流采纳响应模型"""
    adoption_id: uuid.UUID
    subdivision_id: uuid.UUID
    subdivision_name: Optional[str] = None
    adopter_id: uuid.UUID
    adopter_name: Optional[str] = None
    new_nodes_count: int
    adopted_at: str


# ==================== API请求/响应模型 ====================

class TaskSubdivisionRequest(BaseModel):
    """任务细分请求模型"""
    subdivision_name: str = Field(..., description="细分工作流名称")
    subdivision_description: str = Field(default="", description="细分说明")
    sub_workflow_data: Dict[str, Any] = Field(..., description="子工作流定义数据")
    execute_immediately: bool = Field(False, description="是否立即执行")
    # 新增任务上下文传递字段
    task_context: Optional[Dict[str, Any]] = Field(None, description="任务上下文信息")
    sub_workflow_base_id: Optional[uuid.UUID] = Field(None, description="已创建的子工作流基础ID")


class SubdivisionPreviewResponse(BaseModel):
    """子工作流预览响应模型"""
    subdivision_id: uuid.UUID
    subdivision_name: str
    subdivider_name: str
    status: TaskSubdivisionStatus
    sub_workflow_name: str
    total_nodes: int
    completed_nodes: int
    success_rate: Optional[float] = None
    created_at: str
    completed_at: Optional[str] = None


class WorkflowSubdivisionsResponse(BaseModel):
    """工作流细分概览响应模型"""
    workflow_base_id: uuid.UUID
    workflow_name: str
    subdivisions: List[SubdivisionPreviewResponse]
    total_count: int
    completed_count: int


class AdoptSubdivisionRequest(BaseModel):
    """采纳子工作流请求模型"""
    subdivision_id: uuid.UUID = Field(..., description="要采纳的细分ID")
    target_node_id: uuid.UUID = Field(..., description="要替换的目标节点ID")
    adoption_name: str = Field(..., description="采纳后的节点名称")