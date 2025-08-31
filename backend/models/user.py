"""
用户模型
User Models
"""

import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from .base import BaseEntity, CreateRequest, UpdateRequest


class UserBase(BaseModel):
    """用户基础模型"""
    username: str = Field(..., min_length=1, max_length=255, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    terminal_endpoint: Optional[str] = Field(None, description="终端端点")
    profile: Optional[Dict[str, Any]] = Field(None, description="用户配置")
    description: Optional[str] = Field(None, description="用户描述")
    role: Optional[str] = Field(None, max_length=50, description="用户角色")
    status: bool = Field(True, description="用户状态")
    is_online: Optional[bool] = Field(False, description="是否在线")
    last_login_at: Optional[datetime] = Field(None, description="最后登录时间")
    last_activity_at: Optional[datetime] = Field(None, description="最后活动时间")


class User(UserBase, BaseEntity):
    """用户完整模型"""
    user_id: uuid.UUID = Field(..., description="用户ID")
    password_hash: str = Field(..., description="密码哈希")


class UserCreate(UserBase, CreateRequest):
    """用户创建模型"""
    password: str = Field(..., min_length=6, description="密码")


class UserUpdate(UpdateRequest):
    """用户更新模型"""
    username: Optional[str] = Field(None, min_length=1, max_length=255, description="用户名")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    terminal_endpoint: Optional[str] = Field(None, description="终端端点")
    profile: Optional[Dict[str, Any]] = Field(None, description="用户配置")
    description: Optional[str] = Field(None, description="用户描述")
    role: Optional[str] = Field(None, max_length=50, description="用户角色")
    status: Optional[bool] = Field(None, description="用户状态")
    password: Optional[str] = Field(None, min_length=6, description="新密码")
    is_online: Optional[bool] = Field(None, description="是否在线")
    last_login_at: Optional[datetime] = Field(None, description="最后登录时间")
    last_activity_at: Optional[datetime] = Field(None, description="最后活动时间")


class UserResponse(UserBase):
    """用户响应模型"""
    user_id: uuid.UUID
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    is_online: Optional[bool] = False
    last_login_at: Optional[str] = None
    last_activity_at: Optional[str] = None


class UserLogin(BaseModel):
    """用户登录模型"""
    username_or_email: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class UserToken(BaseModel):
    """用户令牌模型"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int