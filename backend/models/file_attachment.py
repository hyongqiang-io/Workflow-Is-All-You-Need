"""
文件附件系统数据模型
File Attachment System Models
"""

import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
from .base import BaseEntity, CreateRequest, UpdateRequest


class AttachmentType(str, Enum):
    """附件类型枚举"""
    INPUT = "input"           # 输入附件
    OUTPUT = "output"         # 输出附件  
    REFERENCE = "reference"   # 参考附件
    TEMPLATE = "template"     # 模板附件


class AccessType(str, Enum):
    """访问类型枚举"""
    OWNER = "owner"           # 所有者
    SHARED = "shared"         # 共享


# ==================== 工作流文件模型 ====================

class WorkflowFileBase(BaseModel):
    """工作流文件基础模型"""
    filename: str = Field(..., min_length=1, max_length=255, description="文件名")
    original_filename: str = Field(..., min_length=1, max_length=255, description="原始文件名")
    content_type: str = Field(..., max_length=100, description="文件MIME类型")


class WorkflowFile(WorkflowFileBase, BaseEntity):
    """工作流文件完整模型"""
    file_id: uuid.UUID = Field(..., description="文件ID")
    file_path: str = Field(..., description="文件存储路径")
    file_size: int = Field(..., ge=0, description="文件大小(字节)")
    file_hash: str = Field(..., max_length=64, description="文件SHA256哈希")
    uploaded_by: uuid.UUID = Field(..., description="上传者用户ID")


class WorkflowFileCreate(WorkflowFileBase, CreateRequest):
    """工作流文件创建模型"""
    file_path: str = Field(..., description="文件存储路径")
    file_size: int = Field(..., ge=0, description="文件大小(字节)")
    file_hash: str = Field(..., max_length=64, description="文件SHA256哈希")
    uploaded_by: uuid.UUID = Field(..., description="上传者用户ID")


class WorkflowFileUpdate(UpdateRequest):
    """工作流文件更新模型"""
    filename: Optional[str] = Field(None, min_length=1, max_length=255, description="文件名")
    original_filename: Optional[str] = Field(None, min_length=1, max_length=255, description="原始文件名")


class WorkflowFileResponse(WorkflowFileBase):
    """工作流文件响应模型"""
    file_id: uuid.UUID
    file_size: int
    file_hash: str
    uploaded_by: uuid.UUID
    uploaded_by_name: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    download_url: Optional[str] = None  # 可选的下载链接


# ==================== 文件上传相关模型 ====================

class FileUploadRequest(BaseModel):
    """文件上传请求模型"""
    workflow_instance_id: Optional[uuid.UUID] = Field(None, description="关联的工作流实例ID")
    node_id: Optional[uuid.UUID] = Field(None, description="关联的节点ID")
    task_instance_id: Optional[uuid.UUID] = Field(None, description="关联的任务实例ID")
    attachment_type: AttachmentType = Field(AttachmentType.INPUT, description="附件类型")
    description: Optional[str] = Field(None, max_length=500, description="文件描述")


class FileUploadResponse(BaseModel):
    """文件上传响应模型"""
    file_id: uuid.UUID
    filename: str
    file_size: int
    content_type: str
    upload_success: bool = True
    message: str = "文件上传成功"


# ==================== 用户文件关联模型 ====================

class UserFileBase(BaseModel):
    """用户文件关联基础模型"""
    access_type: AccessType = Field(AccessType.OWNER, description="访问类型")


class UserFile(UserFileBase, BaseEntity):
    """用户文件关联完整模型"""
    user_file_id: uuid.UUID = Field(..., description="用户文件关联ID")
    user_id: uuid.UUID = Field(..., description="用户ID")
    file_id: uuid.UUID = Field(..., description="文件ID")


class UserFileCreate(UserFileBase, CreateRequest):
    """用户文件关联创建模型"""
    user_id: uuid.UUID = Field(..., description="用户ID")
    file_id: uuid.UUID = Field(..., description="文件ID")


class UserFileResponse(UserFileBase):
    """用户文件关联响应模型"""
    user_file_id: uuid.UUID
    user_id: uuid.UUID
    file_id: uuid.UUID
    file_info: Optional[WorkflowFileResponse] = None
    created_at: Optional[str] = None


# ==================== 节点文件关联模型 ====================

class NodeFileBase(BaseModel):
    """节点文件关联基础模型"""
    attachment_type: AttachmentType = Field(AttachmentType.INPUT, description="附件类型")


class NodeFile(NodeFileBase, BaseEntity):
    """节点文件关联完整模型"""
    node_file_id: uuid.UUID = Field(..., description="节点文件关联ID")
    node_id: uuid.UUID = Field(..., description="节点ID")
    file_id: uuid.UUID = Field(..., description="文件ID")


class NodeFileCreate(NodeFileBase, CreateRequest):
    """节点文件关联创建模型"""
    node_id: uuid.UUID = Field(..., description="节点ID")
    file_id: uuid.UUID = Field(..., description="文件ID")


class NodeFileResponse(NodeFileBase):
    """节点文件关联响应模型"""
    node_file_id: uuid.UUID
    node_id: uuid.UUID
    file_id: uuid.UUID
    file_info: Optional[WorkflowFileResponse] = None
    created_at: Optional[str] = None


# ==================== 节点实例文件关联模型 ====================

class NodeInstanceFileBase(BaseModel):
    """节点实例文件关联基础模型"""
    attachment_type: AttachmentType = Field(AttachmentType.INPUT, description="附件类型")


