"""
工作流商店模型
Workflow Store Models
"""

import uuid
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from .base import BaseEntity, CreateRequest, UpdateRequest
from .workflow_import_export import WorkflowExport


class StoreCategory(str, Enum):
    """商店分类枚举"""
    AUTOMATION = "automation"        # 自动化
    DATA_PROCESSING = "data_processing"  # 数据处理
    AI_ML = "ai_ml"                 # AI/机器学习
    BUSINESS = "business"           # 商业流程
    INTEGRATION = "integration"     # 系统集成
    TEMPLATE = "template"           # 模板
    OTHER = "other"                 # 其他


class StoreStatus(str, Enum):
    """商店状态枚举"""
    DRAFT = "draft"                 # 草稿
    PUBLISHED = "published"         # 已发布
    ARCHIVED = "archived"           # 已归档
    REJECTED = "rejected"           # 已拒绝


class WorkflowStoreBase(BaseModel):
    """工作流商店基础模型"""
    title: str = Field(..., min_length=1, max_length=255, description="标题")
    description: Optional[str] = Field(None, max_length=2000, description="描述")
    category: StoreCategory = Field(..., description="分类")
    tags: List[str] = Field(default_factory=list, description="标签")
    is_featured: bool = Field(False, description="是否推荐")
    is_free: bool = Field(True, description="是否免费")
    price: Optional[float] = Field(None, description="价格")


class WorkflowStore(WorkflowStoreBase, BaseEntity):
    """工作流商店完整模型"""
    store_id: uuid.UUID = Field(..., description="商店条目ID")
    author_id: uuid.UUID = Field(..., description="作者ID")
    author_name: str = Field(..., description="作者名称")
    workflow_export_data: WorkflowExport = Field(..., description="工作流导出数据")

    # 统计信息
    downloads: int = Field(0, description="下载次数")
    views: int = Field(0, description="查看次数")
    rating: float = Field(0.0, description="平均评分")
    rating_count: int = Field(0, description="评分人数")

    # 状态信息
    status: StoreStatus = Field(StoreStatus.DRAFT, description="状态")
    published_at: Optional[str] = Field(None, description="发布时间")
    featured_at: Optional[str] = Field(None, description="推荐时间")

    # 版本信息
    version: str = Field("1.0.0", description="版本号")
    changelog: Optional[str] = Field(None, description="更新日志")


class WorkflowStoreCreate(WorkflowStoreBase, CreateRequest):
    """工作流商店创建模型"""
    workflow_base_id: uuid.UUID = Field(..., description="源工作流基础ID")


class WorkflowStoreUpdate(UpdateRequest):
    """工作流商店更新模型"""
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="标题")
    description: Optional[str] = Field(None, max_length=2000, description="描述")
    category: Optional[StoreCategory] = Field(None, description="分类")
    tags: Optional[List[str]] = Field(None, description="标签")
    is_featured: Optional[bool] = Field(None, description="是否推荐")
    is_free: Optional[bool] = Field(None, description="是否免费")
    price: Optional[float] = Field(None, description="价格")
    status: Optional[StoreStatus] = Field(None, description="状态")
    changelog: Optional[str] = Field(None, description="更新日志")


class WorkflowStoreResponse(WorkflowStoreBase):
    """工作流商店响应模型"""
    store_id: uuid.UUID
    author_id: uuid.UUID
    author_name: str
    downloads: int
    views: int
    rating: float
    rating_count: int
    status: StoreStatus
    published_at: Optional[str] = None
    featured_at: Optional[str] = None
    version: str
    changelog: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # 简化的工作流信息
    workflow_info: Optional[Dict[str, Any]] = Field(None, description="工作流基本信息")


class WorkflowStoreDetail(WorkflowStoreResponse):
    """工作流商店详情模型"""
    workflow_export_data: WorkflowExport = Field(..., description="完整工作流导出数据")


class WorkflowStoreList(BaseModel):
    """工作流商店列表模型"""
    items: List[WorkflowStoreResponse] = Field(..., description="商店条目列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")
    total_pages: int = Field(..., description="总页数")


class WorkflowStoreQuery(BaseModel):
    """工作流商店查询模型"""
    keyword: Optional[str] = Field(None, description="关键词搜索")
    category: Optional[StoreCategory] = Field(None, description="分类筛选")
    tags: Optional[List[str]] = Field(None, description="标签筛选")
    author_id: Optional[uuid.UUID] = Field(None, description="作者筛选")
    is_featured: Optional[bool] = Field(None, description="是否只显示推荐")
    is_free: Optional[bool] = Field(None, description="是否只显示免费")
    min_rating: Optional[float] = Field(None, description="最低评分")
    sort_by: Optional[str] = Field("created_at", description="排序字段")
    sort_order: Optional[str] = Field("desc", description="排序方向")
    page: int = Field(1, description="页码")
    page_size: int = Field(20, description="每页大小")


class WorkflowStoreRating(BaseModel):
    """工作流商店评分模型"""
    rating_id: uuid.UUID = Field(..., description="评分ID")
    store_id: uuid.UUID = Field(..., description="商店条目ID")
    user_id: uuid.UUID = Field(..., description="用户ID")
    user_name: str = Field(..., description="用户名称")
    rating: int = Field(..., ge=1, le=5, description="评分(1-5)")
    comment: Optional[str] = Field(None, max_length=1000, description="评论")
    created_at: str = Field(..., description="创建时间")


class WorkflowStoreRatingCreate(BaseModel):
    """工作流商店评分创建模型"""
    store_id: uuid.UUID = Field(..., description="商店条目ID")
    rating: int = Field(..., ge=1, le=5, description="评分(1-5)")
    comment: Optional[str] = Field(None, max_length=1000, description="评论")


class WorkflowStoreImportRequest(BaseModel):
    """工作流商店导入请求模型"""
    store_id: uuid.UUID = Field(..., description="商店条目ID")
    import_name: Optional[str] = Field(None, description="导入后的工作流名称")
    import_description: Optional[str] = Field(None, description="导入后的工作流描述")


class WorkflowStoreImportResult(BaseModel):
    """工作流商店导入结果模型"""
    success: bool = Field(..., description="是否成功")
    workflow_id: Optional[uuid.UUID] = Field(None, description="导入的工作流ID")
    workflow_base_id: Optional[uuid.UUID] = Field(None, description="导入的工作流基础ID")
    message: str = Field(..., description="结果消息")
    warnings: List[str] = Field(default_factory=list, description="警告信息")
    errors: List[str] = Field(default_factory=list, description="错误信息")


class WorkflowStoreStats(BaseModel):
    """工作流商店统计模型"""
    total_workflows: int = Field(..., description="总工作流数")
    total_downloads: int = Field(..., description="总下载次数")
    featured_count: int = Field(..., description="推荐工作流数")
    categories_stats: Dict[str, int] = Field(..., description="分类统计")
    top_authors: List[Dict[str, Any]] = Field(..., description="热门作者")
    recent_uploads: List[WorkflowStoreResponse] = Field(..., description="最近上传")