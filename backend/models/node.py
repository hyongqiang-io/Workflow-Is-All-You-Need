"""
节点模型
Node Models
"""

import uuid
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from .base import BaseEntity, CreateRequest, UpdateRequest


class NodeType(str, Enum):
    """节点类型枚举"""
    START = "start"
    PROCESSOR = "processor"
    END = "end"


class ConnectionType(str, Enum):
    """连接类型枚举"""
    NORMAL = "normal"
    CONDITIONAL = "conditional"


class NodeBase(BaseModel):
    """节点基础模型"""
    name: str = Field(..., min_length=1, max_length=255, description="节点名称")
    type: NodeType = Field(..., description="节点类型")
    task_description: Optional[str] = Field(None, description="任务描述")
    position_x: Optional[float] = Field(None, description="X坐标")
    position_y: Optional[float] = Field(None, description="Y坐标")


class Node(NodeBase, BaseEntity):
    """节点完整模型"""
    node_id: uuid.UUID = Field(..., description="节点ID")
    node_base_id: uuid.UUID = Field(..., description="节点基础ID")
    workflow_id: uuid.UUID = Field(..., description="工作流ID")
    workflow_base_id: uuid.UUID = Field(..., description="工作流基础ID")
    version: int = Field(1, description="版本号")
    parent_version_id: Optional[uuid.UUID] = Field(None, description="父版本ID")
    is_current_version: bool = Field(True, description="是否为当前版本")


class NodeCreate(NodeBase, CreateRequest):
    """节点创建模型"""
    workflow_base_id: uuid.UUID = Field(..., description="工作流基础ID")


class NodeUpdate(UpdateRequest):
    """节点更新模型"""
    name: Optional[str] = Field(None, description="节点名称")
    type: Optional[NodeType] = Field(None, description="节点类型")
    task_description: Optional[str] = Field(None, description="任务描述") 
    position_x: Optional[float] = Field(None, description="X坐标")
    position_y: Optional[float] = Field(None, description="Y坐标")
    processor_id: Optional[str] = Field(None, description="关联的处理器ID")
    
    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        """确保空字符串被处理为None"""
        super().__pydantic_init_subclass__(**kwargs)
    
    def __init__(self, **data):
        # 处理空字符串的情况
        if 'name' in data and data['name'] == '':
            data['name'] = None
        if 'task_description' in data and data['task_description'] == '':
            data['task_description'] = None
        super().__init__(**data)


class NodeResponse(NodeBase):
    """节点响应模型"""
    node_id: uuid.UUID
    node_base_id: uuid.UUID
    workflow_id: uuid.UUID
    workflow_base_id: uuid.UUID
    version: int
    parent_version_id: Optional[uuid.UUID] = None
    is_current_version: bool
    created_at: Optional[str] = None
    workflow_name: Optional[str] = None
    processor_id: Optional[str] = None


class NodeConnection(BaseModel):
    """节点连接模型"""
    from_node_id: uuid.UUID = Field(..., description="源节点ID")
    to_node_id: uuid.UUID = Field(..., description="目标节点ID")
    workflow_id: uuid.UUID = Field(..., description="工作流ID")
    connection_type: ConnectionType = Field(ConnectionType.NORMAL, description="连接类型")
    condition_config: Optional[Dict[str, Any]] = Field(None, description="条件配置")
    created_at: Optional[str] = None


class NodeConnectionCreate(BaseModel):
    """节点连接创建模型"""
    from_node_base_id: uuid.UUID = Field(..., description="源节点基础ID")
    to_node_base_id: uuid.UUID = Field(..., description="目标节点基础ID")
    workflow_base_id: uuid.UUID = Field(..., description="工作流基础ID")
    connection_type: ConnectionType = Field(ConnectionType.NORMAL, description="连接类型")
    condition_config: Optional[Dict[str, Any]] = Field(None, description="条件配置")


class NodeConnectionUpdate(BaseModel):
    """节点连接更新模型"""
    connection_type: Optional[ConnectionType] = Field(None, description="连接类型")
    condition_config: Optional[Dict[str, Any]] = Field(None, description="条件配置")


class NodeVersionCreate(BaseModel):
    """节点版本创建模型"""
    node_base_id: uuid.UUID = Field(..., description="节点基础ID")
    workflow_base_id: uuid.UUID = Field(..., description="工作流基础ID")
    new_name: Optional[str] = Field(None, description="新节点名称")
    new_description: Optional[str] = Field(None, description="新任务描述")
    new_position_x: Optional[int] = Field(None, description="新X坐标")
    new_position_y: Optional[int] = Field(None, description="新Y坐标")