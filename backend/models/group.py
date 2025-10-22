"""
群组模型
Group Models
"""

import uuid
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from .base import BaseEntity, CreateRequest, UpdateRequest


class GroupBase(BaseModel):
    """群组基础模型"""
    group_name: str = Field(..., min_length=1, max_length=255, description="群组名称")
    description: Optional[str] = Field(None, max_length=1000, description="群组描述")
    avatar_url: Optional[str] = Field(None, max_length=500, description="群组头像URL")
    is_public: bool = Field(True, description="是否公开群组")


class Group(GroupBase, BaseEntity):
    """群组完整模型"""
    group_id: uuid.UUID = Field(..., description="群组ID")
    creator_id: uuid.UUID = Field(..., description="创建者ID")
    member_count: int = Field(0, description="成员数量")


class GroupCreate(GroupBase, CreateRequest):
    """群组创建模型"""
    pass


class GroupUpdate(UpdateRequest):
    """群组更新模型"""
    group_name: Optional[str] = Field(None, min_length=1, max_length=255, description="群组名称")
    description: Optional[str] = Field(None, max_length=1000, description="群组描述")
    avatar_url: Optional[str] = Field(None, max_length=500, description="群组头像URL")
    is_public: Optional[bool] = Field(None, description="是否公开群组")


class GroupResponse(GroupBase):
    """群组响应模型"""
    group_id: uuid.UUID
    creator_id: uuid.UUID
    creator_name: Optional[str] = None
    member_count: int
    is_member: bool = Field(False, description="当前用户是否为群组成员")
    is_creator: bool = Field(False, description="当前用户是否为群组创建者")
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class GroupMember(BaseModel):
    """群组成员模型"""
    id: uuid.UUID = Field(..., description="成员关系ID")
    group_id: uuid.UUID = Field(..., description="群组ID")
    user_id: uuid.UUID = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    joined_at: str = Field(..., description="加入时间")
    status: str = Field(..., description="状态")


class GroupMemberAdd(BaseModel):
    """添加群组成员模型"""
    user_ids: List[uuid.UUID] = Field(..., description="用户ID列表")


class GroupList(BaseModel):
    """群组列表响应模型"""
    groups: List[GroupResponse]
    total: int = Field(..., description="总数量")
    page: int = Field(1, description="页码")
    page_size: int = Field(20, description="每页大小")
    total_pages: int = Field(..., description="总页数")


class GroupQuery(BaseModel):
    """群组查询参数模型"""
    keyword: Optional[str] = Field(None, description="关键词搜索")
    is_public: Optional[bool] = Field(None, description="是否公开")
    creator_id: Optional[uuid.UUID] = Field(None, description="创建者ID")
    member_user_id: Optional[uuid.UUID] = Field(None, description="成员用户ID")
    my_groups: Optional[bool] = Field(None, description="只显示我的群组")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页大小")


class ProcessorGroupInfo(BaseModel):
    """Processor的群组信息模型"""
    group_id: Optional[uuid.UUID] = None
    group_name: Optional[str] = None
    is_member: bool = Field(False, description="当前用户是否为群组成员")