"""
Agent模型
Agent Models
"""

import uuid
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from .base import BaseEntity, CreateRequest, UpdateRequest


class AgentBase(BaseModel):
    """Agent基础模型"""
    model_config = ConfigDict(protected_namespaces=())
    
    agent_name: str = Field(..., min_length=1, max_length=255, description="Agent名称")
    description: Optional[str] = Field(None, description="Agent描述")
    base_url: Optional[str] = Field(None, max_length=255, description="基础URL")
    api_key: Optional[str] = Field(None, max_length=255, description="API密钥")
    model_name: Optional[str] = Field(None, max_length=255, description="模型名称")
    tool_config: Optional[Dict[str, Any]] = Field(None, description="工具配置")
    parameters: Optional[Dict[str, Any]] = Field(None, description="参数配置")
    is_autonomous: bool = Field(False, description="是否自主运行")


class Agent(AgentBase, BaseEntity):
    """Agent完整模型"""
    agent_id: uuid.UUID = Field(..., description="Agent ID")


class AgentCreate(AgentBase, CreateRequest):
    """Agent创建模型"""
    pass


class AgentUpdate(UpdateRequest):
    """Agent更新模型"""
    agent_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Agent名称")
    description: Optional[str] = Field(None, description="Agent描述")
    base_url: Optional[str] = Field(None, max_length=255, description="基础URL")
    api_key: Optional[str] = Field(None, max_length=255, description="API密钥")
    model_name: Optional[str] = Field(None, max_length=255, description="模型名称")
    tool_config: Optional[Dict[str, Any]] = Field(None, description="工具配置")
    parameters: Optional[Dict[str, Any]] = Field(None, description="参数配置")
    is_autonomous: Optional[bool] = Field(None, description="是否自主运行")
    capabilities: Optional[list] = Field(None, description="能力列表")


class AgentResponse(AgentBase):
    """Agent响应模型"""
    agent_id: uuid.UUID
    created_at: Optional[str] = None
    updated_at: Optional[str] = None