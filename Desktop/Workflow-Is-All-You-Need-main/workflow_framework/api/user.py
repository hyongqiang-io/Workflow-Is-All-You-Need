"""
用户管理API路由
User Management API Routes
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from loguru import logger

from ..models.base import BaseResponse
from ..models.user import User, UserUpdate
from ..repositories.user.user_repository import UserRepository
from ..utils.middleware import get_current_user_context, CurrentUser
from ..utils.exceptions import ValidationError, handle_validation_error

# 创建路由器
router = APIRouter(prefix="/users", tags=["用户管理"])

# 用户仓库实例
user_repository = UserRepository()


@router.get("/{user_id}", response_model=BaseResponse)
async def get_user(
    user_id: uuid.UUID = Path(..., description="用户ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取用户信息
    
    Args:
        user_id: 用户ID
        current_user: 当前用户
        
    Returns:
        用户信息
    """
    try:
        user = await user_repository.get_by_id(user_id, "user_id")
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 移除敏感信息
        if user.get('password_hash'):
            del user['password_hash']
        
        return BaseResponse(
            success=True,
            message="获取用户信息成功",
            data=user
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户信息异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户信息失败"
        )


@router.put("/{user_id}", response_model=BaseResponse)
async def update_user(
    user_id: uuid.UUID,
    user_data: UserUpdate,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    更新用户信息
    
    Args:
        user_id: 用户ID
        user_data: 用户更新数据
        current_user: 当前用户
        
    Returns:
        更新结果
    """
    try:
        # 添加调试日志
        logger.info(f"收到用户更新请求 - 用户ID: {user_id}")
        logger.info(f"更新数据: {user_data}")
        logger.info(f"数据类型: {type(user_data)}")
        
        # 验证输入数据
        if not user_data:
            raise ValidationError("请提供用户更新数据")
        
        # user_data 已经是 UserUpdate 对象
        user_update = user_data
        
        # 更新用户信息
        updated_user = await user_repository.update_user(user_id, user_update)
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 移除敏感信息
        if updated_user.get('password_hash'):
            del updated_user['password_hash']
        
        return BaseResponse(
            success=True,
            message="用户信息更新成功",
            data=updated_user
        )
        
    except ValidationError as e:
        logger.warning(f"用户更新验证失败: {e}")
        raise handle_validation_error(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"用户更新异常: {e}")
        logger.error(f"异常类型: {type(e)}")
        logger.error(f"异常详情: {str(e)}")
        import traceback
        logger.error(f"完整堆栈跟踪: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="用户信息更新失败，请稍后再试"
        )