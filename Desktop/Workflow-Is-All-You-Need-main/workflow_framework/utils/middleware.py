"""
中间件工具
Middleware Utilities
"""

import uuid
from typing import Optional
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .security import verify_token, TokenData, extract_token_from_header
from ..services.auth_service import AuthService
from ..models.user import UserResponse

# HTTP Bearer 安全方案
security = HTTPBearer()


class AuthenticationException(HTTPException):
    """认证异常"""
    def __init__(self, detail: str = "认证失败"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthorizationException(HTTPException):
    """授权异常"""
    def __init__(self, detail: str = "权限不足"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserResponse:
    """
    获取当前用户中间件
    
    Args:
        credentials: HTTP认证凭据
        
    Returns:
        当前用户信息
        
    Raises:
        AuthenticationException: 认证失败时抛出
    """
    # 验证令牌
    token_data = verify_token(credentials.credentials)
    if token_data is None:
        raise AuthenticationException("无效的访问令牌")
    
    # 获取用户信息
    auth_service = AuthService()
    user = await auth_service.get_user_by_id(uuid.UUID(token_data.user_id))
    
    if user is None:
        raise AuthenticationException("用户不存在")
    
    if not user.status:
        raise AuthenticationException("账户已被禁用")
    
    return user


async def get_current_active_user(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    """
    获取当前活跃用户（已激活且未被禁用）
    
    Args:
        current_user: 当前用户
        
    Returns:
        当前活跃用户信息
        
    Raises:
        AuthenticationException: 用户未激活时抛出
    """
    if not current_user.status:
        raise AuthenticationException("账户未激活")
    
    return current_user


def require_role(required_role: str):
    """
    角色权限检查装饰器
    
    Args:
        required_role: 所需角色
        
    Returns:
        依赖函数
    """
    async def check_role(current_user: UserResponse = Depends(get_current_active_user)) -> UserResponse:
        if current_user.role != required_role and current_user.role != "admin":
            raise AuthorizationException(f"需要 {required_role} 权限")
        return current_user
    
    return check_role


def require_admin():
    """
    管理员权限检查
    
    Returns:
        依赖函数
    """
    return require_role("admin")


async def get_optional_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[UserResponse]:
    """
    获取可选的当前用户（不强制要求认证）
    
    Args:
        credentials: HTTP认证凭据（可选）
        
    Returns:
        当前用户信息或None
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


class CurrentUser:
    """当前用户依赖注入类"""
    
    def __init__(self, user: UserResponse):
        self.user = user
        self.user_id = user.user_id
        self.username = user.username
        self.email = user.email
        self.role = user.role
        self.status = user.status
    
    def is_admin(self) -> bool:
        """检查是否为管理员"""
        return self.role == "admin"
    
    def has_role(self, role: str) -> bool:
        """检查是否具有指定角色"""
        return self.role == role or self.role == "admin"
    
    def is_active(self) -> bool:
        """检查是否为活跃用户"""
        return self.status


async def get_current_user_context(current_user: UserResponse = Depends(get_current_active_user)) -> CurrentUser:
    """
    获取当前用户上下文
    
    Args:
        current_user: 当前用户
        
    Returns:
        用户上下文对象
    """
    return CurrentUser(current_user)