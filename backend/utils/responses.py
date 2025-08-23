"""
API响应工具模块
API Response Utilities

提供统一的API响应格式化函数
"""

from typing import Any, Optional, Dict
from fastapi.responses import JSONResponse
from fastapi import status


def success_response(
    data: Any = None,
    message: str = "操作成功",
    status_code: int = status.HTTP_200_OK,
    extra: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """
    成功响应格式化函数
    
    Args:
        data: 响应数据
        message: 响应消息
        status_code: HTTP状态码
        extra: 额外的响应字段
        
    Returns:
        JSONResponse: 格式化的成功响应
    """
    response_data = {
        "success": True,
        "message": message,
        "data": data
    }
    
    # 添加额外字段
    if extra:
        response_data.update(extra)
    
    return JSONResponse(
        status_code=status_code,
        content=response_data
    )


def error_response(
    message: str = "操作失败",
    error_code: Optional[str] = None,
    data: Any = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    extra: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """
    错误响应格式化函数
    
    Args:
        message: 错误消息
        error_code: 错误代码
        data: 错误详情数据
        status_code: HTTP状态码
        extra: 额外的响应字段
        
    Returns:
        JSONResponse: 格式化的错误响应
    """
    response_data = {
        "success": False,
        "message": message,
        "data": data
    }
    
    if error_code:
        response_data["error_code"] = error_code
    
    # 添加额外字段
    if extra:
        response_data.update(extra)
    
    return JSONResponse(
        status_code=status_code,
        content=response_data
    )


def validation_error_response(
    message: str = "请求参数验证失败",
    errors: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """
    参数验证错误响应
    
    Args:
        message: 错误消息
        errors: 验证错误详情
        
    Returns:
        JSONResponse: 验证错误响应
    """
    return error_response(
        message=message,
        error_code="VALIDATION_ERROR",
        data={"validation_errors": errors} if errors else None,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )


def not_found_response(
    message: str = "资源未找到",
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None
) -> JSONResponse:
    """
    资源未找到错误响应
    
    Args:
        message: 错误消息
        resource_type: 资源类型
        resource_id: 资源ID
        
    Returns:
        JSONResponse: 未找到错误响应
    """
    extra_data = {}
    if resource_type:
        extra_data["resource_type"] = resource_type
    if resource_id:
        extra_data["resource_id"] = resource_id
    
    return error_response(
        message=message,
        error_code="NOT_FOUND",
        data=extra_data if extra_data else None,
        status_code=status.HTTP_404_NOT_FOUND
    )


def unauthorized_response(
    message: str = "未授权访问"
) -> JSONResponse:
    """
    未授权访问错误响应
    
    Args:
        message: 错误消息
        
    Returns:
        JSONResponse: 未授权错误响应
    """
    return error_response(
        message=message,
        error_code="UNAUTHORIZED",
        status_code=status.HTTP_401_UNAUTHORIZED
    )


def forbidden_response(
    message: str = "禁止访问"
) -> JSONResponse:
    """
    禁止访问错误响应
    
    Args:
        message: 错误消息
        
    Returns:
        JSONResponse: 禁止访问错误响应
    """
    return error_response(
        message=message,
        error_code="FORBIDDEN",
        status_code=status.HTTP_403_FORBIDDEN
    )


def internal_error_response(
    message: str = "服务器内部错误",
    error_details: Optional[str] = None
) -> JSONResponse:
    """
    服务器内部错误响应
    
    Args:
        message: 错误消息
        error_details: 错误详情（开发环境可显示）
        
    Returns:
        JSONResponse: 内部错误响应
    """
    data = {"error_details": error_details} if error_details else None
    
    return error_response(
        message=message,
        error_code="INTERNAL_ERROR", 
        data=data,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


# 便捷的响应函数别名
def ok(data: Any = None, message: str = "操作成功") -> JSONResponse:
    """成功响应的简写形式"""
    return success_response(data=data, message=message)


def created(data: Any = None, message: str = "创建成功") -> JSONResponse:
    """创建成功响应"""
    return success_response(
        data=data, 
        message=message, 
        status_code=status.HTTP_201_CREATED
    )


def bad_request(message: str = "请求错误") -> JSONResponse:
    """错误请求响应的简写形式"""
    return error_response(message=message)


def not_found(message: str = "资源未找到") -> JSONResponse:
    """未找到响应的简写形式"""
    return not_found_response(message=message)