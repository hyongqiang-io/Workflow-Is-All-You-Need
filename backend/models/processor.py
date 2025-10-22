"""
处理器模型
Processor Models
"""

import uuid
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum
from .base import BaseEntity, CreateRequest, UpdateRequest


class ProcessorType(str, Enum):
    """处理器类型枚举"""
    HUMAN = "human"
    AGENT = "agent"
    MIX = "mix"
    SIMULATOR = "simulator"


class ProcessorBase(BaseModel):
    """处理器基础模型"""
    name: str = Field(..., min_length=1, max_length=255, description="处理器名称")
    type: ProcessorType = Field(..., description="处理器类型")


class Processor(ProcessorBase, BaseEntity):
    """处理器完整模型"""
    processor_id: uuid.UUID = Field(..., description="处理器ID")
    user_id: Optional[uuid.UUID] = Field(None, description="用户ID")
    agent_id: Optional[uuid.UUID] = Field(None, description="Agent ID")
    created_by: Optional[uuid.UUID] = Field(None, description="创建者ID")
    version: int = Field(1, description="版本号")


class ProcessorCreate(ProcessorBase, CreateRequest):
    """处理器创建模型"""
    user_id: Optional[uuid.UUID] = Field(None, description="用户ID")
    agent_id: Optional[uuid.UUID] = Field(None, description="Agent ID")
    group_id: Optional[uuid.UUID] = Field(None, description="群组ID")


class ProcessorUpdate(UpdateRequest):
    """处理器更新模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="处理器名称")
    type: Optional[ProcessorType] = Field(None, description="处理器类型")
    user_id: Optional[uuid.UUID] = Field(None, description="用户ID")
    agent_id: Optional[uuid.UUID] = Field(None, description="Agent ID")
    group_id: Optional[uuid.UUID] = Field(None, description="群组ID")


class ProcessorResponse(ProcessorBase):
    """处理器响应模型"""
    processor_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    agent_id: Optional[uuid.UUID] = None
    created_by: Optional[uuid.UUID] = None
    version: int
    created_at: Optional[str] = None
    user_name: Optional[str] = None
    agent_name: Optional[str] = None


class NodeProcessor(BaseModel):
    """节点处理器关联模型"""
    node_id: uuid.UUID = Field(..., description="节点ID")
    processor_id: uuid.UUID = Field(..., description="处理器ID")
    created_at: Optional[str] = None


class NodeProcessorCreate(BaseModel):
    """节点处理器关联创建模型"""
    node_base_id: uuid.UUID = Field(..., description="节点基础ID")
    workflow_base_id: uuid.UUID = Field(..., description="工作流基础ID")
    processor_id: uuid.UUID = Field(..., description="处理器ID")