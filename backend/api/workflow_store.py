"""
工作流商店API路由
Workflow Store API Routes
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from fastapi.responses import JSONResponse
from loguru import logger

from ..models.base import BaseResponse
from ..models.workflow_store import (
    WorkflowStoreCreate, WorkflowStoreUpdate, WorkflowStoreResponse,
    WorkflowStoreDetail, WorkflowStoreQuery, WorkflowStoreList,
    WorkflowStoreRatingCreate, WorkflowStoreRating,
    WorkflowStoreImportRequest, WorkflowStoreImportResult,
    WorkflowStoreStats, StoreCategory, StoreStatus
)
from ..services.workflow_store_service import WorkflowStoreService
from ..utils.middleware import get_current_active_user, CurrentUser
from ..utils.exceptions import (
    ValidationError, ConflictError, NotFoundError, AuthorizationError,
    handle_validation_error, handle_conflict_error
)

# 创建路由器
router = APIRouter(prefix="/store", tags=["工作流商店"])

# 工作流商店服务实例
store_service = WorkflowStoreService()


@router.post("/publish", response_model=BaseResponse)
async def publish_workflow_to_store(
    store_data: WorkflowStoreCreate,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """发布工作流到商店"""
    try:
        store_id = await store_service.publish_workflow(
            store_data.workflow_base_id, store_data, current_user.user_id
        )

        return BaseResponse(
            success=True,
            message="工作流发布成功",
            data={"store_id": store_id}
        )

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"发布工作流到商店失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="发布工作流失败"
        )


@router.get("/workflows", response_model=WorkflowStoreList)
async def search_store_workflows(
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    category: Optional[StoreCategory] = Query(None, description="分类筛选"),
    tags: Optional[str] = Query(None, description="标签筛选，逗号分隔"),
    author_id: Optional[uuid.UUID] = Query(None, description="作者筛选"),
    is_featured: Optional[bool] = Query(None, description="是否只显示推荐"),
    is_free: Optional[bool] = Query(None, description="是否只显示免费"),
    min_rating: Optional[float] = Query(None, description="最低评分"),
    sort_by: Optional[str] = Query("created_at", description="排序字段"),
    sort_order: Optional[str] = Query("desc", description="排序方向"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小")
):
    """搜索商店中的工作流"""
    try:
        logger.info(f"🔍 收到搜索工作流请求: keyword={keyword}, category={category}, page={page}")

        # 解析标签
        tag_list = []
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        search_params = WorkflowStoreQuery(
            keyword=keyword,
            category=category,
            tags=tag_list if tag_list else None,
            author_id=author_id,
            is_featured=is_featured,
            is_free=is_free,
            min_rating=min_rating,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size
        )

        logger.info(f"📋 搜索参数: {search_params}")
        result = await store_service.search_store_items(search_params)
        logger.info(f"✅ 搜索完成，返回 {len(result.items) if result.items else 0} 个结果")
        return result

    except Exception as e:
        logger.error(f"搜索商店工作流失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="搜索工作流失败"
        )


@router.get("/workflows/{store_id}", response_model=WorkflowStoreDetail)
async def get_store_workflow_detail(
    store_id: str = Path(..., description="商店条目ID"),
    current_user: Optional[CurrentUser] = Depends(get_current_active_user)
):
    """获取商店工作流详情"""
    try:
        user_id = current_user.user_id if current_user else None
        item = await store_service.get_store_item(store_id, str(user_id) if user_id else None)

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流不存在"
            )

        return item

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取商店工作流详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取工作流详情失败"
        )


@router.put("/workflows/{store_id}/view", response_model=BaseResponse)
async def increment_workflow_view(
    store_id: str = Path(..., description="商店条目ID"),
    current_user: Optional[CurrentUser] = Depends(get_current_active_user)
):
    """增加工作流浏览次数"""
    try:
        # 先检查工作流是否存在
        item = await store_service.get_store_item(store_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流不存在"
            )

        user_id = current_user.user_id if current_user else None
        success = await store_service.increment_store_view(store_id, str(user_id) if user_id else None)

        if success:
            return BaseResponse(
                success=True,
                message="浏览次数已更新"
            )
        else:
            return BaseResponse(
                success=False,
                message="更新浏览次数失败"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"增加工作流浏览次数失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新浏览次数失败"
        )


@router.put("/workflows/{store_id}", response_model=BaseResponse)
async def update_store_workflow(
    store_id: str = Path(..., description="商店条目ID"),
    update_data: WorkflowStoreUpdate = None,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """更新商店工作流"""
    try:
        success = await store_service.update_store_item(
            store_id, update_data, current_user.user_id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="更新工作流失败"
            )

        return BaseResponse(
            success=True,
            message="工作流更新成功"
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"更新商店工作流失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新工作流失败"
        )


@router.delete("/workflows/{store_id}", response_model=BaseResponse)
async def delete_store_workflow(
    store_id: str = Path(..., description="商店条目ID"),
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """删除商店工作流"""
    try:
        success = await store_service.delete_store_item(
            store_id, current_user.user_id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="删除工作流失败"
            )

        return BaseResponse(
            success=True,
            message="工作流删除成功"
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"删除商店工作流失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除工作流失败"
        )


@router.get("/featured", response_model=List[WorkflowStoreResponse])
async def get_featured_workflows(
    limit: int = Query(10, ge=1, le=50, description="返回数量")
):
    """获取推荐工作流"""
    try:
        return await store_service.get_featured_items(limit)

    except Exception as e:
        logger.error(f"获取推荐工作流失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取推荐工作流失败"
        )


@router.get("/popular", response_model=List[WorkflowStoreResponse])
async def get_popular_workflows(
    limit: int = Query(10, ge=1, le=50, description="返回数量")
):
    """获取热门工作流"""
    try:
        return await store_service.get_popular_items(limit)

    except Exception as e:
        logger.error(f"获取热门工作流失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取热门工作流失败"
        )


@router.get("/my-workflows", response_model=List[WorkflowStoreResponse])
async def get_my_store_workflows(
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """获取我发布的工作流"""
    try:
        return await store_service.get_user_items(current_user.user_id)

    except Exception as e:
        logger.error(f"获取用户工作流失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户工作流失败"
        )


@router.post("/import", response_model=BaseResponse)
async def import_workflow_from_store(
    import_request: WorkflowStoreImportRequest,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """从商店导入工作流"""
    try:
        result = await store_service.import_workflow_from_store(
            import_request, current_user.user_id
        )

        return BaseResponse(
            success=result.success,
            message=result.message,
            data=result.model_dump()
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"从商店导入工作流失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导入工作流失败"
        )


@router.post("/workflows/{store_id}/ratings", response_model=BaseResponse)
async def create_workflow_rating(
    store_id: str = Path(..., description="商店条目ID"),
    rating_data: WorkflowStoreRatingCreate = None,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """为工作流评分"""
    try:
        # 确保store_id匹配
        if str(rating_data.store_id) != store_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="商店条目ID不匹配"
            )

        rating_id = await store_service.create_rating(
            rating_data, current_user.user_id
        )

        if not rating_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="创建评分失败"
            )

        return BaseResponse(
            success=True,
            message="评分创建成功",
            data={"rating_id": rating_id}
        )

    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"创建工作流评分失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建评分失败"
        )


@router.get("/workflows/{store_id}/ratings", response_model=List[WorkflowStoreRating])
async def get_workflow_ratings(
    store_id: str = Path(..., description="商店条目ID"),
    limit: int = Query(50, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量")
):
    """获取工作流评分"""
    try:
        return await store_service.get_store_ratings(store_id, limit, offset)

    except Exception as e:
        logger.error(f"获取工作流评分失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取评分失败"
        )


@router.get("/stats", response_model=WorkflowStoreStats)
async def get_store_stats():
    """获取商店统计信息"""
    try:
        return await store_service.get_store_stats()

    except Exception as e:
        logger.error(f"获取商店统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取统计信息失败"
        )