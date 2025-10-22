"""
群组API路由
Group API Routes
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from fastapi.responses import JSONResponse
from loguru import logger

from ..models.base import BaseResponse
from ..models.group import (
    GroupCreate, GroupUpdate, GroupResponse, GroupQuery,
    GroupList, GroupMember
)
from ..services.group_service import GroupService
from ..utils.middleware import get_current_active_user, CurrentUser
from ..utils.exceptions import (
    ValidationError, ConflictError, NotFoundError, AuthorizationError
)

# 创建路由器
router = APIRouter(prefix="/groups", tags=["群组管理"])

# 群组服务实例
group_service = GroupService()


@router.post("", response_model=GroupResponse)
async def create_group(
    group_data: GroupCreate,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """创建群组"""
    try:
        logger.info(f"API收到创建群组请求 - 用户ID: {current_user.user_id}, 用户名: {current_user.username}")
        logger.debug(f"群组数据: {group_data.dict()}")

        result = await group_service.create_group(group_data, current_user.user_id)

        logger.info(f"群组创建成功，返回结果: {result.dict()}")
        return result

    except ValidationError as e:
        logger.warning(f"群组创建参数验证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"群组创建API异常，错误类型: {type(e).__name__}, 错误信息: {e}")
        logger.exception("群组创建API完整错误堆栈:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建群组失败"
        )


@router.get("", response_model=GroupList)
async def search_groups(
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    is_public: Optional[bool] = Query(None, description="是否公开"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    current_user: Optional[CurrentUser] = Depends(get_current_active_user)
):
    """搜索群组列表"""
    try:
        query_params = GroupQuery(
            keyword=keyword,
            is_public=is_public,
            page=page,
            page_size=page_size
        )

        user_id = current_user.user_id if current_user else None
        result = await group_service.search_groups(query_params, user_id)
        return result

    except Exception as e:
        logger.error(f"搜索群组失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="搜索群组失败"
        )


@router.get("/my", response_model=List[GroupResponse])
async def get_my_groups(
    is_creator: Optional[bool] = Query(None, description="是否只获取我创建的群组"),
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """获取我的群组列表"""
    try:
        if is_creator:
            # 获取用户创建的群组
            query = GroupQuery(
                creator_id=current_user.user_id,
                page=1,
                page_size=100
            )
            result = await group_service.search_groups(query, current_user.user_id)
            return result.groups
        else:
            # 获取用户参与的所有群组
            result = await group_service.get_user_groups(current_user.user_id)
            return result

    except Exception as e:
        logger.error(f"获取用户群组失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户群组失败"
        )


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group_detail(
    group_id: str = Path(..., description="群组ID"),
    current_user: Optional[CurrentUser] = Depends(get_current_active_user)
):
    """获取群组详情"""
    try:
        user_id = current_user.user_id if current_user else None
        result = await group_service.get_group_by_id(group_id, user_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="群组不存在"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取群组详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取群组详情失败"
        )


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: str = Path(..., description="群组ID"),
    group_data: GroupUpdate = None,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """更新群组信息"""
    try:
        result = await group_service.update_group(group_id, group_data, current_user.user_id)
        return result

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
        logger.error(f"更新群组失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新群组失败"
        )


@router.delete("/{group_id}", response_model=BaseResponse)
async def delete_group(
    group_id: str = Path(..., description="群组ID"),
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """删除群组"""
    try:
        success = await group_service.delete_group(group_id, current_user.user_id)

        if success:
            return BaseResponse(
                success=True,
                message="群组删除成功"
            )
        else:
            return BaseResponse(
                success=False,
                message="删除群组失败"
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
        logger.error(f"删除群组失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除群组失败"
        )


@router.post("/{group_id}/join", response_model=BaseResponse)
async def join_group(
    group_id: str = Path(..., description="群组ID"),
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """加入群组"""
    try:
        success = await group_service.join_group(group_id, current_user.user_id)

        if success:
            return BaseResponse(
                success=True,
                message="加入群组成功"
            )
        else:
            return BaseResponse(
                success=False,
                message="加入群组失败"
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
        logger.error(f"加入群组失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="加入群组失败"
        )


@router.delete("/{group_id}/leave", response_model=BaseResponse)
async def leave_group(
    group_id: str = Path(..., description="群组ID"),
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """退出群组"""
    try:
        success = await group_service.leave_group(group_id, current_user.user_id)

        if success:
            return BaseResponse(
                success=True,
                message="退出群组成功"
            )
        else:
            return BaseResponse(
                success=False,
                message="退出群组失败"
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
        logger.error(f"退出群组失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="退出群组失败"
        )


@router.get("/{group_id}/members", response_model=List[GroupMember])
async def get_group_members(
    group_id: str = Path(..., description="群组ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=100, description="每页大小"),
    current_user: Optional[CurrentUser] = Depends(get_current_active_user)
):
    """获取群组成员列表"""
    try:
        members, total = await group_service.get_group_members(group_id, page, page_size)
        return members

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"获取群组成员失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取群组成员失败"
        )


@router.get("/{group_id}/processors")
async def get_group_processors(
    group_id: str = Path(..., description="群组ID"),
    current_user: Optional[CurrentUser] = Depends(get_current_active_user)
):
    """获取群组内的processor列表"""
    try:
        user_id = current_user.user_id if current_user else None
        processors = await group_service.get_group_processors(group_id, user_id)
        return processors

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
        logger.error(f"获取群组processor失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取群组processor失败"
        )