class NodeInstanceFile(NodeInstanceFileBase, BaseEntity):
    """节点实例文件关联完整模型"""
    node_instance_file_id: uuid.UUID = Field(..., description="节点实例文件关联ID")
    node_instance_id: uuid.UUID = Field(..., description="节点实例ID")
    file_id: uuid.UUID = Field(..., description="文件ID")


class NodeInstanceFileCreate(NodeInstanceFileBase, CreateRequest):
    """节点实例文件关联创建模型"""
    node_instance_id: uuid.UUID = Field(..., description="节点实例ID")
    file_id: uuid.UUID = Field(..., description="文件ID")


class NodeInstanceFileResponse(NodeInstanceFileBase):
    """节点实例文件关联响应模型"""
    node_instance_file_id: uuid.UUID
    node_instance_id: uuid.UUID
    file_id: uuid.UUID
    file_info: Optional[WorkflowFileResponse] = None
    created_at: Optional[str] = None


# ==================== 任务实例文件关联模型 ====================

class TaskInstanceFileBase(BaseModel):
    """任务实例文件关联基础模型"""
    attachment_type: AttachmentType = Field(AttachmentType.INPUT, description="附件类型")


class TaskInstanceFile(TaskInstanceFileBase, BaseEntity):
    """任务实例文件关联完整模型"""
    task_instance_file_id: uuid.UUID = Field(..., description="任务实例文件关联ID")
    task_instance_id: uuid.UUID = Field(..., description="任务实例ID")
    file_id: uuid.UUID = Field(..., description="文件ID")
    uploaded_by: uuid.UUID = Field(..., description="上传者用户ID")


class TaskInstanceFileCreate(TaskInstanceFileBase, CreateRequest):
    """任务实例文件关联创建模型"""
    task_instance_id: uuid.UUID = Field(..., description="任务实例ID")
    file_id: uuid.UUID = Field(..., description="文件ID")
    uploaded_by: uuid.UUID = Field(..., description="上传者用户ID")


class TaskInstanceFileResponse(TaskInstanceFileBase):
    """任务实例文件关联响应模型"""
    task_instance_file_id: uuid.UUID
    task_instance_id: uuid.UUID
    file_id: uuid.UUID
    uploaded_by: uuid.UUID
    uploaded_by_name: Optional[str] = None
    file_info: Optional[WorkflowFileResponse] = None
    created_at: Optional[str] = None


# ==================== 批量操作模型 ====================

class FileBatchAssociateRequest(BaseModel):
    """文件批量关联请求模型"""
    file_ids: List[uuid.UUID] = Field(..., min_items=1, description="文件ID列表")
    attachment_type: AttachmentType = Field(AttachmentType.INPUT, description="附件类型")


class FileBatchResponse(BaseModel):
    """文件批量操作响应模型"""
    success_count: int = Field(0, description="成功数量")
    failed_count: int = Field(0, description="失败数量")
    success_files: List[str] = Field(default_factory=list, description="成功的文件ID列表")  # Linus式修复: 使用字符串而非UUID
    failed_files: List[Dict[str, Any]] = Field(default_factory=list, description="失败的文件信息列表")
    message: str = "批量操作完成"


# ==================== 文件搜索和过滤模型 ====================

class FileSearchRequest(BaseModel):
    """文件搜索请求模型"""
    keyword: Optional[str] = Field(None, max_length=100, description="关键词搜索")
    content_type: Optional[str] = Field(None, description="文件类型过滤")
    uploaded_by: Optional[uuid.UUID] = Field(None, description="上传者过滤")
    date_from: Optional[datetime] = Field(None, description="创建日期开始")
    date_to: Optional[datetime] = Field(None, description="创建日期结束")
    min_size: Optional[int] = Field(None, ge=0, description="最小文件大小")
    max_size: Optional[int] = Field(None, ge=0, description="最大文件大小")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


class FileSearchResponse(BaseModel):
    """文件搜索响应模型"""
    files: List[WorkflowFileResponse] = Field(default_factory=list, description="文件列表")
    total: int = Field(0, description="总数量")
    page: int = Field(1, description="当前页码")
    page_size: int = Field(20, description="每页数量")
    total_pages: int = Field(0, description="总页数")


# ==================== 文件统计模型 ====================

class FileStatistics(BaseModel):
    """文件统计模型"""
    total_files: int = Field(0, description="总文件数")
    total_size: int = Field(0, description="总文件大小(字节)")
    total_size_mb: float = Field(0.0, description="总文件大小(MB)")
    file_type_stats: Dict[str, int] = Field(default_factory=dict, description="文件类型统计")
    upload_trend: Dict[str, int] = Field(default_factory=dict, description="上传趋势(按日期)")
    top_uploaders: List[Dict[str, Any]] = Field(default_factory=list, description="活跃上传者")


# ==================== 文件权限验证模型 ====================

class FilePermissionRequest(BaseModel):
    """文件权限验证请求模型"""
    file_id: uuid.UUID = Field(..., description="文件ID")
    user_id: uuid.UUID = Field(..., description="用户ID")
    action: str = Field(..., description="操作类型: read, write, delete")


class FilePermissionResponse(BaseModel):
    """文件权限验证响应模型"""
    has_permission: bool = Field(False, description="是否有权限")
    reason: Optional[str] = Field(None, description="权限说明")
    access_type: Optional[AccessType] = Field(None, description="访问类型")