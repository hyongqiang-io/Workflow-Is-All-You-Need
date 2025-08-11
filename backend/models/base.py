"""
基础数据模型
Base Data Models
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class BaseEntity(BaseModel):
    """基础实体模型"""
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        arbitrary_types_allowed=True
    )
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_deleted: bool = False


class TimestampMixin(BaseModel):
    """时间戳混入类"""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SoftDeleteMixin(BaseModel):
    """软删除混入类"""
    is_deleted: bool = False


class BaseResponse(BaseModel):
    """基础响应模型"""
    success: bool = True
    message: str = "操作成功"
    data: Optional[Any] = None


class PaginationParams(BaseModel):
    """分页参数模型"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页大小")
    
    @property
    def offset(self) -> int:
        """计算偏移量"""
        return (self.page - 1) * self.page_size


class PaginationResponse(BaseModel):
    """分页响应模型"""
    items: list = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
    
    def __init__(self, **data):
        super().__init__(**data)
        if self.total > 0 and self.page_size > 0:
            self.total_pages = (self.total + self.page_size - 1) // self.page_size


class CreateRequest(BaseModel):
    """创建请求基类"""
    pass


class UpdateRequest(BaseModel):
    """更新请求基类"""
    pass


class IDMixin(BaseModel):
    """ID混入类"""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)