"""
异常处理工具
Exception Handling Utilities
"""

from typing import Dict, Any
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """错误响应模型"""
    success: bool = False
    error_code: str
    message: str
    details: Dict[str, Any] = {}


class BusinessException(HTTPException):
    """业务异常基类"""
    
    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Dict[str, Any] = None
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        
        super().__init__(
            status_code=status_code,
            detail={
                "error_code": error_code,
                "message": message,
                "details": self.details
            }
        )


class ValidationError(BusinessException):
    """输入验证错误"""
    
    def __init__(self, message: str, field: str = None, details: Dict[str, Any] = None):
        error_details = details or {}
        if field:
            error_details["field"] = field
            
        super().__init__(
            error_code="VALIDATION_ERROR",
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=error_details
        )


class AuthenticationError(BusinessException):
    """认证错误"""
    
    def __init__(self, message: str = "认证失败", details: Dict[str, Any] = None):
        super().__init__(
            error_code="AUTHENTICATION_ERROR",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details or {}
        )


class AuthorizationError(BusinessException):
    """授权错误"""
    
    def __init__(self, message: str = "权限不足", details: Dict[str, Any] = None):
        super().__init__(
            error_code="AUTHORIZATION_ERROR",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details or {}
        )


class NotFoundError(BusinessException):
    """资源未找到错误"""
    
    def __init__(self, resource: str, identifier: str = None, details: Dict[str, Any] = None):
        message = f"{resource}未找到"
        if identifier:
            message += f": {identifier}"
            
        error_details = details or {}
        error_details.update({
            "resource": resource,
            "identifier": identifier
        })
        
        super().__init__(
            error_code="NOT_FOUND",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=error_details
        )


class ConflictError(BusinessException):
    """资源冲突错误"""
    
    def __init__(self, resource: str, message: str = None, details: Dict[str, Any] = None):
        error_message = message or f"{resource}已存在"
        
        error_details = details or {}
        error_details["resource"] = resource
        
        super().__init__(
            error_code="CONFLICT",
            message=error_message,
            status_code=status.HTTP_409_CONFLICT,
            details=error_details
        )


class InternalServerError(BusinessException):
    """内部服务器错误"""
    
    def __init__(self, message: str = "内部服务器错误", details: Dict[str, Any] = None):
        super().__init__(
            error_code="INTERNAL_SERVER_ERROR",
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details or {}
        )


def create_error_response(
    error_code: str,
    message: str,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    details: Dict[str, Any] = None
) -> JSONResponse:
    """
    创建错误响应
    
    Args:
        error_code: 错误代码
        message: 错误消息
        status_code: HTTP状态码
        details: 错误详情
        
    Returns:
        JSON错误响应
    """
    error_response = ErrorResponse(
        error_code=error_code,
        message=message,
        details=details or {}
    )
    
    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump()
    )


def handle_registration_error(error: Exception) -> HTTPException:
    """
    处理注册错误
    
    Args:
        error: 异常对象
        
    Returns:
        HTTP异常
    """
    from ..services.auth_service import RegistrationError
    
    if isinstance(error, RegistrationError):
        if "已存在" in str(error) or "已被注册" in str(error):
            return ConflictError("用户", str(error))
        else:
            return ValidationError(str(error))
    
    return InternalServerError("注册失败")


def handle_authentication_error(error: Exception) -> HTTPException:
    """
    处理认证错误
    
    Args:
        error: 异常对象
        
    Returns:
        HTTP异常
    """
    from ..services.auth_service import AuthenticationError as AuthError
    
    if isinstance(error, AuthError):
        return AuthenticationError(str(error))
    
    return InternalServerError("认证失败")


def handle_validation_error(error: Exception) -> HTTPException:
    """
    处理验证错误
    
    Args:
        error: 异常对象
        
    Returns:
        HTTP异常
    """
    if isinstance(error, ValidationError):
        return error
    
    return ValidationError(str(error))


def handle_conflict_error(error: Exception) -> HTTPException:
    """
    处理冲突错误
    
    Args:
        error: 异常对象
        
    Returns:
        HTTP异常
    """
    if isinstance(error, ConflictError):
        return error
    
    return ConflictError("资源", str(error))