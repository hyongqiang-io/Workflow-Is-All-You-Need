"""
工作流模型
Workflow Models
"""

import uuid
from typing import Optional, List
from pydantic import BaseModel, Field
from .base import BaseEntity, CreateRequest, UpdateRequest


class WorkflowBase(BaseModel):
    """工作流基础模型"""
    name: str = Field(..., min_length=1, max_length=255, description="工作流名称")
    description: Optional[str] = Field(None, description="工作流描述")


class Workflow(WorkflowBase, BaseEntity):
    """工作流完整模型"""
    workflow_id: uuid.UUID = Field(..., description="工作流ID")
    workflow_base_id: uuid.UUID = Field(..., description="工作流基础ID")
    creator_id: uuid.UUID = Field(..., description="创建者ID")
    version: int = Field(1, description="版本号")
    parent_version_id: Optional[uuid.UUID] = Field(None, description="父版本ID")
    is_current_version: bool = Field(True, description="是否为当前版本")
    change_description: Optional[str] = Field(None, description="变更说明")


class WorkflowCreate(WorkflowBase, CreateRequest):
    """工作流创建模型"""
    creator_id: uuid.UUID = Field(..., description="创建者ID")


class WorkflowUpdate(UpdateRequest):
    """工作流更新模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="工作流名称")
    description: Optional[str] = Field(None, description="工作流描述")
    change_description: Optional[str] = Field(None, description="变更说明")


class WorkflowResponse(WorkflowBase):
    """工作流响应模型"""
    workflow_id: uuid.UUID
    workflow_base_id: uuid.UUID
    creator_id: uuid.UUID
    version: int
    parent_version_id: Optional[uuid.UUID] = None
    is_current_version: bool
    change_description: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    creator_name: Optional[str] = None


class WorkflowVersion(BaseModel):
    """工作流版本模型"""
    workflow_id: uuid.UUID
    workflow_base_id: uuid.UUID
    name: str
    version: int
    change_description: Optional[str] = None
    created_at: str
    creator_name: str
    is_current_version: bool
    node_count: int


class WorkflowVersionCreate(BaseModel):
    """工作流版本创建模型"""
    workflow_base_id: uuid.UUID = Field(..., description="工作流基础ID")
    editor_user_id: Optional[uuid.UUID] = Field(None, description="编辑用户ID")
    change_description: Optional[str] = Field(None, description="变更说明")


class WorkflowUser(BaseModel):
    """工作流用户关联模型"""
    workflow_base_id: uuid.UUID = Field(..., description="工作流基础ID")
    user_id: uuid.UUID = Field(..., description="用户ID")
    created_at: Optional[str] = None


class WorkflowUserAdd(BaseModel):
    """添加工作流用户模型"""
    user_ids: List[uuid.UUID] = Field(..., description="用户ID列表")