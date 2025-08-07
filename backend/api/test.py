"""
测试管理API路由
Test Management API Routes
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from loguru import logger

from ..models.base import BaseResponse
from ..utils.middleware import get_current_user_context, CurrentUser

# 创建路由器
router = APIRouter(prefix="/test", tags=["测试管理"])


@router.get("/suites", response_model=BaseResponse)
async def get_test_suites(
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取测试套件列表
    
    Args:
        current_user: 当前用户
        
    Returns:
        测试套件列表
    """
    try:
        # 模拟测试套件数据，实际应该从数据库获取
        test_suites = [
            {
                "id": "suite-001",
                "name": "基础功能测试",
                "description": "测试系统基础功能",
                "status": "active",
                "test_count": 10,
                "last_run": "2024-01-15T10:30:00Z"
            },
            {
                "id": "suite-002",
                "name": "工作流测试",
                "description": "测试工作流执行功能",
                "status": "active", 
                "test_count": 15,
                "last_run": "2024-01-14T14:20:00Z"
            },
            {
                "id": "suite-003",
                "name": "性能测试",
                "description": "测试系统性能指标",
                "status": "inactive",
                "test_count": 8,
                "last_run": "2024-01-10T09:15:00Z"
            }
        ]
        
        return BaseResponse(
            success=True,
            message="获取测试套件列表成功",
            data={
                "test_suites": test_suites,
                "count": len(test_suites)
            }
        )
        
    except Exception as e:
        logger.error(f"获取测试套件列表异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取测试套件列表失败"
        ) 